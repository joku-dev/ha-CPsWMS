"""Resolve enrichment targets based on canonical and legacy entity graphs."""

from config import ENRICHMENT_TARGET_MODE


class EnrichmentTargetResolver:
    """Decides whether semantic writes should target CanonicalEntity or Entity."""

    VALID_MODES = {"canonical_first", "entity_first", "dual_write"}

    def __init__(self, mode: str | None = None):
        self.mode = (mode or ENRICHMENT_TARGET_MODE).lower()
        if self.mode not in self.VALID_MODES:
            self.mode = "canonical_first"

    def canonical_context_clause(self) -> str:
        """Return the Cypher snippet that enrichers can use to expose canonical context."""
        return """
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)
        """

    def build_write_query(self, canonical_body: str, entity_body: str) -> str:
        """Build a Cypher query that targets the selected enrichment mode."""
        if self.mode == "entity_first":
            return f"""
            MATCH (e:Entity {{entity_id: $entity_id}})
            {self.canonical_context_clause()}
            WITH e, c
            {entity_body}
            """

        if self.mode == "dual_write":
            return f"""
            MATCH (e:Entity {{entity_id: $entity_id}})
            {self.canonical_context_clause()}
            WITH e, c
            FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
                {canonical_body}
            )
            FOREACH (_ IN [1] |
                {entity_body}
            )
            """

        return f"""
        MATCH (e:Entity {{entity_id: $entity_id}})
        {self.canonical_context_clause()}
        WITH e, c
        FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
            {canonical_body}
        )
        FOREACH (_ IN CASE WHEN c IS NULL THEN [1] ELSE [] END |
            {entity_body}
        )
        """

    def get_mode(self) -> str:
        return self.mode
