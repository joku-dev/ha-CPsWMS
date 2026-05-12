"""Dependency reasoning enrichment across entities in the graph."""

from enrichers.base import BaseEnricher


class DependencyReasoningEnricher(BaseEnricher):
    """Infer semantic relationships between entity pairs."""

    name = "dependency_reasoning"
    prompt_file = "dependency_reasoning.md"
    schema_file = "dependency_reasoning_schema.json"
    response_key = "relationships"
    graph_relationship_types = {
        "depends_on": "DEPENDS_ON",
    }

    def create_constraints(self):
        """No additional constraints required for relationship edges."""
        pass

    def get_candidates(self, limit):
        """Fetch entity context used to infer semantic dependencies."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

        OPTIONAL MATCH (e)-[:BELONGS_TO_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (c)-[:HAS_SEMANTIC_ROLE]->(canonical_role:SemanticRole)
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(entity_role:SemanticRole)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(area:Area)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            d.name AS domain,
            coalesce(canonical_role.name, entity_role.name) AS semantic_role,
            area.name AS area,
        
            raw.raw_entity_id AS raw_entity_id,
            raw.source_entity_id AS source_entity_id,
            c.canonical_id AS canonical_id
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep only valid in-batch source/target ids and confidence."""
        allowed_ids = {item["entity_id"] for item in input_items}
        valid = []

        for item in llm_items:
            if item.get("source_entity_id") not in allowed_ids:
                continue

            if item.get("target_entity_id") not in allowed_ids:
                continue

            if not self.validate_confidence(item):
                continue

            valid.append(item)

        return valid

    def write_results(self, items):
        """Persist inferred relationships on canonical targets when available."""
        with self.driver.session() as session:
            for item in items:
                relationship_type = self.graph_relationship_type(item)
                query = f"""
        MATCH (source_entity:Entity {{entity_id: $source_entity_id}})
        OPTIONAL MATCH (source_entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(source_canonical:CanonicalEntity)
        MATCH (target_entity:Entity {{entity_id: $target_entity_id}})
        OPTIONAL MATCH (target_entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(target_canonical:CanonicalEntity)
        WITH
            source_entity,
            target_entity,
            source_canonical,
            coalesce(source_canonical, source_entity) AS source,
            coalesce(target_canonical, target_entity) AS target
        MERGE (source)-[r:{relationship_type}]->(target)
        SET r.relationship_type = $relationship_type,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET source_entity.dependency_reasoning_enriched = true,
            source_entity.dependency_reasoning_enriched_at = datetime()
        FOREACH (_ IN CASE WHEN source_canonical IS NULL THEN [] ELSE [1] END |
            SET source_canonical.dependency_reasoning_enriched = true,
                source_canonical.dependency_reasoning_enriched_at = datetime()
        )
        """
                session.run(query, **item)

    def graph_relationship_type(self, item):
        """Map LLM relationship labels to safe graph relationship tokens."""
        relationship_type = item.get("relationship_type", "unknown")
        return self.graph_relationship_types.get(
            relationship_type,
            "SEMANTICALLY_RELATED_TO",
        )
