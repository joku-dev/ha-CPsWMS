"""Simulation readiness enrichment for what-if scenario coverage."""

from enrichers.base import BaseEnricher


class SimulationReadinessEnricher(BaseEnricher):
    """Assess whether the graph has enough evidence for what-if simulations."""

    name = "simulation_readiness"
    prompt_file = "simulation_readiness.md"
    schema_file = "simulation_readiness_schema.json"
    response_key = "readiness_assessments"

    target_matchers = {
        "capability": "MATCH (target:Capability {name: $target_id})",
        "integration": "MATCH (target:Integration {domain: $target_id})",
        "entity": "MATCH (target:Entity {entity_id: $target_id})",
    }

    def create_constraints(self):
        """Ensure simulation scenarios and readiness levels are reusable."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT simulation_scenario_id_unique IF NOT EXISTS
            FOR (s:SimulationScenario)
            REQUIRE s.scenario_id IS UNIQUE
            """)

            session.run("""
            CREATE CONSTRAINT simulation_readiness_level_unique IF NOT EXISTS
            FOR (r:SimulationReadinessLevel)
            REQUIRE r.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch scenario candidates with capability, dependency and history signals."""
        query = """
        CALL {
            MATCH (target:Integration)
            WHERE target.domain IS NOT NULL
            RETURN
                "integration_outage:" + target.domain AS scenario_id,
                "integration_outage" AS scenario_type,
                target.domain AS target_id,
                "integration" AS target_type,
                target.domain AS target_name

            UNION

            MATCH (target:Capability)
            WHERE target.name IS NOT NULL
            RETURN
                "capability_loss:" + target.name AS scenario_id,
                "capability_loss" AS scenario_type,
                target.name AS target_id,
                "capability" AS target_type,
                target.name AS target_name

            UNION

            MATCH (target:Entity)-[:HAS_CRITICALITY]->(crit:Criticality)
            WHERE crit.level IN ["high", "critical"]
            RETURN
                "entity_failure:" + target.entity_id AS scenario_id,
                "entity_failure" AS scenario_type,
                target.entity_id AS target_id,
                "entity" AS target_type,
                coalesce(target.friendly_name, target.entity_id) AS target_name
        }

        WITH scenario_id, scenario_type, target_id, target_type, target_name
        ORDER BY scenario_id
        LIMIT $limit

        OPTIONAL MATCH (scenario:SimulationScenario {scenario_id: scenario_id})
        WITH scenario_id, scenario_type, target_id, target_type, target_name, scenario
        WHERE scenario IS NULL
           OR coalesce(scenario.simulation_readiness_checked, false) = false

        CALL {
            WITH target_id, target_type
            OPTIONAL MATCH (cap:Capability {name: target_id})
            WHERE target_type = "capability"
            OPTIONAL MATCH (cap)<-[cap_rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]-()
            RETURN count(DISTINCT cap_rel) AS capability_dependency_count
        }

        CALL {
            WITH target_id, target_type
            OPTIONAL MATCH (integration:Integration {domain: target_id})
            WHERE target_type = "integration"
            OPTIONAL MATCH (entity:Entity)-[:PROVIDED_BY]->(integration)
            OPTIONAL MATCH (entity)-[rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]-()
            RETURN
                count(DISTINCT entity) AS integration_entity_count,
                count(DISTINCT rel) AS integration_dependency_count,
                collect(DISTINCT entity.entity_id)[0..10] AS integration_entities
        }

        CALL {
            WITH target_id, target_type
            OPTIONAL MATCH (entity:Entity {entity_id: target_id})
            WHERE target_type = "entity"
            OPTIONAL MATCH (entity)-[rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]-()
            RETURN count(DISTINCT rel) AS entity_dependency_count
        }

        CALL {
            WITH target_id, target_type
            OPTIONAL MATCH (entity:Entity)
            OPTIONAL MATCH (entity)-[impact_rel:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
            OPTIONAL MATCH (entity)-[provides_rel:PROVIDES_CAPABILITY]->(provided_capability:Capability)
            WHERE
                (target_type = "entity" AND entity.entity_id = target_id)
                OR (target_type = "integration" AND exists {
                    MATCH (entity)-[:PROVIDED_BY]->(:Integration {domain: target_id})
                })
                OR (
                    target_type = "capability"
                    AND (
                        impact_rel.affected_capability = target_id
                        OR provided_capability.name = target_id
                    )
                )
            OPTIONAL MATCH (entity)-[:HAS_INCIDENT]->(incident:Incident)
            OPTIONAL MATCH (entity)-[:HAS_FAULT_ANALYSIS]->(fault:FaultType)
            OPTIONAL MATCH (entity)-[:HAS_ANOMALY]->(anomaly:AnomalyType)
            OPTIONAL MATCH (entity)-[:HAS_TIMELINE_EVENT]->(timeline:TimelineEvent)
            OPTIONAL MATCH (entity)<-[:TRIGGERED_BY|CONTROLS|HAS_CONDITION]-(automation:Automation)
            OPTIONAL MATCH (entity)-[:HAS_CRITICALITY]->(criticality:Criticality)
            RETURN
                count(DISTINCT impact_rel) + count(DISTINCT provides_rel) AS capability_signal_count,
                count(DISTINCT incident) + count(DISTINCT fault) + count(DISTINCT anomaly) AS failure_history_count,
                count(DISTINCT timeline) AS temporal_event_count,
                count(DISTINCT automation) AS automation_relationship_count,
                count(DISTINCT CASE
                    WHEN criticality.level IN ["high", "critical"] THEN entity
                    ELSE NULL
                END) AS critical_entity_count,
                collect(DISTINCT {
                    entity_id: entity.entity_id,
                    friendly_name: entity.friendly_name,
                    criticality: criticality.level,
                    affected_capability: coalesce(provided_capability.name, impact_rel.affected_capability)
                })[0..10] AS entity_samples
        }

        RETURN
            scenario_id,
            scenario_type,
            target_id,
            target_type,
            target_name,
            capability_signal_count,
            capability_dependency_count + integration_dependency_count + entity_dependency_count AS dependency_count,
            failure_history_count,
            temporal_event_count,
            automation_relationship_count,
            critical_entity_count,
            integration_entity_count,
            integration_entities,
            entity_samples
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep only known scenarios with valid readiness and confidence fields."""
        allowed = {item["scenario_id"]: item for item in input_items}
        valid_readiness = {"ready", "partial", "not_ready", "unknown"}
        valid = []

        for item in llm_items:
            input_item = allowed.get(item.get("scenario_id"))
            if input_item is None:
                continue

            for key in ("scenario_type", "target_type", "target_id", "target_name"):
                if item.get(key) != input_item.get(key):
                    item[key] = input_item.get(key)

            if item.get("readiness") not in valid_readiness:
                continue

            if not self.validate_confidence(item):
                continue

            valid.append(item)

        return valid

    def write_results(self, items):
        """Persist simulation readiness assessments per scenario."""
        with self.driver.session() as session:
            for item in items:
                session.run(self.build_write_query(item), **item)

    def build_write_query(self, item):
        """Build a Cypher statement with a validated target label."""
        target_type = item["target_type"]
        target_clause = self.target_matchers[target_type]

        return f"""
        MERGE (scenario:SimulationScenario {{scenario_id: $scenario_id}})
        SET scenario.scenario_type = $scenario_type,
            scenario.target_type = $target_type,
            scenario.target_id = $target_id,
            scenario.target_name = $target_name,
            scenario.simulation_readiness_checked = true,
            scenario.simulation_readiness_checked_at = datetime()

        MERGE (level:SimulationReadinessLevel {{name: $readiness}})
        MERGE (scenario)-[r:HAS_SIMULATION_READINESS]->(level)
        SET r.coverage_score = $coverage_score,
            r.missing_data = $missing_data,
            r.supported_questions = $supported_questions,
            r.required_next_steps = $required_next_steps,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        {target_clause}
        MERGE (scenario)-[:EVALUATES_TARGET]->(target)
        """
