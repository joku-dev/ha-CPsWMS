# Portable pipeline-l1 pilot

The separate `Portable Pipeline L1 (report-only)` workflow prepares fresh evidence
for the portable governance runtime. It runs on pull requests, pushes to `main`
and manual dispatch. Its runtime is pinned to governance commit
`adc4643bb7a5c962e4efb1525298ad9e652c73d2`, the implementation installed on both
the Mac and Ubuntu VM when this pilot was prepared. The released baseline remains
`l1-baseline-v1.1.3`. This new job is not added to required branch checks.

## Evidence and scope

`scripts/portable_evidence.py prepare` archives the tested Git revision, including
`quality/application-requirements.lock`, and derives an exact dependency inventory
from that committed, hashed lock. It rejects a changed working lock. Trivy 0.70.0
generates a CycloneDX SBOM from those dependency pins and scans its own SBOM. All
versions are taken from that lock; there is no new dependency resolution.

`normalize` verifies that the archive contains the same lock and that the SBOM
and scan cover exactly its package/version set. It retains findings and their
scanner severities, binds the SBOM application component and normalized scan to
the archive SHA-256, and retains hashes of the original raw reports. Missing
packages, scanner errors, unknown severities, changed inputs and duplicate JSON
keys stop execution. No unknown severity is converted into a clean scan.

This inventories **declared locked Python dependencies in a source archive**.
It does not build or scan deployed images, inventory OS packages, execute the
application, establish reachability or replace the separate L1 Measured Evidence
workflow. Trivy's advisory data and target-platform interpretation can affect
findings. See its [SBOM scanning contract](https://trivy.dev/docs/latest/target/sbom/).

The runtime evaluates five mapped L1 controls (003, 006, 009, 010, 011); the other
eleven remain `not_evaluated`. Report-only findings return success after a complete
evaluation; technical/incomplete execution fails visibly. The original result
keeps `evidence_trust: unverified`, `full_baseline_assessment: false` and no merge
blocking claim. Existing legacy DevSecOps and architecture workflows keep their
current modes and frozen baselines.

## Artifacts and host comparison

Each execution preserves `portable-producer-raw-v1` (archive, inventory, raw
scanner/version output, normalized files and available runtime diagnostics) and,
when export succeeds, `axiom-portable-bundle-v2`. Both expire after 14 days on
GitHub, so copy the exact ZIP and its independently read native digest into private
operations storage promptly. Missing bundles are a failed prerequisite, not a
valid empty assessment. Do not commit generated evidence back into this checkout.

The bundle can be verified independently with the **same pinned runtime** on Mac
and VM, separate private state roots and a private intake policy. Compare exact
subject digests, context, checks, controls, decision and the verifier's separate
receipt. A locally verified import reaches integrity verification only. Replaying
a bundle is not a new scanner run or new native provenance verification.

Run producer boundary tests locally with:

```sh
python3 -m unittest discover -s quality_tests -p test_portable_evidence.py -v
```

## Native collection and shadow acceptance

The actual repository identity is recorded in `.governance/portable-profile.json`.
The workflow copies it outside the application checkout before context collection.
This placement does not itself establish trust: central adoption must separately
review and pin the workflow, producer script, imported `scripts/l1/evidence.py`,
dependency locks, profile, action/runtime references and runner/credential scope.
The profile cannot authorize itself or update a central allowlist.

The optional `AXIOM_SCM_READ_TOKEN` secret may supply read-only SCM facts; the
workflow otherwise uses GitHub's read token. Missing effective protection facts
remain explicit runtime gaps. Do not add write permissions to resolve them.

The native collector must bind this exact workflow path, native job name
`Portable pipeline L1 (report-only)`, logical job ID `portable`, upload step
`Upload portable bundle`, artifact name `axiom-portable-bundle-v2` and reviewed
configuration digest. GitHub PR provenance is not supported by the current native
verifier. A PR run is therefore a diagnostic and host-comparison input; a fresh
literal-branch `main` push is required for supported native provenance.

VM shadow operation needs a reviewed central consumer profile, a separate private
operations root and unique node ID, provisioned reader credentials and no publisher
ownership. Publication remains disabled. At least 24 hours of successful shadow
observation and a **new matching native default-branch run after that full window**
are prerequisites for the separate handoff. An old receipt or elapsed timer does
not satisfy it. This change prepares the producer; it does not claim completion
of host comparison, M2 live acceptance or the shadow window.
