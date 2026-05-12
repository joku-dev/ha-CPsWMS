"""Home Assistant source adapter for converting entities to RawEntity."""

from typing import Dict, Any

from semantic_core.identity.models import RawEntity


class HomeAssistantAdapter:
    """Converts Home Assistant entities into RawEntity models."""

    def __init__(self, source_id: str = "homeassistant"):
        self.source_id = source_id

    def convert_entity(self, ha_entity: Dict[str, Any]) -> RawEntity:
        """
        Convert a Home Assistant entity dict to a RawEntity.

        Args:
            ha_entity: Home Assistant entity dictionary.

        Returns:
            RawEntity instance.
        """
        entity_id = ha_entity.get("entity_id", "")
        state = ha_entity.get("state", "")
        attributes = ha_entity.get("attributes", {})

        # Extract domain from entity_id (e.g., "sensor.livingroom_temperature" -> "sensor")
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

        # Extract area from attributes or entity_id if possible
        area = attributes.get("area") or self._infer_area_from_entity_id(entity_id)

        # Device class
        device_class = attributes.get("device_class")

        # Friendly name
        name = attributes.get("friendly_name", entity_id)

        # Create RawEntity
        raw_entity = RawEntity(
            raw_entity_id=f"{self.source_id}_{entity_id}",
            source_id=self.source_id,
            source_entity_id=entity_id,
            entity_type=domain,  # Use domain as entity_type
            name=name,
            domain=domain,
            device_class=device_class,
            area=area,
            attributes={
                **attributes,
                "state": state,  # Include current state
                "entity_id": entity_id  # Preserve original
            }
        )

        return raw_entity

    def _infer_area_from_entity_id(self, entity_id: str) -> str | None:
        """Infer area from entity_id if possible."""
        # Simple heuristic: look for common area words
        parts = entity_id.lower().split(".")
        if len(parts) > 1:
            entity_part = parts[1]
            area_keywords = ["livingroom", "bedroom", "kitchen", "bathroom", "hallway", "garage"]
            for keyword in area_keywords:
                if keyword in entity_part:
                    return keyword.replace("room", "_room")  # Normalize
        return None