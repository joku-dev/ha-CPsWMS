#!/usr/bin/env python3
"""Derive causal and simulation-readiness edges from existing evidence."""

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


def create_constraints(session) -> None:
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


def derive_degradation_causal_dependencies(session) -> DerivationResult:
    query = """
    MATCH (source)-[degradation:DEGRADES]->(capability:Capability)
    WHERE source:Entity OR source:CanonicalEntity
    MERGE (source)-[causal:HAS_CAUSAL_DEPENDENCY]->(capability)
    SET causal.relationship_type = coalesce(causal.relationship_type, "degrades"),
        causal.causal_stage = coalesce(causal.causal_stage, "degradation"),
        causal.confidence = coalesce(causal.confidence, degradation.confidence, 0.84),
        causal.reason = coalesce(
            causal.reason,
            degradation.reason,
            "Existing degradation evidence establishes a causal dependency to this capability."
        ),
        causal.source = coalesce(causal.source, "deterministic_causal_backfill"),
        causal.updated_at = datetime()
    RETURN count(DISTINCT source) AS count
    """
    return run_count(session, "degradation_causal_dependencies", query)


def derive_problem_failure_causes(session) -> DerivationResult:
    query = """
    MATCH (e:Entity)
    WHERE coalesce(e.is_problem, false) = true
    MATCH (e)-[impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
    WHERE impact.affected_capability IS NOT NULL
    MERGE (capability:Capability {name: impact.affected_capability})
    MERGE (e)-[entity_cause:CAUSES]->(capability)
    SET entity_cause.relationship_type = "causes",
        entity_cause.causal_stage = "impact",
        entity_cause.confidence = coalesce(entity_cause.confidence, impact.confidence, 0.78),
        entity_cause.reason = coalesce(
            entity_cause.reason,
            impact.reason,
            "Problem-state entity has failure-impact evidence for this capability."
        ),
        entity_cause.source = coalesce(entity_cause.source, "deterministic_causal_backfill"),
        entity_cause.updated_at = datetime()

    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    FOREACH (_ IN CASE WHEN canonical IS NULL THEN [] ELSE [1] END |
        MERGE (canonical)-[canonical_cause:CAUSES]->(capability)
        SET canonical_cause.relationship_type = "causes",
            canonical_cause.causal_stage = "impact",
            canonical_cause.confidence = coalesce(canonical_cause.confidence, impact.confidence, 0.78),
            canonical_cause.reason = coalesce(
                canonical_cause.reason,
                impact.reason,
                "Problem-state raw entity has failure-impact evidence for this canonical capability impact."
            ),
            canonical_cause.source = coalesce(canonical_cause.source, "deterministic_causal_backfill"),
            canonical_cause.updated_at = datetime()
    )
    RETURN count(DISTINCT e) AS count
    """
    return run_count(session, "problem_failure_causes", query)


def derive_incident_causal_dependencies(session) -> DerivationResult:
    query = """
    MATCH (source)-[:HAS_INCIDENT]->(incident:Incident)
    WHERE source:Entity OR source:CanonicalEntity
    MERGE (source)-[causal:HAS_CAUSAL_DEPENDENCY]->(incident)
    SET causal.relationship_type = "incident_evidence",
        causal.causal_stage = "evidence",
        causal.confidence = coalesce(causal.confidence, 0.72),
        causal.reason = coalesce(
            causal.reason,
            "Incident evidence marks this node as relevant for causal analysis."
        ),
        causal.source = coalesce(causal.source, "deterministic_causal_backfill"),
        causal.updated_at = datetime()
    RETURN count(DISTINCT source) AS count
    """
    return run_count(session, "incident_causal_dependencies", query)


def derive_automation_causal_edges(session) -> DerivationResult:
    query = """
    MATCH (trigger:Entity)<-[trigger_rel:TRIGGERED_BY]-(automation:Automation)-[control_rel:CONTROLS]->(target:Entity)
    WHERE trigger.entity_id IS NOT NULL AND target.entity_id IS NOT NULL
    MERGE (trigger)-[entity_cause:CAUSES]->(target)
    SET entity_cause.relationship_type = "causes",
        entity_cause.causal_stage = "automation",
        entity_cause.confidence = coalesce(entity_cause.confidence, 0.86),
        entity_cause.reason = coalesce(
            entity_cause.reason,
            "Automation trigger controls the target entity."
        ),
        entity_cause.via_automation = automation.automation_id,
        entity_cause.source = coalesce(entity_cause.source, "deterministic_causal_backfill"),
        entity_cause.updated_at = datetime()

    OPTIONAL MATCH (trigger)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(trigger_canonical:CanonicalEntity)
    OPTIONAL MATCH (target)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(target_canonical:CanonicalEntity)
    FOREACH (_ IN CASE
        WHEN trigger_canonical IS NULL OR target_canonical IS NULL THEN []
        ELSE [1]
    END |
        MERGE (trigger_canonical)-[canonical_cause:CAUSES]->(target_canonical)
        SET canonical_cause.relationship_type = "causes",
            canonical_cause.causal_stage = "automation",
            canonical_cause.confidence = coalesce(canonical_cause.confidence, 0.86),
            canonical_cause.reason = coalesce(
                canonical_cause.reason,
                "Canonical trigger entity controls canonical target entity through an automation."
            ),
            canonical_cause.via_automation = automation.automation_id,
            canonical_cause.source = coalesce(canonical_cause.source, "deterministic_causal_backfill"),
            canonical_cause.updated_at = datetime()
    )
    RETURN count(DISTINCT trigger.entity_id + "->" + target.entity_id) AS count
    """
    return run_count(session, "automation_causal_edges", query)


def derive_can_cause_edges(session) -> DerivationResult:
    query = """
    MATCH (source:Entity)-[shortcut:CAN_CAUSE]->(target:Entity)
    WHERE source.entity_id IS NOT NULL AND target.entity_id IS NOT NULL
    MERGE (source)-[entity_cause:CAUSES]->(target)
    SET entity_cause.relationship_type = "causes",
        entity_cause.causal_stage = "automation",
        entity_cause.confidence = coalesce(entity_cause.confidence, 0.82),
        entity_cause.reason = coalesce(
            entity_cause.reason,
            "Existing CAN_CAUSE shortcut was materialized as a causal edge."
        ),
        entity_cause.via_automation = shortcut.via,
        entity_cause.source = coalesce(entity_cause.source, "deterministic_causal_backfill"),
        entity_cause.updated_at = datetime()

    OPTIONAL MATCH (source)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(source_canonical:CanonicalEntity)
    OPTIONAL MATCH (target)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(target_canonical:CanonicalEntity)
    FOREACH (_ IN CASE
        WHEN source_canonical IS NULL OR target_canonical IS NULL THEN []
        ELSE [1]
    END |
        MERGE (source_canonical)-[canonical_cause:CAUSES]->(target_canonical)
        SET canonical_cause.relationship_type = "causes",
            canonical_cause.causal_stage = "automation",
            canonical_cause.confidence = coalesce(canonical_cause.confidence, 0.82),
            canonical_cause.reason = coalesce(
                canonical_cause.reason,
                "Existing raw CAN_CAUSE shortcut was materialized as a canonical causal edge."
            ),
            canonical_cause.via_automation = shortcut.via,
            canonical_cause.source = coalesce(canonical_cause.source, "deterministic_causal_backfill"),
            canonical_cause.updated_at = datetime()
    )
    RETURN count(DISTINCT source.entity_id + "->" + target.entity_id) AS count
    """
    return run_count(session, "can_cause_materialized_edges", query)


def derive_simulation_readiness_baseline(session) -> DerivationResult:
    query = """
    MATCH (canonical:CanonicalEntity)
    WHERE canonical.canonical_id IS NOT NULL
      AND exists { MATCH (canonical)-[:HAS_SEMANTIC_ROLE]->() }
      AND exists { MATCH (canonical)-[:PROVIDES_CAPABILITY]->() }
      AND exists { MATCH (canonical)-[:DEPENDS_ON|IMPACTS|DEGRADES|CAUSES|HAS_CAUSAL_DEPENDENCY]-() }
    OPTIONAL MATCH (canonical)-[causal:CAUSES|HAS_CAUSAL_DEPENDENCY]-()
    WITH canonical, count(causal) AS causal_count
    MERGE (scenario:SimulationScenario {
        scenario_id: "canonical_entity_failure:" + canonical.canonical_id
    })
    SET scenario.scenario_type = "entity_failure",
        scenario.target_type = "canonical_entity",
        scenario.target_id = canonical.canonical_id,
        scenario.target_name = coalesce(canonical.canonical_name, canonical.canonical_id),
        scenario.simulation_readiness_checked = true,
        scenario.simulation_readiness_checked_at = datetime(),
        scenario.source = coalesce(scenario.source, "deterministic_causal_backfill")

    MERGE (level:SimulationReadinessLevel {
        name: CASE WHEN causal_count > 0 THEN "partial" ELSE "not_ready" END
    })
    MERGE (scenario)-[readiness:HAS_SIMULATION_READINESS]->(level)
    SET readiness.coverage_score = CASE WHEN causal_count > 0 THEN 0.68 ELSE 0.45 END,
        readiness.missing_data = CASE
            WHEN causal_count > 0 THEN [
                "validated automation trigger/action paths",
                "time-ordered causal incident chains",
                "human-reviewed causal confidence"
            ]
            ELSE [
                "causal dependency edges",
                "validated automation trigger/action paths",
                "incident or timeline evidence"
            ]
        END,
        readiness.supported_questions = [
            "Which integration and capability dependencies are connected to this canonical entity?",
            "Which capabilities can be degraded by this canonical entity?",
            "Which causal evidence exists for this canonical entity?"
        ],
        readiness.required_next_steps = [
            "Extract automation trigger/action/condition relationships where available",
            "Link time-ordered incidents and timeline events",
            "Review high-impact causal paths"
        ],
        readiness.confidence = CASE WHEN causal_count > 0 THEN 0.76 ELSE 0.64 END,
        readiness.reason = CASE
            WHEN causal_count > 0 THEN
                "Deterministic graph evidence provides semantic, dependency and causal signals, but causal chains still need validation."
            ELSE
                "Deterministic graph evidence provides semantic and dependency signals, but causal evidence is still incomplete."
        END,
        readiness.source = coalesce(readiness.source, "deterministic_causal_backfill"),
        readiness.updated_at = datetime()

    MERGE (scenario)-[:EVALUATES_TARGET]->(canonical)
    RETURN count(DISTINCT canonical) AS count
    """
    return run_count(session, "canonical_simulation_readiness_baseline", query)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive causal and simulation-readiness edges from existing graph evidence."
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
            create_constraints(session)
            results = [
                derive_degradation_causal_dependencies(session),
                derive_problem_failure_causes(session),
                derive_incident_causal_dependencies(session),
                derive_automation_causal_edges(session),
                derive_can_cause_edges(session),
                derive_simulation_readiness_baseline(session),
            ]
    finally:
        driver.close()

    for result in results:
        print(f"{result.name}: {result.count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
