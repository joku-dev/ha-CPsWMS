"""Schema mapper for source-specific payloads into canonical semantic models."""

from typing import Any, Dict

from semantic_core.identity.models import RawEntity


class SchemaMapper:
    """Maps heterogeneous source schemas into RawEntity objects."""

    def map_homeassistant_entity(self, ha_entity: Dict[str, Any], source_id: str = "homeassistant") -> RawEntity:
        """Convert a Home Assistant entity payload into a RawEntity."""
        entity_id = ha_entity.get("entity_id", "")
        attributes = ha_entity.get("attributes", {}) or {}
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

        raw_entity = RawEntity(
            raw_entity_id=f"{source_id}_{entity_id}",
            source_id=source_id,
            source_entity_id=entity_id,
            entity_type=domain,
            name=attributes.get("friendly_name", entity_id),
            domain=domain,
            device_class=attributes.get("device_class"),
            area=attributes.get("area"),
            attributes={
                **attributes,
                "state": ha_entity.get("state"),
                "entity_id": entity_id,
            },
        )
        return raw_entity

    def validate_raw_entity(self, raw_entity: RawEntity) -> bool:
        """Validate that a RawEntity has the minimum semantic shape."""
        return bool(raw_entity.raw_entity_id and raw_entity.source_entity_id and raw_entity.source_id)
