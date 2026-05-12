"""Tests for resolution pipeline."""

from semantic_core.identity.canonical_registry import CanonicalRegistry
from semantic_core.identity.confidence_model import ConfidenceModel
from semantic_core.identity.identity_resolver import IdentityResolver
from semantic_core.identity.resolution_pipeline import ResolutionPipeline
from semantic_core.identity.models import RawEntity


def test_pipeline_process():
    registry = CanonicalRegistry()
    confidence_model = ConfidenceModel()
    resolver = IdentityResolver(registry, confidence_model)
    pipeline = ResolutionPipeline(registry, resolver)

    raw = RawEntity(
        raw_entity_id="raw1",
        source_id="ha",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor",
        name="Living Room Temperature"
    )

    decision = pipeline.process(raw)

    assert decision.raw_entity_id == raw.raw_entity_id
    assert decision.decision_type in ["created_new", "resolved_existing", "candidate_review"]