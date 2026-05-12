"""Cypher query benchmark runner."""

from __future__ import annotations

import time
from pathlib import Path

from .metrics_collector import QueryBenchmarkMetrics, QueryResultMetric, latency_summary, ratio
from .neo4j_metrics import Neo4jBenchmarkClient


QUERIES_DIR = Path(__file__).with_name("queries")


def load_query_file(path: Path) -> list[tuple[str, str]]:
    """Load named Cypher queries separated by comments like `-- name: query_name`."""
    if not path.exists():
        return []

    queries: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current_name and current_lines:
                queries.append((current_name, "\n".join(current_lines).strip()))
            current_name = stripped.split(":", 1)[1].strip()
            current_lines = []
            continue
        if stripped.startswith("--") and current_name is None:
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name and current_lines:
        queries.append((current_name, "\n".join(current_lines).strip()))

    return [(name, cypher) for name, cypher in queries if cypher]


class QueryBenchmarkRunner:
    """Run benchmark query groups and collect latency/result metrics."""

    def __init__(self, client: Neo4jBenchmarkClient, queries_dir: Path = QUERIES_DIR):
        self.client = client
        self.queries_dir = queries_dir

    def run(self) -> QueryBenchmarkMetrics:
        results: list[QueryResultMetric] = []
        for path in sorted(self.queries_dir.glob("*.cypher")):
            query_group = path.stem.replace("_queries", "")
            for query_name, cypher in load_query_file(path):
                results.append(self._run_query(query_group, query_name, cypher))

        successful = [item for item in results if item.success]
        answerable = [item for item in successful if item.result_count > 0]
        latencies = [item.duration_ms for item in successful]
        summary = latency_summary(latencies)

        return QueryBenchmarkMetrics(
            results=results,
            query_success_ratio=ratio(len(successful), len(results)),
            query_answerability_ratio=ratio(len(answerable), len(results)),
            query_latency_p50_ms=summary["p50_ms"],
            query_latency_p95_ms=summary["p95_ms"],
        )

    def _run_query(self, query_group: str, query_name: str, cypher: str) -> QueryResultMetric:
        started = time.perf_counter()
        try:
            rows = self.client.query(cypher)
            duration_ms = (time.perf_counter() - started) * 1000.0
            return QueryResultMetric(
                query_name=query_name,
                query_group=query_group,
                cypher=cypher,
                duration_ms=duration_ms,
                result_count=len(rows),
                success=True,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000.0
            return QueryResultMetric(
                query_name=query_name,
                query_group=query_group,
                cypher=cypher,
                duration_ms=duration_ms,
                result_count=0,
                success=False,
                error_message=str(exc),
            )

