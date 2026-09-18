"""Actual HTTP/Neo4j/container integration in an isolated, disposable CI network."""
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/l1'))
from evidence import context
from report import inspect_image, verify_bundle


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def request(url):
    try:
        with urllib.request.urlopen(url, timeout=80) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


@pytest.fixture(scope='module')
def runtime():
    if os.environ.get('L1_RUNTIME_TESTS') != '1':
        pytest.skip('Explicit L1_RUNTIME_TESTS=1 and disposable Docker required')
    out = Path(os.environ['L1_EVIDENCE_DIR'])
    out.mkdir(parents=True, exist_ok=True)
    subjects = {}
    for service, env in [('query-api', 'L1_QUERY_IMAGE_DIR'), ('neo4j', 'L1_NEO4J_IMAGE_DIR')]:
        image_dir = Path(os.environ[env])
        verify_bundle(image_dir, context())
        subject = inspect_image(image_dir, service)
        assert subject['commit'] == os.environ['GITHUB_SHA']
        docker('load', '--input', str(image_dir / 'image.tar'))
        assert docker('image', 'inspect', '--format', '{{.Id}}', subject['image_id']) == subject['image_id']
        subjects[service] = subject
    manifest = subjects['query-api']
    tag = 'l1-test-' + uuid.uuid4().hex[:12]
    db, api = tag + '-db', tag + '-api'
    password = 'isolated-test-password'
    neo4j_image = subjects['neo4j']['image_id']
    docker('network', 'create', tag)
    driver = None
    started = time.time()
    try:
        docker('run', '--pull=never', '-d', '--name', db, '--network', tag, '--network-alias', 'graph',
               '--security-opt', 'no-new-privileges:true', '--pids-limit', '512',
               '-p', '127.0.0.1::7687', '-e', 'NEO4J_AUTH=neo4j/' + password, neo4j_image)
        port = docker('port', db, '7687/tcp').split(':')[-1]
        driver = GraphDatabase.driver('bolt://127.0.0.1:' + port, auth=('neo4j', password), connection_timeout=3)
        for _ in range(90):
            try:
                driver.verify_connectivity()
                break
            except (Neo4jError, ServiceUnavailable, SessionExpired, OSError):
                time.sleep(2)
        else:
            pytest.fail('Disposable Neo4j did not become ready')
        with driver.session() as session:
            # Dedicated empty container; no production credentials, graph or volume.
            session.run("CREATE (i:Integration {domain:'test_zigbee'}), (e:Entity {entity_id:'sensor.l1', friendly_name:'L1 Sensor', state:'on'}), (c:Capability {name:'l1_temperature'}), (raw:RawEntity {raw_entity_id:'l1-raw'}), (canonical:CanonicalEntity {canonical_id:'l1-canonical'}), (e)-[:PROVIDED_BY]->(i), (e)-[:PROVIDES_CAPABILITY {confidence:0.95}]->(c), (e)-[:HAS_RAW_REPRESENTATION]->(raw), (raw)-[:RESOLVED_TO]->(canonical)").consume()
            assert session.run('MATCH (n) RETURN count(n) AS count').single()['count'] == 5
        docker('run', '--pull=never', '-d', '--name', api, '--network', tag, '-p', '127.0.0.1::8080',
               '--user', '65532:65532', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--pids-limit', '128',
               '-e', 'NEO4J_URI=bolt://graph:7687', '-e', 'NEO4J_USER=neo4j',
               '-e', 'NEO4J_PASSWORD=' + password, '-e', 'PYTHONDONTWRITEBYTECODE=1', manifest['image_id'])
        api_port = docker('port', api, '8080/tcp').split(':')[-1]
        base = 'http://127.0.0.1:' + api_port
        for _ in range(40):
            try:
                if request(base + '/health')[0] == 200:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            pytest.fail('Query API did not become ready')
        yield {'base': base, 'driver': driver, 'db': db}
    finally:
        # Evidence identifies actual images, not environment secrets from docker inspect.
        deployments = []
        for name in (api, db):
            result = subprocess.run(['docker', 'inspect', '--format', '{{.Image}}', name], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                deployments.append({'container': name, 'image_id': result.stdout.strip(), 'environment': 'ephemeral-ci'})
                logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True, check=False)
                (out / (('query-api' if name == api else 'neo4j') + '.log')).write_text(logs.stdout + logs.stderr)
        (out / 'deployment.json').write_text(json.dumps({'commit': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'], 'scope': 'ephemeral-ci; not production deployment or release authorization', 'started_unix': started, 'finished_unix': time.time(), 'containers': deployments}, indent=2) + '\n')
        if driver:
            driver.close()
        for name in (api, db):
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)
        subprocess.run(['docker', 'network', 'rm', tag], capture_output=True, check=False)


def test_health_uses_real_database(runtime):
    assert request(runtime['base'] + '/health') == (200, {'status': 'ok'})


def test_capabilities_return_seeded_content(runtime):
    status, result = request(runtime['base'] + '/api/capabilities?limit=1')
    assert status == 200
    assert len(result['capabilities']) == 1
    assert result['capabilities'][0]['capability'] == 'l1_temperature'
    assert result['capabilities'][0]['providers'][0]['entity_id'] == 'sensor.l1'


def test_integration_impact_is_computed_from_graph(runtime):
    status, result = request(runtime['base'] + '/api/what-if/integration/test_zigbee')
    assert status == 200
    assert [e['entity_id'] for e in result['impacted_entities']] == ['sensor.l1']


def test_entity_impact_returns_graph_identity(runtime):
    status, result = request(runtime['base'] + '/api/entities/sensor.l1/impact')
    assert status == 200 and result['entity_id'] == 'sensor.l1'
    assert result['provided_capabilities'][0]['capability'] == 'l1_temperature'


def test_unknown_route_returns_404(runtime):
    status, body = request(runtime['base'] + '/does-not-exist')
    assert status == 404 and body['error'] == 'not_found'


def test_query_parameters_do_not_inject_cypher(runtime):
    status, body = request(runtime['base'] + '/api/what-if/integration/%27%20OR%201%3D1')
    assert status == 200 and body['impacted_entities'] == []
    assert request(runtime['base'] + '/api/capabilities')[1]['capabilities'][0]['capability'] == 'l1_temperature'


def test_enrichment_writes_canonical_target(runtime, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'semantic-enrichment'))
    monkeypatch.delitem(sys.modules, 'config', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'unused')
    monkeypatch.setenv('NEO4J_PASSWORD', 'unused')
    monkeypatch.setenv('NEO4J_URI', 'bolt://127.0.0.1:1')
    monkeypatch.setenv('NEO4J_USER', 'neo4j')
    spec = importlib.util.spec_from_file_location('runtime_resolver', ROOT / 'semantic-enrichment/enrichment_target_resolver.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    query = module.EnrichmentTargetResolver('canonical_first').build_write_query('SET c.l1_quality = $quality', 'SET e.l1_quality = $quality')
    with runtime['driver'].session() as session:
        session.run(query, entity_id='sensor.l1', quality='measured').consume()
        row = session.run("MATCH (c:CanonicalEntity {canonical_id:'l1-canonical'}), (e:Entity {entity_id:'sensor.l1'}) RETURN c.l1_quality AS canonical, e.l1_quality AS legacy").single()
        assert row['canonical'] == 'measured' and row['legacy'] is None


def test_database_outage_is_visible_and_recovers(runtime):
    # This is last intentionally: stop only the disposable container created above.
    docker('stop', '--time', '5', runtime['db'])
    try:
        status, body = request(runtime['base'] + '/health')
        assert status == 500 and body['error'] == 'query_failed'
    finally:
        docker('start', runtime['db'])
    for _ in range(60):
        try:
            if request(runtime['base'] + '/health') == (200, {'status': 'ok'}):
                return
        except OSError:
            pass
        time.sleep(2)
    pytest.fail('API did not recover after database restart')
