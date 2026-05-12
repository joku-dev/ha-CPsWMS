"""Tests for identity models."""

import pytest
from datetime import datetime

from semantic_core.identity.models import (
    SourceSystem, Observation, RawEntity, CanonicalEntity, Evidence, ResolutionDecision
)


def test_source_system():
    source = SourceSystem(
        source_id="ha",
        source_type="homeassistant",
        name="Home Assistant",
        trust_level=0.9,
        metadata={"version": "2023.1"}
    )
    assert source.source_id == "ha"
    assert source.trust_level == 0.9


def test_raw_entity():
    entity = RawEntity(
        raw_entity_id="ha_sensor_temp",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor",
        name="Living Room Temperature",
        domain="sensor",
        device_class="temperature",
        area="living_room",
        attributes={"unit": "°C"}
    )
    assert entity.entity_type == "sensor"
    assert entity.area == "living_room"


def test_canonical_entity():
    entity = CanonicalEntity(
        canonical_id="canonical.sensor.living_room.temperature",
        entity_type="sensor",
        canonical_name="Living Room Temperature",
        lifecycle_state="active",
        confidence_status="high",
        attributes={"unit": "°C"},
        created_at=datetime.now()
    )
    assert entity.canonical_id.startswith("canonical.")
    assert entity.lifecycle_state == "active"


def test_resolution_decision():
    evidence = [Evidence(
        evidence_id="ev1",
        evidence_type="name_similarity",
        description="Names match",
        score=1.0
    )]
    decision = ResolutionDecision(
        decision_id="dec1",
        raw_entity_id="raw1",
        canonical_id="can1",
        decision_type="resolved_existing",
        method="confidence",
        overall_confidence=0.95,
        evidence=evidence,
        review_required=False
    )
    assert decision.decision_type == "resolved_existing"
    assert not decision.review_required