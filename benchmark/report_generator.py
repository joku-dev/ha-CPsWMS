"""Benchmark report generation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .metrics_collector import BenchmarkReport, json_safe


class ReportGenerator:
    """Write benchmark reports as JSON, Markdown and CSV."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, report: BenchmarkReport, formats: list[str]) -> dict[str, Path]:
        written: dict[str, Path] = {}
        if "json" in formats:
            written["json"] = self.write_json(report)
        if "md" in formats or "markdown" in formats:
            written["md"] = self.write_markdown(report)
        if "csv" in formats:
            written["csv"] = self.write_csv(report)
        return written

    def write_json(self, report: BenchmarkReport) -> Path:
        path = self.output_dir / f"{report.benchmark_id}_benchmark.json"
        path.write_text(json.dumps(json_safe(report), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_markdown(self, report: BenchmarkReport) -> Path:
        path = self.output_dir / f"{report.benchmark_id}_benchmark.md"
        path.write_text(self.render_markdown(report), encoding="utf-8")
        return path

    def write_csv(self, report: BenchmarkReport) -> Path:
        path = self.output_dir / f"{report.benchmark_id}_benchmark.csv"
        flat = flatten_dict(json_safe(asdict(report)))
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["metric", "value"])
            for key, value in sorted(flat.items()):
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                writer.writerow([key, value])
        return path

    def render_markdown(self, report: BenchmarkReport) -> str:
        graph = report.graph_metrics
        semantic = report.semantic_metrics
        query = report.query_metrics
        llm = report.llm_metrics
        scores = report.scores
        interpretation = build_interpretation(report)

        return "\n".join([
            "# Benchmark Report",
            "",
            "## Summary",
            f"- Target: `{report.target_name}`",
            f"- Benchmark ID: `{report.benchmark_id}`",
            f"- Git commit: `{report.git_commit or 'unknown'}`",
            f"- Semantic score: `{scores.semantic_score:.4f}`",
            f"- World model score: `{scores.world_model_score:.4f}`",
            "",
            "## Environment",
            f"- Repository: `{report.repo}`",
            f"- Started at: `{report.started_at}`",
            f"- Finished at: `{report.finished_at or 'unknown'}`",
            "",
            "## Technical Performance",
            f"- Total runtime seconds: `{report.technical_metrics.total_runtime_seconds}`",
            f"- Query latency p50 ms: `{report.technical_metrics.query_latency_p50_ms}`",
            f"- Query latency p95 ms: `{report.technical_metrics.query_latency_p95_ms}`",
            "",
            "## Graph Structure",
            f"- Nodes: `{graph.node_count_total}`",
            f"- Relationships: `{graph.relationship_count_total}`",
            f"- Entities: `{graph.entity_count}`",
            f"- Raw entities: `{graph.raw_entity_count}`",
            f"- Canonical entities: `{graph.canonical_entity_count}`",
            f"- Canonical coverage: `{graph.canonical_coverage_ratio:.4f}`",
            f"- Raw-to-canonical resolution: `{graph.raw_to_canonical_resolution_ratio:.4f}`",
            "",
            "## Semantic Quality",
            f"- Semantic role coverage: `{semantic.semantic_role_coverage_ratio:.4f}`",
            f"- Capability coverage: `{semantic.capability_coverage_ratio:.4f}`",
            f"- Dependency coverage: `{semantic.dependency_coverage_ratio:.4f}`",
            f"- Causal relation coverage: `{semantic.causal_relation_coverage_ratio:.4f}`",
            f"- Average semantic confidence: `{semantic.average_semantic_confidence}`",
            f"- Explainability coverage: `{semantic.explainability_coverage_ratio:.4f}`",
            "",
            "## Query Benchmark",
            f"- Query success ratio: `{query.query_success_ratio:.4f}`",
            f"- Query answerability ratio: `{query.query_answerability_ratio:.4f}`",
            f"- Query latency p50 ms: `{query.query_latency_p50_ms}`",
            f"- Query latency p95 ms: `{query.query_latency_p95_ms}`",
            "",
            "## LLM Metrics",
            f"- LLM calls total: `{llm.llm_calls_total}`",
            f"- LLM tokens total: `{llm.llm_tokens_total}`",
            f"- Estimated LLM cost: `{llm.estimated_llm_cost}`",
            "",
            "## Scores",
            f"- Semantic value per second: `{scores.semantic_value_per_second}`",
            f"- Semantic value per LLM call: `{scores.semantic_value_per_llm_call}`",
            f"- Semantic value per 1000 tokens: `{scores.semantic_value_per_1000_tokens}`",
            f"- World model value per second: `{scores.world_model_value_per_second}`",
            "",
            "## Warnings",
            *(f"- {warning}" for warning in report.warnings),
            "",
            "## Interpretation",
            interpretation,
            "",
            "## Recommendations",
            build_recommendations(report),
            "",
        ])


def flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dictionaries for simple CSV output."""
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(flatten_dict(value, full_key))
        else:
            flattened[full_key] = value
    return flattened


def build_interpretation(report: BenchmarkReport) -> str:
    graph = report.graph_metrics
    semantic = report.semantic_metrics
    scores = report.scores
    parts = []
    if graph.canonical_entity_count > 0:
        parts.append("The target graph contains a canonical identity layer with measurable raw-to-canonical resolution.")
    else:
        parts.append("No canonical identity layer was detected, so canonical coverage contributes no value to the score.")
    if semantic.semantic_relationship_count > 0:
        parts.append("Semantic relationships are present and increase the graph's world-model value beyond plain entity storage.")
    else:
        parts.append("No semantic relationships were detected; semantic score is therefore limited.")
    if scores.semantic_value_per_second is None:
        parts.append("Runtime-based efficiency could not be calculated because total runtime is unavailable or zero.")
    return " ".join(parts)


def build_recommendations(report: BenchmarkReport) -> str:
    recommendations = []
    if report.semantic_metrics.average_semantic_confidence is None:
        recommendations.append("Persist confidence values on semantic relationships to improve quality tracking.")
    if report.graph_metrics.canonical_coverage_ratio == 0:
        recommendations.append("Verify RawEntity-to-CanonicalEntity linking if canonical benchmarking is expected.")
    if report.query_metrics.query_answerability_ratio < 0.5:
        recommendations.append("Review benchmark query coverage and ensure enrichment jobs have completed before benchmarking.")
    if not recommendations:
        recommendations.append("Use the generated JSON report as a baseline for future regression comparisons.")
    return "\n".join(f"- {item}" for item in recommendations)

