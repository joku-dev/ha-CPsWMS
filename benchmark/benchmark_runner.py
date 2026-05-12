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


def generate_performance_evolution(output_dir: Path) -> None:
    """Generate performance evolution summary by comparing all benchmark reports."""
    import json
    from pathlib import Path

    # Find all benchmark JSON files
    benchmark_files = list(output_dir.glob("*_benchmark.json"))
    if len(benchmark_files) < 2:
        return  # Need at least 2 reports for comparison

    # Sort by timestamp (filename contains ISO timestamp)
    benchmark_files.sort(key=lambda p: p.name)

    # Load all reports
    reports = []
    for bf in benchmark_files:
        try:
            data = json.loads(bf.read_text(encoding="utf-8"))
            reports.append((bf, data))
        except Exception:
            continue  # Skip invalid files

    if len(reports) < 2:
        return

    # Generate pairwise comparisons
    comparisons = []
    for i in range(len(reports) - 1):
        baseline_file, baseline_data = reports[i]
        target_file, target_data = reports[i + 1]

        # Run comparison
        try:
            result = subprocess.run([
                "python3", "-m", "benchmark.compare_reports",
                "--baseline", str(baseline_file),
                "--target", str(target_file)
            ], capture_output=True, text=True, cwd=Path.cwd())

            if result.returncode == 0:
                comparison_data = json.loads(result.stdout)
                comparison_file = output_dir / f"comparison_{baseline_file.name.replace('_benchmark.json', '')}_to_{target_file.name.replace('_benchmark.json', '')}.json"
                comparison_file.write_text(json.dumps(comparison_data, indent=2, ensure_ascii=False))
                comparisons.append((baseline_file, target_file, comparison_data))
                print(f"Generated comparison: {comparison_file.name}")
        except Exception as e:
            print(f"Warning: Failed to compare {baseline_file.name} vs {target_file.name}: {e}")

    # Generate markdown summary
    if comparisons:
        summary_file = output_dir / "performance_evolution_summary.md"
        summary_content = generate_evolution_summary(reports, comparisons)
        summary_file.write_text(summary_content)
        print(f"Updated performance evolution summary: {summary_file.name}")


def generate_evolution_summary(reports: list, comparisons: list) -> str:
    """Generate markdown summary of performance evolution."""
    lines = ["# Benchmark Performance Evolution Summary\n"]

    # List all reports
    lines.append("## Available benchmark reports")
    for file_path, _ in reports:
        lines.append(f"- `{file_path.name}`")
    lines.append("")

    # List comparison files
    lines.append("## Generated comparison files")
    for baseline_file, target_file, _ in comparisons:
        comp_name = f"comparison_{baseline_file.name.replace('_benchmark.json', '')}_to_{target_file.name.replace('_benchmark.json', '')}.json"
        lines.append(f"- `{comp_name}`")
    lines.append("")

    # Summary of results
    lines.append("## Summary of results\n")
    for baseline_file, target_file, comparison_data in comparisons:
        baseline_time = baseline_file.name.split('_')[0]
        target_time = target_file.name.split('_')[0]
        lines.append(f"### {baseline_time} → {target_time}")

        for metric, data in comparison_data.items():
            if data.get("delta_percent") is not None:
                delta_pct = data["delta_percent"]
                if abs(delta_pct) > 0.1:  # Only show significant changes
                    direction = "+" if delta_pct > 0 else ""
                    lines.append(f"- `{metric}` changed by {direction}{delta_pct:.1f}%")
        lines.append("")

    lines.append("## Notes")
    lines.append("- This summary is automatically generated after each benchmark run.")
    lines.append("- Comparisons show significant changes (>0.1% absolute).")
    lines.append("- All metrics are calculated from the JSON benchmark reports.")

    return "\n".join(lines)


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

        # Generate performance evolution summary
        try:
            generate_performance_evolution(cfg.output_dir)
        except Exception as exc:
            print(f"Warning: Failed to generate performance evolution: {exc}")

        return 1 if report.errors else 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
