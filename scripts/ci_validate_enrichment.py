#!/usr/bin/env python3
"""Static CI checks for semantic enrichment wiring."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_DIR = ROOT / "semantic-enrichment"
ENRICHERS_DIR = SEMANTIC_DIR / "enrichers"
PROMPTS_DIR = SEMANTIC_DIR / "prompts"
SCHEMAS_DIR = SEMANTIC_DIR / "schemas"
ORCHESTRATOR = SEMANTIC_DIR / "semantic_enrich.py"

LEGACY_ROOT_ENRICHERS = [
    "semantic_roles.py",
    "automation_intent.py",
    "fault_analysis.py",
    "anomaly_detection.py",
    "room_inference.py",
    "dependency_reasoning.py",
    "failure_impact.py",
    "semantic_descriptions.py",
    "recommended_actions.py",
    "temporal_event_model.py",
    "base.py",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def parse_enricher(path: Path) -> tuple[str, str, str, str] | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    class_node = None

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseEnricher":
                    class_node = node
                    break
                if isinstance(base, ast.Attribute) and base.attr == "BaseEnricher":
                    class_node = node
                    break
        if class_node:
            break

    if class_node is None:
        fail(f"No BaseEnricher subclass found in {path}")
        return None

    attrs: dict[str, str] = {}
    for stmt in class_node.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        key = stmt.targets[0].id
        if key not in {"prompt_file", "schema_file", "response_key"}:
            continue
        if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            attrs[key] = stmt.value.value

    missing = [k for k in ("prompt_file", "schema_file", "response_key") if k not in attrs]
    if missing:
        fail(f"Missing class attrs {missing} in {path}")
        return None

    return class_node.name, attrs["prompt_file"], attrs["schema_file"], attrs["response_key"]


def parse_orchestrator_classes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            if node.targets[0].id != "enrichers":
                continue
            if not isinstance(node.value, ast.List):
                continue
            for elt in node.value.elts:
                if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                    found.append(elt.func.id)
    return found


def main() -> int:
    ok = True

    for required in [SEMANTIC_DIR, ENRICHERS_DIR, PROMPTS_DIR, SCHEMAS_DIR, ORCHESTRATOR]:
        if not required.exists():
            fail(f"Required path missing: {required}")
            ok = False

    for legacy in LEGACY_ROOT_ENRICHERS:
        if (SEMANTIC_DIR / legacy).exists():
            fail(f"Legacy duplicate file still exists: semantic-enrichment/{legacy}")
            ok = False

    enricher_files = sorted(
        p
        for p in ENRICHERS_DIR.glob("*.py")
        if p.name not in {"__init__.py", "base.py"}
    )

    if not enricher_files:
        fail("No enricher modules found in semantic-enrichment/enrichers")
        return 1

    discovered_classes: set[str] = set()

    for module in enricher_files:
        if module.stat().st_size == 0:
            fail(f"Empty enricher module: {module}")
            ok = False
            continue

        parsed = parse_enricher(module)
        if parsed is None:
            ok = False
            continue

        class_name, prompt_file, schema_file, response_key = parsed
        discovered_classes.add(class_name)

        prompt_path = PROMPTS_DIR / prompt_file
        schema_path = SCHEMAS_DIR / schema_file

        if not prompt_path.exists():
            fail(f"Missing prompt file referenced by {module.name}: {prompt_file}")
            ok = False
        elif not prompt_path.read_text(encoding="utf-8").strip():
            fail(f"Prompt file is empty: {prompt_path}")
            ok = False

        if not schema_path.exists():
            fail(f"Missing schema file referenced by {module.name}: {schema_file}")
            ok = False
            continue

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"Invalid JSON in schema {schema_path}: {exc}")
            ok = False
            continue

        props = schema.get("properties", {})
        required_keys = schema.get("required", [])

        if response_key not in props:
            fail(f"Schema {schema_file} missing properties['{response_key}'] for {module.name}")
            ok = False

        if response_key not in required_keys:
            fail(f"Schema {schema_file} missing required '{response_key}' for {module.name}")
            ok = False

    orchestrator_classes = parse_orchestrator_classes(ORCHESTRATOR)
    if not orchestrator_classes:
        fail("No enricher class list found in semantic_enrich.py")
        ok = False

    orchestrator_set = set(orchestrator_classes)
    if orchestrator_set != discovered_classes:
        fail(
            "Orchestrator class set does not match enricher modules. "
            f"orchestrator={sorted(orchestrator_set)} discovered={sorted(discovered_classes)}"
        )
        ok = False

    if len(orchestrator_classes) != len(orchestrator_set):
        fail("Duplicate enricher class entries found in orchestrator list")
        ok = False

    if not ok:
        return 1

    print("CI enrichment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
