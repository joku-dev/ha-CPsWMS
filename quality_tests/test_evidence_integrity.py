"""Negative tests prevent stale, tampered and failed tool output becoming evidence."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/l1'))
from evidence import context, seal, sha, write
from report import build_report, execution_ok, inspect_image, junit, verify_bundle


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
    (tmp_path / 'image.tar').write_bytes(b'test archive')
    write(tmp_path / 'subject.json', {'service': 'query-api', 'image_id': image_id,
                                    'archive_sha256': sha(tmp_path / 'image.tar')})
    write(tmp_path / 'sbom.cyclonedx.json', {'bomFormat': 'CycloneDX', 'components': [{'name': 'python'}]})
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
