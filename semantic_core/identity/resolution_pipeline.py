"""Resolution pipeline for processing raw entities into canonical entities."""

from .canonical_registry import CanonicalRegistry
from .identity_resolver import IdentityResolver
from .models import RawEntity, ResolutionDecision


class ResolutionPipeline:
    """Orchestrates the full resolution process for raw entities."""

    def __init__(self, registry: CanonicalRegistry, resolver: IdentityResolver):
        self.registry = registry
        self.resolver = resolver

    def process(self, raw_entity: RawEntity, source_trust: float = 0.8) -> ResolutionDecision:
        """
        Process a raw entity through the resolution pipeline.

        Args:
            raw_entity: The raw entity to process.
            source_trust: Trust level of the source.

        Returns:
            ResolutionDecision with the resolution outcome.
        """
        # Step 1: Normalization (already handled in models and registry)

        # Step 2: Candidate lookup
        candidates = self.registry.find_candidates(raw_entity)

        # Step 3: Resolution decision
        decision = self.resolver.resolve(raw_entity, candidates, source_trust)

        # Step 4: Registry update (if new entity was created, it's already registered)
        # For resolved_existing, we might want to add aliases, but for now, skip

        return decision