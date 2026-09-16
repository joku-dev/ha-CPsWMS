"""Keep the prepared staging deployment isolated until a real host is selected."""
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
    assert all('external' not in value for value in config['volumes'].values() if value)
