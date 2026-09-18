"""Data models for the Canonical Entity Resolution & Semantic Identity Layer."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceSystem:
    """Represents a data source system."""
    source_id: str
    source_type: str
    name: str
    trust_level: float
    metadata: dict[str, any] = field(default_factory=dict)


@dataclass
class Observation:
    """Represents a concrete measurement or detection at a point in time."""
    observation_id: str
    source_id: str
    timestamp: datetime | None = None
    observation_type: str = ""
    raw_payload: dict[str, any] = field(default_factory=dict)
    attributes: dict[str, any] = field(default_factory=dict)


@dataclass
class RawEntity:
    """Represents a source-specific entity."""
    raw_entity_id: str
    source_id: str
    source_entity_id: str
    entity_type: str | None = None
    name: str | None = None
    domain: str | None = None
    device_class: str | None = None
    area: str | None = None
    attributes: dict[str, any] = field(default_factory=dict)


@dataclass
class CanonicalEntity:
    """Represents a stable semantic identity in the world model."""
    canonical_id: str
    entity_type: str
    canonical_name: str | None = None
    lifecycle_state: str = "active"
    confidence_status: str = "unknown"
    attributes: dict[str, any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Evidence:
    """Represents evidence supporting a resolution decision."""
    evidence_id: str
    evidence_type: str
    description: str
    score: float
    source: str | None = None
    details: dict[str, any] = field(default_factory=dict)


@dataclass
class ResolutionDecision:
    """Represents a decision on how to resolve a raw entity."""
    decision_id: str
    raw_entity_id: str
    decision_type: str  # 'resolved_existing', 'created_new', 'candidate_review', 'rejected'
    method: str
    overall_confidence: float
    canonical_id: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    review_required: bool = False
    created_at: datetime | None = None