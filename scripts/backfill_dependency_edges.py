#!/usr/bin/env python3
"""Derive deterministic dependency edges from existing graph facts."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from neo4j import GraphDatabase


@dataclass(frozen=True)
class DerivationResult:
    name: str
    count: int


def run_count(session, name: str, query: str) -> DerivationResult:
    record = session.run(query).single()
    return DerivationResult(name=name, count=int(record["count"] or 0))


def derive_entity_integration_dependencies(session) -> DerivationResult:
    query = """
    MATCH (e:Entity)-[:PROVIDED_BY]->(integration:Integration)
    WHERE integration.domain IS NOT NULL
    MERGE (e)-[entity_rel:DEPENDS_ON]->(integration)
    SET entity_rel.relationship_type = "depends_on",
        entity_rel.confidence = coalesce(entity_rel.confidence, 0.95),
        entity_rel.reason = coalesce(
            entity_rel.reason,
            "Entity is provided by this Home Assistant integration."
        ),
        entity_rel.source = coalesce(entity_rel.source, "deterministic_dependency_backfill"),
        entity_rel.updated_at = datetime()

    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    FOREACH (_ IN CASE WHEN canonical IS NULL THEN [] ELSE [1] END |
        MERGE (canonical)-[canonical_rel:DEPENDS_ON]->(integration)
        SET canonical_rel.relationship_type = "depends_on",
            canonical_rel.confidence = coalesce(canonical_rel.confidence, 0.95),
            canonical_rel.reason = coalesce(
                canonical_rel.reason,
                "Canonical entity is backed by a raw entity provided by this Home Assistant integration."
            ),
            canonical_rel.source = coalesce(canonical_rel.source, "deterministic_dependency_backfill"),
            canonical_rel.updated_at = datetime()
    )
    RETURN count(DISTINCT e) AS count
    """
    return run_count(session, "entity_integration_depends_on", query)


def derive_capability_impact_edges(session) -> DerivationResult:
    query = """
    MATCH (e:Entity)-[:PROVIDES_CAPABILITY]->(capability:Capability)
    WHERE capability.name IS NOT NULL
    MERGE (e)-[entity_rel:IMPACTS]->(capability)
    SET entity_rel.relationship_type = "impacts",
        entity_rel.confidence = coalesce(entity_rel.confidence, 0.9),
        entity_rel.reason = coalesce(
            entity_rel.reason,
            "Entity availability directly impacts a capability it provides."
        ),
        entity_rel.source = coalesce(entity_rel.source, "deterministic_dependency_backfill"),
        entity_rel.updated_at = datetime()

    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    FOREACH (_ IN CASE WHEN canonical IS NULL THEN [] ELSE [1] END |
        MERGE (canonical)-[canonical_rel:IMPACTS]->(capability)
        SET canonical_rel.relationship_type = "impacts",
            canonical_rel.confidence = coalesce(canonical_rel.confidence, 0.9),
            canonical_rel.reason = coalesce(
                canonical_rel.reason,
                "Canonical entity availability directly impacts a capability provided by one of its raw entities."
            ),
            canonical_rel.source = coalesce(canonical_rel.source, "deterministic_dependency_backfill"),
            canonical_rel.updated_at = datetime()
    )
    RETURN count(DISTINCT e) AS count
    """
    return run_count(session, "entity_capability_impacts", query)


def derive_failure_degradation_edges(session) -> DerivationResult:
    query = """
    MATCH (e:Entity)-[impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
    WHERE impact.affected_capability IS NOT NULL
    MERGE (capability:Capability {name: impact.affected_capability})
    MERGE (e)-[entity_rel:DEGRADES]->(capability)
    SET entity_rel.relationship_type = "degrades",
        entity_rel.confidence = coalesce(entity_rel.confidence, impact.confidence, 0.85),
        entity_rel.reason = coalesce(
            entity_rel.reason,
            impact.reason,
            "Failure impact evidence says this entity can degrade the affected capability."
        ),
        entity_rel.source = coalesce(entity_rel.source, "deterministic_dependency_backfill"),
        entity_rel.updated_at = datetime()

    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    FOREACH (_ IN CASE WHEN canonical IS NULL THEN [] ELSE [1] END |
        MERGE (canonical)-[canonical_rel:DEGRADES]->(capability)
        SET canonical_rel.relationship_type = "degrades",
            canonical_rel.confidence = coalesce(canonical_rel.confidence, impact.confidence, 0.85),
            canonical_rel.reason = coalesce(
                canonical_rel.reason,
                impact.reason,
                "Failure impact evidence from a raw entity says this canonical entity can degrade the affected capability."
            ),
            canonical_rel.source = coalesce(canonical_rel.source, "deterministic_dependency_backfill"),
            canonical_rel.updated_at = datetime()
    )
    RETURN count(DISTINCT e) AS count
    """
    return run_count(session, "failure_capability_degrades", query)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive DEPENDS_ON/IMPACTS/DEGRADES edges from existing entity facts."
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
                derive_entity_integration_dependencies(session),
                derive_capability_impact_edges(session),
                derive_failure_degradation_edges(session),
            ]
    finally:
        driver.close()

    for result in results:
        print(f"{result.name}: {result.count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
