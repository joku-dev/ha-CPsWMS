"""Unit normalization utilities for semantic entity attributes."""

from typing import Dict

_UNIT_ALIASES = {
    "°c": "celsius",
    "c": "celsius",
    "°f": "fahrenheit",
    "f": "fahrenheit",
    "percent": "%",
    "pct": "%",
    "lux": "lux",
    "w": "watt",
    "kw": "kilowatt",
    "kwh": "kilowatt_hour",
}

_CONVERSION_FACTORS = {
    ("fahrenheit", "celsius"): lambda v: (v - 32) * 5.0 / 9.0,
    ("celsius", "fahrenheit"): lambda v: (v * 9.0 / 5.0) + 32,
}


def normalize_unit(unit: str) -> str:
    """Normalize a unit string into a canonical token."""
    if not unit:
        return ""

    normalized = unit.lower().strip().replace("°", "").replace(" ", "")
    return _UNIT_ALIASES.get(normalized, normalized)


def convert_unit(value: float, from_unit: str, to_unit: str) -> float | None:
    """Convert a numeric value between supported units."""
    from_normalized = normalize_unit(from_unit)
    to_normalized = normalize_unit(to_unit)

    if from_normalized == to_normalized:
        return value

    converter = _CONVERSION_FACTORS.get((from_normalized, to_normalized))
    if converter is None:
        return None

    return converter(value)


def normalize_attribute_units(attributes: dict) -> dict:
    """Normalize the unit information inside an attribute dictionary."""
    normalized = {}
    for key, value in attributes.items():
        if key.lower().endswith("unit") and isinstance(value, str):
            normalized[key] = normalize_unit(value)
        else:
            normalized[key] = value
    return normalized
