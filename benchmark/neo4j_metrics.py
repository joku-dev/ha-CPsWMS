"""Neo4j graph structure metric collection."""

from __future__ import annotations

import time
from typing import Any

from .metrics_collector import GraphStructureMetrics, json_safe, ratio


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
    "EVALUATES_TARGET",
]


class Neo4jBenchmarkClient:
    """Small benchmark-specific Neo4j client with JSON-safe results."""

    def __init__(self, uri: str, user: str, password: str, database: str | None = None):
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError(
                "The Python package 'neo4j' is required to run benchmarks against Neo4j. "
                "Install the project dependency in the active Python environment."
            ) from exc

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self) -> None:
        self.driver.close()

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        session_kwargs = {"database": self.database} if self.database else {}
        with self.driver.session(**session_kwargs) as session:
            records = session.run(cypher, **params)
            return [json_safe(dict(record)) for record in records]

    def scalar(self, cypher: str, key: str, default: Any = 0, **params: Any) -> Any:
        rows = self.query(cypher, **params)
        if not rows:
            return default
        return rows[0].get(key, default)

    def timed_query(self, cypher: str, **params: Any) -> tuple[list[dict[str, Any]], float]:
        started = time.perf_counter()
        rows = self.query(cypher, **params)
        return rows, (time.perf_counter() - started) * 1000.0


class Neo4jMetricsCollector:
    """Collect graph structure metrics from Neo4j."""

    def __init__(self, client: Neo4jBenchmarkClient):
        self.client = client

    def collect(self) -> GraphStructureMetrics:
        metrics = GraphStructureMetrics()
        metrics.node_count_total = int(self.client.scalar("MATCH (n) RETURN count(n) AS value", "value", 0))
        metrics.relationship_count_total = int(self.client.scalar("MATCH ()-[r]->() RETURN count(r) AS value", "value", 0))
        metrics.node_count_by_label = {
            row["label"]: int(row["count"])
            for row in self.client.query("""
                MATCH (n)
                UNWIND labels(n) AS label
                RETURN label, count(n) AS count
                ORDER BY count DESC
            """)
        }
        metrics.relationship_count_by_type = {
            row["relationship_type"]: int(row["count"])
            for row in self.client.query("""
                MATCH ()-[r]->()
                RETURN type(r) AS relationship_type, count(r) AS count
                ORDER BY count DESC
            """)
        }
        metrics.avg_relationships_per_node = (
            (metrics.relationship_count_total * 2.0) / metrics.node_count_total
            if metrics.node_count_total
            else None
        )
        metrics.orphan_node_count = int(self.client.scalar("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS value", "value", 0))
        metrics.entity_count = int(self.client.scalar("MATCH (e:Entity) RETURN count(e) AS value", "value", 0))
        metrics.raw_entity_count = int(self.client.scalar("MATCH (r:RawEntity) RETURN count(r) AS value", "value", 0))
        metrics.canonical_entity_count = int(self.client.scalar("MATCH (c:CanonicalEntity) RETURN count(c) AS value", "value", 0))
        metrics.resolution_decision_count = int(self.client.scalar("MATCH (d:ResolutionDecision) RETURN count(d) AS value", "value", 0))
        metrics.evidence_count = int(self.client.scalar("MATCH (e:Evidence) RETURN count(e) AS value", "value", 0))
        metrics.canonical_coverage_ratio = self._canonical_coverage(metrics.entity_count)
        metrics.raw_to_canonical_resolution_ratio = ratio(
            self.client.scalar("MATCH (r:RawEntity)-[:RESOLVED_TO]->(:CanonicalEntity) RETURN count(DISTINCT r) AS value", "value", 0),
            metrics.raw_entity_count,
        )
        metrics.duplicate_candidate_count = int(self.client.scalar("""
            MATCH (c:CanonicalEntity)<-[:RESOLVED_TO]-(r:RawEntity)
            WITH c, count(r) AS raw_count
            WHERE raw_count > 1
            RETURN count(c) AS value
        """, "value", 0))
        metrics.semantic_relationship_count = int(self.client.scalar("""
            MATCH ()-[r]->()
            WHERE type(r) IN $types
            RETURN count(r) AS value
        """, "value", 0, types=SEMANTIC_RELATIONSHIP_TYPES))
        return metrics

    def _canonical_coverage(self, entity_count: int) -> float:
        if entity_count == 0:
            return 0.0

        linked_entities = int(self.client.scalar("""
            MATCH (e:Entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)-[:RESOLVED_TO]->(:CanonicalEntity)
            RETURN count(DISTINCT e) AS value
        """, "value", 0))

        if linked_entities == 0:
            linked_entities = int(self.client.scalar("""
                MATCH (raw:RawEntity)-[:RESOLVED_TO]->(:CanonicalEntity)
                WHERE raw.source_entity_id IS NOT NULL
                RETURN count(DISTINCT raw.source_entity_id) AS value
            """, "value", 0))

        return ratio(linked_entities, entity_count)
