"""Confidence scoring model for entity resolution."""

from typing import Dict, List, Tuple

from .models import CanonicalEntity, Evidence, RawEntity


class ConfidenceModel:
    """Calculates confidence scores for entity resolution."""

    def __init__(self):
        # Weights for different similarity dimensions
        self.weights = {
            'identity_similarity': 0.30,
            'name_similarity': 0.25,
            'type_similarity': 0.15,
            'location_similarity': 0.15,
            'attribute_similarity': 0.10,
            'source_trust': 0.05
        }

    def calculate_confidence(
        self,
        raw_entity: RawEntity,
        candidate: CanonicalEntity,
        source_trust: float = 0.8
    ) -> Tuple[float, List[Evidence]]:
        """
        Calculate overall confidence score and evidence.

        Args:
            raw_entity: The raw entity to resolve.
            candidate: The candidate canonical entity.
            source_trust: Trust level of the source (0.0 to 1.0).

        Returns:
            Tuple of (overall_confidence, evidence_list)
        """
        scores = {}

        # Identity similarity (based on normalized names)
        scores['identity_similarity'] = self._identity_similarity(raw_entity, candidate)

        # Name similarity
        scores['name_similarity'] = self._name_similarity(raw_entity, candidate)

        # Type similarity
        scores['type_similarity'] = self._type_similarity(raw_entity, candidate)

        # Location similarity
        scores['location_similarity'] = self._location_similarity(raw_entity, candidate)

        # Attribute similarity
        scores['attribute_similarity'] = self._attribute_similarity(raw_entity, candidate)

        # Source trust
        scores['source_trust'] = source_trust

        # Calculate weighted overall confidence
        overall_confidence = sum(
            scores[dimension] * weight
            for dimension, weight in self.weights.items()
        )

        # Clamp to [0.0, 1.0]
        overall_confidence = max(0.0, min(1.0, overall_confidence))

        # Create evidence
        evidence = []
        for dimension, score in scores.items():
            evidence.append(Evidence(
                evidence_id=f"{raw_entity.raw_entity_id}_{candidate.canonical_id}_{dimension}",
                evidence_type=dimension,
                description=f"{dimension.replace('_', ' ').title()}: {score:.3f}",
                score=score,
                source="confidence_model",
                details={"dimension": dimension, "raw_score": score}
            ))

        return overall_confidence, evidence

    def _identity_similarity(self, raw: RawEntity, canonical: CanonicalEntity) -> float:
        """Calculate identity similarity based on normalized entity IDs."""
        from ..normalization.normalizer import normalize_entity_name

        raw_tokens = normalize_entity_name(raw.source_entity_id)
        canonical_tokens = normalize_entity_name(canonical.canonical_id)

        if not raw_tokens or not canonical_tokens:
            return 0.0

        # Remove generic canonical prefix
        canonical_tokens = [token for token in canonical_tokens if token != "canonical"]

        if not canonical_tokens:
            return 0.0

        def token_match(a: str, b: str) -> bool:
            return a == b or a in b or b in a

        match_count = 0
        for raw_token in raw_tokens:
            if any(token_match(raw_token, canonical_token) for canonical_token in canonical_tokens):
                match_count += 1

        max_size = max(len(raw_tokens), len(canonical_tokens))
        return match_count / max_size if max_size else 0.0

    def _name_similarity(self, raw: RawEntity, canonical: CanonicalEntity) -> float:
        """Calculate name similarity."""
        raw_name = (raw.name or "").lower()
        canonical_name = (canonical.canonical_name or "").lower()

        if not raw_name or not canonical_name:
            return 0.5  # Neutral if missing

        # Simple string similarity (could be enhanced with difflib)
        return 1.0 if raw_name == canonical_name else 0.0

    def _type_similarity(self, raw: RawEntity, canonical: CanonicalEntity) -> float:
        """Calculate type similarity."""
        raw_type = raw.entity_type or raw.domain
        canonical_type = canonical.entity_type

        if raw_type and canonical_type:
            return 1.0 if raw_type.lower() == canonical_type.lower() else 0.0
        return 0.5

    def _location_similarity(self, raw: RawEntity, canonical: CanonicalEntity) -> float:
        """Calculate location similarity."""
        raw_area = raw.area
        # Extract area from canonical_id if possible
        canonical_parts = canonical.canonical_id.split('.')
        canonical_area = None
        if len(canonical_parts) > 2 and canonical_parts[1] == 'area':
            canonical_area = canonical_parts[2]

        if raw_area and canonical_area:
            return 1.0 if raw_area.lower() == canonical_area.lower() else 0.0
        if not raw_area and not canonical_area:
            return 1.0
        return 0.5

    def _attribute_similarity(self, raw: RawEntity, canonical: CanonicalEntity) -> float:
        """Calculate attribute similarity."""
        raw_attrs = set(raw.attributes.keys())
        canonical_attrs = set(canonical.attributes.keys())

        if not raw_attrs or not canonical_attrs:
            return 0.5

        intersection = raw_attrs & canonical_attrs
        union = raw_attrs | canonical_attrs
        return len(intersection) / len(union)