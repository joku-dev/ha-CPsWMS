"""Tests for confidence model."""

from semantic_core.identity.confidence_model import ConfidenceModel
from semantic_core.identity.models import RawEntity, CanonicalEntity


def test_confidence_calculation():
    model = ConfidenceModel()

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor",
        name="Living Room Temperature",
        attributes={"device_class": "temperature"}
    )

    canonical = CanonicalEntity(
        canonical_id="canonical.sensor.living_room.temperature",
        entity_type="sensor",
        canonical_name="Living Room Temperature",
        attributes={"device_class": "temperature"}
    )

    confidence, evidence = model.calculate_confidence(raw, canonical)

    assert 0.0 <= confidence <= 1.0
    assert len(evidence) == 6  # All dimensions
    assert any(e.evidence_type == "name_similarity" for e in evidence)


def test_low_confidence():
    model = ConfidenceModel()

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor"
    )

    canonical = CanonicalEntity(
        canonical_id="canonical.binary_sensor.garage_motion",
        entity_type="binary_sensor"
    )

    confidence, _ = model.calculate_confidence(raw, canonical)

    assert confidence < 0.5  # Should be low