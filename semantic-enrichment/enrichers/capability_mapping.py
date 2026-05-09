"""Capability mapping enrichment for Home Assistant entities."""

from enrichers.base import BaseEnricher


class CapabilityMappingEnricher(BaseEnricher):
    """Map entities to the capabilities they provide in the smart home."""

    name = "capability_mapping"
    prompt_file = "capability_mapping.md"
    schema_file = "capability_mapping_schema.json"
    response_key = "capability_mappings"

    def create_constraints(self):
        """Ensure capability nodes are addressable by stable names."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT capability_name_unique IF NOT EXISTS
            FOR (c:Capability)
            REQUIRE c.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch semantically enriched entities that still need capability mapping."""
        query = """
        MATCH (e:Entity)
        WHERE coalesce(e.capability_mapped, false) = false
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        OPTIONAL MATCH (e)-[:HAS_SEMANTIC_CATEGORY]->(category:SemanticCategory)
        OPTIONAL MATCH (e)-[:HAS_CRITICALITY]->(criticality:Criticality)
        OPTIONAL MATCH (e)-[:HAS_DEVICE_CLASS]->(device_class:DeviceClass)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(area:Area)
        OPTIONAL MATCH (e)-[impact_rel:HAS_FAILURE_IMPACT]->(impact:FailureImpactLevel)
        OPTIONAL MATCH (e)<-[:TRIGGERED_BY]-(triggered:Automation)
        OPTIONAL MATCH (e)<-[:CONTROLS]-(controlled:Automation)
        OPTIONAL MATCH (e)<-[:HAS_CONDITION]-(condition:Automation)
        WITH
            e,
            role,
            category,
            criticality,
            device_class,
            area,
            collect(DISTINCT impact_rel.affected_capability) AS affected_capabilities,
            collect(DISTINCT triggered.name) AS triggered_automations,
            collect(DISTINCT controlled.name) AS controlled_by_automations,
            collect(DISTINCT condition.name) AS condition_automations
        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.icon AS icon,
            e.entity_category AS entity_category,
            e.platform AS platform,
            e.is_problem AS is_problem,
            role.name AS semantic_role,
            category.name AS semantic_category,
            criticality.level AS criticality,
            device_class.name AS device_class,
            area.name AS area,
            [cap IN affected_capabilities WHERE cap IS NOT NULL] AS affected_capabilities,
            triggered_automations AS triggered_automations,
            controlled_by_automations AS controlled_by_automations,
            condition_automations AS condition_automations
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep only in-batch entity ids with valid capability mapping fields."""
        allowed_ids = {item["entity_id"] for item in input_items}
        allowed_levels = {"primary", "supporting", "diagnostic", "unknown"}
        valid = []

        for item in llm_items:
            if item.get("entity_id") not in allowed_ids:
                continue

            if not item.get("capability"):
                continue

            if item.get("provides_level") not in allowed_levels:
                continue

            if not self.validate_confidence(item):
                continue

            valid.append(item)

        return valid

    def write_results(self, items):
        """Persist explicit PROVIDES_CAPABILITY relationships."""
        query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MERGE (cap:Capability {name: $capability})

        MERGE (e)-[r:PROVIDES_CAPABILITY]->(cap)
        SET r.provides_level = $provides_level,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET e.capability_mapped = true,
            e.capability_mapped_at = datetime()
        """

        with self.driver.session() as session:
            for item in items:
                session.run(query, **item)
