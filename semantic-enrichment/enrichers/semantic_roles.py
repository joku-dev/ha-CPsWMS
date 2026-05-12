"""Semantic role enrichment for Home Assistant entities."""

from config import OPENAI_MODEL
from enrichers.base import BaseEnricher


class SemanticRolesEnricher(BaseEnricher):
    """Assign semantic role, category and criticality to entities."""

    name = "semantic_roles"
    prompt_file = "semantic_roles.md"
    schema_file = "semantic_roles_schema.json"
    response_key = "enrichments"

    def create_constraints(self):
        """Ensure uniqueness constraints for role/category/criticality nodes."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT semantic_role_name_unique IF NOT EXISTS
            FOR (r:SemanticRole)
            REQUIRE r.name IS UNIQUE
            """)

            session.run("""
            CREATE CONSTRAINT semantic_category_name_unique IF NOT EXISTS
            FOR (c:SemanticCategory)
            REQUIRE c.name IS UNIQUE
            """)

            session.run("""
            CREATE CONSTRAINT criticality_level_unique IF NOT EXISTS
            FOR (c:Criticality)
            REQUIRE c.level IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities that have not yet been semantically classified."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

        WHERE coalesce(e.semantic_enriched, false) = false
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.icon AS icon,
            e.entity_category AS entity_category,
            e.platform AS platform,
            e.is_problem AS is_problem,
        
            raw.raw_entity_id AS raw_entity_id,
            raw.source_entity_id AS source_entity_id,
            c.canonical_id AS canonical_id
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep only in-batch entity ids with valid confidence."""
        allowed_ids = {item["entity_id"] for item in input_items}

        return [
            item
            for item in llm_items
            if item.get("entity_id") in allowed_ids and self.validate_confidence(item)
        ]

    def write_results(self, items):
        """Persist role/category/criticality relationships and audit event."""
        canonical_body = """
        MERGE (role:SemanticRole {name: $semantic_role})
        MERGE (category:SemanticCategory {name: $semantic_category})
        MERGE (criticality:Criticality {level: $criticality})

        MERGE (c)-[r1:HAS_SEMANTIC_ROLE]->(role)
        SET r1.confidence = $confidence,
            r1.reason = $reason,
            r1.source = "openai",
            r1.updated_at = datetime()

        MERGE (c)-[r2:HAS_SEMANTIC_CATEGORY]->(category)
        SET r2.confidence = $confidence,
            r2.source = "openai",
            r2.updated_at = datetime()

        MERGE (c)-[r3:HAS_CRITICALITY]->(criticality)
        SET r3.confidence = $confidence,
            r3.source = "openai",
            r3.updated_at = datetime()

        CREATE (event:SemanticEnrichmentEvent {
            event_id: randomUUID(),
            enricher: "semantic_roles",
            model: $model,
            source: "openai",
            confidence: $confidence,
            reason: $reason,
            created_at: datetime()
        })

        MERGE (e)-[:GENERATED_BY]->(event)
        MERGE (event)-[:GENERATED_ROLE]->(role)
        MERGE (event)-[:GENERATED_CATEGORY]->(category)
        MERGE (event)-[:GENERATED_CRITICALITY]->(criticality)

        SET e.semantic_enriched = true,
            e.semantic_enriched_at = datetime()
        """

        entity_body = """
        MERGE (role:SemanticRole {name: $semantic_role})
        MERGE (category:SemanticCategory {name: $semantic_category})
        MERGE (criticality:Criticality {level: $criticality})

        MERGE (e)-[r1:HAS_SEMANTIC_ROLE]->(role)
        SET r1.confidence = $confidence,
            r1.reason = $reason,
            r1.source = "openai",
            r1.updated_at = datetime()

        MERGE (e)-[r2:HAS_SEMANTIC_CATEGORY]->(category)
        SET r2.confidence = $confidence,
            r2.source = "openai",
            r2.updated_at = datetime()

        MERGE (e)-[r3:HAS_CRITICALITY]->(criticality)
        SET r3.confidence = $confidence,
            r3.source = "openai",
            r3.updated_at = datetime()

        CREATE (event:SemanticEnrichmentEvent {
            event_id: randomUUID(),
            enricher: "semantic_roles",
            model: $model,
            source: "openai",
            confidence: $confidence,
            reason: $reason,
            created_at: datetime()
        })

        MERGE (e)-[:GENERATED_BY]->(event)
        MERGE (event)-[:GENERATED_ROLE]->(role)
        MERGE (event)-[:GENERATED_CATEGORY]->(category)
        MERGE (event)-[:GENERATED_CRITICALITY]->(criticality)

        SET e.semantic_enriched = true,
            e.semantic_enriched_at = datetime()
        """

        for item in items:
            from config import OPENAI_MODEL
            item['model'] = OPENAI_MODEL
            self.execute_targeted_write(canonical_body, entity_body, item)
