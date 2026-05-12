"""Neo4j writer for semantic core models."""

from .repository import Neo4jRepository
from semantic_core.identity.models import CanonicalEntity, RawEntity, ResolutionDecision, SourceSystem


class SemanticCoreWriter:
    """Writer for persisting semantic core models to Neo4j."""

    def __init__(self, repository: Neo4jRepository):
        self.repository = repository

    def write_resolution_result(
        self,
        raw_entity: RawEntity,
        canonical_entity: CanonicalEntity | None,
        decision: ResolutionDecision,
        source_system: SourceSystem | None = None,
        session=None
    ) -> None:
        """
        Write a complete resolution result to Neo4j.

        Args:
            raw_entity: The raw entity.
            canonical_entity: The resolved canonical entity (if any).
            decision: The resolution decision.
            source_system: The source system (optional).
        """
        # Save source system if provided
        if source_system:
            self.repository.save_source_system(source_system, session=session)

        # Save raw entity
        self.repository.save_raw_entity(raw_entity, session=session)

        # Save canonical entity if created
        if canonical_entity:
            self.repository.save_canonical_entity(canonical_entity, session=session)

        # Save decision
        self.repository.save_resolution_decision(decision, session=session)

    def write_source_system(self, source_system: SourceSystem, session=None) -> None:
        """Persist a source system node using an existing session."""
        self.repository.save_source_system(source_system, session=session)