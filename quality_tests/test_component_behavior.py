"""Deterministic component tests. No live LLM or Home Assistant claim."""
import json

import pytest


def test_sync_preserves_structured_state(load_component):
    sync = load_component('ha-sync', 'sync.py', 'ha_sync_test')
    assert json.loads(sync.normalize_value({'state': ['on', 'off']})) == {'state': ['on', 'off']}
    assert sync.normalize_value(None) is None
    assert sync.normalize_value(23) == '23'


def test_sync_finds_nested_entity_references(load_component):
    sync = load_component('ha-sync', 'sync.py', 'ha_sync_test')
    assert sync.extract_entity_ids_from_object({'trigger': ['sensor.temperature', {'entity': 'light.kitchen'}]}) == {'sensor.temperature', 'light.kitchen'}


def test_sync_deduplicates_integration_domains(load_component):
    sync = load_component('ha-sync', 'sync.py', 'ha_sync_test')
    rows = sync.derive_integrations_from_states([{'entity_id': 'light.a'}, {'entity_id': 'light.b'}, {'entity_id': 'sensor.c'}, {'entity_id': 'invalid'}])
    assert {r['domain'] for r in rows} == {'light', 'sensor'}
    assert len(rows) == 2


@pytest.mark.parametrize('cypher', [
    'MATCH (n) DELETE n RETURN n LIMIT 1',
    'MATCH (n) RETURN n LIMIT 1; MATCH (m) RETURN m LIMIT 1',
    'MATCH (n) RETURN n',
    'CALL dbms.components() RETURN 1 LIMIT 1',
])
def test_chat_rejects_unsafe_queries(load_component, cypher):
    chat = load_component('world-model-chat', 'app.py', 'chat_test')
    generated = chat.GeneratedCypher(intent='test', cypher=cypher, parameters={}, confidence=0.99, reason='test')
    with pytest.raises(chat.HTTPException) as exc:
        chat.validate_cypher(generated)
    assert exc.value.status_code == 422


def test_chat_accepts_bounded_read_and_rejects_low_confidence(load_component):
    chat = load_component('world-model-chat', 'app.py', 'chat_test')
    generated = chat.GeneratedCypher(intent='test', cypher='MATCH (n) RETURN n LIMIT $limit', parameters={'limit': 5}, confidence=0.99, reason='test')
    assert chat.validate_cypher(generated) == generated.cypher
    generated.confidence = 0
    with pytest.raises(chat.HTTPException):
        chat.validate_cypher(generated)


def test_chat_rejects_nested_parameters(load_component):
    chat = load_component('world-model-chat', 'app.py', 'chat_test')
    with pytest.raises(chat.HTTPException):
        chat.bound_parameters({'nested': {'query': 'bad'}})
    assert len(chat.bound_parameters({'values': list(range(1000))})['values']) == chat.MAX_QUERY_ROWS


def test_query_limits_are_bounded(load_component):
    api = load_component('query-api', 'app.py', 'query_test')
    assert api.parse_limit({'limit': ['-100']}) == 1
    assert api.parse_limit({'limit': ['999999']}) == api.MAX_LIMIT
    assert api.parse_limit({'limit': ['invalid']}) == api.DEFAULT_LIMIT
