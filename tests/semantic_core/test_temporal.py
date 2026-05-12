"""Tests for temporal modeling and state evolution."""

from datetime import datetime, timedelta
from semantic_core.temporal.temporal_event_model import TemporalEventModel
from semantic_core.temporal.state_evolution import StateEvolution, StateTransition
from semantic_core.identity.models import Observation


def test_temporal_event_model():
    timeline = TemporalEventModel()
    obs = Observation(
        observation_id="obs1",
        source_id="homeassistant",
        timestamp=datetime.utcnow(),
        observation_type="state_update",
        raw_payload={"value": 1},
    )

    timeline.add_observation(obs)
    events = timeline.get_events()
    assert len(events) == 1
    assert events[0].observation_id == "obs1"


def test_state_evolution_transitions():
    evolution = StateEvolution()
    transition = StateTransition(
        source_entity_id="sensor.livingroom_temperature",
        previous_state="19",
        next_state="20",
        timestamp=datetime.utcnow(),
        reason="scheduled update",
    )
    evolution.add_transition(transition)

    transitions = evolution.get_transitions_for_entity("sensor.livingroom_temperature")
    assert len(transitions) == 1
    assert transitions[0].reason == "scheduled update"
