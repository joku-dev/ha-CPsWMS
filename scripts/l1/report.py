#!/usr/bin/env python3
"""Read-only L1 evidence coverage, distinct from the released compliance evaluator."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence import (
    ROOT,
    SERVICES,
    archive_identity,
    context,
    locked_packages,
    sha,
    write,
)

BASELINE = 'l1-baseline-v1.1.3'
TITLES = [
    'Requirements / test / report traceability', 'Source history and accountable authors',
    'Protected branches and direct changes', 'Secure coding and reviewed findings',
    'Dependency inventory', 'SBOM for releasable artifacts', 'Controlled automated builds',
    'Identifiable build outputs', 'Automated vulnerability scanning',
    'Vulnerability assessment before release', 'Artifact integrity', 'Artifact identity',
    'Authorized deployment approval', 'Only approved artifacts deployed',
    'Machine-readable pipeline evidence', 'Operational versions and security events',
]
REQUIRED_CHECKS = {
    'validate-ubuntu', 'validate-debian', 'DevSecOps Governance',
    'Architecture Runtime Governance', 'L1 coverage report',
}


def load(path):
    return json.loads(Path(path).read_text())


def verify_bundle(directory, expected):
    manifest = load(directory / 'manifest.json')
    for key in ('repository', 'commit', 'run_id', 'attempt'):
        if manifest['context'].get(key) != expected[key]:
            raise ValueError('Context mismatch: ' + key)
    for name, record in manifest['files'].items():
        path = directory / name
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Unsafe evidence path')
        if not path.is_file() or sha(path) != record['sha256'] or path.stat().st_size != record['bytes']:
            raise ValueError('Changed/missing bytes: ' + name)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    if actual != set(manifest['files']):
        raise ValueError('Unmanifested evidence')
    return manifest


def junit(path):
    root = ET.parse(path).getroot()
    cases = []
    for case in root.iter('testcase'):
        state = 'pass'
        for name in ('skipped', 'failure', 'error'):
            if case.find(name) is not None:
                state = name
        cases.append({'class': case.get('classname', ''), 'name': case.get('name', ''), 'status': state})
    if not cases:
        raise ValueError('Empty JUnit is not test evidence')
    return cases


def execution_ok(directory, name, accepted=(0,)):
    record = load(directory / (name + '.execution.json'))
    return record['exit_code'] in accepted


def inspect_image(directory, service):
    subject = load(directory / 'subject.json')
    if subject['service'] != service or not re.fullmatch(r'sha256:[a-f0-9]{64}', subject['image_id']):
        raise ValueError('Invalid image identity')
    if sha(directory / 'image.tar') != subject['archive_sha256']:
        raise ValueError('Archive digest mismatch')
    identity = archive_identity(directory / 'image.tar')
    if (subject.get('archive_config_digest') != subject['image_id']
            or identity['config_digest'] != subject['image_id']
            or subject.get('archive_tag') not in identity['repo_tags']):
        raise ValueError('Archive transport identity mismatch')
    sbom = load(directory / 'sbom.cyclonedx.json')
    if sbom.get('bomFormat') != 'CycloneDX' or not sbom.get('components'):
        raise ValueError('SBOM has no measured components')
    component = sbom.get('metadata', {}).get('component', {})
    properties = {p.get('name'): p.get('value') for p in component.get('properties', [])}
    if component.get('type') != 'container' or properties.get('aquasecurity:trivy:ImageID') != subject['image_id']:
        raise ValueError('SBOM bound to another image')
    scan = load(directory / 'vulnerabilities.json')
    results = scan.get('Results', [])
    # Trivy 0.70 ArtifactID hashes image + repository; ImageID is the Docker config digest.
    if not results or scan.get('Metadata', {}).get('ImageID') != subject['image_id']:
        raise ValueError('Scan missing results or bound to another image')
    for name in ('build', 'sbom', 'vulnerabilities', 'archive'):
        if not execution_ok(directory, name):
            raise ValueError('Tool did not finish: ' + name)
    return {**subject, 'components': len(sbom['components']),
            'vulnerabilities': [v for result in results for v in result.get('Vulnerabilities', [])]}


def inspect_dependencies(directory):
    record = load(directory / 'dependency-locks.json')
    if record.get('python') != '3.12' or set(record.get('locks', {})) != {
            'ha-sync', 'query-api', 'semantic-enrichment', 'world-model-chat', 'application', 'ci'}:
        raise ValueError('Dependency lock profiles are incomplete')
    packages = {}
    for name, lock in record['locks'].items():
        input_path = directory / lock['evidence_input']
        lock_path = directory / lock['evidence_lock']
        if (sha(input_path) != lock['input_sha256'] or sha(lock_path) != lock['lock_sha256']
                or not lock.get('hashes_required')):
            raise ValueError('Dependency lock bytes do not match: ' + name)
        packages[name] = locked_packages(lock_path)
        if len(packages[name]) != lock['package_count']:
            raise ValueError('Dependency package count mismatch: ' + name)
    for service in ('ha-sync', 'query-api', 'semantic-enrichment', 'world-model-chat'):
        if not set(packages[service].items()).issubset(set(packages['application'].items())):
            raise ValueError('Application inventory omits ' + service)
    if not set(packages['application'].items()).issubset(set(packages['ci'].items())):
        raise ValueError('CI inventory omits application packages')
    sboms = {}
    for profile in ('application', 'ci'):
        sbom = load(directory / ('dependency-sbom-' + profile + '.cyclonedx.json'))
        if sbom.get('bomFormat') != 'CycloneDX' or len(sbom.get('components', [])) < len(packages[profile]):
            raise ValueError('Dependency SBOM incomplete: ' + profile)
        if not execution_ok(directory, 'dependency-sbom-' + profile):
            raise ValueError('Dependency SBOM command failed: ' + profile)
        sboms[profile] = len(sbom['components'])
    if not execution_ok(directory, 'dependency-audit', (0, 1)):
        raise ValueError('Dependency audit command failed')
    audit = load(directory / 'dependency-audit.json')
    if not isinstance(audit.get('dependencies'), list):
        raise TypeError('Dependency audit is invalid')
    vulnerabilities = [v for dependency in audit['dependencies'] for v in dependency.get('vulns', [])]
    return {'packages': {name: len(value) for name, value in packages.items()},
            'sbom_components': sboms, 'vulnerabilities': vulnerabilities,
            'resolver': record.get('resolver')}


def inspect_main_ruleset(directory):
    try:
        listing = load(directory / 'rulesets.json')
    except (OSError, ValueError, TypeError):
        return None
    if listing.get('http_status') != 200 or not isinstance(listing.get('data'), list):
        return None
    details = load(directory / 'ruleset-details.json')
    if not isinstance(details, list):
        return None
    by_id = {row.get('data', {}).get('id'): row for row in details}
    for summary in listing['data']:
        ruleset_id = summary.get('id')
        if not isinstance(ruleset_id, int):
            continue
        detail_response = by_id.get(ruleset_id, {})
        if detail_response.get('http_status') != 200:
            continue
        detail = detail_response.get('data', {})
        conditions = detail.get('conditions', {}).get('ref_name', {})
        includes = set(conditions.get('include', []))
        rules = {rule.get('type'): rule for rule in detail.get('rules', [])}
        checks = {item.get('context') for item in rules.get('required_status_checks', {}).get(
            'parameters', {}).get('required_status_checks', [])}
        protects_main = 'refs/heads/main' in includes or '~DEFAULT_BRANCH' in includes
        required_rules = {'deletion', 'non_fast_forward', 'pull_request', 'required_status_checks'}
        if (detail.get('enforcement') == 'active' and protects_main
                and not detail.get('bypass_actors') and required_rules.issubset(rules)
                and REQUIRED_CHECKS.issubset(checks)):
            return {'id': ruleset_id, 'name': detail.get('name'),
                    'required_checks': sorted(checks),
                    'required_approvals': rules['pull_request'].get('parameters', {}).get(
                        'required_approving_review_count')}
    return None


def build_report(base, expected):
    errors, manifests = {}, {}
    names = ['source', 'platform', 'runtime', *('image-' + s for s in SERVICES)]
    for name in names:
        try:
            manifests[name] = verify_bundle(base / name, expected)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors[name] = str(exc)
    rows = []

    def row(number, state, detail, refs):
        rows.append({'control_id': f'DSCB-L1-REQ-{number:03}', 'title': TITLES[number - 1],
                     'coverage': state, 'detail': detail, 'evidence': refs})

    cases, source_ok, runtime_ok = [], False, False
    for name, execution in [('source', 'tests'), ('runtime', 'runtime-tests')]:
        if name not in errors:
            try:
                found = junit(base / name / 'junit.xml')
                cases.extend(found)
                good = execution_ok(base / name, execution) and all(c['status'] == 'pass' for c in found)
                if name == 'source':
                    source_ok = good
                else:
                    runtime_ok = good
            except (OSError, ValueError, ET.ParseError, KeyError) as exc:
                errors[name] = str(exc)
    traceability = load(ROOT / 'quality/traceability.json')
    links = []
    for req in traceability['requirements']:
        matched = [c for c in cases if c['class'].startswith(req['test_class_prefix']) and c['name'].startswith(req.get('test_name_prefix', ''))]
        links.append({**req, 'executed_cases': matched, 'matched': bool(matched),
                      'passed': bool(matched) and all(c['status'] == 'pass' for c in matched)})
    row(1, 'partial' if source_ok and runtime_ok and all(r['passed'] for r in links) else 'gap',
        'Actual JUnit links for technical requirements; full approved system/component requirement coverage remains open.', ['source/junit.xml', 'runtime/junit.xml', 'quality/traceability.json'])

    platform = base / 'platform'
    identity_ok = False
    protection = None
    main_ruleset = None
    if 'platform' not in errors:
        try:
            commit = load(platform / 'commit.json')
            identity_ok = commit.get('http_status') == 200 and commit['data'].get('sha') == expected['commit'] and bool(commit['data'].get('author', {}).get('id') if commit['data'].get('author') else False)
            response = load(platform / 'protection.json')
            if response.get('http_status') == 200:
                protection = response['data']
            main_ruleset = inspect_main_ruleset(platform)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors['platform'] = str(exc)
            identity_ok = False
            protection = None
            main_ruleset = None
    row(2, 'measured' if identity_ok else 'gap',
        'GitHub commit identity queried directly. PR/review responses retained; this does not invent an independent approval.', ['platform/commit.json', 'platform/pulls.json'])
    row(3, 'measured' if main_ruleset else 'partial' if protection else 'gap',
        ('Active main ruleset requires pull requests and five governance/validation checks, blocks deletion and force pushes, and has no bypass actors.'
         if main_ruleset else 'Legacy protection captured, but no complete active main ruleset without bypass actors was verified.'
         if protection else 'Protection APIs unavailable or no verified direct-push prohibition.'),
        ['platform/protection.json', 'platform/rules.json', 'platform/rulesets.json'])
    static = None
    if 'source' not in errors:
        try:
            bandit = load(base / 'source/bandit.json')
            ruff = load(base / 'source/ruff.json')
            if bandit.get('errors') or not execution_ok(base / 'source', 'bandit', (0, 1)) or not execution_ok(base / 'source', 'ruff', (0, 1)):
                raise ValueError('Static scanner failed')
            static = {'bandit': len(bandit['results']), 'ruff': len(ruff)}
        except (OSError, ValueError, KeyError):
            pass
    row(4, 'findings' if static and sum(static.values()) else 'measured' if static else 'gap',
        f'Executed SAST/lint: {static}. No machine findings remain.' if static and not sum(static.values())
        else f'Executed SAST/lint: {static}. Findings need assessment.' if static
        else 'No valid SAST/lint evidence.', ['source/bandit.json', 'source/ruff.json'])

    dependencies = None
    if 'source' not in errors:
        try:
            dependencies = inspect_dependencies(base / 'source')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors['source-dependencies'] = str(exc)

    images = {}
    for service in SERVICES:
        name = 'image-' + service
        if name not in errors:
            try:
                images[service] = inspect_image(base / name, service)
                if images[service]['commit'] != expected['commit']:
                    raise ValueError('Subject commit mismatch')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                images.pop(service, None)
                errors[name] = str(exc)
    all_images = len(images) == len(SERVICES)
    image_refs = ['image-' + s + '/subject.json' for s in SERVICES]
    row(5, 'measured' if all_images and dependencies else 'gap',
        'Hash-locked application and CI/tool inventories plus actual packages from all five immutable images.'
        if all_images and dependencies else 'Complete image and hash-locked dependency inventories were not verified.',
        ['source/dependency-locks.json', 'source/dependency-sbom-application.cyclonedx.json',
         'source/dependency-sbom-ci.cyclonedx.json', *('image-' + s + '/sbom.cyclonedx.json' for s in SERVICES)])
    row(6, 'measured' if all_images else 'gap', 'CycloneDX generated for each archived image, bound through immutable image ID and archive digest.', image_refs)
    row(7, 'measured' if all_images and dependencies else 'gap',
        'Automated builds use digest-pinned base images and Python 3.12 locks with exact versions and SHA-256 hashes.'
        if all_images and dependencies else 'Pinned build inputs and dependency locks were not both verified.',
        [*image_refs, 'source/dependency-locks.json'])
    row(8, 'measured' if all_images else 'gap', 'Build outputs identified by image ID, source commit and archive SHA-256.', image_refs)
    row(9, 'measured' if all_images else 'gap', 'Trivy executed on the same immutable image IDs, including OS packages; scanner errors invalidate evidence.', ['image-' + s + '/vulnerabilities.json' for s in SERVICES])
    vulnerabilities = [v for i in images.values() for v in i['vulnerabilities']]
    dependency_vulnerabilities = dependencies['vulnerabilities'] if dependencies else []
    all_vulnerabilities = vulnerabilities + dependency_vulnerabilities
    row(10, 'findings' if all_vulnerabilities else 'measured' if all_images and dependencies else 'gap',
        f'{len(vulnerabilities)} image findings and {len(dependency_vulnerabilities)} application dependency findings. No release risk acceptance is inferred.'
        if all_images and dependencies else 'Complete vulnerability assessment evidence was not verified.',
        [*('image-' + s + '/vulnerabilities.json' for s in SERVICES), 'source/dependency-audit.json'])
    row(11, 'partial' if all_images else 'gap', 'Archives and evidence hashes recomputed after artifact download. Repository access controls/retention and independent provenance remain separate checks.', image_refs)
    row(12, 'measured' if all_images else 'gap', 'Build config digests, transported tags and archive hashes verified for the actual archived artifacts; target runtime IDs are recorded after import.', image_refs)
    row(13, 'gap', 'No production/staging deployment approval is recorded. A push, green run, PR merge or review exception is not deployment approval.', ['platform/environments.json'])
    row(14, 'gap', 'Tests deploy the archived query and Neo4j images in disposable CI. Approved-artifact enforcement in a target deployment is not yet evidenced.', ['runtime/deployment.json'])
    row(15, 'measured' if not errors else 'gap', 'Machine-readable raw reports and run-bound manifests; every referenced file is hashed and rechecked.', ['*/manifest.json'])
    row(16, 'partial' if runtime_ok else 'gap', 'Actual CI container image IDs and HTTP/database outage logs retained. No production deployment register or operational security-event retention is claimed.', ['runtime/deployment.json', 'runtime/query-api.log', 'runtime/neo4j.log', 'runtime/junit.xml'])
    return {'schema_version': '1.0', 'report_type': 'l1-measured-evidence-coverage',
            'reference_baseline': BASELINE, 'context': expected, 'enforcement': 'report-only',
            'official_compliance_result': False, 'production_approval': False,
            'summary': dict(Counter(r['coverage'] for r in rows)), 'controls': rows,
            'traceability': links, 'test_summary': dict(Counter(c['status'] for c in cases)),
            'static_analysis': static, 'images': {s: {k: v for k, v in i.items() if k != 'vulnerabilities'} for s, i in images.items()},
            'dependency_inventory': ({k: v for k, v in dependencies.items() if k != 'vulnerabilities'}
                                     if dependencies else None),
            'main_ruleset': main_ruleset,
            'vulnerability_severities': dict(Counter(v.get('Severity', 'UNKNOWN') for v in vulnerabilities)),
            'dependency_vulnerability_count': len(dependency_vulnerabilities),
            'evidence_errors': errors,
            'limitations': traceability['remaining_scope']}


def typed_evidence_manifest(report, input_path):
    """Declare the five-image transport only when the whole profile is valid."""
    if report['evidence_errors'] or set(report['images']) != set(SERVICES):
        return None
    return {
        'profile': 'ha-cpswms-container-evidence-v2', 'enforcement': 'report-only',
        'context': {key: report['context'][key] for key in ('repository', 'commit', 'run_id', 'attempt', 'event')},
        'images': {service: {
            'artifact_name': 'l1-image-' + service,
            'image_id': report['images'][service]['image_id'],
            'archive_sha256': load(input_path / ('image-' + service) / 'subject.json')['archive_sha256'],
            'sbom_sha256': sha(input_path / ('image-' + service) / 'sbom.cyclonedx.json'),
            'sbom_component_count': report['images'][service]['components'],
        } for service in SERVICES},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.input, context())
    write(args.out / 'l1-coverage.json', report)
    # Stable transport contract for the central five-image Trust collector.
    # A partial report never advertises a complete Typed Evidence bundle.
    manifest = typed_evidence_manifest(report, args.input)
    if manifest is not None:
        write(args.out / 'typed-evidence-manifest.json', manifest)
    lines = ['# L1 measured evidence coverage', '', f'Reference: `{BASELINE}`. Scope: CI validation, report-only.',
             '**This is evidence coverage, not a production approval or replacement baseline result.**', '',
             '| Control | Coverage | Observation |', '|---|---|---|']
    for row in report['controls']:
        lines.append(f"| {row['control_id']} | {row['coverage']} | {row['detail']} |")
    lines += ['', '## Executed tests', '', json.dumps(report['test_summary']), '',
              '## Evidence errors', '', '```json', json.dumps(report['evidence_errors'], indent=2), '```', '',
              '## Remaining scope', '', *('- ' + v for v in report['limitations'])]
    (args.out / 'l1-coverage.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(report['summary'], sort_keys=True))
    # Findings are report-only; missing/corrupt tooling output is an execution failure.
    return 1 if report['evidence_errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
