#!/usr/bin/env python3
"""Collect measured consumer evidence. Never infer approvals from a green job."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ('ha-sync', 'semantic-enrichment', 'query-api', 'world-model-chat', 'neo4j')
CODE = ('ha-sync', 'semantic-enrichment', 'query-api', 'world-model-chat', 'semantic_core', 'sources', 'storage')
LOCKS = {
    'ha-sync': ('ha-sync/requirements.txt', 'ha-sync/requirements.lock'),
    'query-api': ('query-api/requirements.txt', 'query-api/requirements.lock'),
    'semantic-enrichment': ('semantic-enrichment/requirements.txt', 'semantic-enrichment/requirements.lock'),
    'world-model-chat': ('world-model-chat/requirements.txt', 'world-model-chat/requirements.lock'),
    'application': ('quality/application-requirements.in', 'quality/application-requirements.lock'),
    'ci': ('quality/ci-requirements.in', 'quality/ci-requirements.lock'),
}


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def archive_identity(path):
    """Return the config digest and transported tags from one Docker archive."""
    with tarfile.open(path, 'r:') as archive:
        manifest_file = archive.extractfile('manifest.json')
        if manifest_file is None:
            raise ValueError('Docker archive has no manifest')
        manifest = json.load(manifest_file)
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise ValueError('Expected exactly one Docker image')
        entry = manifest[0]
        config_name = entry.get('Config')
        config_file = archive.extractfile(config_name) if isinstance(config_name, str) else None
        if config_file is None:
            raise ValueError('Docker archive has no image config')
        digest = 'sha256:' + hashlib.sha256(config_file.read()).hexdigest()
        expected = Path(config_name).name.removesuffix('.json')
        if expected != digest.removeprefix('sha256:'):
            raise ValueError('Docker archive config path does not match its content')
        tags = entry.get('RepoTags') or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError('Docker archive tags are invalid')
        return {'config_digest': digest, 'repo_tags': tags, 'layer_count': len(entry.get('Layers') or [])}


def context():
    return {'repository': os.getenv('GITHUB_REPOSITORY', 'local'),
            'commit': os.getenv('GITHUB_SHA', subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()),
            'run_id': os.getenv('GITHUB_RUN_ID', 'local'), 'attempt': os.getenv('GITHUB_RUN_ATTEMPT', '1'),
            'event': os.getenv('GITHUB_EVENT_NAME', 'local'),
            'observed_at': datetime.now(timezone.utc).isoformat()}


def execute(out, name, command, accepted=(0,)):
    started = time.monotonic()
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
    record = {'command': command, 'exit_code': result.returncode, 'accepted_exit_codes': list(accepted),
              'execution_ok': result.returncode in accepted, 'seconds': time.monotonic() - started}
    write(out / (name + '.execution.json'), record)
    return record['execution_ok']


def locked_packages(path):
    """Return exact pins and reject lock entries without an artifact hash."""
    text = Path(path).read_text()
    packages = {}
    matches = list(re.finditer(
        r'(?m)^([A-Za-z0-9_.-]+)==([^\s\\]+)(.*?)(?=^[A-Za-z0-9_.-]+==|\Z)',
        text, re.DOTALL))
    for match in matches:
        name, version, block = match.groups()
        if '--hash=sha256:' not in block:
            raise ValueError(f'Unhashed lock entry: {name}')
        packages[name.lower().replace('_', '-')] = version
    if not packages:
        raise ValueError('Lock has no exact package pins')
    return packages


def dependency_inventory(out):
    """Record locked inputs and generate application plus CI/tool inventories."""
    records, parsed = {}, {}
    try:
        for name, (input_name, lock_name) in LOCKS.items():
            input_path, lock_path = ROOT / input_name, ROOT / lock_name
            parsed[name] = locked_packages(lock_path)
            evidence_input = out / 'dependency-files' / (name + '.in')
            evidence_lock = out / 'dependency-files' / (name + '.lock')
            evidence_input.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(input_path, evidence_input)
            shutil.copyfile(lock_path, evidence_lock)
            records[name] = {
                'input': input_name,
                'input_sha256': sha(input_path),
                'lock': lock_name,
                'lock_sha256': sha(lock_path),
                'package_count': len(parsed[name]),
                'hashes_required': True,
                'evidence_input': str(evidence_input.relative_to(out)),
                'evidence_lock': str(evidence_lock.relative_to(out)),
            }
        for service in SERVICES[:4]:
            if not set(parsed[service].items()).issubset(set(parsed['application'].items())):
                raise ValueError(f'Application lock does not contain {service} lock')
        if not set(parsed['application'].items()).issubset(set(parsed['ci'].items())):
            raise ValueError('CI lock does not contain the application lock')
        write(out / 'dependency-locks.json', {
            'python': '3.12',
            'resolver': 'uv 0.8.22',
            'locks': records,
        })
    except (OSError, ValueError):
        return False

    checks = []
    for profile in ('application', 'ci'):
        checks.append(execute(out, 'dependency-sbom-' + profile, [
            'cyclonedx-py', 'requirements', '--output-reproducible',
            '--output-format', 'JSON', '--output-file',
            str(out / ('dependency-sbom-' + profile + '.cyclonedx.json')),
            str(ROOT / LOCKS[profile][1]),
        ]))
    checks.append(execute(out, 'dependency-audit', [
        sys.executable, '-m', 'pip_audit', '--require-hashes', '--disable-pip',
        '--progress-spinner', 'off', '--format', 'json', '--output',
        str(out / 'dependency-audit.json'), '-r', str(ROOT / LOCKS['application'][1]),
    ], accepted=(0, 1)))
    try:
        for profile in ('application', 'ci'):
            sbom = json.loads((out / ('dependency-sbom-' + profile + '.cyclonedx.json')).read_text())
            if sbom.get('bomFormat') != 'CycloneDX' or len(sbom.get('components', [])) < len(parsed[profile]):
                raise ValueError('Incomplete dependency SBOM')
        audit = json.loads((out / 'dependency-audit.json').read_text())
        if not isinstance(audit.get('dependencies'), list):
            raise TypeError('Invalid dependency audit')
    except (OSError, ValueError, TypeError):
        checks.append(False)
    return all(checks)


def seal(out):
    """Bind raw output bytes to the producer run; this is integrity, not attestation."""
    files = {str(p.relative_to(out)): {'sha256': sha(p), 'bytes': p.stat().st_size}
             for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
    write(out / 'manifest.json', {'context': context(), 'files': files})


def source(out):
    checks = []
    checks.append(execute(out, 'tests', [sys.executable, '-m', 'pytest', 'tests', 'quality_tests',
        '--ignore=quality_tests/test_runtime.py', '-q', '--junitxml=' + str(out / 'junit.xml'),
        '--cov=semantic_core', '--cov=sources', '--cov=storage', '--cov=ha-sync',
        '--cov=query-api', '--cov=world-model-chat', '--cov=semantic-enrichment',
        '--cov-report=xml:' + str(out / 'coverage.xml'), '--cov-report=term']))
    checks.append(execute(out, 'bandit', [sys.executable, '-m', 'bandit', '-r', *CODE,
        '-f', 'json', '-o', str(out / 'bandit.json')], accepted=(0, 1)))
    checks.append(execute(out, 'ruff', [sys.executable, '-m', 'ruff', 'check', *CODE,
        '--output-format', 'json', '--output-file', str(out / 'ruff.json')], accepted=(0, 1)))
    checks.append(execute(out, 'installed-tools', [sys.executable, '-m', 'pip', 'freeze']))
    checks.append(dependency_inventory(out))
    # A tools exit 1 is a finding only when its structured result actually exists.
    for name in ('bandit', 'ruff'):
        try:
            report = json.loads((out / (name + '.json')).read_text())
            if name == 'bandit' and (not isinstance(report, dict) or report.get('errors')):
                checks.append(False)
        except (OSError, ValueError):
            checks.append(False)
    seal(out)
    return all(checks)


def image(out, service):
    images = json.loads((ROOT / 'quality/runtime-images.json').read_text())
    tag = 'l1-' + service + ':' + context()['commit'][:12]
    if service == 'neo4j':
        ok = execute(out, 'build', ['docker', 'build', '--pull', '--build-arg',
            'NEO4J_IMAGE=' + images['neo4j']['reference'], '--label',
            'org.opencontainers.image.revision=' + context()['commit'],
            '-f', 'deployment/images/neo4j/Dockerfile', '-t', tag, 'deployment/images/neo4j'])
    else:
        build_context = '.' if service == 'ha-sync' else service
        ok = execute(out, 'build', ['docker', 'build', '--pull', '--build-arg',
            'PYTHON_IMAGE=' + images['python']['reference'], '--label',
            'org.opencontainers.image.revision=' + context()['commit'],
            '-f', service + '/Dockerfile', '-t', tag, build_context])
    if not ok:
        seal(out)
        return False
    image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', tag], text=True).strip()
    inspection = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image_id], text=True))[0]
    write(out / 'image-metadata.json', {k: inspection.get(k) for k in ('Id', 'RepoDigests', 'Created', 'Architecture', 'Os')})
    # Scan the immutable local image ID that is saved and later tested.
    checks = [execute(out, 'sbom', ['trivy', 'image', '--image-src', 'docker', '--format', 'cyclonedx',
        '--output', str(out / 'sbom.cyclonedx.json'), image_id])]
    checks.append(execute(out, 'vulnerabilities', ['trivy', 'image', '--image-src', 'docker',
        '--scanners', 'vuln', '--format', 'json', '--exit-code', '0',
        '--output', str(out / 'vulnerabilities.json'), image_id]))
    checks.append(execute(out, 'trivy-version', ['trivy', 'version']))
    # Save by tag so Docker engines using different image stores can resolve the
    # imported image even when their local runtime ID differs from the config digest.
    checks.append(execute(out, 'archive', ['docker', 'save', '--output', str(out / 'image.tar'), tag]))
    transport = None
    if checks[-1]:
        try:
            transport = archive_identity(out / 'image.tar')
            checks.append(transport['config_digest'] == image_id and tag in transport['repo_tags'])
        except (OSError, ValueError, KeyError, tarfile.TarError):
            checks.append(False)
    if all(checks):
        write(out / 'subject.json', {'service': service, 'image_id': image_id,
            'archive_config_digest': transport['config_digest'], 'archive_tag': tag,
            'archive_sha256': sha(out / 'image.tar'), 'commit': context()['commit'],
            'python_base': images['python']['reference'] if service != 'neo4j' else None,
            'external_image': images['neo4j']['reference'] if service == 'neo4j' else None,
            'scope': 'actual patched image built from pinned upstream; no production release authorization'})
    seal(out)
    return all(checks)


def api_request(endpoint):
    token = os.environ.get('GH_TOKEN', '')
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + '/' + endpoint, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return {'http_status': response.status, 'data': json.load(response)}
    except urllib.error.HTTPError as error:
        return {'http_status': error.code, 'error': 'Evidence unavailable; no positive assertion inferred'}


def platform(out):
    commit = context()['commit']
    ruleset_details = []
    for name, endpoint in {
        'commit': 'commits/' + commit,
        'branch': 'branches/main',
        'protection': 'branches/main/protection',
        'rules': 'rules/branches/main',
        'rulesets': 'rulesets?includes_parents=true&per_page=100',
        'run': 'actions/runs/' + context()['run_id'],
        'pulls': 'commits/' + commit + '/pulls?per_page=100',
        'environments': 'environments?per_page=100',
    }.items():
        result = api_request(endpoint)
        write(out / (name + '.json'), result)
        if name == 'rulesets' and result['http_status'] == 200:
            for ruleset in result['data']:
                ruleset_id = ruleset.get('id')
                if isinstance(ruleset_id, int):
                    ruleset_details.append(api_request(
                        'rulesets/' + str(ruleset_id) + '?includes_parents=true'))
        if name == 'pulls' and result['http_status'] == 200:
            for pull in result['data']:
                write(out / ('reviews-' + str(pull['number']) + '.json'),
                      api_request('pulls/' + str(pull['number']) + '/reviews?per_page=100'))
    write(out / 'ruleset-details.json', ruleset_details)
    seal(out)
    return True  # Missing API permissions are explicit report gaps, not fake PASS.


def runtime(out):
    os.environ['L1_RUNTIME_TESTS'] = '1'
    os.environ['L1_EVIDENCE_DIR'] = str(out)
    ok = execute(out, 'runtime-tests', [sys.executable, '-m', 'pytest', 'quality_tests/test_runtime.py',
        '-q', '--junitxml=' + str(out / 'junit.xml')])
    seal(out)
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['source', 'image', 'platform', 'runtime'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--service', choices=SERVICES)
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('Output must be empty: retained files cannot become fresh evidence')
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        ok = image(args.out, args.service) if args.operation == 'image' else globals()[args.operation](args.out)
    finally:
        seal(args.out)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
