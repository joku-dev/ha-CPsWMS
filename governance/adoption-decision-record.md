# Adoption Decision Record

## Decision Metadata

| Field | Value |
| --- | --- |
| Application repository | `joku-dev/ha-CPsWMS` |
| Application owner | To be confirmed |
| Pipeline owner | To be confirmed |
| Security reviewer | To be confirmed |
| Architecture reviewer | To be confirmed |
| Governance reviewer | To be confirmed |
| Decision date | 2026-07-15 |
| Evaluated framework release or commit | `l1-baseline-v1.1.3`, `architecture-baseline-l1-v0.1.0` |
| Evaluated workflow runs | DevSecOps Baseline `29407237525`, Architecture Runtime Governance `29407236968`, DevSecOps Governance `29407237030`, CI `29407236974` |

## Decision

- [x] Continue `report-only`
- [ ] Start controlled blocking pilot
- [ ] Not ready for adoption

## Context

The `ha-CPsWMS` repository is used as a first real consumer pilot for the public DevSecOps Governance Framework.

The pilot evaluates whether the repository can consume the released public baselines without copying governance framework logic into the application repository.

- DevSecOps baseline in scope: yes
- Architecture governance in scope: yes
- Branch or pull request scope: branch and pull request validation on `codex/use-architecture-baseline-release`
- Evidence maturity: mixed; real repository, traceability, architecture, SBOM, and static-analysis evidence exist, but some generated security evidence remains placeholder-like
- Known limitations: no artifact signature, no protected signing-key evidence, no dedicated IaC repository evidence, monitoring integration not yet proven, vulnerability scan handling must be normalized before blocking mode

## Evidence Reviewed

| Evidence | Status | Notes |
| --- | --- | --- |
| Application artifact | real | `dist/ha-cpswms-source.tar.gz` is produced by the workflow. |
| SBOM | real | `security/sbom.cyclonedx.json` exists; workflow also generates dependency-based SBOM evidence. |
| Vulnerability scan | needs follow-up | Committed Grype/Trivy evidence exists, but the baseline workflow currently writes a placeholder `security/vulnerability-scan.json`. |
| Static analysis | real | Workflow runs `ruff` and `bandit` and uploads reports. |
| Governance run input | real | `governance/governance-run-input.json` is generated from repository and workflow context. |
| Architecture evidence | real | `.governance/architecture/` contains approved demo evidence for the architecture baseline. |
| Workflow artifacts | real | Latest evaluated PR run produced successful governance workflow artifacts. |
| Job summary | real | DevSecOps and architecture governance workflows produced successful job summaries. |

Use status values:

- `real`
- `placeholder`
- `missing`
- `not applicable`
- `needs follow-up`

## Findings

| Finding | Type | Severity | Owner | Due date |
| --- | --- | --- | --- | --- |
| Normalize vulnerability scan evidence so the workflow uploads scanner output instead of placeholder output. | evidence issue | high | Security reviewer / Pipeline owner | To be planned |
| Add artifact signature or document accepted non-signing rationale for the pilot. | governance issue | medium | Governance reviewer | To be planned |
| Clarify signing-key protection evidence before blocking mode. | governance issue | medium | Pipeline owner | To be planned |
| Decide whether IaC evidence is required for this repository or explicitly out of scope. | governance issue | medium | Application owner | To be planned |
| Confirm branch protection and required checks before any blocking pilot. | repository protection issue | high | Application owner | To be planned |

## Blocking Readiness

| Criterion | Ready? | Notes |
| --- | --- | --- |
| Evidence paths are stable | partial | Workflow paths are stable, but vulnerability scan normalization is still needed. |
| Placeholder evidence removed or explicitly accepted | no | Vulnerability scan placeholder generation remains in the DevSecOps baseline workflow. |
| Findings are triaged | partial | Initial findings are listed here; owners and due dates still need confirmation. |
| Branch protection is configured | to be confirmed | Must be verified on the GitHub repository before blocking mode. |
| Required checks are agreed | no | Required check set has not yet been formally agreed. |
| Waiver handling is agreed | no | No waiver process has been accepted for blocking operation. |
| Owners accept recurring maintenance | to be confirmed | Application, pipeline, security, architecture, and governance owners need confirmation. |

## Decision Rationale

The public framework integration is technically working in `report-only` mode. The latest evaluated PR run completed successfully for CI, DevSecOps Baseline, DevSecOps Governance, and Architecture Runtime Governance.

The repository should remain in `report-only` until evidence quality is production-ready. The main blocker for controlled blocking is vulnerability evidence normalization: scanner-produced results should be uploaded by the workflow instead of relying on placeholder output. Branch protection, required checks, waiver handling, and ownership also need confirmation before blocking checks are enabled.

## Follow-Up Actions

| Action | Owner | Due date | Exit criteria |
| --- | --- | --- | --- |
| Replace placeholder vulnerability scan generation with scanner-produced evidence. | Security reviewer / Pipeline owner | To be planned | `security/vulnerability-scan.json` is generated from an agreed scanner in CI. |
| Verify branch protection and required checks on `main`. | Application owner | To be planned | Required checks are documented and visible in repository settings. |
| Decide artifact signing approach or document accepted pilot limitation. | Governance reviewer | To be planned | Signing evidence exists or a documented pilot exception is accepted. |
| Confirm recurring evidence owners. | Application owner | To be planned | Owners are named in this decision record or repository documentation. |
| Re-run the pilot after evidence normalization. | Pipeline owner | To be planned | DevSecOps Baseline and Architecture Runtime Governance complete successfully in `report-only`. |

## Approval

| Role | Name | Approval |
| --- | --- | --- |
| Application owner | To be confirmed | pending |
| Security reviewer | To be confirmed | pending |
| Architecture reviewer | To be confirmed | pending |
| Governance reviewer | To be confirmed | pending |

## Notes

- PR: `https://github.com/joku-dev/ha-CPsWMS/pull/13`
- DevSecOps Baseline: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29407237525`
- Architecture Runtime Governance: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29407236968`
- DevSecOps Governance: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29407237030`
- CI: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29407236974`
