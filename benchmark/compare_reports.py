"""Compare two benchmark JSON reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _get(data: dict, dotted: str):
    value = data
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _delta(baseline, target):
    if baseline in (None, 0) or target is None:
        return {"delta": None, "delta_percent": None}
    delta = target - baseline
    return {"delta": delta, "delta_percent": (delta / baseline) * 100.0}


def compare(baseline: dict, target: dict) -> dict:
    fields = {
        "runtime": "technical_metrics.total_runtime_seconds",
        "semantic_score": "scores.semantic_score",
        "world_model_score": "scores.world_model_score",
        "query_answerability": "query_metrics.query_answerability_ratio",
        "canonical_coverage": "graph_metrics.canonical_coverage_ratio",
        "llm_cost": "llm_metrics.estimated_llm_cost",
        "semantic_value_per_second": "scores.semantic_value_per_second",
    }
    result = {}
    for name, path in fields.items():
        base_value = _get(baseline, path)
        target_value = _get(target, path)
        result[name] = {
            "baseline": base_value,
            "target": target_value,
            **_delta(base_value, target_value),
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two benchmark JSON reports.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args(argv)

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    target = json.loads(Path(args.target).read_text(encoding="utf-8"))
    print(json.dumps(compare(baseline, target), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

