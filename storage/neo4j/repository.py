"""Neo4j repository for semantic core operations."""

import json

from neo4j import GraphDatabase

from semantic_core.identity.models import CanonicalEntity, Evidence, RawEntity, ResolutionDecision, SourceSystem


def serialize_property(value):
    """Convert complex values into Neo4j property-compatible values."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, list):
        return [
            item if isinstance(item, (str, int, float, bool)) or item is None else json.dumps(item, ensure_ascii=False, default=str)
            for item in value
        ]
    return value


class Neo4jRepository:
    """Repository for Neo4j operations on semantic core models."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _run(self, query: str, session=None, **kwargs):
        if session is not None:
            session.run(query, **kwargs)
            return
        with self.driver.session() as session:
            session.run(query, **kwargs)

    def save_source_system(self, source: SourceSystem, session=None) -> None:
        """Save a source system node."""
        self._run("""
            MERGE (s:SourceSystem {source_id: $source_id})
            SET s.source_type = $source_type,
                s.name = $name,
                s.trust_level = $trust_level,
                s.metadata = $metadata
        """, session=session, **{
            **source.__dict__,
            "metadata": serialize_property(source.metadata),
        })

    def save_raw_entity(self, entity: RawEntity, session=None) -> None:
        """Save a raw entity node."""
        self._run("""
            MERGE (r:RawEntity {raw_entity_id: $raw_entity_id})
            SET r.source_id = $source_id,
                r.source_entity_id = $source_entity_id,
                r.entity_type = $entity_type,
                r.name = $name,
                r.domain = $domain,
                r.device_class = $device_class,
                r.area = $area,
                r.attributes = $attributes
        """, session=session, **{
            **entity.__dict__,
            "attributes": serialize_property(entity.attributes),
        })

    def save_canonical_entity(self, entity: CanonicalEntity, session=None) -> None:
        """Save a canonical entity node."""
        self._run("""
            MERGE (c:CanonicalEntity {canonical_id: $canonical_id})
            SET c.entity_type = $entity_type,
                c.canonical_name = $canonical_name,
                c.lifecycle_state = $lifecycle_state,
                c.confidence_status = $confidence_status,
                c.attributes = $attributes,
                c.created_at = $created_at,
                c.updated_at = $updated_at
        """, session=session, **{
            **entity.__dict__,
            "attributes": serialize_property(entity.attributes),
        })

    def save_resolution_decision(self, decision: ResolutionDecision, session=None) -> None:
        """Save a resolution decision and relationships."""
        decision_params = {
            "decision_id": decision.decision_id,
            "raw_entity_id": decision.raw_entity_id,
            "canonical_id": decision.canonical_id,
            "decision_type": decision.decision_type,
            "method": decision.method,
            "overall_confidence": decision.overall_confidence,
            "review_required": decision.review_required,
            "created_at": decision.created_at,
        }

        self._run("""
            MERGE (d:ResolutionDecision {decision_id: $decision_id})
            SET d.raw_entity_id = $raw_entity_id,
                d.canonical_id = $canonical_id,
                d.decision_type = $decision_type,
                d.method = $method,
                d.overall_confidence = $overall_confidence,
                d.review_required = $review_required,
                d.created_at = $created_at
        """, session=session, **decision_params)

        # Create relationships
        if decision.canonical_id:
            self._run("""
                MATCH (d:ResolutionDecision {decision_id: $decision_id})
                MATCH (c:CanonicalEntity {canonical_id: $canonical_id})
                MERGE (d)-[:DECIDED_FOR]->(c)
            """, session=session, decision_id=decision.decision_id, canonical_id=decision.canonical_id)

            self._run("""
                MATCH (r:RawEntity {raw_entity_id: $raw_entity_id})
                MATCH (c:CanonicalEntity {canonical_id: $canonical_id})
                MERGE (r)-[rel:RESOLVED_TO]->(c)
                SET rel.confidence = $overall_confidence,
                    rel.method = $method,
                    rel.decision_type = $decision_type,
                    rel.review_required = $review_required,
                    rel.created_at = $created_at
            """, session=session, raw_entity_id=decision.raw_entity_id, canonical_id=decision.canonical_id,
                overall_confidence=decision.overall_confidence,
                method=decision.method,
                decision_type=decision.decision_type,
                review_required=decision.review_required,
                created_at=decision.created_at)

        self._run("""
            MATCH (d:ResolutionDecision {decision_id: $decision_id})
            MATCH (r:RawEntity {raw_entity_id: $raw_entity_id})
            MERGE (d)-[:DECIDED_ON]->(r)
        """, session=session, decision_id=decision.decision_id, raw_entity_id=decision.raw_entity_id)

        # Save evidence
        for evidence in decision.evidence:
            self._run("""
                MERGE (e:Evidence {evidence_id: $evidence_id})
                SET e.evidence_type = $evidence_type,
                    e.description = $description,
                    e.score = $score,
                    e.source = $source,
                    e.details = $details
                WITH e
                MATCH (d:ResolutionDecision {decision_id: $decision_id})
                MERGE (d)-[:BASED_ON]->(e)
            """, session=session, decision_id=decision.decision_id, **{
                **evidence.__dict__,
                "details": serialize_property(evidence.details),
            })
