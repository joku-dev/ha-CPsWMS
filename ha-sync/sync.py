"""Sync Home Assistant state data into Neo4j.

Dieses Modul liest Home Assistant Entity-States über die REST-API
und speichert sie in einer Neo4j-Datenbank. Dabei werden Knoten für
Entity, Room, DeviceClass und Unit angelegt und Beziehungen erstellt.
"""




import os
import re
import json
import time
import yaml
import requests
import websocket
from neo4j import GraphDatabase


HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))

# Optional: automations.yaml in den Container mounten
AUTOMATIONS_YAML_PATH = os.getenv("AUTOMATIONS_YAML_PATH", "/config/automations.yaml")


ENTITY_ID_PATTERN = re.compile(r"\b[a-zA-Z_]+\.[a-zA-Z0-9_]+\b")


def ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def get_ha_states():
    response = requests.get(
        f"{HA_URL}/api/states",
        headers=ha_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def ha_ws_command(command_type):
    """
    Nutzt die Home-Assistant-WebSocket-API für Registries:
    - config/entity_registry/list
    - config/device_registry/list
    - config/area_registry/list
    - config/floor_registry/list
    """
    ws_url = HA_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/websocket"

    ws = websocket.create_connection(ws_url, timeout=30)

    auth_required = json.loads(ws.recv())
    if auth_required.get("type") != "auth_required":
        raise RuntimeError(f"Unexpected websocket response: {auth_required}")

    ws.send(json.dumps({
        "type": "auth",
        "access_token": HA_TOKEN
    }))

    auth_ok = json.loads(ws.recv())
    if auth_ok.get("type") != "auth_ok":
        raise RuntimeError(f"Home Assistant websocket auth failed: {auth_ok}")

    ws.send(json.dumps({
        "id": 1,
        "type": command_type
    }))

    result = json.loads(ws.recv())
    ws.close()

    if not result.get("success"):
        raise RuntimeError(f"HA websocket command failed: {command_type}: {result}")

    return result.get("result", [])


def get_entity_registry():
    try:
        return ha_ws_command("config/entity_registry/list")
    except Exception as exc:
        print(f"Could not read entity registry: {exc}")
        return []


def get_device_registry():
    try:
        return ha_ws_command("config/device_registry/list")
    except Exception as exc:
        print(f"Could not read device registry: {exc}")
        return []


def get_area_registry():
    try:
        return ha_ws_command("config/area_registry/list")
    except Exception as exc:
        print(f"Could not read area registry: {exc}")
        return []


def get_floor_registry():
    try:
        return ha_ws_command("config/floor_registry/list")
    except Exception as exc:
        print(f"Could not read floor registry: {exc}")
        return []


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def extract_entity_ids_from_object(obj):
    """
    Extrahiert Entity-IDs aus beliebigen YAML-Strukturen.
    Funktioniert für:
    entity_id: light.kitchen
    entity_id:
      - light.kitchen
      - switch.fan
    service_data/entity_id
    target/entity_id
    Templates mit enthaltenen Entity-IDs
    """
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
        for key, value in obj.items():
            found.update(extract_entity_ids_from_object(value))

    return found


def load_automations_yaml():
    if not os.path.exists(AUTOMATIONS_YAML_PATH):
        print(f"No automations.yaml found at {AUTOMATIONS_YAML_PATH}")
        return []

    try:
        with open(AUTOMATIONS_YAML_PATH, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or []

        if isinstance(data, dict):
            data = [data]

        return data

    except Exception as exc:
        print(f"Could not parse automations.yaml: {exc}")
        return []


def create_constraints(driver):
    with driver.session() as session:
        constraints = [
            """
            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
            FOR (e:Entity)
            REQUIRE e.entity_id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT device_id_unique IF NOT EXISTS
            FOR (d:Device)
            REQUIRE d.device_id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT area_id_unique IF NOT EXISTS
            FOR (a:Area)
            REQUIRE a.area_id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT floor_id_unique IF NOT EXISTS
            FOR (f:Floor)
            REQUIRE f.floor_id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT device_class_unique IF NOT EXISTS
            FOR (d:DeviceClass)
            REQUIRE d.name IS UNIQUE
            """,
            """
            CREATE CONSTRAINT unit_name_unique IF NOT EXISTS
            FOR (u:Unit)
            REQUIRE u.name IS UNIQUE
            """,
            """
            CREATE CONSTRAINT automation_id_unique IF NOT EXISTS
            FOR (a:Automation)
            REQUIRE a.automation_id IS UNIQUE
            """,
            """
            CREATE CONSTRAINT domain_name_unique IF NOT EXISTS
            FOR (d:Domain)
            REQUIRE d.name IS UNIQUE
            """
        ]

        for constraint in constraints:
            session.run(constraint)


def sync_floors(tx, floors):
    for floor in floors:
        floor_id = floor.get("floor_id")
        if not floor_id:
            continue

        tx.run(
            """
            MERGE (f:Floor {floor_id: $floor_id})
            SET
                f.name = $name,
                f.icon = $icon
            """,
            floor_id=floor_id,
            name=floor.get("name"),
            icon=floor.get("icon"),
        )


def sync_areas(tx, areas):
    for area in areas:
        area_id = area.get("area_id")
        if not area_id:
            continue

        tx.run(
            """
            MERGE (a:Area {area_id: $area_id})
            SET
                a.name = $name,
                a.icon = $icon

            FOREACH (_ IN CASE WHEN $floor_id IS NOT NULL THEN [1] ELSE [] END |
                MERGE (f:Floor {floor_id: $floor_id})
                MERGE (a)-[:LOCATED_ON]->(f)
            )
            """,
            area_id=area_id,
            name=area.get("name"),
            icon=area.get("icon"),
            floor_id=area.get("floor_id"),
        )


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

        identifiers = normalize_value(device.get("identifiers"))
        connections = normalize_value(device.get("connections"))

        tx.run(
            """
            MERGE (d:Device {device_id: $device_id})
            SET
                d.name = $name,
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
            """,
            device_id=device_id,
            name=name,
            manufacturer=device.get("manufacturer"),
            model=device.get("model"),
            sw_version=device.get("sw_version"),
            hw_version=device.get("hw_version"),
            configuration_url=device.get("configuration_url"),
            identifiers=identifiers,
            connections=connections,
            area_id=device.get("area_id"),
        )


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

    device_class = attributes.get("device_class") or registry.get("device_class")
    unit = attributes.get("unit_of_measurement")
    icon = attributes.get("icon") or registry.get("icon")
    entity_category = attributes.get("entity_category") or registry.get("entity_category")
    platform = registry.get("platform")
    unique_id = registry.get("unique_id")

    is_problem = state in ["unavailable", "unknown", "none", None]

    tx.run(
        """
        MERGE (e:Entity {entity_id: $entity_id})
        SET
            e.domain = $domain,
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
        last_updated=entity["last_updated"],
    )


def sync_automations_from_states(tx, states):
    for entity in states:
        entity_id = entity["entity_id"]
        if not entity_id.startswith("automation."):
            continue

        attributes = entity.get("attributes", {})
        name = attributes.get("friendly_name", entity_id)
        last_triggered = attributes.get("last_triggered")

        tx.run(
            """
            MERGE (a:Automation {automation_id: $automation_id})
            SET
                a.name = $name,
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
            last_triggered=last_triggered,
        )


def sync_automations_from_yaml(tx, automations):
    for automation in automations:
        if not isinstance(automation, dict):
            continue

        alias = automation.get("alias") or automation.get("id") or "unknown automation"
        automation_id = automation.get("id") or f"automation.{alias.lower().replace(' ', '_')}"

        trigger_block = automation.get("trigger") or automation.get("triggers")
        action_block = automation.get("action") or automation.get("actions")
        condition_block = automation.get("condition") or automation.get("conditions")

        trigger_entities = extract_entity_ids_from_object(trigger_block)
        action_entities = extract_entity_ids_from_object(action_block)
        condition_entities = extract_entity_ids_from_object(condition_block)

        tx.run(
            """
            MERGE (a:Automation {automation_id: $automation_id})
            SET
                a.name = $alias,
                a.mode = $mode,
                a.raw_id = $raw_id
            """,
            automation_id=automation_id,
            alias=alias,
            mode=automation.get("mode"),
            raw_id=automation.get("id"),
        )

        for entity_id in trigger_entities:
            tx.run(
                """
                MERGE (a:Automation {automation_id: $automation_id})
                MERGE (e:Entity {entity_id: $entity_id})
                MERGE (a)-[:TRIGGERED_BY]->(e)
                """,
                automation_id=automation_id,
                entity_id=entity_id,
            )

        for entity_id in action_entities:
            tx.run(
                """
                MERGE (a:Automation {automation_id: $automation_id})
                MERGE (e:Entity {entity_id: $entity_id})
                MERGE (a)-[:CONTROLS]->(e)
                """,
                automation_id=automation_id,
                entity_id=entity_id,
            )

        for entity_id in condition_entities:
            tx.run(
                """
                MERGE (a:Automation {automation_id: $automation_id})
                MERGE (e:Entity {entity_id: $entity_id})
                MERGE (a)-[:HAS_CONDITION]->(e)
                """,
                automation_id=automation_id,
                entity_id=entity_id,
            )


def run_sync(driver):
    states = get_ha_states()

    entity_registry = get_entity_registry()
    device_registry = get_device_registry()
    area_registry = get_area_registry()
    floor_registry = get_floor_registry()
    automations_yaml = load_automations_yaml()

    registry_by_entity_id = {
        item.get("entity_id"): item
        for item in entity_registry
        if item.get("entity_id")
    }

    with driver.session() as session:
        session.execute_write(sync_floors, floor_registry)
        session.execute_write(sync_areas, area_registry)
        session.execute_write(sync_devices, device_registry)

        for entity in states:
            session.execute_write(sync_entity, entity, registry_by_entity_id)

        session.execute_write(sync_automations_from_states, states)
        session.execute_write(sync_automations_from_yaml, automations_yaml)

    print(
        f"Synced: {len(states)} states, "
        f"{len(entity_registry)} entity registry entries, "
        f"{len(device_registry)} devices, "
        f"{len(area_registry)} areas, "
        f"{len(floor_registry)} floors, "
        f"{len(automations_yaml)} automations"
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
    print("HA Neo4j sync with areas, devices, automations and diagnostics loaded")

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