"""Intake notification failures must not rewrite completed producer results."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _step(workflow: str, job: str, name: str) -> dict:
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    return next(step for step in document["jobs"][job]["steps"] if step.get("name") == name)


def test_governance_dispatches_are_non_blocking_transport_steps():
    architecture = _step(
        "architecture-governance.yml", "architecture-governance", "Notify governance repository"
    )
    devsecops = _step(
        "devsecops-baseline.yml", "notify-governance-repository", "Notify governance repository"
    )
    assert architecture["continue-on-error"] is True
    assert devsecops["continue-on-error"] is True


def test_typed_evidence_dispatch_is_non_blocking_and_handles_missing_token():
    step = _step(
        "typed-evidence-intake.yml", "notify", "Request central full-archive Trust verification"
    )
    assert step["continue-on-error"] is True
    assert 'if [ -z "${GH_TOKEN}" ]' in step["run"]
    assert "typed evidence intake was not triggered" in step["run"]
