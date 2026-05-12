"""Failure impact enrichment for Home Assistant entities."""

from enrichers.base import BaseEnricher


class FailureImpactEnricher(BaseEnricher):
    """Infer operational impact if an entity fails."""

    name = "failure_impact"
    prompt_file = "failure_impact.md"
    schema_file = "failure_impact_schema.json"
    response_key = "failure_impacts"

    def create_constraints(self):
        """Ensure unique failure impact level nodes by level value."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT failure_impact_level_unique IF NOT EXISTS
            FOR (f:FailureImpactLevel)
            REQUIRE f.level IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities that still need failure impact assessment."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

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
            collect(DISTINCT a2.name) AS controlled_by_automations,
        
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
        """Persist failure impact relationships and summaries."""
        canonical_body = """
        MERGE (level:FailureImpactLevel {level: $impact_level})

        MERGE (c)-[r:HAS_FAILURE_IMPACT]->(level)
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

        entity_body = """
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

        for item in items:
            self.execute_targeted_write(canonical_body, entity_body, item)
