"""Data models for the Canonical Entity Resolution & Semantic Identity Layer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SourceSystem:
    """Represents a data source system."""
    source_id: str
    source_type: str
    name: str
    trust_level: float
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class Observation:
    """Represents a concrete measurement or detection at a point in time."""
    observation_id: str
    source_id: str
    timestamp: Optional[datetime] = None
    observation_type: str = ""
    raw_payload: Dict[str, any] = field(default_factory=dict)
    attributes: Dict[str, any] = field(default_factory=dict)


@dataclass
class RawEntity:
    """Represents a source-specific entity."""
    raw_entity_id: str
    source_id: str
    source_entity_id: str
    entity_type: Optional[str] = None
    name: Optional[str] = None
    domain: Optional[str] = None
    device_class: Optional[str] = None
    area: Optional[str] = None
    attributes: Dict[str, any] = field(default_factory=dict)


@dataclass
class CanonicalEntity:
    """Represents a stable semantic identity in the world model."""
    canonical_id: str
    entity_type: str
    canonical_name: Optional[str] = None
    lifecycle_state: str = "active"
    confidence_status: str = "unknown"
    attributes: Dict[str, any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Evidence:
    """Represents evidence supporting a resolution decision."""
    evidence_id: str
    evidence_type: str
    description: str
    score: float
    source: Optional[str] = None
    details: Dict[str, any] = field(default_factory=dict)


@dataclass
class ResolutionDecision:
    """Represents a decision on how to resolve a raw entity."""
    decision_id: str
    raw_entity_id: str
    decision_type: str  # 'resolved_existing', 'created_new', 'candidate_review', 'rejected'
    method: str
    overall_confidence: float
    canonical_id: Optional[str] = None
    evidence: List[Evidence] = field(default_factory=list)
    review_required: bool = False
    created_at: Optional[datetime] = None