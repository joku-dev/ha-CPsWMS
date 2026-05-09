"""Room inference enrichment for entities without explicit HA area mapping."""

from enrichers.base import BaseEnricher


class RoomInferenceEnricher(BaseEnricher):
    """Infer probable area assignments and store them as inferred links."""

    name = "room_inference"
    prompt_file = "room_inference.md"
    schema_file = "room_inference_schema.json"
    response_key = "room_inferences"

    def create_constraints(self):
        """No additional constraints required for inferred area links."""
        pass

    def get_candidates(self, limit):
        """Select entities without explicit room assignment."""
        query = """
        MATCH (e:Entity)
        WHERE NOT (e)-[:LOCATED_IN]->(:Area)
          AND (e.room_inference_checked IS NULL OR e.room_inference_checked = false)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.platform AS platform,
            e.icon AS icon
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
        """Write inferred room links and mark entities as processed."""
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MERGE (a:Area {area_id: $suggested_area})
        SET a.name = $suggested_area

        MERGE (e)-[r:INFERRED_LOCATION]->(a)
        SET r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.room_inference_checked = true,
            e.room_inference_checked_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
