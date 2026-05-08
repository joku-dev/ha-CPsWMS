"""Intent enrichment for Home Assistant automations."""

from enrichers.base import BaseEnricher


class AutomationIntentEnricher(BaseEnricher):
    """Infer business intent from automation triggers/conditions/targets."""

    name = "automation_intent"
    prompt_file = "automation_intent.md"
    schema_file = "automation_intent_schema.json"
    response_key = "automation_intents"

    def create_constraints(self):
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT automation_intent_name_unique IF NOT EXISTS
            FOR (i:AutomationIntent)
            REQUIRE i.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        query = """
        MATCH (a:Automation)
        WHERE a.intent_enriched IS NULL
           OR a.intent_enriched = false
        OPTIONAL MATCH (a)-[:TRIGGERED_BY]->(trigger:Entity)
        OPTIONAL MATCH (a)-[:CONTROLS]->(target:Entity)
        OPTIONAL MATCH (a)-[:HAS_CONDITION]->(condition:Entity)
        RETURN
            a.automation_id AS automation_id,
            a.name AS name,
            collect(DISTINCT trigger.entity_id) AS triggers,
            collect(DISTINCT target.entity_id) AS targets,
            collect(DISTINCT condition.entity_id) AS conditions
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        allowed_ids = {item["automation_id"] for item in input_items}
        return [
            item
            for item in llm_items
            if item.get("automation_id") in allowed_ids and self.validate_confidence(item)
        ]

    def write_results(self, items):
        query = """
        MATCH (a:Automation {automation_id: $automation_id})
        MERGE (intent:AutomationIntent {name: $intent})
        MERGE (a)-[r:HAS_AUTOMATION_INTENT]->(intent)
        SET r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET a.intent_enriched = true,
            a.intent_enriched_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
