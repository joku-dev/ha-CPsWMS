"""Recommended action enrichment for Home Assistant entities."""

from enrichers.base import BaseEnricher


class RecommendedActionsEnricher(BaseEnricher):
    """Suggest practical and safe follow-up actions for entities."""

    name = "recommended_actions"
    prompt_file = "recommended_actions.md"
    schema_file = "recommended_actions_schema.json"
    response_key = "recommended_actions"

    def create_constraints(self):
        """Ensure unique recommended action type nodes by name."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT recommended_action_type_unique IF NOT EXISTS
            FOR (a:RecommendedActionType)
            REQUIRE a.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities that still need actionable recommendations."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

        WHERE e.recommended_actions_enriched IS NULL
           OR e.recommended_actions_enriched = false
        OPTIONAL MATCH (e)-[:HAS_ANOMALY]->(anomaly:AnomalyType)
        OPTIONAL MATCH (e)-[:HAS_FAULT_ANALYSIS]->(fault:FaultType)
        OPTIONAL MATCH (e)-[:HAS_FAILURE_IMPACT]->(impact:FailureImpactLevel)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.is_problem AS is_problem,
            collect(DISTINCT anomaly.name) AS anomalies,
            collect(DISTINCT fault.name) AS faults,
            impact.level AS failure_impact,
        
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
        """Persist recommended actions and prioritization metadata."""
        canonical_body = """
        MERGE (a:RecommendedActionType {name: $action_type})

        MERGE (c)-[r:HAS_RECOMMENDED_ACTION]->(a)
        SET r.recommended_action = $recommended_action,
            r.priority = $priority,
            r.effort = $effort,
            r.requires_human_approval = $requires_human_approval,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.recommended_actions_enriched = true,
            e.recommended_actions_enriched_at = datetime()
        """

        entity_body = """
        MERGE (a:RecommendedActionType {name: $action_type})

        MERGE (e)-[r:HAS_RECOMMENDED_ACTION]->(a)
        SET r.recommended_action = $recommended_action,
            r.priority = $priority,
            r.effort = $effort,
            r.requires_human_approval = $requires_human_approval,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.recommended_actions_enriched = true,
            e.recommended_actions_enriched_at = datetime()
        """

        for item in items:
            self.execute_targeted_write(canonical_body, entity_body, item)
