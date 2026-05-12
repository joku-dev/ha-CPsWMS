"""Tests for the semantic benchmark framework."""

import json
from pathlib import Path

from benchmark.config import load_config
from benchmark.metrics_collector import (
    BenchmarkReport,
    GraphStructureMetrics,
    LLMMetrics,
    QueryBenchmarkMetrics,
    SemanticQualityMetrics,
    TechnicalMetrics,
    latency_summary,
)
from benchmark.neo4j_metrics import Neo4jMetricsCollector
from benchmark.query_benchmark import load_query_file
from benchmark.report_generator import ReportGenerator
from benchmark.score_calculator import ScoreCalculator
from benchmark.semantic_metrics import SemanticMetricsCollector


class FakeNeo4jClient:
    """Minimal fake for collector unit tests."""

    def __init__(self, scalars=None, queries=None):
        self.scalars = scalars or {}
        self.queries = queries or {}

    def scalar(self, cypher, key, default=0, **params):
        for marker, value in self.scalars.items():
            if marker in " ".join(cypher.split()):
                return value
        return default

    def query(self, cypher, **params):
        for marker, value in self.queries.items():
            if marker in " ".join(cypher.split()):
                return value
        return []


def test_latency_summary_calculates_percentiles():
    summary = latency_summary([10, 20, 30, 40, 50])

    assert summary["avg_ms"] == 30
    assert summary["p50_ms"] == 30
    assert summary["p95_ms"] == 50
    assert summary["max_ms"] == 50


def test_score_calculator_handles_division_by_zero_and_missing_confidence():
    scores = ScoreCalculator().calculate(
        TechnicalMetrics(total_runtime_seconds=0),
        GraphStructureMetrics(),
        SemanticQualityMetrics(semantic_role_coverage_ratio=1.0, average_semantic_confidence=None),
        QueryBenchmarkMetrics(query_answerability_ratio=0.5),
        LLMMetrics(llm_calls_total=0, llm_tokens_total=0),
    )

    assert scores.semantic_score == 0.20
    assert scores.semantic_value_per_second is None
    assert scores.semantic_value_per_llm_call is None
    assert scores.semantic_value_per_1000_tokens is None
    assert "average_semantic_confidence" in scores.missing_semantic_score_inputs


def test_report_generator_writes_json_and_markdown(tmp_path):
    report = BenchmarkReport(
        benchmark_id="test-benchmark",
        target_name="target",
        repo="repo",
        git_commit=None,
        started_at="2026-05-12T00:00:00Z",
        finished_at="2026-05-12T00:00:01Z",
    )

    written = ReportGenerator(tmp_path).write(report, ["json", "md", "csv"])

    assert written["json"].exists()
    assert written["md"].exists()
    assert written["csv"].exists()
    data = json.loads(written["json"].read_text(encoding="utf-8"))
    assert data["target_name"] == "target"
    assert "Benchmark Report" in written["md"].read_text(encoding="utf-8")


def test_load_query_file_reads_named_queries(tmp_path):
    query_file = tmp_path / "queries.cypher"
    query_file.write_text(
        "-- name: first\nMATCH (n) RETURN n LIMIT 1\n\n-- name: second\nMATCH (m) RETURN m LIMIT 1\n",
        encoding="utf-8",
    )

    queries = load_query_file(query_file)

    assert len(queries) == 2
    assert queries[0][0] == "first"
    assert "MATCH (n)" in queries[0][1]


def test_config_loading_supports_yaml_and_env(tmp_path, monkeypatch):
    config_path = tmp_path / "benchmark_config.yaml"
    config_path.write_text(
        """
benchmark:
  target_name: "example"
neo4j:
  uri: "bolt://example:7687"
  user: "neo4j"
  password_env: "TEST_NEO4J_PASSWORD"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.setenv("TEST_NEO4J_PASSWORD", "secret")

    cfg = load_config(config_path)

    assert cfg.target_name == "example"
    assert cfg.neo4j_uri == "bolt://example:7687"
    assert cfg.neo4j_password == "secret"


def test_empty_graph_handling_for_graph_collector():
    metrics = Neo4jMetricsCollector(FakeNeo4jClient()).collect()

    assert metrics.node_count_total == 0
    assert metrics.canonical_coverage_ratio == 0.0
    assert metrics.raw_to_canonical_resolution_ratio == 0.0


def test_missing_confidence_properties_for_semantic_collector():
    client = FakeNeo4jClient(
        queries={
            "type(r) IN $types AND r.confidence IS NOT NULL": [
                {"average": None, "total": 0, "low": 0, "high": 0}
            ],
            "WITH r, [key IN keys(r)": [{"total": 2, "explainable": 1}],
        }
    )

    metrics = SemanticMetricsCollector(client).collect()

    assert metrics.average_semantic_confidence is None
    assert metrics.low_confidence_ratio == 0.0
    assert metrics.explainability_coverage_ratio == 0.5


def test_missing_canonical_layer_uses_entity_target_count():
    client = FakeNeo4jClient(
        scalars={
            "MATCH (c:CanonicalEntity) RETURN count(c) AS value": 0,
            "MATCH (e:Entity) RETURN count(e) AS value": 10,
            "MATCH (target:Entity)-[r:HAS_SEMANTIC_ROLE]->() RETURN count(DISTINCT target) AS value": 5,
        }
    )

    metrics = SemanticMetricsCollector(client).collect()

    assert metrics.semantic_role_coverage_ratio == 0.5
