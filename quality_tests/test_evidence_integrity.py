"""Negative tests prevent stale, tampered and failed tool output becoming evidence."""
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/l1'))
from evidence import context, seal, sha, write
from report import (
    build_report,
    execution_ok,
    inspect_image,
    inspect_main_ruleset,
    junit,
    typed_evidence_manifest,
    verify_bundle,
)


def test_main_ruleset_requires_controls_and_no_bypass(tmp_path):
    write(tmp_path / 'rulesets.json', {'http_status': 200, 'data': [{'id': 42}]})
    ruleset = {
        'id': 42,
        'name': 'main protection',
        'enforcement': 'active',
        'bypass_actors': [],
        'conditions': {'ref_name': {'include': ['refs/heads/main'], 'exclude': []}},
        'rules': [
            {'type': 'deletion'},
            {'type': 'non_fast_forward'},
            {'type': 'pull_request', 'parameters': {'required_approving_review_count': 0}},
            {'type': 'required_status_checks', 'parameters': {'required_status_checks': [
                {'context': name} for name in (
                    'validate-ubuntu', 'validate-debian', 'DevSecOps Governance',
                    'Architecture Runtime Governance', 'L1 coverage report')]}},
        ],
    }
    write(tmp_path / 'ruleset-details.json', [{'http_status': 200, 'data': ruleset}])
    assert inspect_main_ruleset(tmp_path)['id'] == 42
    ruleset['bypass_actors'] = [{'actor_type': 'RepositoryRole', 'actor_id': 5}]
    write(tmp_path / 'ruleset-details.json', [{'http_status': 200, 'data': ruleset}])
    assert inspect_main_ruleset(tmp_path) is None


def test_changed_raw_bytes_are_rejected(tmp_path):
    (tmp_path / 'raw.json').write_text('{"measured":true}')
    seal(tmp_path)
    (tmp_path / 'raw.json').write_text('{"measured":false}')
    with pytest.raises(ValueError, match='Changed/missing'):
        verify_bundle(tmp_path, context())


def test_stale_run_binding_is_rejected(tmp_path):
    (tmp_path / 'raw.json').write_text('{}')
    seal(tmp_path)
    wrong = {**context(), 'run_id': 'other-run'}
    with pytest.raises(ValueError, match='Context mismatch'):
        verify_bundle(tmp_path, wrong)


def test_unmanifested_evidence_is_rejected(tmp_path):
    seal(tmp_path)
    (tmp_path / 'added.json').write_text('{}')
    with pytest.raises(ValueError, match='Unmanifested'):
        verify_bundle(tmp_path, context())


def test_tool_crash_is_not_a_finding(tmp_path):
    write(tmp_path / 'bandit.execution.json', {'exit_code': 2})
    assert not execution_ok(tmp_path, 'bandit', (0, 1))


def test_skipped_tests_are_not_passes(tmp_path):
    path = tmp_path / 'junit.xml'
    path.write_text('<testsuite><testcase name="unexecuted"><skipped/></testcase></testsuite>')
    assert junit(path)[0]['status'] == 'skipped'


def test_empty_junit_is_not_evidence(tmp_path):
    path = tmp_path / 'junit.xml'
    path.write_text('<testsuite tests="0"/>')
    with pytest.raises(ValueError, match='Empty JUnit'):
        junit(path)


def test_missing_outputs_never_satisfy_controls(tmp_path):
    result = build_report(tmp_path, context())
    assert len(result['controls']) == 16
    assert all(row['coverage'] == 'gap' for row in result['controls'])
    assert result['official_compliance_result'] is False
    assert result['production_approval'] is False
    assert len(result['evidence_errors']) == 8


@pytest.fixture
def image_evidence(tmp_path):
    image_id = 'sha256:' + 'a' * 64
    archive_tag = 'l1-query-api:test'
    config = b'{"architecture":"amd64","os":"linux"}'
    image_id = 'sha256:' + hashlib.sha256(config).hexdigest()
    manifest = json.dumps([{'Config': 'blobs/sha256/' + image_id.removeprefix('sha256:'),
                            'RepoTags': [archive_tag], 'Layers': []}]).encode()
    with tarfile.open(tmp_path / 'image.tar', 'w') as archive:
        for name, content in [('manifest.json', manifest),
                              ('blobs/sha256/' + image_id.removeprefix('sha256:'), config)]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    write(tmp_path / 'subject.json', {'service': 'query-api', 'image_id': image_id,
                                    'archive_config_digest': image_id, 'archive_tag': archive_tag,
                                    'archive_sha256': sha(tmp_path / 'image.tar')})
    write(tmp_path / 'sbom.cyclonedx.json', {'bomFormat': 'CycloneDX', 'components': [{'name': 'python'}], 'metadata': {'component': {'type': 'container', 'properties': [{'name': 'aquasecurity:trivy:ImageID', 'value': image_id}]}}})
    write(tmp_path / 'vulnerabilities.json', {'ArtifactID': 'sha256:' + 'b' * 64,
        'Metadata': {'ImageID': image_id}, 'Results': [{'Target': 'os', 'Class': 'os-pkgs'}]})
    for name in ('build', 'sbom', 'vulnerabilities', 'archive'):
        write(tmp_path / (name + '.execution.json'), {'exit_code': 0})
    return tmp_path


def test_trivy_070_binds_image_metadata_not_repository_artifact_id(image_evidence):
    assert inspect_image(image_evidence, 'query-api')['components'] == 1


def test_other_image_scan_is_rejected(image_evidence):
    write(image_evidence / 'vulnerabilities.json', {'ArtifactID': 'sha256:' + 'a' * 64,
        'Metadata': {'ImageID': 'sha256:' + 'c' * 64}, 'Results': [{'Target': 'os'}]})
    with pytest.raises(ValueError, match='another image'):
        inspect_image(image_evidence, 'query-api')


def test_archive_without_declared_transport_tag_is_rejected(image_evidence):
    subject = json.loads((image_evidence / 'subject.json').read_text())
    subject['archive_tag'] = 'l1-query-api:other'
    write(image_evidence / 'subject.json', subject)
    with pytest.raises(ValueError, match='transport identity'):
        inspect_image(image_evidence, 'query-api')


def test_empty_component_template_is_rejected(image_evidence):
    write(image_evidence / 'sbom.cyclonedx.json', {'bomFormat': 'CycloneDX', 'components': []})
    with pytest.raises(ValueError, match='no measured components'):
        inspect_image(image_evidence, 'query-api')


def test_partial_platform_capture_remains_explicit_gap(tmp_path):
    platform = tmp_path / 'platform'
    platform.mkdir()
    seal(platform)
    result = build_report(tmp_path, context())
    assert 'platform' in result['evidence_errors']
    assert result['controls'][1]['coverage'] == 'gap'


def test_typed_manifest_requires_and_binds_all_five_images(tmp_path):
    report = {
        'context': {key: context()[key] for key in ('repository', 'commit', 'run_id', 'attempt', 'event')},
        'evidence_errors': {},
        'images': {},
    }
    for service in ('ha-sync', 'semantic-enrichment', 'query-api', 'world-model-chat', 'neo4j'):
        subject = tmp_path / ('image-' + service) / 'subject.json'
        subject.parent.mkdir()
        write(subject, {'archive_sha256': service.replace('-', '0').ljust(64, '0')[:64]})
        write(subject.parent / 'sbom.cyclonedx.json', {'bomFormat': 'CycloneDX', 'components': [{'name': service}]})
        report['images'][service] = {'image_id': 'sha256:' + service.replace('-', '0').ljust(64, '0')[:64], 'components': 1}
    manifest = typed_evidence_manifest(report, tmp_path)
    assert manifest['profile'] == 'ha-cpswms-container-evidence-v2'
    assert manifest['enforcement'] == 'report-only'
    assert set(manifest['images']) == set(report['images'])
    assert manifest['images']['query-api']['artifact_name'] == 'l1-image-query-api'
    assert len(manifest['images']['query-api']['sbom_sha256']) == 64
    assert manifest['images']['query-api']['sbom_component_count'] == 1

    incomplete = {**report, 'images': dict(report['images'])}
    incomplete['images'].pop('neo4j')
    assert typed_evidence_manifest(incomplete, tmp_path) is None
    failed = {**report, 'evidence_errors': {'image-neo4j': 'failed'}}
    assert typed_evidence_manifest(failed, tmp_path) is None


def test_sbom_for_another_image_is_rejected(image_evidence):
    write(image_evidence / 'sbom.cyclonedx.json', {'bomFormat': 'CycloneDX',
        'components': [{'name': 'python'}], 'metadata': {'component': {'type': 'container',
        'properties': [{'name': 'aquasecurity:trivy:ImageID', 'value': 'sha256:' + 'c' * 64}]}}})
    with pytest.raises(ValueError, match='SBOM bound to another image'):
        inspect_image(image_evidence, 'query-api')
