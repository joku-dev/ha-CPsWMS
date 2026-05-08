"""Fault type and impact enrichment for problematic entities."""

from enrichers.base import BaseEnricher


class FaultAnalysisEnricher(BaseEnricher):
    """Classify problem entities into fault type and impact."""

    name = "fault_analysis"
    prompt_file = "fault_analysis.md"
    schema_file = "fault_analysis_schema.json"
    response_key = "faults"

    def create_constraints(self):
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT fault_type_name_unique IF NOT EXISTS
            FOR (f:FaultType)
            REQUIRE f.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        query = """
        MATCH (e:Entity)
        WHERE e.is_problem = true
          AND (e.fault_enriched IS NULL OR e.fault_enriched = false)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(a:Area)
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.last_updated AS last_updated,
            a.name AS area,
            role.name AS semantic_role
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        allowed_ids = {item["entity_id"] for item in input_items}
        return [
            item
            for item in llm_items
            if item.get("entity_id") in allowed_ids and self.validate_confidence(item)
        ]

    def write_results(self, items):
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MERGE (f:FaultType {name: $fault_type})
        MERGE (e)-[r:HAS_FAULT_ANALYSIS]->(f)
        SET r.impact = $impact,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.fault_enriched = true,
            e.fault_enriched_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
