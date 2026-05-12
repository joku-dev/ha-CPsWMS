"""Benchmark score calculation."""

from __future__ import annotations

from .metrics_collector import (
    GraphStructureMetrics,
    LLMMetrics,
    QueryBenchmarkMetrics,
    ScoreMetrics,
    SemanticQualityMetrics,
    TechnicalMetrics,
    safe_divide,
)


DEFAULT_SEMANTIC_WEIGHTS = {
    "semantic_role_coverage_ratio": 0.20,
    "semantic_category_coverage_ratio": 0.15,
    "capability_coverage_ratio": 0.15,
    "dependency_coverage_ratio": 0.15,
    "causal_relation_coverage_ratio": 0.10,
    "simulation_readiness_coverage_ratio": 0.10,
    "average_semantic_confidence": 0.10,
    "explainability_coverage_ratio": 0.05,
}


class ScoreCalculator:
    """Calculate semantic, world-model and value-efficiency scores."""

    def __init__(self, semantic_weights: dict[str, float] | None = None):
        self.semantic_weights = semantic_weights or DEFAULT_SEMANTIC_WEIGHTS

    def calculate(
        self,
        technical: TechnicalMetrics,
        graph: GraphStructureMetrics,
        semantic: SemanticQualityMetrics,
        query: QueryBenchmarkMetrics,
        llm: LLMMetrics,
    ) -> ScoreMetrics:
        missing_inputs: list[str] = []
        semantic_score = 0.0

        for metric_name, weight in self.semantic_weights.items():
            value = getattr(semantic, metric_name, None)
            if value is None:
                missing_inputs.append(metric_name)
                value = 0.0
            semantic_score += weight * float(value)

        world_model_score = (
            0.25 * graph.canonical_coverage_ratio
            + 0.20 * graph.raw_to_canonical_resolution_ratio
            + 0.20 * semantic_score
            + 0.20 * query.query_answerability_ratio
            + 0.15 * semantic.explainability_coverage_ratio
        )

        return ScoreMetrics(
            semantic_score=semantic_score,
            world_model_score=world_model_score,
            semantic_value_per_second=safe_divide(semantic_score, technical.total_runtime_seconds),
            semantic_value_per_llm_call=safe_divide(semantic_score, llm.llm_calls_total),
            semantic_value_per_1000_tokens=(
                safe_divide(semantic_score, (llm.llm_tokens_total / 1000.0))
                if llm.llm_tokens_total
                else None
            ),
            world_model_value_per_second=safe_divide(world_model_score, technical.total_runtime_seconds),
            missing_semantic_score_inputs=missing_inputs,
        )

