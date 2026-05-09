"""Failure impact enrichment for Home Assistant entities."""

from enrichers.base import BaseEnricher


class FailureImpactEnricher(BaseEnricher):
    """Infer operational impact if an entity fails."""

    name = "failure_impact"
    prompt_file = "failure_impact.md"
    schema_file = "failure_impact_schema.json"
    response_key = "failure_impacts"

    def create_constraints(self):
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT failure_impact_level_unique IF NOT EXISTS
            FOR (f:FailureImpactLevel)
            REQUIRE f.level IS UNIQUE
            """)

    def get_candidates(self, limit):
        query = """
        MATCH (e:Entity)
        WHERE e.failure_impact_enriched IS NULL
           OR e.failure_impact_enriched = false
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        OPTIONAL MATCH (e)-[:HAS_CRITICALITY]->(crit:Criticality)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(area:Area)
        OPTIONAL MATCH (e)<-[:TRIGGERED_BY]-(a1:Automation)
        OPTIONAL MATCH (e)<-[:CONTROLS]-(a2:Automation)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.is_problem AS is_problem,
            role.name AS semantic_role,
            crit.level AS criticality,
            area.name AS area,
            collect(DISTINCT a1.name) AS triggered_automations,
            collect(DISTINCT a2.name) AS controlled_by_automations
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
        MERGE (level:FailureImpactLevel {level: $impact_level})

        MERGE (e)-[r:HAS_FAILURE_IMPACT]->(level)
        SET r.impact_summary = $impact_summary,
            r.affected_capability = $affected_capability,
            r.operational_consequence = $operational_consequence,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.failure_impact_enriched = true,
            e.failure_impact_enriched_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
