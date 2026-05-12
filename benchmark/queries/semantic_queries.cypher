-- name: critical_entities
MATCH (e:Entity)-[:HAS_CRITICALITY]->(c:Criticality)
RETURN e.entity_id AS entity_id, e.friendly_name AS friendly_name, c.level AS criticality
LIMIT 25

-- name: semantic_roles
MATCH (e:Entity)-[r:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
RETURN e.entity_id AS entity_id, role.name AS role, r.confidence AS confidence
LIMIT 25

-- name: lighting_capabilities
MATCH (e:Entity)-[r:PROVIDES_CAPABILITY]->(cap:Capability)
WHERE toLower(cap.name) CONTAINS "lighting"
RETURN e.entity_id AS entity_id, cap.name AS capability, r.confidence AS confidence
LIMIT 25

-- name: dependency_links
MATCH (source)-[r:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]->(target)
RETURN labels(source) AS source_labels,
       coalesce(source.entity_id, source.canonical_id, source.name, source.automation_id) AS source_id,
       type(r) AS relation_type,
       labels(target) AS target_labels,
       coalesce(target.entity_id, target.canonical_id, target.name, target.automation_id) AS target_id
LIMIT 25

-- name: recommended_actions
MATCH (e:Entity)-[r:HAS_RECOMMENDED_ACTION]->(action:RecommendedActionType)
RETURN e.entity_id AS entity_id, action.name AS action, r.priority AS priority, r.confidence AS confidence
LIMIT 25

-- name: simulation_readiness
MATCH (scenario:SimulationScenario)-[r:HAS_SIMULATION_READINESS]->(level:SimulationReadinessLevel)
RETURN scenario.scenario_id AS scenario_id, level.name AS readiness, r.coverage_score AS coverage_score
LIMIT 25

