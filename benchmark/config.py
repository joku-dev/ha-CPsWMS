"""Configuration loading for benchmark runs."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML is absent
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).with_name("benchmark_config.yaml")


@dataclass
class BenchmarkConfig:
    target_name: str = "ha-CPsWMS"
    low_confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.8
    output_dir: Path = Path("benchmark/reports")
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str | None = None
    run_query_benchmark: bool = True
    query_timeout_seconds: int = 30
    collect_llm_metrics: bool = True
    cost_estimation_enabled: bool = False
    default_cost_per_1000_tokens: float | None = None
    formats: list[str] = field(default_factory=lambda: ["json", "md", "csv"])
    semantic_score_weights: dict[str, float] = field(default_factory=lambda: {
        "semantic_role_coverage_ratio": 0.20,
        "semantic_category_coverage_ratio": 0.15,
        "capability_coverage_ratio": 0.15,
        "dependency_coverage_ratio": 0.15,
        "causal_relation_coverage_ratio": 0.10,
        "simulation_readiness_coverage_ratio": 0.10,
        "average_semantic_confidence": 0.10,
        "explainability_coverage_ratio": 0.05,
    })


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE lines into the environment if python-dotenv is absent."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_config(path: str | Path | None = None, args: argparse.Namespace | None = None) -> BenchmarkConfig:
    """Load benchmark configuration from YAML, environment variables and CLI args."""
    _load_dotenv()
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = _read_yaml(config_path)

    benchmark = raw.get("benchmark", {})
    neo4j = raw.get("neo4j", {})
    queries = raw.get("queries", {})
    llm = raw.get("llm", {})
    scores = raw.get("scores", {})

    password_env = neo4j.get("password_env", "NEO4J_PASSWORD")

    cfg = BenchmarkConfig(
        target_name=benchmark.get("target_name", "ha-CPsWMS"),
        low_confidence_threshold=float(benchmark.get("low_confidence_threshold", 0.5)),
        high_confidence_threshold=float(benchmark.get("high_confidence_threshold", 0.8)),
        output_dir=Path(benchmark.get("output_dir", "benchmark/reports")),
        neo4j_uri=os.getenv("NEO4J_URI", neo4j.get("uri", "bolt://localhost:7687")),
        neo4j_user=os.getenv("NEO4J_USER", neo4j.get("user", "neo4j")),
        neo4j_password=os.getenv(password_env, os.getenv("NEO4J_PASSWORD")),
        neo4j_database=os.getenv("NEO4J_DATABASE", neo4j.get("database")),
        run_query_benchmark=bool(queries.get("run_query_benchmark", True)),
        query_timeout_seconds=int(queries.get("query_timeout_seconds", 30)),
        collect_llm_metrics=bool(llm.get("collect_llm_metrics", True)),
        cost_estimation_enabled=bool(llm.get("cost_estimation_enabled", False)),
        default_cost_per_1000_tokens=llm.get("default_cost_per_1000_tokens"),
        semantic_score_weights=scores.get("semantic_score_weights") or BenchmarkConfig().semantic_score_weights,
    )

    if args is not None:
        if getattr(args, "target", None):
            cfg.target_name = args.target
        if getattr(args, "neo4j_uri", None):
            cfg.neo4j_uri = args.neo4j_uri
        if getattr(args, "neo4j_user", None):
            cfg.neo4j_user = args.neo4j_user
        if getattr(args, "neo4j_password", None):
            cfg.neo4j_password = args.neo4j_password
        if getattr(args, "database", None):
            cfg.neo4j_database = args.database
        if getattr(args, "output", None):
            cfg.output_dir = Path(args.output)
        if getattr(args, "run_query_benchmark", None) is not None:
            cfg.run_query_benchmark = args.run_query_benchmark
        if getattr(args, "run_llm_metrics", None) is not None:
            cfg.collect_llm_metrics = args.run_llm_metrics
        if getattr(args, "format", None):
            cfg.formats = [item.strip() for item in args.format.split(",") if item.strip()]

    return cfg

