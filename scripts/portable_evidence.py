#!/usr/bin/env python3
"""Bind a real locked-dependency inventory and Trivy scan to a source archive.

This is dependency evidence for pipeline-l1, not an image or application test.
Raw scanner outputs are retained; missing/unknown data is a technical error.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

from l1.evidence import locked_packages

LOCK = 'quality/application-requirements.lock'
ARCHIVE_PATHS = ('ha-sync', 'query-api', 'semantic-enrichment', 'semantic_core',
                 'world-model-chat', 'scripts', 'tests', 'quality',
                 'docker-compose.yml', 'README.md')
SEVERITIES = ('none', 'low', 'medium', 'high', 'critical')
TRIVY_VERSION = '0.70.0'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def git(checkout, *arguments):
    return subprocess.check_output(['git', '-C', str(checkout), *arguments])


def prepare(checkout, output):
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    revision = git(checkout, 'rev-parse', '--verify', 'HEAD').decode().strip()
    lock = git(checkout, 'show', f'{revision}:{LOCK}')
    if (checkout / LOCK).read_bytes() != lock:
        raise ValueError('Working dependency lock differs from tested revision')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'inventory').mkdir()
    (output / 'raw').mkdir()
    (output / 'application-requirements.lock').write_bytes(lock)
    packages = locked_packages(output / 'application-requirements.lock')
    requirements = ''.join(f'{name}=={version}\n' for name, version in sorted(packages.items()))
    (output / 'inventory/requirements.txt').write_text(requirements)
    archive = git(checkout, 'archive', '--format=tar', revision, *ARCHIVE_PATHS)
    (output / 'application-source.tar.gz').write_bytes(gzip.compress(archive, mtime=0))
    write(output / 'build.json', {
        'commit': revision, 'artifact_sha256': digest(output / 'application-source.tar.gz'),
        'lock_sha256': digest(output / 'application-requirements.lock'),
        'inventory_sha256': digest(output / 'inventory/requirements.txt'),
        'scope': 'locked-python-dependencies-in-source-archive',
    })


def normalize(checkout, output):
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    # Never replace an earlier normalized assessment after a retry/error.
    if any((output / name).exists() for name in ('sbom.cyclonedx.json', 'vulnerability-scan.json')):
        raise ValueError('Normalized evidence already exists')
    build = read(output / 'build.json')
    artifact = output / 'application-source.tar.gz'
    if (git(checkout, 'rev-parse', 'HEAD').decode().strip() != build['commit']
            or digest(artifact) != build['artifact_sha256']
            or digest(output / 'application-requirements.lock') != build['lock_sha256']
            or digest(output / 'inventory/requirements.txt') != build['inventory_sha256']):
        raise ValueError('Changed source artifact or inventory')
    lock = (output / 'application-requirements.lock').read_bytes()
    if git(checkout, 'show', f"{build['commit']}:{LOCK}") != lock:
        raise ValueError('Lock differs from tested commit')
    with tarfile.open(artifact, 'r:gz') as archive:
        member = archive.getmember(LOCK)
        if not member.isfile() or archive.extractfile(member).read() != lock:
            raise ValueError('Archive contains another dependency lock')
    expected = set(locked_packages(output / 'application-requirements.lock').items())
    sbom = read(output / 'raw/sbom.cyclonedx.json')
    if sbom.get('bomFormat') != 'CycloneDX' or not isinstance(sbom.get('components'), list):
        raise ValueError('Missing real CycloneDX inventory')
    observed = {(row['name'].lower().replace('_', '-'), row['version'])
                for row in sbom['components'] if row.get('type') == 'library'}
    if not expected or observed != expected:
        raise ValueError('SBOM does not cover exact locked dependency set')
    version = read(output / 'raw/trivy-version.json')
    if version.get('Version') != TRIVY_VERSION:
        raise ValueError('Unexpected scanner version')
    scan = read(output / 'raw/trivy-scan.json')
    if scan.get('ArtifactType') != 'cyclonedx' or not isinstance(scan.get('Results'), list):
        raise ValueError('Missing real Trivy SBOM scan')
    scanned = {(row['Name'].lower().replace('_', '-'), row['Version'])
               for result in scan['Results'] for row in result.get('Packages', [])}
    if scanned != expected:
        raise ValueError('Scan does not cover exact locked dependency set')
    findings = []
    for result in scan['Results']:
        for row in result.get('Vulnerabilities', []):
            severity = str(row.get('Severity', '')).lower()
            if severity not in SEVERITIES[1:]:
                raise ValueError('Unknown vulnerability severity; no safe normalization')
            identity = row.get('VulnerabilityID')
            if not isinstance(identity, str) or not identity.strip():
                raise ValueError('Missing vulnerability identity')
            package = row.get('PkgName', '').lower().replace('_', '-')
            if (package, row.get('InstalledVersion')) not in expected:
                raise ValueError('Finding refers to another dependency')
            findings.append({'id': identity, 'severity': severity, 'package': package,
                             'installed_version': row['InstalledVersion'],
                             'fixed_version': row.get('FixedVersion', ''),
                             'description': row.get('Title', ''),
                             'severity_source': row.get('SeveritySource')})
    maximum = max((SEVERITIES.index(row['severity']) for row in findings), default=0)
    normalized = {
        'scanner': 'trivy', 'scanner_version': TRIVY_VERSION,
        'artifact_sha256': build['artifact_sha256'],
        'max_severity': SEVERITIES[maximum], 'findings': findings,
        'scope': build['scope'], 'dependency_lock_sha256': build['lock_sha256'],
        'raw_scan_sha256': digest(output / 'raw/trivy-scan.json'),
        'raw_sbom_sha256': digest(output / 'raw/sbom.cyclonedx.json'),
        'summary': {'dependency_count': len(expected), 'finding_count': len(findings)},
    }
    metadata = sbom.setdefault('metadata', {})
    metadata['component'] = {**metadata.get('component', {}),
        'type': 'application', 'name': 'ha-CPsWMS-source', 'version': build['commit'],
        'hashes': [{'alg': 'SHA-256', 'content': build['artifact_sha256']}],
        'properties': [{'name': 'axiom:inventory-scope', 'value': build['scope']},
                       {'name': 'axiom:dependency-lock-sha256', 'value': build['lock_sha256']}],
    }
    write(output / 'sbom.cyclonedx.json', sbom)
    write(output / 'vulnerability-scan.json', normalized)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'normalize'))
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    {'prepare': prepare, 'normalize': normalize}[args.action](args.checkout, args.output)


if __name__ == '__main__':
    main()
