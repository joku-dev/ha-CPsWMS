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
| Evaluated workflow runs | DevSecOps Baseline `29414077429`, Architecture Runtime Governance `29414076871`, DevSecOps Governance `29414076853`, CI `29414076865` |

## Decision

- [x] Continue `report-only`
- [ ] Start controlled blocking pilot
- [ ] Not ready for adoption

## Context

The `ha-CPsWMS` repository is an active `main`-branch consumer pilot for the public DevSecOps Governance Framework.

The pilot evaluates whether the repository can consume the released public baselines without copying governance framework logic into the application repository.

- DevSecOps baseline in scope: yes
- Architecture governance in scope: yes
- Branch or pull request scope: `main` branch validation after PR `13` merge
- Evidence maturity: mixed; real repository, traceability, architecture, SBOM, vulnerability, and static-analysis evidence exist
- Known limitations: no artifact signature, no protected signing-key evidence, no dedicated IaC repository evidence, monitoring integration not yet proven, vulnerability severity enrichment must be agreed before blocking mode

## Evidence Reviewed

| Evidence | Status | Notes |
| --- | --- | --- |
| Application artifact | real | `dist/ha-cpswms-source.tar.gz` is produced by the workflow. |
| SBOM | real | `security/sbom.cyclonedx.json` exists; workflow also generates dependency-based SBOM evidence. |
| Vulnerability scan | real | The baseline workflow runs `pip-audit`, stores raw output in `security/pip-audit-report.json`, and writes normalized framework evidence to `security/vulnerability-scan.json`. |
| Static analysis | real | Workflow runs `ruff` and `bandit` and uploads reports. |
| Governance run input | real | `governance/governance-run-input.json` is generated from repository and workflow context. |
| Architecture evidence | real | `.governance/architecture/` contains approved demo evidence for the architecture baseline. |
| Workflow artifacts | real | Latest evaluated `main` runs produced successful workflow artifacts. |
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
| Review `pip-audit` finding severity normalization before any blocking pilot. | evidence issue | medium | Security reviewer / Pipeline owner | To be planned |
| Add artifact signature or document accepted non-signing rationale for the pilot. | governance issue | medium | Governance reviewer | To be planned |
| Clarify signing-key protection evidence before blocking mode. | governance issue | medium | Pipeline owner | To be planned |
| Decide whether IaC evidence is required for this repository or explicitly out of scope. | governance issue | medium | Application owner | To be planned |
| Confirm branch protection and required checks before any blocking pilot. | repository protection issue | high | Application owner | To be planned |

## Blocking Readiness

| Criterion | Ready? | Notes |
| --- | --- | --- |
| Evidence paths are stable | yes | Workflow uploads application, SBOM, vulnerability, static-analysis, traceability, and governance-run input evidence. |
| Placeholder evidence removed or explicitly accepted | partial | Vulnerability scan placeholder generation has been removed; artifact signing and selected repository-control evidence still need decision. |
| Findings are triaged | partial | Initial findings are listed here; owners and due dates still need confirmation. |
| Branch protection is configured | to be confirmed | Must be verified on the GitHub repository before blocking mode. |
| Required checks are agreed | no | Required check set has not yet been formally agreed. |
| Waiver handling is agreed | no | No waiver process has been accepted for blocking operation. |
| Owners accept recurring maintenance | to be confirmed | Application, pipeline, security, architecture, and governance owners need confirmation. |

## Decision Rationale

The public framework integration is technically working on `main` in `report-only` mode. The latest evaluated `main` runs completed successfully for CI, DevSecOps Baseline, DevSecOps Governance, and Architecture Runtime Governance.

The repository should remain in `report-only` until evidence quality is production-ready. Vulnerability evidence is now scanner-produced by `pip-audit`, but severity enrichment, branch protection, required checks, waiver handling, signing evidence, and ownership still need confirmation before blocking checks are enabled.

## Follow-Up Actions

| Action | Owner | Due date | Exit criteria |
| --- | --- | --- | --- |
| Review `pip-audit` severity normalization and decide whether additional severity enrichment is required. | Security reviewer / Pipeline owner | To be planned | Severity policy is documented and accepted for blocking mode. |
| Verify branch protection and required checks on `main`. | Application owner | To be planned | Required checks are documented and visible in repository settings. |
| Decide artifact signing approach or document accepted pilot limitation. | Governance reviewer | To be planned | Signing evidence exists or a documented pilot exception is accepted. |
| Confirm recurring evidence owners. | Application owner | To be planned | Owners are named in this decision record or repository documentation. |
| Re-run after the next readiness change. | Pipeline owner | To be planned | DevSecOps Baseline and Architecture Runtime Governance complete successfully in `report-only`. |

## Approval

| Role | Name | Approval |
| --- | --- | --- |
| Application owner | To be confirmed | pending |
| Security reviewer | To be confirmed | pending |
| Architecture reviewer | To be confirmed | pending |
| Governance reviewer | To be confirmed | pending |

## Notes

- PR: `https://github.com/joku-dev/ha-CPsWMS/pull/13`
- Merge commit: `085ba5e5b14fcf557cd22747d07ca287884b93df`
- DevSecOps Baseline: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29414077429`
- Architecture Runtime Governance: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29414076871`
- DevSecOps Governance: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29414076853`
- CI: `https://github.com/joku-dev/ha-CPsWMS/actions/runs/29414076865`
