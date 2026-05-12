"""Semantic description enrichment for Home Assistant entities."""

from enrichers.base import BaseEnricher


class SemanticDescriptionsEnricher(BaseEnricher):
    """Generate concise semantic descriptions per entity."""

    name = "semantic_descriptions"
    prompt_file = "semantic_descriptions.md"
    schema_file = "semantic_descriptions_schema.json"
    response_key = "semantic_descriptions"

    def create_constraints(self):
        """Ensure one semantic description node per entity."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT semantic_description_entity_unique IF NOT EXISTS
            FOR (d:SemanticDescription)
            REQUIRE d.entity_id IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities that still need generated semantic descriptions."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

        WHERE e.semantic_description_enriched IS NULL
           OR e.semantic_description_enriched = false
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_CATEGORY]->(category:SemanticCategory)
        OPTIONAL MATCH (e)-[:HAS_CRITICALITY]->(criticality:Criticality)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            role.name AS semantic_role,
            category.name AS semantic_category,
            criticality.level AS criticality,
        
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
        """Persist description nodes and HAS_SEMANTIC_DESCRIPTION links."""
        canonical_body = """
        MERGE (d:SemanticDescription {entity_id: $entity_id})
        SET d.short_description = $short_description,
            d.technical_context = $technical_context,
            d.source = "openai",
            d.updated_at = datetime()

        MERGE (c)-[r:HAS_SEMANTIC_DESCRIPTION]->(d)
        SET r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.semantic_description_enriched = true,
            e.semantic_description_enriched_at = datetime()
        """

        entity_body = """
        MERGE (d:SemanticDescription {entity_id: $entity_id})
        SET d.short_description = $short_description,
            d.technical_context = $technical_context,
            d.source = "openai",
            d.updated_at = datetime()

        MERGE (e)-[r:HAS_SEMANTIC_DESCRIPTION]->(d)
        SET r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.semantic_description_enriched = true,
            e.semantic_description_enriched_at = datetime()
        """

        for item in items:
            self.execute_targeted_write(canonical_body, entity_body, item)
