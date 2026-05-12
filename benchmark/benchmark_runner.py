"""CLI entry point for semantic benchmark runs."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from .config import load_config
from .llm_metrics import LLMMetricsCollector
from .metrics_collector import BenchmarkReport, TechnicalMetrics, latency_summary, now_iso
from .neo4j_metrics import Neo4jBenchmarkClient, Neo4jMetricsCollector
from .query_benchmark import QueryBenchmarkRunner
from .report_generator import ReportGenerator
from .score_calculator import ScoreCalculator
from .semantic_metrics import SemanticMetricsCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run semantic world-model benchmark metrics.")
    parser.add_argument("--target", help="Benchmark target name")
    parser.add_argument("--neo4j-uri", help="Neo4j Bolt URI")
    parser.add_argument("--neo4j-user", help="Neo4j user")
    parser.add_argument("--neo4j-password", help="Neo4j password")
    parser.add_argument("--database", help="Neo4j database")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--config", help="Benchmark YAML config path")
    parser.add_argument("--run-query-benchmark", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--run-llm-metrics", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--format", default=None, help="Comma-separated output formats: json,md,csv")
    parser.add_argument("--sync-duration-seconds", type=float, default=None)
    parser.add_argument("--enrichment-duration-seconds", type=float, default=None)
    parser.add_argument("--total-runtime-seconds", type=float, default=None)
    return parser


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config, args)

    if not cfg.neo4j_password:
        parser.error("Neo4j password is required via --neo4j-password, NEO4J_PASSWORD or benchmark_config.yaml password_env")

    started_at = now_iso()
    benchmark_id = started_at.replace(":", "-").replace("+00:00", "Z")
    start = time.perf_counter()
    report = BenchmarkReport(
        benchmark_id=benchmark_id,
        target_name=cfg.target_name,
        repo=Path.cwd().name,
        git_commit=git_commit(),
        started_at=started_at,
    )

    try:
        client = Neo4jBenchmarkClient(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password, cfg.neo4j_database)
    except Exception as exc:
        print(f"Benchmark setup failed: {exc}")
        return 1
    try:
        try:
            graph_started = time.perf_counter()
            report.graph_metrics = Neo4jMetricsCollector(client).collect()
            graph_duration = time.perf_counter() - graph_started
            report.technical_metrics.neo4j_read_duration_seconds = graph_duration
        except Exception as exc:
            report.errors.append(f"Graph metrics collection failed: {exc}")

        try:
            report.semantic_metrics = SemanticMetricsCollector(
                client,
                cfg.low_confidence_threshold,
                cfg.high_confidence_threshold,
            ).collect()
        except Exception as exc:
            report.errors.append(f"Semantic metrics collection failed: {exc}")

        if cfg.run_query_benchmark:
            try:
                report.query_metrics = QueryBenchmarkRunner(client).run()
            except Exception as exc:
                report.errors.append(f"Query benchmark failed: {exc}")

        if cfg.collect_llm_metrics:
            llm_metrics, warnings = LLMMetricsCollector().collect()
            report.llm_metrics = llm_metrics
            report.warnings.extend(warnings)

        query_latencies = [item.duration_ms for item in report.query_metrics.results if item.success]
        summary = latency_summary(query_latencies)
        report.technical_metrics = TechnicalMetrics(
            sync_duration_seconds=args.sync_duration_seconds,
            enrichment_duration_seconds=args.enrichment_duration_seconds,
            total_runtime_seconds=args.total_runtime_seconds or (time.perf_counter() - start),
            entities_processed_total=report.graph_metrics.entity_count,
            entities_per_second=None,
            neo4j_read_duration_seconds=report.technical_metrics.neo4j_read_duration_seconds,
            query_latency_avg_ms=summary["avg_ms"],
            query_latency_p50_ms=summary["p50_ms"],
            query_latency_p95_ms=summary["p95_ms"],
            query_latency_max_ms=summary["max_ms"],
            query_latencies_ms=query_latencies,
        )
        if report.technical_metrics.total_runtime_seconds:
            report.technical_metrics.entities_per_second = (
                report.technical_metrics.entities_processed_total / report.technical_metrics.total_runtime_seconds
            )

        if report.graph_metrics.node_count_total == 0:
            report.warnings.append("Neo4j graph appears to be empty.")
        if report.graph_metrics.canonical_entity_count == 0:
            report.warnings.append("CanonicalEntity layer was not detected.")
        if report.semantic_metrics.confidence_relation_count == 0:
            report.warnings.append("No confidence properties were found on semantic relationships.")

        report.scores = ScoreCalculator(cfg.semantic_score_weights).calculate(
            report.technical_metrics,
            report.graph_metrics,
            report.semantic_metrics,
            report.query_metrics,
            report.llm_metrics,
        )
        report.finished_at = now_iso()
        written = ReportGenerator(cfg.output_dir).write(report, cfg.formats)
        for output_format, path in written.items():
            print(f"Wrote {output_format}: {path}")
        return 1 if report.errors else 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
