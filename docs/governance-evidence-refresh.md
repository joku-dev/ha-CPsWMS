# Refresh governance evidence

The 11 September 2026 maintenance review requested a fresh evaluation of the
current application revision using the existing governance baselines.

1. Merge the reviewed maintenance change through a pull request. The resulting
   push to `main` starts `DevSecOps Baseline` and `Architecture Runtime Governance`.
2. Inspect both completed runs and their actual governance reports. A successful
   workflow is not a new production approval or proof that every control passed.
3. Collect each new run in `joku-dev/devsecops-governance-framework`, inspect the
   proposed snapshots and merge their reviewed intake PRs before relying on the
   central viewer.
4. Confirm repository, commit, run attempt, baseline and evidence integrity in
   the accepted snapshots. Keep existing results as immutable history.

Manual `workflow_dispatch` runs are useful diagnostics. They do not replace an
available official `main` push result in the central indexes. Rebuilding the
viewer alone does not produce fresh application evidence.

The existing DevSecOps blocking mode, architecture report-only behavior and
baseline versions are retained. The central review deadline for the legacy
DevSecOps blocking exception remains 12 December 2026. This maintenance record
does not approve new enforcement or certify the outcome of the upcoming runs.

The downstream dispatch uses `GH_RESULT_INTAKE_TOKEN`. A missing, expired or
rejected token is emitted as a visible warning and means that no central intake
was requested. It does not rewrite a completed producer assessment as a failed
governance result. Restore the token and retry the dispatch or request the
central intake manually before treating the new result as accepted.
