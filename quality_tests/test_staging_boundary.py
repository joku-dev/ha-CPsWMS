"""Keep the prepared staging deployment isolated and least-privileged."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_staging_exposes_only_loopback_api_and_pins_runtime_selection():
    config = yaml.safe_load((ROOT / 'deployment/staging/compose.yml').read_text())
    assert set(config['services']) == {'query-api', 'neo4j'}
    assert config['services']['query-api']['ports'] == ['127.0.0.1:18080:8080']
    assert not config['services']['neo4j'].get('ports')
    assert config['networks']['staging']['internal'] is True
    for service in config['services'].values():
        assert service['pull_policy'] == 'never'
        assert service['image'].startswith('${') and ':?' in service['image']
        assert service['networks'] == ['staging']
        assert 'privileged' not in service and 'network_mode' not in service
        assert service['security_opt'] == ['no-new-privileges:true']
        assert service['pids_limit'] > 0
    query = config['services']['query-api']
    assert query['user'] == '65532:65532'
    assert query['read_only'] is True
    assert query['cap_drop'] == ['ALL']
    assert query['tmpfs'] == ['/tmp:rw,noexec,nosuid,nodev,size=64m']
    assert query['environment']['PYTHONDONTWRITEBYTECODE'] == '1'
    assert query['healthcheck']['test'][:3] == ['CMD', 'python', '-c']
    assert all('external' not in value for value in config['volumes'].values() if value)
