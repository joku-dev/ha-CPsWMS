"""Cypher queries for semantic core operations."""

# Source System queries
GET_SOURCE_SYSTEM = """
MATCH (s:SourceSystem {source_id: $source_id})
RETURN s
"""

# Raw Entity queries
GET_RAW_ENTITY = """
MATCH (r:RawEntity {raw_entity_id: $raw_entity_id})
RETURN r
"""

# Canonical Entity queries
GET_CANONICAL_ENTITY = """
MATCH (c:CanonicalEntity {canonical_id: $canonical_id})
RETURN c
"""

FIND_CANONICAL_CANDIDATES_BY_TYPE = """
MATCH (c:CanonicalEntity {entity_type: $entity_type})
RETURN c
"""

# Resolution Decision queries
GET_RESOLUTION_DECISION = """
MATCH (d:ResolutionDecision {decision_id: $decision_id})
RETURN d
"""

GET_DECISIONS_FOR_RAW_ENTITY = """
MATCH (d:ResolutionDecision)-[:DECIDED_ON]->(r:RawEntity {raw_entity_id: $raw_entity_id})
RETURN d
"""

GET_DECISIONS_FOR_CANONICAL_ENTITY = """
MATCH (d:ResolutionDecision)-[:DECIDED_FOR]->(c:CanonicalEntity {canonical_id: $canonical_id})
RETURN d
"""

# Evidence queries
GET_EVIDENCE_FOR_DECISION = """
MATCH (d:ResolutionDecision {decision_id: $decision_id})-[:BASED_ON]->(e:Evidence)
RETURN e
"""

# Relationships
GET_RAW_TO_CANONICAL_RESOLUTIONS = """
MATCH (r:RawEntity)-[rel:RESOLVED_TO]->(c:CanonicalEntity)
RETURN r, rel, c
"""

# Statistics
COUNT_ENTITIES_BY_TYPE = """
MATCH (c:CanonicalEntity {entity_type: $entity_type})
RETURN count(c) as count
"""

COUNT_PENDING_REVIEWS = """
MATCH (d:ResolutionDecision {review_required: true})
RETURN count(d) as count
"""