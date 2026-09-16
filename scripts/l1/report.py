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
from evidence import ROOT, SERVICES, context, sha, write

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
    if 'platform' not in errors:
        try:
            commit = load(platform / 'commit.json')
            identity_ok = commit.get('http_status') == 200 and commit['data'].get('sha') == expected['commit'] and bool(commit['data'].get('author', {}).get('id') if commit['data'].get('author') else False)
            response = load(platform / 'protection.json')
            if response.get('http_status') == 200:
                protection = response['data']
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors['platform'] = str(exc)
            identity_ok = False
            protection = None
    row(2, 'measured' if identity_ok else 'gap',
        'GitHub commit identity queried directly. PR/review responses retained; this does not invent an independent approval.', ['platform/commit.json', 'platform/pulls.json'])
    row(3, 'partial' if protection else 'gap',
        'Protection configuration captured; bypass/direct-push policy requires assessment.' if protection else 'Protection API unavailable or collection invalid; protected=True is insufficient to prove direct-push prohibition.', ['platform/protection.json', 'platform/rules.json'])
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
    row(4, 'findings' if static and sum(static.values()) else 'partial' if static else 'gap',
        f'Executed SAST/lint: {static}. Findings need assessment; findings_reviewed is never inferred.' if static else 'No valid SAST/lint evidence.', ['source/bandit.json', 'source/ruff.json'])

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
    row(5, 'measured' if all_images else 'gap', 'Actual OS and application packages from all five immutable images; development/build tools are outside runtime inventory.', ['image-' + s + '/sbom.cyclonedx.json' for s in SERVICES])
    row(6, 'measured' if all_images else 'gap', 'CycloneDX generated for each archived image, bound through immutable image ID and archive digest.', image_refs)
    row(7, 'partial' if all_images else 'gap', 'Automated builds with pinned base images and retained logs; Python dependency resolution is recorded by SBOM but lockfiles/reproducible rebuilds remain open.', image_refs)
    row(8, 'measured' if all_images else 'gap', 'Build outputs identified by image ID, source commit and archive SHA-256.', image_refs)
    row(9, 'measured' if all_images else 'gap', 'Trivy executed on the same immutable image IDs, including OS packages; scanner errors invalidate evidence.', ['image-' + s + '/vulnerabilities.json' for s in SERVICES])
    vulnerabilities = [v for i in images.values() for v in i['vulnerabilities']]
    row(10, 'findings' if vulnerabilities else 'partial' if all_images else 'gap',
        f'{len(vulnerabilities)} image/package findings (may repeat across images). No release assessment or risk acceptance is inferred from scanner completion.', ['image-' + s + '/vulnerabilities.json' for s in SERVICES])
    row(11, 'partial' if all_images else 'gap', 'Archives and evidence hashes recomputed after artifact download. Repository access controls/retention and independent provenance remain separate checks.', image_refs)
    row(12, 'measured' if all_images else 'gap', 'Unique content identities verified for the actual archived artifacts.', image_refs)
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
            'vulnerability_severities': dict(Counter(v.get('Severity', 'UNKNOWN') for v in vulnerabilities)),
            'evidence_errors': errors,
            'limitations': traceability['remaining_scope']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.input, context())
    write(args.out / 'l1-coverage.json', report)
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
