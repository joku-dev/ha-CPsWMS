"""Shared benchmark metric models and helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any


def now_iso() -> str:
    """Return a timezone-aware ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    """Return numerator / denominator, or None when the denominator is unusable."""
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def ratio(numerator: float | int | None, denominator: float | int | None) -> float:
    """Return a bounded ratio, defaulting to 0 for empty denominators."""
    value = safe_divide(numerator, denominator)
    if value is None:
        return 0.0
    return max(0.0, min(1.0, value))


def percentile(values: list[float], percentile_value: float) -> float | None:
    """Calculate a nearest-rank percentile for latency summaries."""
    if not values:
        return None

    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]

    index = round((percentile_value / 100.0) * (len(ordered) - 1))
    return ordered[index]


def latency_summary(values: list[float]) -> dict[str, float | None]:
    """Return avg/p50/p95/max for millisecond latency values."""
    if not values:
        return {"avg_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}

    return {
        "avg_ms": mean(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "max_ms": max(values),
    }


def json_safe(value: Any) -> Any:
    """Convert dataclasses and native client values into JSON-safe objects."""
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "to_native"):
        return json_safe(value.to_native())
    return value


@dataclass
class TechnicalMetrics:
    sync_duration_seconds: float | None = None
    enrichment_duration_seconds: float | None = None
    total_runtime_seconds: float | None = None
    entities_processed_total: int = 0
    entities_per_second: float | None = None
    neo4j_write_duration_seconds: float | None = None
    neo4j_read_duration_seconds: float | None = None
    query_latency_avg_ms: float | None = None
    query_latency_p50_ms: float | None = None
    query_latency_p95_ms: float | None = None
    query_latency_max_ms: float | None = None
    query_latencies_ms: list[float] = field(default_factory=list)


@dataclass
class GraphStructureMetrics:
    node_count_total: int = 0
    relationship_count_total: int = 0
    node_count_by_label: dict[str, int] = field(default_factory=dict)
    relationship_count_by_type: dict[str, int] = field(default_factory=dict)
    avg_relationships_per_node: float | None = None
    orphan_node_count: int = 0
    entity_count: int = 0
    raw_entity_count: int = 0
    canonical_entity_count: int = 0
    resolution_decision_count: int = 0
    evidence_count: int = 0
    canonical_coverage_ratio: float = 0.0
    raw_to_canonical_resolution_ratio: float = 0.0
    duplicate_candidate_count: int = 0
    semantic_relationship_count: int = 0


@dataclass
class SemanticQualityMetrics:
    semantic_role_coverage_ratio: float = 0.0
    semantic_category_coverage_ratio: float = 0.0
    criticality_coverage_ratio: float = 0.0
    capability_coverage_ratio: float = 0.0
    dependency_coverage_ratio: float = 0.0
    causal_relation_coverage_ratio: float = 0.0
    recommended_action_coverage_ratio: float = 0.0
    simulation_readiness_coverage_ratio: float = 0.0
    average_semantic_confidence: float | None = None
    low_confidence_ratio: float = 0.0
    high_confidence_ratio: float = 0.0
    explainability_coverage_ratio: float = 0.0
    conflicting_semantics_count: int = 0
    confidence_relation_count: int = 0
    explainable_relation_count: int = 0
    semantic_relationship_count: int = 0


@dataclass
class QueryResultMetric:
    query_name: str
    query_group: str
    cypher: str
    duration_ms: float
    result_count: int
    success: bool
    error_message: str | None = None


@dataclass
class QueryBenchmarkMetrics:
    results: list[QueryResultMetric] = field(default_factory=list)
    query_success_ratio: float = 0.0
    query_answerability_ratio: float = 0.0
    query_latency_p50_ms: float | None = None
    query_latency_p95_ms: float | None = None


@dataclass
class LLMMetrics:
    llm_calls_total: int = 0
    llm_calls_by_enricher: dict[str, int] = field(default_factory=dict)
    llm_errors_total: int = 0
    llm_retry_count: int = 0
    llm_prompt_tokens_total: int | None = None
    llm_completion_tokens_total: int | None = None
    llm_tokens_total: int | None = None
    estimated_llm_cost: float | None = None
    average_llm_latency_ms: float | None = None
    llm_latency_p95_ms: float | None = None


@dataclass
class ScoreMetrics:
    semantic_score: float = 0.0
    world_model_score: float = 0.0
    semantic_value_per_second: float | None = None
    semantic_value_per_llm_call: float | None = None
    semantic_value_per_1000_tokens: float | None = None
    world_model_value_per_second: float | None = None
    missing_semantic_score_inputs: list[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    benchmark_id: str
    target_name: str
    repo: str
    git_commit: str | None
    started_at: str
    finished_at: str | None = None
    technical_metrics: TechnicalMetrics = field(default_factory=TechnicalMetrics)
    graph_metrics: GraphStructureMetrics = field(default_factory=GraphStructureMetrics)
    semantic_metrics: SemanticQualityMetrics = field(default_factory=SemanticQualityMetrics)
    query_metrics: QueryBenchmarkMetrics = field(default_factory=QueryBenchmarkMetrics)
    llm_metrics: LLMMetrics = field(default_factory=LLMMetrics)
    scores: ScoreMetrics = field(default_factory=ScoreMetrics)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

