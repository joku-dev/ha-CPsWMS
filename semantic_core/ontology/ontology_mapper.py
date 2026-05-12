"""Ontology mapper that maps raw entities into canonical semantic categories."""

from typing import Optional

from semantic_core.identity.models import RawEntity
from .ontology_store import OntologyStore


class OntologyMapper:
    """Maps RawEntity characteristics into ontology concept identifiers."""

    def __init__(self, ontology_store: OntologyStore):
        self.ontology_store = ontology_store

    def map_entity_type(self, raw_entity: RawEntity) -> Optional[str]:
        """Map a raw entity type to an ontology concept."""
        entity_type = raw_entity.entity_type or raw_entity.domain
        if not entity_type:
            return None

        candidate = f"concept.{entity_type}"
        return candidate if self.ontology_store.get_concept(candidate) else None

    def map_entity_area(self, raw_entity: RawEntity) -> Optional[str]:
        """Map a raw entity area to an ontology location concept."""
        if not raw_entity.area:
            return None

        concept_id = f"concept.area.{raw_entity.area}"
        return concept_id if self.ontology_store.get_concept(concept_id) else None

    def enrich_raw_entity(self, raw_entity: RawEntity) -> RawEntity:
        """Embed ontology annotations into RawEntity attributes."""
        mapped_type = self.map_entity_type(raw_entity)
        mapped_area = self.map_entity_area(raw_entity)

        enriched_attributes = raw_entity.attributes.copy()
        if mapped_type:
            enriched_attributes["ontology_type"] = mapped_type
        if mapped_area:
            enriched_attributes["ontology_area"] = mapped_area

        return RawEntity(
            raw_entity_id=raw_entity.raw_entity_id,
            source_id=raw_entity.source_id,
            source_entity_id=raw_entity.source_entity_id,
            entity_type=raw_entity.entity_type,
            name=raw_entity.name,
            domain=raw_entity.domain,
            device_class=raw_entity.device_class,
            area=raw_entity.area,
            attributes=enriched_attributes,
        )
