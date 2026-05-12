-- name: raw_to_canonical_resolution
MATCH (raw:RawEntity)-[r:RESOLVED_TO]->(canonical:CanonicalEntity)
RETURN raw.raw_entity_id AS raw_entity_id,
       raw.source_entity_id AS source_entity_id,
       canonical.canonical_id AS canonical_id,
       r.confidence AS confidence
LIMIT 25

-- name: canonical_entities_with_multiple_raw_representations
MATCH (canonical:CanonicalEntity)<-[:RESOLVED_TO]-(raw:RawEntity)
WITH canonical, count(raw) AS raw_count
WHERE raw_count > 1
RETURN canonical.canonical_id AS canonical_id, canonical.canonical_name AS canonical_name, raw_count
LIMIT 25

-- name: canonical_semantic_roles
MATCH (canonical:CanonicalEntity)-[r:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
RETURN canonical.canonical_id AS canonical_id, role.name AS role, r.confidence AS confidence
LIMIT 25

