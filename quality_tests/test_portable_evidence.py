"""Synthetic producer contract tests; not live vulnerability evidence."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from portable_evidence import ARCHIVE_PATHS, normalize, prepare, read, write


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        self.root.mkdir()
        self.output = Path(self.temp.name) / 'evidence'
        for name in ARCHIVE_PATHS:
            target = self.root / name
            if '.' in name:
                target.write_text('synthetic source fixture\n')
            else:
                target.mkdir()
                (target / 'fixture.py').write_text('# synthetic source fixture\n')
        (self.root / 'quality/application-requirements.lock').write_text(
            'fixture-package==1.0 \\\n    --hash=sha256:' + 'a' * 64 + '\n')
        for command in (['init', '-q'], ['add', '.'],
                        ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                         'commit', '-qm', 'Synthetic producer fixture']):
            subprocess.run(['git', '-C', str(self.root), *command], check=True,
                           capture_output=True)
        prepare(self.root, self.output)
        self.sbom = {'bomFormat': 'CycloneDX', 'specVersion': '1.5',
                     'components': [{'type': 'library', 'name': 'fixture-package', 'version': '1.0'}]}
        self.scan = {'ArtifactType': 'cyclonedx', 'Results': [{
            'Packages': [{'Name': 'fixture-package', 'Version': '1.0'}],
            'Vulnerabilities': [{'VulnerabilityID': 'FIXTURE-1', 'Severity': 'CRITICAL',
                                 'PkgName': 'fixture-package', 'InstalledVersion': '1.0'}]}]}
        write(self.output / 'raw/trivy-version.json', {'Version': '0.70.0'})
        self.raw()

    def raw(self):
        write(self.output / 'raw/sbom.cyclonedx.json', self.sbom)
        write(self.output / 'raw/trivy-scan.json', self.scan)

    def test_binds_both_subjects_and_retains_critical_finding(self):
        original = (self.output / 'raw/trivy-scan.json').read_bytes()
        normalize(self.root, self.output)
        build = read(self.output / 'build.json')
        scan = read(self.output / 'vulnerability-scan.json')
        sbom = read(self.output / 'sbom.cyclonedx.json')
        self.assertEqual(scan['artifact_sha256'], build['artifact_sha256'])
        self.assertEqual(sbom['metadata']['component']['hashes'][0]['content'], build['artifact_sha256'])
        self.assertEqual(scan['max_severity'], 'critical')
        self.assertEqual(scan['summary']['finding_count'], 1)
        self.assertEqual((self.output / 'raw/trivy-scan.json').read_bytes(), original)

    def test_empty_findings_need_complete_package_inventory(self):
        self.scan['Results'][0]['Vulnerabilities'] = []
        self.raw()
        normalize(self.root, self.output)
        self.assertEqual(read(self.output / 'vulnerability-scan.json')['max_severity'], 'none')

    def test_rejects_unknown_missing_or_invalid_severity(self):
        for severity in ('UNKNOWN', '', 'invented'):
            self.scan['Results'][0]['Vulnerabilities'][0]['Severity'] = severity
            self.raw()
            with self.assertRaisesRegex(ValueError, 'Unknown vulnerability severity'):
                normalize(self.root, self.output)

    def test_rejects_missing_scan_or_sbom_packages(self):
        for target in ('sbom', 'scan'):
            with self.subTest(target=target):
                original = deepcopy(self.sbom if target == 'sbom' else self.scan)
                if target == 'sbom':
                    self.sbom['components'] = []
                else:
                    self.scan['Results'][0]['Packages'] = []
                self.raw()
                with self.assertRaisesRegex(ValueError, 'exact locked dependency set'):
                    normalize(self.root, self.output)
                if target == 'sbom':
                    self.sbom = original
                else:
                    self.scan = original

    def test_rejects_changed_artifact(self):
        with (self.output / 'application-source.tar.gz').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed source artifact'):
            normalize(self.root, self.output)

    def test_rejects_changed_inventory_and_lock(self):
        for name in ('inventory/requirements.txt', 'application-requirements.lock'):
            path = self.output / name
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.assertRaisesRegex(ValueError, 'Changed source artifact or inventory'):
                normalize(self.root, self.output)
            path.write_bytes(original)

    def test_rejects_scanner_error_object(self):
        write(self.output / 'raw/trivy-scan.json', {'error': 'synthetic tool crash'})
        with self.assertRaisesRegex(ValueError, 'Missing real Trivy'):
            normalize(self.root, self.output)

    def test_rejects_wrong_scanner_version(self):
        write(self.output / 'raw/trivy-version.json', {'Version': 'dev'})
        with self.assertRaisesRegex(ValueError, 'Unexpected scanner version'):
            normalize(self.root, self.output)

    def test_rejects_another_package_in_findings(self):
        self.scan['Results'][0]['Vulnerabilities'][0]['InstalledVersion'] = '2.0'
        self.raw()
        with self.assertRaisesRegex(ValueError, 'another dependency'):
            normalize(self.root, self.output)

    def test_does_not_replace_existing_output(self):
        normalize(self.root, self.output)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            normalize(self.root, self.output)
        with self.assertRaises(FileExistsError):
            prepare(self.root, self.output)

    def test_rejects_duplicate_json_keys(self):
        (self.output / 'raw/trivy-scan.json').write_text('{"Results":[],"Results":[]}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            normalize(self.root, self.output)

    def test_refuses_uncommitted_dependency_lock(self):
        with (self.root / 'quality/application-requirements.lock').open('a') as stream:
            stream.write('# changed\n')
        with self.assertRaisesRegex(ValueError, 'differs from tested revision'):
            prepare(self.root, self.output.parent / 'another-evidence')


if __name__ == '__main__':
    unittest.main()
