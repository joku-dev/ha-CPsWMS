"""Ontology store for semantic categories and concept relationships."""

from typing import Dict, List, Optional


class OntologyStore:
    """Stores ontology concepts and simple hierarchies."""

    def __init__(self):
        self.concepts: Dict[str, Dict[str, str]] = {}
        self.relationships: Dict[str, List[str]] = {}

    def register_concept(self, concept_id: str, metadata: Dict[str, str] | None = None) -> None:
        """Register a semantic concept in the ontology."""
        self.concepts[concept_id] = metadata or {}

    def add_relationship(self, source_concept: str, target_concept: str) -> None:
        """Add a directional relationship between concepts."""
        self.relationships.setdefault(source_concept, []).append(target_concept)

    def get_concept(self, concept_id: str) -> Optional[Dict[str, str]]:
        """Retrieve metadata for a concept."""
        return self.concepts.get(concept_id)

    def get_children(self, concept_id: str) -> List[str]:
        """Get immediate sub-concepts."""
        return self.relationships.get(concept_id, [])

    def is_subconcept(self, source: str, target: str) -> bool:
        """Check if source concept is a descendant of target concept."""
        if source == target:
            return True
        for child in self.get_children(target):
            if self.is_subconcept(source, child):
                return True
        return False
