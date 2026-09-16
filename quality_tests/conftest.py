"""Explicitly scoped application tests; never connect to a live HA or LLM service."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_component(monkeypatch):
    for key, value in {
        'HA_URL': 'http://127.0.0.1:1', 'HA_TOKEN': 'test-only',
        'NEO4J_URI': 'bolt://127.0.0.1:1', 'NEO4J_USER': 'neo4j',
        'NEO4J_PASSWORD': 'test-only', 'OPENAI_API_KEY': 'test-only',
    }.items():
        monkeypatch.setenv(key, value)
    loaded = []

    def load(directory, filename, name):
        # Services use separate top-level config modules in production.
        monkeypatch.delitem(sys.modules, 'config', raising=False)
        monkeypatch.syspath_prepend(str(ROOT / directory))
        spec = importlib.util.spec_from_file_location(name, ROOT / directory / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded.append(module)
        return module

    yield load
    for module in loaded:
        for attr in ('driver', 'neo4j_driver', 'openai_client'):
            client = getattr(module, attr, None)
            if client is not None:
                client.close()
