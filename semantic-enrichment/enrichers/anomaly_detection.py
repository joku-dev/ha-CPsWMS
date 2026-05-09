"""Anomaly enrichment using entity state and recent event context."""

from enrichers.base import BaseEnricher


class AnomalyDetectionEnricher(BaseEnricher):
    """Detect potential anomalies per entity and persist graph annotations."""

    name = "anomaly_detection"
    prompt_file = "anomaly_detection.md"
    schema_file = "anomaly_detection_schema.json"
    response_key = "anomalies"

    def create_constraints(self):
        """Ensure unique anomaly type nodes by name."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT anomaly_type_name_unique IF NOT EXISTS
            FOR (a:AnomalyType)
            REQUIRE a.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities that have not yet been anomaly-checked."""
        query = """
        MATCH (e:Entity)
        WHERE e.anomaly_checked IS NULL
           OR e.anomaly_checked = false
        OPTIONAL MATCH (ev:HomeAssistantEvent)-[:AFFECTED_ENTITY]->(e)
        WITH e, collect(ev.message)[0..10] AS recent_events
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.last_updated AS last_updated,
            e.is_problem AS is_problem,
            recent_events AS recent_events
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
        """Persist anomaly relationships with severity metadata."""
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MERGE (a:AnomalyType {name: $anomaly_type})
        MERGE (e)-[r:HAS_ANOMALY]->(a)
        SET r.severity = $severity,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.anomaly_checked = true,
            e.anomaly_checked_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
