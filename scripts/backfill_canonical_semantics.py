#!/usr/bin/env python3
"""Backfill existing Entity-level semantic relationships to CanonicalEntity."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from neo4j import GraphDatabase


SEMANTIC_RELATIONSHIP_TYPES = [
    "HAS_SEMANTIC_ROLE",
    "HAS_SEMANTIC_CATEGORY",
    "HAS_CRITICALITY",
    "HAS_AUTOMATION_INTENT",
    "HAS_FAULT_ANALYSIS",
    "HAS_ANOMALY",
    "HAS_OBSERVATION",
    "HAS_TIMELINE_EVENT",
    "HAS_STATE_TRANSITION",
    "HAS_INCIDENT",
    "INFERRED_LOCATION",
    "SEMANTICALLY_RELATED_TO",
    "PROVIDES_CAPABILITY",
    "CAUSES",
    "DEPENDS_ON",
    "IMPACTS",
    "DEGRADES",
    "RECOVERS",
    "HAS_CAUSAL_DEPENDENCY",
    "HAS_FAILURE_IMPACT",
    "HAS_SEMANTIC_DESCRIPTION",
    "HAS_RECOMMENDED_ACTION",
    "HAS_SIMULATION_READINESS",
]


@dataclass(frozen=True)
class BackfillResult:
    relationship_type: str
    outgoing_count: int
    incoming_count: int


def relationship_count(session, query: str, relationship_type: str) -> int:
    record = session.run(query.format(relationship_type=relationship_type)).single()
    return int(record["count"] or 0)


def backfill_relationship_type(session, relationship_type: str) -> BackfillResult:
    outgoing_query = """
    MATCH (e:Entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(c:CanonicalEntity)
    MATCH (e)-[r:{relationship_type}]->(target)
    MERGE (c)-[copy:{relationship_type}]->(target)
    SET copy += properties(r),
        copy.backfilled_from_entity = e.entity_id,
        copy.backfilled_at = datetime(),
        copy.source = coalesce(copy.source, r.source, "canonical_backfill")
    RETURN count(copy) AS count
    """

    incoming_query = """
    MATCH (e:Entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(c:CanonicalEntity)
    MATCH (source)-[r:{relationship_type}]->(e)
    WHERE NOT source:CanonicalEntity
    MERGE (source)-[copy:{relationship_type}]->(c)
    SET copy += properties(r),
        copy.backfilled_to_entity = e.entity_id,
        copy.backfilled_at = datetime(),
        copy.source = coalesce(copy.source, r.source, "canonical_backfill")
    RETURN count(copy) AS count
    """

    return BackfillResult(
        relationship_type=relationship_type,
        outgoing_count=relationship_count(session, outgoing_query, relationship_type),
        incoming_count=relationship_count(session, incoming_query, relationship_type),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill semantic relationships from Entity to CanonicalEntity."
    )
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.neo4j_password:
        raise SystemExit("NEO4J_PASSWORD or --neo4j-password is required.")

    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )

    try:
        with driver.session() as session:
            results = [
                backfill_relationship_type(session, relationship_type)
                for relationship_type in SEMANTIC_RELATIONSHIP_TYPES
            ]
    finally:
        driver.close()

    for result in results:
        if result.outgoing_count or result.incoming_count:
            print(
                f"{result.relationship_type}: "
                f"outgoing={result.outgoing_count} incoming={result.incoming_count}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
