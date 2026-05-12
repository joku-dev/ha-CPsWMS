"""Normalization utilities for entity names and attributes."""

import re
from typing import List


def normalize_entity_name(entity_name: str) -> List[str]:
    """
    Normalize an entity name into semantic tokens.

    - Convert to lowercase
    - Remove common separators: '.', '_', '-'
    - Normalize spaces
    - Extract weak semantic hints

    Args:
        entity_name: The raw entity name to normalize.

    Returns:
        List of normalized semantic tokens.
    """
    if not entity_name:
        return []

    # Convert to lowercase
    normalized = entity_name.lower()

    # Replace separators with spaces
    normalized = re.sub(r'[._-]', ' ', normalized)

    # Normalize multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # Split into tokens
    tokens = normalized.split()

    return tokens


def normalize_attributes(attributes: dict) -> dict:
    """
    Normalize attributes while preserving originals.

    Args:
        attributes: Original attributes dict.

    Returns:
        Normalized attributes dict with '_original' keys preserved.
    """
    normalized = {}
    for key, value in attributes.items():
        if isinstance(value, str):
            # Normalize string values
            normalized[key] = value.lower().strip()
            normalized[f"{key}_original"] = value
        else:
            normalized[key] = value
    return normalized