"""Canonical entity registry for managing stable identities."""

from typing import Dict, List, Optional
from uuid import uuid4

from .models import CanonicalEntity, RawEntity


class CanonicalRegistry:
    """Manages canonical entities and their aliases."""

    def __init__(self):
        self.entities: Dict[str, CanonicalEntity] = {}
        self.aliases: Dict[str, str] = {}  # alias -> canonical_id

    def register_entity(self, entity: CanonicalEntity) -> None:
        """Register a new canonical entity."""
        self.entities[entity.canonical_id] = entity

    def get_entity(self, canonical_id: str) -> Optional[CanonicalEntity]:
        """Retrieve a canonical entity by ID."""
        return self.entities.get(canonical_id)

    def find_candidates(self, raw_entity: RawEntity) -> List[CanonicalEntity]:
        """Find candidate canonical entities for a raw entity."""
        # Simple implementation: return all entities of same type
        candidates = []
        for entity in self.entities.values():
            if entity.entity_type == raw_entity.entity_type:
                candidates.append(entity)
        return candidates

    def generate_canonical_id(self, raw_entity: RawEntity) -> str:
        """Generate a stable canonical ID for a raw entity."""
        from ..normalization.normalizer import normalize_entity_name

        tokens = normalize_entity_name(raw_entity.source_entity_id)

        if not tokens:
            # Fallback
            return f"canonical.unknown.{raw_entity.source_entity_id.replace('.', '_')}"

        # Try to infer type
        entity_type = raw_entity.entity_type or "unknown"

        # Build hierarchical ID
        if raw_entity.area:
            return f"canonical.{entity_type}.{raw_entity.area}.{'.'.join(tokens[1:])}"
        elif raw_entity.domain:
            return f"canonical.{entity_type}.{raw_entity.domain}.{'.'.join(tokens[1:])}"
        else:
            return f"canonical.{entity_type}.{'.'.join(tokens)}"

    def add_alias(self, alias: str, canonical_id: str) -> None:
        """Add an alias for a canonical entity."""
        self.aliases[alias] = canonical_id

    def resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to a canonical ID."""
        return self.aliases.get(alias)

    def create_new_entity(self, raw_entity: RawEntity) -> CanonicalEntity:
        """Create a new canonical entity from a raw entity."""
        canonical_id = self.generate_canonical_id(raw_entity)
        entity = CanonicalEntity(
            canonical_id=canonical_id,
            entity_type=raw_entity.entity_type or "unknown",
            canonical_name=raw_entity.name,
            attributes=raw_entity.attributes.copy()
        )
        self.register_entity(entity)
        return entity