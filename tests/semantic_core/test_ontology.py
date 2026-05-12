"""Tests for semantic ontology mapping."""

from semantic_core.ontology.ontology_store import OntologyStore
from semantic_core.ontology.ontology_mapper import OntologyMapper
from semantic_core.identity.models import RawEntity


def test_ontology_store_and_mapper():
    store = OntologyStore()
    store.register_concept("concept.sensor", {"label": "Sensor"})
    store.register_concept("concept.area.livingroom", {"label": "Living Room"})

    mapper = OntologyMapper(store)
    raw = RawEntity(
        raw_entity_id="homeassistant_sensor.livingroom_temperature",
        source_id="homeassistant",
        source_entity_id="sensor.livingroom_temperature",
        entity_type="sensor",
        area="livingroom",
    )

    mapped_type = mapper.map_entity_type(raw)
    mapped_area = mapper.map_entity_area(raw)
    enriched = mapper.enrich_raw_entity(raw)

    assert mapped_type == "concept.sensor"
    assert mapped_area == "concept.area.livingroom"
    assert enriched.attributes["ontology_type"] == "concept.sensor"
    assert enriched.attributes["ontology_area"] == "concept.area.livingroom"
