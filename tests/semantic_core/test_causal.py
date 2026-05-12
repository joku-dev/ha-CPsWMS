"""Tests for causal dependency graph."""

from semantic_core.causal.causal_dependency import CausalDependencyGraph


def test_causal_dependency_graph():
    graph = CausalDependencyGraph()
    graph.add_dependency("sensor.motion", "light.on")
    graph.add_dependency("light.on", "alarm.triggered")

    assert graph.get_effects("sensor.motion") == ["light.on"]
    assert graph.is_causal_path("sensor.motion", "alarm.triggered")
    assert graph.get_causal_chain("sensor.motion", "alarm.triggered") == ["sensor.motion", "light.on", "alarm.triggered"]
