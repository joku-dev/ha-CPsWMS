"""Identity resolver for mapping raw entities to canonical entities."""

from datetime import datetime
from typing import List, Optional

from .canonical_registry import CanonicalRegistry
from .confidence_model import ConfidenceModel
from .models import CanonicalEntity, RawEntity, ResolutionDecision


class IdentityResolver:
    """Resolves raw entities to canonical entities using confidence scoring."""

    def __init__(self, registry: CanonicalRegistry, confidence_model: ConfidenceModel):
        self.registry = registry
        self.confidence_model = confidence_model

    def resolve(
        self,
        raw_entity: RawEntity,
        candidates: List[CanonicalEntity],
        source_trust: float = 0.8
    ) -> ResolutionDecision:
        """
        Resolve a raw entity to a canonical entity.

        Args:
            raw_entity: The raw entity to resolve.
            candidates: List of candidate canonical entities.
            source_trust: Trust level of the source.

        Returns:
            ResolutionDecision with the outcome.
        """
        if not candidates:
            # No candidates, create new
            new_entity = self.registry.create_new_entity(raw_entity)
            return ResolutionDecision(
                decision_id=f"decision_{raw_entity.raw_entity_id}_{datetime.now().isoformat()}",
                raw_entity_id=raw_entity.raw_entity_id,
                canonical_id=new_entity.canonical_id,
                decision_type="created_new",
                method="no_candidates",
                overall_confidence=0.0,
                evidence=[],
                review_required=False,
                created_at=datetime.now()
            )

        # Score all candidates
        scored_candidates = []
        for candidate in candidates:
            confidence, evidence = self.confidence_model.calculate_confidence(
                raw_entity, candidate, source_trust
            )
            scored_candidates.append((candidate, confidence, evidence))

        # Sort by confidence descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        best_candidate, best_confidence, best_evidence = scored_candidates[0]

        # Determine decision type based on thresholds
        if best_confidence >= 0.85:
            decision_type = "resolved_existing"
            review_required = False
        elif 0.60 <= best_confidence < 0.85:
            decision_type = "candidate_review"
            review_required = True
        else:
            # Create new entity
            new_entity = self.registry.create_new_entity(raw_entity)
            return ResolutionDecision(
                decision_id=f"decision_{raw_entity.raw_entity_id}_{datetime.now().isoformat()}",
                raw_entity_id=raw_entity.raw_entity_id,
                canonical_id=new_entity.canonical_id,
                decision_type="created_new",
                method="low_confidence",
                overall_confidence=best_confidence,
                evidence=best_evidence,
                review_required=False,
                created_at=datetime.now()
            )

        return ResolutionDecision(
            decision_id=f"decision_{raw_entity.raw_entity_id}_{datetime.now().isoformat()}",
            raw_entity_id=raw_entity.raw_entity_id,
            canonical_id=best_candidate.canonical_id,
            decision_type=decision_type,
            method="confidence_scoring",
            overall_confidence=best_confidence,
            evidence=best_evidence,
            review_required=review_required,
            created_at=datetime.now()
        )