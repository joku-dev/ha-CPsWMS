"""Sync Home Assistant state data into Neo4j.

Dieses Modul liest Home Assistant Entity-States über die REST-API
und speichert sie in einer Neo4j-Datenbank. Dabei werden Knoten für
Entity, Room, DeviceClass und Unit angelegt und Beziehungen erstellt.
"""

import os
import time
import requests
from neo4j import GraphDatabase


# Erforderliche Umgebungsvariablen für den Container.
HA_URL = os.environ["HA_URL"].rstrip("/")
HA_TOKEN = os.environ["HA_TOKEN"]

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# Intervall in Sekunden, wie oft ein Sync durchgeführt wird.
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))


def get_ha_states():
    """Ruft alle Entity-States von Home Assistant ab."""
    response = requests.get(
        f"{HA_URL}/api/states",
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def room_from_attributes(attributes):
    """Ermittelt den Raum oder die Area aus den Entity-Attributen."""
    area = attributes.get("area_id")
    room = attributes.get("room")

    if area:
        return area
    if room:
        return room

    return "unknown"


def normalize_value(value):
    """Bereitet Werte für die Speicherung in Neo4j vor."""
    if value is None:
        return None
    return str(value)


def create_constraints(driver):
    """Legt eindeutige Constraints in Neo4j für die wichtigsten Knoten an."""
    with driver.session() as session:
        session.run("""
        CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
        FOR (e:Entity)
        REQUIRE e.entity_id IS UNIQUE
        """)

        session.run("""
        CREATE CONSTRAINT room_name_unique IF NOT EXISTS
        FOR (r:Room)
        REQUIRE r.name IS UNIQUE
        """)

        session.run("""
        CREATE CONSTRAINT device_class_unique IF NOT EXISTS
        FOR (d:DeviceClass)
        REQUIRE d.name IS UNIQUE
        """)

        session.run("""
        CREATE CONSTRAINT unit_name_unique IF NOT EXISTS
        FOR (u:Unit)
        REQUIRE u.name IS UNIQUE
        """)


def sync_entity(tx, entity):
    """Synchronisiert eine einzelne Home Assistant Entity mit Neo4j."""
    entity_id = entity["entity_id"]
    domain = entity_id.split(".")[0]
    state = normalize_value(entity.get("state"))

    attributes = entity.get("attributes", {})

    friendly_name = attributes.get("friendly_name", entity_id)
    room = room_from_attributes(attributes)

    device_class = attributes.get("device_class")
    unit = attributes.get("unit_of_measurement")
    icon = attributes.get("icon")
    entity_category = attributes.get("entity_category")

    tx.run(
        """
        MERGE (e:Entity {entity_id: $entity_id})
        SET
            e.domain = $domain,
            e.state = $state,
            e.friendly_name = $friendly_name,
            e.icon = $icon,
            e.entity_category = $entity_category,
            e.last_changed = datetime($last_changed),
            e.last_updated = datetime($last_updated)

        MERGE (r:Room {name: $room})
        MERGE (e)-[:LOCATED_IN]->(r)

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
        room=room,
        device_class=device_class,
        unit=unit,
        icon=icon,
        entity_category=entity_category,
        last_changed=entity["last_changed"],
        last_updated=entity["last_updated"],
    )


def run_sync(driver):
    """Führt den kompletten Synchronisationslauf aus."""
    states = get_ha_states()

    with driver.session() as session:
        for entity in states:
            session.execute_write(sync_entity, entity)

    print(f"Synced {len(states)} Home Assistant entities to Neo4j")


def wait_for_neo4j(driver, retries=30, delay=5):
    """Wartet, bis die Neo4j-Datenbank erreichbar ist."""
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
    """Startet die Sync-Anwendung."""
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
