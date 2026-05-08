"""Dependency reasoning enrichment across entities in the graph."""

from enrichers.base import BaseEnricher


class DependencyReasoningEnricher(BaseEnricher):
    """Infer semantic relationships between entity pairs."""

    name = "dependency_reasoning"
    prompt_file = "dependency_reasoning.md"
    schema_file = "dependency_reasoning_schema.json"
    response_key = "relationships"

    def create_constraints(self):
        pass

    def get_candidates(self, limit):
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:BELONGS_TO_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(area:Area)
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            d.name AS domain,
            role.name AS semantic_role,
            area.name AS area
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
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
        query = """
        MATCH (source:Entity {entity_id: $source_entity_id})
        MATCH (target:Entity {entity_id: $target_entity_id})
        MERGE (source)-[r:SEMANTICALLY_RELATED_TO]->(target)
        SET r.relationship_type = $relationship_type,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
