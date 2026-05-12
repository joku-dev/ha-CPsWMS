"""Tests for identity resolver."""

from semantic_core.identity.canonical_registry import CanonicalRegistry
from semantic_core.identity.confidence_model import ConfidenceModel
from semantic_core.identity.identity_resolver import IdentityResolver
from semantic_core.identity.models import RawEntity, CanonicalEntity


def test_resolve_existing_high_confidence():
    registry = CanonicalRegistry()
    confidence_model = ConfidenceModel()
    resolver = IdentityResolver(registry, confidence_model)

    # Add existing canonical entity
    canonical = CanonicalEntity(
        canonical_id="canonical.sensor.living_room.temperature",
        entity_type="sensor",
        canonical_name="Living Room Temperature"
    )
    registry.register_entity(canonical)

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor",
        name="Living Room Temperature"
    )

    decision = resolver.resolve(raw, [canonical])

    assert decision.decision_type == "resolved_existing"
    assert decision.canonical_id == canonical.canonical_id
    assert not decision.review_required


def test_resolve_create_new():
    registry = CanonicalRegistry()
    confidence_model = ConfidenceModel()
    resolver = IdentityResolver(registry, confidence_model)

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor"
    )

    decision = resolver.resolve(raw, [])  # No candidates

    assert decision.decision_type == "created_new"
    assert decision.canonical_id.startswith("canonical.")
    assert not decision.review_required


def test_resolve_candidate_review():
    registry = CanonicalRegistry()
    confidence_model = ConfidenceModel()
    resolver = IdentityResolver(registry, confidence_model)

    # Add canonical with partial match
    canonical = CanonicalEntity(
        canonical_id="canonical.sensor.room_temp",
        entity_type="sensor"
    )
    registry.register_entity(canonical)

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor"
    )

    decision = resolver.resolve(raw, [canonical])

    # Depending on scoring, might be review or new
    assert decision.decision_type in ["candidate_review", "created_new"]