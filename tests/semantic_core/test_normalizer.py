"""Tests for semantic normalization utilities."""

from semantic_core.normalization.unit_normalizer import normalize_unit, convert_unit, normalize_attribute_units
from semantic_core.normalization.schema_mapper import SchemaMapper


def test_normalize_unit_aliases():
    assert normalize_unit("°C") == "celsius"
    assert normalize_unit("pct") == "%"
    assert normalize_unit("Lux") == "lux"


def test_convert_unit_temperature():
    assert convert_unit(32, "°F", "°C") == 0.0
    assert convert_unit(0, "°C", "°F") == 32.0
    assert convert_unit(10, "m", "km") is None


def test_normalize_attribute_units():
    result = normalize_attribute_units({"temperature_unit": "°C", "value": 22})
    assert result["temperature_unit"] == "celsius"
    assert result["value"] == 22


def test_schema_mapper_homeassistant():
    mapper = SchemaMapper()
    raw = mapper.map_homeassistant_entity({
        "entity_id": "sensor.livingroom_temperature",
        "state": "20",
        "attributes": {"friendly_name": "Living Room Temperature", "device_class": "temperature"},
    })
    assert raw.raw_entity_id == "homeassistant_sensor.livingroom_temperature"
    assert raw.entity_type == "sensor"
    assert raw.attributes["state"] == "20"
    assert mapper.validate_raw_entity(raw)
