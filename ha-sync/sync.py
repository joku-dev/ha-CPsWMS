"""Sync Home Assistant state data into Neo4j.

Dieses Modul liest Home Assistant Entity-States über die REST-API
und speichert sie in einer Neo4j-Datenbank. Dabei werden Knoten für
Entity, Room, DeviceClass und Unit angelegt und Beziehungen erstellt.
"""

import os
import re
import sys
import json
import time
import yaml
import requests
import websocket
from pathlib import Path
from neo4j import GraphDatabase

# Expose repository root so local packages can be imported when running from ha-sync
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from semantic_core.identity.canonical_registry import CanonicalRegistry
from semantic_core.identity.confidence_model import ConfidenceModel
from semantic_core.identity.identity_resolver import IdentityResolver
from semantic_core.identity.resolution_pipeline import ResolutionPipeline
from semantic_core.identity.models import RawEntity as SemanticRawEntity, SourceSystem
from sources.homeassistant.adapter import HomeAssistantAdapter
from storage.neo4j.repository import Neo4jRepository
from storage.neo4j.writer import SemanticCoreWriter


HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
AUTOMATIONS_YAML_PATH = os.getenv("AUTOMATIONS_YAML_PATH", "/config/automations.yaml")

ENABLE_EVENT_HISTORY = os.getenv("ENABLE_EVENT_HISTORY", "true").lower() == "true"
ENABLE_MQTT_MODEL = os.getenv("ENABLE_MQTT_MODEL", "true").lower() == "true"
ENABLE_ZIGBEE_MODEL = os.getenv("ENABLE_ZIGBEE_MODEL", "true").lower() == "true"
ENABLE_SEMANTIC_IDENTITY = os.getenv("ENABLE_SEMANTIC_IDENTITY", "true").lower() == "true"
SEMANTIC_SOURCE_TRUST = float(os.getenv("SEMANTIC_SOURCE_TRUST", "0.8"))

ENTITY_ID_PATTERN = re.compile(r"\b[a-zA-Z_]+\.[a-zA-Z0-9_]+\b")


def ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def get_ha_states():
    response = requests.get(
        f"{HA_URL}/api/states",
        headers=ha_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_ha_logbook():
    try:
        response = requests.get(
            f"{HA_URL}/api/logbook",
            headers=ha_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Could not read logbook: {exc}")
        return []


def get_ha_events():
    try:
        response = requests.get(
            f"{HA_URL}/api/events",
            headers=ha_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Could not read event types: {exc}")
        return []


def ha_ws_command(command_type):
    ws_url = HA_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/websocket"

    ws = websocket.create_connection(ws_url, timeout=30)

    auth_required = json.loads(ws.recv())
    if auth_required.get("type") != "auth_required":
        raise RuntimeError(f"Unexpected websocket response: {auth_required}")

    ws.send(json.dumps({
        "type": "auth",
        "access_token": HA_TOKEN,
    }))

    auth_ok = json.loads(ws.recv())
    if auth_ok.get("type") != "auth_ok":
        raise RuntimeError(f"Home Assistant websocket auth failed: {auth_ok}")

    ws.send(json.dumps({
        "id": 1,
        "type": command_type,
    }))

    result = json.loads(ws.recv())
    ws.close()

    if not result.get("success"):
        raise RuntimeError(f"HA websocket command failed: {command_type}: {result}")

    return result.get("result", [])


def safe_ws(command_type, label):
    try:
        return ha_ws_command(command_type)
    except Exception as exc:
        print(f"Could not read {label}: {exc}")
        return []


def get_ha_config_entries_rest():
    try:
        response = requests.get(
            f"{HA_URL}/api/config/config_entries/entry",
            headers=ha_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Could not read config entries via REST: {exc}")
        return []


def get_entity_registry():
    return safe_ws("config/entity_registry/list", "entity registry")


def get_device_registry():
    return safe_ws("config/device_registry/list", "device registry")


def get_area_registry():
    return safe_ws("config/area_registry/list", "area registry")


def get_floor_registry():
    return safe_ws("config/floor_registry/list", "floor registry")


def get_label_registry():
    return safe_ws("config/label_registry/list", "label registry")


def get_config_entry_registry():
    config_entries = safe_ws("config/config_entries/list", "config entries")
    if config_entries:
        return config_entries

    print("Falling back to REST API for config entry registry")
    config_entries = get_ha_config_entries_rest()
    if config_entries:
        return config_entries

    return []


def derive_integrations_from_states(states):
    integrations = {}
    for entity in states:
        entity_id = entity.get("entity_id")
        if not entity_id or "." not in entity_id:
            continue

        domain = entity_id.split(".")[0]
        if domain in integrations:
            continue

        integrations[domain] = {
            "domain": domain,
            "title": f"Derived integration for {domain}",
            "source": "derived_from_states",
            "disabled_by": None,
            "state": "unknown",
        }

    return list(integrations.values())


def extract_entity_ids_from_object(obj):
    found = set()

    if obj is None:
        return found

    if isinstance(obj, str):
        found.update(ENTITY_ID_PATTERN.findall(obj))
        return found

    if isinstance(obj, list):
        for item in obj:
            found.update(extract_entity_ids_from_object(item))
        return found

    if isinstance(obj, dict):
        for value in obj.values():
            found.update(extract_entity_ids_from_object(value))

    return found


def load_yaml_file(path):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or []

        if isinstance(data, dict):
            data = [data]

        return data

    except Exception as exc:
        print(f"Could not parse YAML file {path}: {exc}")
        return []


def create_constraints(driver):
    constraints = [
        ("Entity", "entity_id"),
        ("Device", "device_id"),
        ("Area", "area_id"),
        ("Floor", "floor_id"),
        ("Automation", "automation_id"),
        ("DeviceClass", "name"),
        ("Domain", "name"),
        ("Unit", "name"),
        ("Integration", "domain"),
        ("EventType", "name"),
        ("Problem", "problem_id"),
        ("MqttTopic", "topic"),
        ("ZigbeeNode", "ieee"),
        ("SourceSystem", "source_id"),
        ("RawEntity", "raw_entity_id"),
        ("CanonicalEntity", "canonical_id"),
        ("ResolutionDecision", "decision_id"),
        ("Evidence", "evidence_id"),
    ]

    with driver.session() as session:
        for label, prop in constraints:
            session.run(f"""
            CREATE CONSTRAINT {label.lower()}_{prop}_unique IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.{prop} IS UNIQUE
            """)


def create_semantic_components():
    registry = CanonicalRegistry()
    confidence_model = ConfidenceModel()
    resolver = IdentityResolver(registry, confidence_model)
    pipeline = ResolutionPipeline(registry, resolver)
    repository = Neo4jRepository(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    writer = SemanticCoreWriter(repository)
    adapter = HomeAssistantAdapter(source_id="homeassistant")
    source_system = SourceSystem(
        source_id="homeassistant",
        source_type="homeassistant",
        name="Home Assistant",
        trust_level=SEMANTIC_SOURCE_TRUST,
        metadata={}
    )
    return pipeline, writer, adapter, source_system


def sync_entity_semantic(session, entity, registry_by_entity_id, pipeline, writer, adapter, source_system):
    raw_entity = adapter.convert_entity(entity)
    decision = pipeline.process(raw_entity, source_trust=SEMANTIC_SOURCE_TRUST)
    canonical_entity = pipeline.registry.get_entity(decision.canonical_id) if decision.canonical_id else None
    writer.write_resolution_result(raw_entity, canonical_entity, decision, source_system=source_system, session=session)
    link_entity_raw_representation(session, raw_entity)
    return decision


def link_entity_raw_representation(session, raw_entity):
    session.run("""
        MATCH (raw:RawEntity {raw_entity_id: $raw_entity_id})
        OPTIONAL MATCH (e:Entity {entity_id: $entity_id})
        FOREACH (_ IN CASE WHEN e IS NOT NULL THEN [1] ELSE [] END |
            MERGE (e)-[:HAS_RAW_REPRESENTATION]->(raw)
        )
    """, raw_entity_id=raw_entity.raw_entity_id, entity_id=raw_entity.source_entity_id)


def sync_floors(tx, floors):
    for floor in floors:
        floor_id = floor.get("floor_id")
        if not floor_id:
            continue

        tx.run("""
        MERGE (f:Floor {floor_id: $floor_id})
        SET f.name = $name,
            f.icon = $icon
        """, floor_id=floor_id, name=floor.get("name"), icon=floor.get("icon"))


def sync_areas(tx, areas):
    for area in areas:
        area_id = area.get("area_id")
        if not area_id:
            continue

        tx.run("""
        MERGE (a:Area {area_id: $area_id})
        SET a.name = $name,
            a.icon = $icon

        FOREACH (_ IN CASE WHEN $floor_id IS NOT NULL THEN [1] ELSE [] END |
            MERGE (f:Floor {floor_id: $floor_id})
            MERGE (a)-[:LOCATED_ON]->(f)
        )
        """,
        area_id=area_id,
        name=area.get("name"),
        icon=area.get("icon"),
        floor_id=area.get("floor_id"))


def sync_integrations(tx, config_entries):
    for entry in config_entries:
        domain = entry.get("domain")
        if not domain:
            continue

        tx.run("""
        MERGE (i:Integration {domain: $domain})
        SET i.title = $title,
            i.source = $source,
            i.disabled_by = $disabled_by,
            i.state = $state
        """,
        domain=domain,
        title=entry.get("title"),
        source=entry.get("source"),
        disabled_by=entry.get("disabled_by"),
        state=entry.get("state"))


def sync_devices(tx, devices):
    for device in devices:
        device_id = device.get("id")
        if not device_id:
            continue

        name = (
            device.get("name_by_user")
            or device.get("name")
            or device.get("model")
            or device_id
        )

        tx.run("""
        MERGE (d:Device {device_id: $device_id})
        SET d.name = $name,
            d.manufacturer = $manufacturer,
            d.model = $model,
            d.sw_version = $sw_version,
            d.hw_version = $hw_version,
            d.configuration_url = $configuration_url,
            d.identifiers = $identifiers,
            d.connections = $connections

        FOREACH (_ IN CASE WHEN $area_id IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a:Area {area_id: $area_id})
            MERGE (d)-[:LOCATED_IN]->(a)
        )

        FOREACH (_ IN CASE WHEN $integration IS NOT NULL THEN [1] ELSE [] END |
            MERGE (i:Integration {domain: $integration})
            MERGE (d)-[:PROVIDED_BY]->(i)
        )
        """,
        device_id=device_id,
        name=name,
        manufacturer=device.get("manufacturer"),
        model=device.get("model"),
        sw_version=device.get("sw_version"),
        hw_version=device.get("hw_version"),
        configuration_url=device.get("configuration_url"),
        identifiers=normalize_value(device.get("identifiers")),
        connections=normalize_value(device.get("connections")),
        area_id=device.get("area_id"),
        integration=device.get("via_device_id"))


def sync_entity(tx, entity, registry_by_entity_id):
    entity_id = entity["entity_id"]
    domain = entity_id.split(".")[0]
    state = normalize_value(entity.get("state"))

    attributes = entity.get("attributes", {})
    registry = registry_by_entity_id.get(entity_id, {})

    friendly_name = (
        registry.get("name")
        or registry.get("original_name")
        or attributes.get("friendly_name")
        or entity_id
    )

    device_id = registry.get("device_id")
    area_id = registry.get("area_id")
    platform = registry.get("platform")
    unique_id = registry.get("unique_id")

    device_class = attributes.get("device_class") or registry.get("device_class")
    unit = attributes.get("unit_of_measurement")
    icon = attributes.get("icon") or registry.get("icon")
    entity_category = attributes.get("entity_category") or registry.get("entity_category")

    is_problem = state in ["unavailable", "unknown", "none", None]

    tx.run("""
    MERGE (e:Entity {entity_id: $entity_id})
    SET e.domain = $domain,
        e.state = $state,
        e.friendly_name = $friendly_name,
        e.icon = $icon,
        e.entity_category = $entity_category,
        e.platform = $platform,
        e.unique_id = $unique_id,
        e.is_problem = $is_problem,
        e.last_changed = datetime($last_changed),
        e.last_updated = datetime($last_updated)

    MERGE (dom:Domain {name: $domain})
    MERGE (e)-[:BELONGS_TO_DOMAIN]->(dom)

    FOREACH (_ IN CASE WHEN $area_id IS NOT NULL THEN [1] ELSE [] END |
        MERGE (a:Area {area_id: $area_id})
        MERGE (e)-[:LOCATED_IN]->(a)
    )

    FOREACH (_ IN CASE WHEN $device_id IS NOT NULL THEN [1] ELSE [] END |
        MERGE (d:Device {device_id: $device_id})
        MERGE (e)-[:REPRESENTS]->(d)
    )

    FOREACH (_ IN CASE WHEN $device_class IS NOT NULL THEN [1] ELSE [] END |
        MERGE (dc:DeviceClass {name: $device_class})
        MERGE (e)-[:HAS_DEVICE_CLASS]->(dc)
    )

    FOREACH (_ IN CASE WHEN $unit IS NOT NULL THEN [1] ELSE [] END |
        MERGE (u:Unit {name: $unit})
        MERGE (e)-[:MEASURED_IN]->(u)
    )

    FOREACH (_ IN CASE WHEN $platform IS NOT NULL THEN [1] ELSE [] END |
        MERGE (i:Integration {domain: $platform})
        MERGE (e)-[:PROVIDED_BY]->(i)
    )
    """,
    entity_id=entity_id,
    domain=domain,
    state=state,
    friendly_name=friendly_name,
    icon=icon,
    entity_category=entity_category,
    platform=platform,
    unique_id=unique_id,
    area_id=area_id,
    device_id=device_id,
    device_class=device_class,
    unit=unit,
    is_problem=is_problem,
    last_changed=entity["last_changed"],
    last_updated=entity["last_updated"])


def sync_automations_from_states(tx, states):
    for entity in states:
        entity_id = entity["entity_id"]

        if not entity_id.startswith("automation."):
            continue

        attributes = entity.get("attributes", {})
        name = attributes.get("friendly_name", entity_id)
        last_triggered = attributes.get("last_triggered")

        tx.run("""
        MERGE (a:Automation {automation_id: $automation_id})
        SET a.name = $name,
            a.entity_id = $automation_id,
            a.state = $state,
            a.last_triggered = CASE
                WHEN $last_triggered IS NULL THEN NULL
                ELSE datetime($last_triggered)
            END

        MERGE (e:Entity {entity_id: $automation_id})
        MERGE (a)-[:REPRESENTED_BY]->(e)
        """,
        automation_id=entity_id,
        name=name,
        state=entity.get("state"),
        last_triggered=last_triggered)


def sync_automations_from_yaml(tx, automations):
    for automation in automations:
        if not isinstance(automation, dict):
            continue

        alias = automation.get("alias") or automation.get("id") or "unknown automation"
        raw_id = automation.get("id")
        automation_id = raw_id or f"automation.{alias.lower().replace(' ', '_')}"

        trigger_block = automation.get("trigger") or automation.get("triggers")
        action_block = automation.get("action") or automation.get("actions")
        condition_block = automation.get("condition") or automation.get("conditions")

        trigger_entities = extract_entity_ids_from_object(trigger_block)
        action_entities = extract_entity_ids_from_object(action_block)
        condition_entities = extract_entity_ids_from_object(condition_block)

        tx.run("""
        MERGE (a:Automation {automation_id: $automation_id})
        SET a.name = $alias,
            a.mode = $mode,
            a.raw_id = $raw_id
        """,
        automation_id=automation_id,
        alias=alias,
        mode=automation.get("mode"),
        raw_id=raw_id)

        for entity_id in trigger_entities:
            tx.run("""
            MERGE (a:Automation {automation_id: $automation_id})
            MERGE (e:Entity {entity_id: $entity_id})
            MERGE (a)-[:TRIGGERED_BY]->(e)
            """, automation_id=automation_id, entity_id=entity_id)

        for entity_id in action_entities:
            tx.run("""
            MERGE (a:Automation {automation_id: $automation_id})
            MERGE (e:Entity {entity_id: $entity_id})
            MERGE (a)-[:CONTROLS]->(e)
            """, automation_id=automation_id, entity_id=entity_id)

        for entity_id in condition_entities:
            tx.run("""
            MERGE (a:Automation {automation_id: $automation_id})
            MERGE (e:Entity {entity_id: $entity_id})
            MERGE (a)-[:HAS_CONDITION]->(e)
            """, automation_id=automation_id, entity_id=entity_id)


def sync_event_types(tx, events):
    for event in events:
        event_type = event.get("event")
        listener_count = event.get("listener_count")

        if not event_type:
            continue

        tx.run("""
        MERGE (ev:EventType {name: $name})
        SET ev.listener_count = $listener_count
        """, name=event_type, listener_count=listener_count)


def sync_logbook_events(tx, logbook):
    for index, entry in enumerate(logbook):
        entity_id = entry.get("entity_id")
        name = entry.get("name")
        message = entry.get("message")
        when = entry.get("when")

        if not when:
            continue

        event_id = f"{when}-{entity_id}-{index}"

        tx.run("""
        MERGE (ev:HomeAssistantEvent {event_id: $event_id})
        SET ev.name = $name,
            ev.message = $message,
            ev.when = datetime($when),
            ev.entity_id = $entity_id,
            ev.domain = $domain

        FOREACH (_ IN CASE WHEN $entity_id IS NOT NULL THEN [1] ELSE [] END |
            MERGE (e:Entity {entity_id: $entity_id})
            MERGE (ev)-[:AFFECTED_ENTITY]->(e)
        )
        """,
        event_id=event_id,
        name=name,
        message=message,
        when=when,
        entity_id=entity_id,
        domain=entry.get("domain"))


def sync_problem_nodes(tx):
    tx.run("""
    MATCH (e:Entity)
    WHERE e.is_problem = true
    MERGE (p:Problem {problem_id: e.entity_id})
    SET p.entity_id = e.entity_id,
        p.state = e.state,
        p.last_updated = e.last_updated,
        p.description = "Entity is unavailable or unknown"
    MERGE (p)-[:AFFECTS]->(e)
    """)


def sync_mqtt_model(tx, states):
    if not ENABLE_MQTT_MODEL:
        return

    mqtt_entities = [
        e for e in states
        if e["entity_id"].startswith(("sensor.", "binary_sensor.", "switch.", "light."))
        and "mqtt" in json.dumps(e.get("attributes", {})).lower()
    ]

    for entity in mqtt_entities:
        entity_id = entity["entity_id"]

        topic = (
            entity.get("attributes", {}).get("state_topic")
            or entity.get("attributes", {}).get("command_topic")
        )

        if not topic:
            topic = f"unknown/{entity_id.replace('.', '/')}"

        tx.run("""
        MERGE (t:MqttTopic {topic: $topic})
        MERGE (e:Entity {entity_id: $entity_id})
        MERGE (e)-[:USES_MQTT_TOPIC]->(t)
        """, topic=topic, entity_id=entity_id)


def sync_zigbee_model(tx, states):
    if not ENABLE_ZIGBEE_MODEL:
        return

    for entity in states:
        entity_id = entity["entity_id"]
        attributes = entity.get("attributes", {})
        as_text = json.dumps(attributes, ensure_ascii=False).lower()

        if "zigbee" not in as_text and "zha" not in as_text and "zigbee2mqtt" not in as_text:
            continue

        ieee = (
            attributes.get("ieee")
            or attributes.get("ieee_address")
            or attributes.get("zigbee")
            or entity_id
        )

        tx.run("""
        MERGE (z:ZigbeeNode {ieee: $ieee})
        SET z.name = $name,
            z.entity_id = $entity_id

        MERGE (e:Entity {entity_id: $entity_id})
        MERGE (e)-[:REPRESENTS_ZIGBEE_NODE]->(z)
        """,
        ieee=normalize_value(ieee),
        name=attributes.get("friendly_name", entity_id),
        entity_id=entity_id)


def create_dependency_shortcuts(tx):
    tx.run("""
    MATCH (trigger:Entity)<-[:TRIGGERED_BY]-(a:Automation)-[:CONTROLS]->(target:Entity)
    MERGE (trigger)-[:CAN_CAUSE {via: a.automation_id}]->(target)
    """)

    tx.run("""
    MATCH (e:Entity)-[:REPRESENTS]->(d:Device)-[:LOCATED_IN]->(a:Area)
    MERGE (e)-[:EFFECTIVE_LOCATION]->(a)
    """)


def run_sync(driver):
    states = get_ha_states()

    entity_registry = get_entity_registry()
    device_registry = get_device_registry()
    area_registry = get_area_registry()
    floor_registry = get_floor_registry()
    config_entries = get_config_entry_registry()

    automations_yaml = load_yaml_file(AUTOMATIONS_YAML_PATH)

    events = get_ha_events() if ENABLE_EVENT_HISTORY else []
    logbook = get_ha_logbook() if ENABLE_EVENT_HISTORY else []

    if not config_entries:
        print("Config entry registry unavailable; deriving integration domains from HA states")
        config_entries = derive_integrations_from_states(states)

    registry_by_entity_id = {
        item.get("entity_id"): item
        for item in entity_registry
        if item.get("entity_id")
    }

    semantic_components = None
    if ENABLE_SEMANTIC_IDENTITY:
        semantic_components = create_semantic_components()

    with driver.session() as session:
        session.execute_write(sync_floors, floor_registry)
        session.execute_write(sync_areas, area_registry)
        session.execute_write(sync_integrations, config_entries)
        session.execute_write(sync_devices, device_registry)

        if ENABLE_SEMANTIC_IDENTITY and semantic_components is not None:
            pipeline, writer, adapter, source_system = semantic_components
            writer.write_source_system(source_system, session=session)

        for entity in states:
            session.execute_write(sync_entity, entity, registry_by_entity_id)
            if ENABLE_SEMANTIC_IDENTITY and semantic_components is not None:
                pipeline, writer, adapter, source_system = semantic_components
                sync_entity_semantic(session, entity, registry_by_entity_id, pipeline, writer, adapter, source_system)

        session.execute_write(sync_automations_from_states, states)
        session.execute_write(sync_automations_from_yaml, automations_yaml)
        session.execute_write(sync_event_types, events)
        session.execute_write(sync_logbook_events, logbook)
        session.execute_write(sync_problem_nodes)
        session.execute_write(sync_mqtt_model, states)
        session.execute_write(sync_zigbee_model, states)
        session.execute_write(create_dependency_shortcuts)

    print(
        f"Synced: {len(states)} states, "
        f"{len(entity_registry)} entities, "
        f"{len(device_registry)} devices, "
        f"{len(area_registry)} areas, "
        f"{len(floor_registry)} floors, "
        f"{len(config_entries)} integrations, "
        f"{len(automations_yaml)} automations, "
        f"{len(events)} event types, "
        f"{len(logbook)} logbook events"
    )


def wait_for_neo4j(driver, retries=30, delay=5):
    for attempt in range(1, retries + 1):
        try:
            with driver.session() as session:
                session.run("RETURN 1")
            print("Neo4j connection established")
            return
        except Exception as exc:
            print(f"Waiting for Neo4j... attempt {attempt}/{retries}: {exc}")
            time.sleep(delay)

    raise RuntimeError("Neo4j not reachable")


def main():
    print("HA Neo4j sync loaded: rooms, automations, diagnostics, events, MQTT, Zigbee")

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

    wait_for_neo4j(driver)
    create_constraints(driver)

    while True:
        try:
            run_sync(driver)
        except Exception as exc:
            print(f"Sync failed: {exc}")

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
