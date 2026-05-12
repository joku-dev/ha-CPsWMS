-- name: entity_count_by_domain
MATCH (e:Entity)
RETURN e.domain AS domain, count(e) AS entity_count
ORDER BY entity_count DESC
LIMIT 25

-- name: unavailable_entities
MATCH (e:Entity)
WHERE e.state IN ["unavailable", "unknown", "none"]
RETURN e.entity_id AS entity_id, e.friendly_name AS friendly_name, e.state AS state
LIMIT 25

-- name: automation_entity_links
MATCH (a:Automation)-[r:TRIGGERED_BY|CONTROLS|HAS_CONDITION]->(e:Entity)
RETURN a.automation_id AS automation_id, type(r) AS relation_type, e.entity_id AS entity_id
LIMIT 25

