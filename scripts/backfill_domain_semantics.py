#!/usr/bin/env python3
"""Derive conservative semantic defaults from Home Assistant domains."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from neo4j import GraphDatabase


DOMAIN_SEMANTICS = [
    {"domain": "sensor", "role": "sensor", "category": "measurement", "capability": "state_monitoring"},
    {"domain": "binary_sensor", "role": "sensor", "category": "status_monitoring", "capability": "binary_state_monitoring"},
    {"domain": "switch", "role": "actuator", "category": "control", "capability": "binary_control"},
    {"domain": "light", "role": "actuator", "category": "lighting", "capability": "lighting_control"},
    {"domain": "cover", "role": "actuator", "category": "shading", "capability": "cover_control"},
    {"domain": "media_player", "role": "actuator", "category": "media", "capability": "media_control"},
    {"domain": "climate", "role": "actuator", "category": "climate", "capability": "climate_control"},
    {"domain": "weather", "role": "sensor", "category": "weather", "capability": "weather_monitoring"},
    {"domain": "calendar", "role": "schedule_source", "category": "scheduling", "capability": "schedule_monitoring"},
    {"domain": "device_tracker", "role": "presence_source", "category": "presence", "capability": "presence_tracking"},
    {"domain": "person", "role": "presence_subject", "category": "presence", "capability": "occupancy_context"},
    {"domain": "zone", "role": "location_context", "category": "presence", "capability": "location_context"},
    {"domain": "automation", "role": "automation", "category": "automation", "capability": "automation_execution"},
    {"domain": "scene", "role": "scene", "category": "automation", "capability": "scene_activation"},
    {"domain": "script", "role": "script", "category": "automation", "capability": "script_execution"},
    {"domain": "button", "role": "command", "category": "control", "capability": "manual_command"},
    {"domain": "number", "role": "configuration", "category": "control", "capability": "numeric_configuration"},
    {"domain": "select", "role": "configuration", "category": "control", "capability": "option_configuration"},
    {"domain": "text", "role": "configuration", "category": "control", "capability": "text_configuration"},
    {"domain": "input_boolean", "role": "helper", "category": "automation", "capability": "boolean_helper"},
    {"domain": "input_number", "role": "helper", "category": "automation", "capability": "numeric_helper"},
    {"domain": "timer", "role": "timer", "category": "automation", "capability": "timer_control"},
    {"domain": "camera", "role": "sensor", "category": "media", "capability": "camera_monitoring"},
    {"domain": "event", "role": "event_source", "category": "eventing", "capability": "event_reporting"},
    {"domain": "update", "role": "maintenance_signal", "category": "maintenance", "capability": "update_monitoring"},
    {"domain": "lock", "role": "actuator", "category": "security", "capability": "lock_control"},
    {"domain": "notify", "role": "notification_channel", "category": "notification", "capability": "notification_delivery"},
    {"domain": "tts", "role": "speech_service", "category": "voice", "capability": "text_to_speech"},
    {"domain": "stt", "role": "speech_service", "category": "voice", "capability": "speech_to_text"},
    {"domain": "group", "role": "group", "category": "aggregation", "capability": "entity_grouping"},
]


@dataclass(frozen=True)
class DomainBackfillResult:
    name: str
    count: int


def run_count(session, name: str, query: str) -> DomainBackfillResult:
    record = session.run(query, mappings=DOMAIN_SEMANTICS).single()
    return DomainBackfillResult(name=name, count=int(record["count"] or 0))


def backfill_roles(session) -> DomainBackfillResult:
    query = """
    UNWIND $mappings AS mapping
    MATCH (e:Entity {domain: mapping.domain})
    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    WITH DISTINCT e, canonical, mapping
    WHERE canonical IS NOT NULL
    MERGE (role:SemanticRole {name: mapping.role})
    MERGE (canonical)-[canonical_rel:HAS_SEMANTIC_ROLE]->(role)
    SET canonical_rel.confidence = coalesce(canonical_rel.confidence, 0.82),
        canonical_rel.reason = coalesce(canonical_rel.reason, "Derived from Home Assistant domain."),
        canonical_rel.source = coalesce(canonical_rel.source, "domain_semantics_backfill"),
        canonical_rel.updated_at = datetime()
    MERGE (e)-[entity_rel:HAS_SEMANTIC_ROLE]->(role)
    SET entity_rel.confidence = coalesce(entity_rel.confidence, 0.82),
        entity_rel.reason = coalesce(entity_rel.reason, "Derived from Home Assistant domain."),
        entity_rel.source = coalesce(entity_rel.source, "domain_semantics_backfill"),
        entity_rel.updated_at = datetime()
    RETURN count(DISTINCT canonical) AS count
    """
    return run_count(session, "domain_semantic_roles", query)


def backfill_categories(session) -> DomainBackfillResult:
    query = """
    UNWIND $mappings AS mapping
    MATCH (e:Entity {domain: mapping.domain})
    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    WITH DISTINCT e, canonical, mapping
    WHERE canonical IS NOT NULL
    MERGE (category:SemanticCategory {name: mapping.category})
    MERGE (canonical)-[canonical_rel:HAS_SEMANTIC_CATEGORY]->(category)
    SET canonical_rel.confidence = coalesce(canonical_rel.confidence, 0.82),
        canonical_rel.reason = coalesce(canonical_rel.reason, "Derived from Home Assistant domain."),
        canonical_rel.source = coalesce(canonical_rel.source, "domain_semantics_backfill"),
        canonical_rel.updated_at = datetime()
    MERGE (e)-[entity_rel:HAS_SEMANTIC_CATEGORY]->(category)
    SET entity_rel.confidence = coalesce(entity_rel.confidence, 0.82),
        entity_rel.reason = coalesce(entity_rel.reason, "Derived from Home Assistant domain."),
        entity_rel.source = coalesce(entity_rel.source, "domain_semantics_backfill"),
        entity_rel.updated_at = datetime()
    RETURN count(DISTINCT canonical) AS count
    """
    return run_count(session, "domain_semantic_categories", query)


def backfill_capabilities(session) -> DomainBackfillResult:
    query = """
    UNWIND $mappings AS mapping
    MATCH (e:Entity {domain: mapping.domain})
    OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(canonical:CanonicalEntity)
    WITH DISTINCT e, canonical, mapping
    WHERE canonical IS NOT NULL
    MERGE (capability:Capability {name: mapping.capability})
    MERGE (canonical)-[canonical_rel:PROVIDES_CAPABILITY]->(capability)
    SET canonical_rel.confidence = coalesce(canonical_rel.confidence, 0.78),
        canonical_rel.reason = coalesce(canonical_rel.reason, "Conservative capability derived from Home Assistant domain."),
        canonical_rel.source = coalesce(canonical_rel.source, "domain_semantics_backfill"),
        canonical_rel.updated_at = datetime()
    MERGE (e)-[entity_rel:PROVIDES_CAPABILITY]->(capability)
    SET entity_rel.confidence = coalesce(entity_rel.confidence, 0.78),
        entity_rel.reason = coalesce(entity_rel.reason, "Conservative capability derived from Home Assistant domain."),
        entity_rel.source = coalesce(entity_rel.source, "domain_semantics_backfill"),
        entity_rel.updated_at = datetime()
    RETURN count(DISTINCT canonical) AS count
    """
    return run_count(session, "domain_capabilities", query)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill conservative semantic defaults from Home Assistant domains."
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
                backfill_roles(session),
                backfill_categories(session),
                backfill_capabilities(session),
            ]
    finally:
        driver.close()

    for result in results:
        print(f"{result.name}: {result.count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
