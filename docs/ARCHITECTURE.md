# Architektur

Diese Architektur-Dokumentation beschreibt den Aufbau des Home Assistant → Neo4j Sync-Projekts.

## Komponenten

- `docker-compose.yml`: Stellt drei Container bereit:
    - `neo4j`: Neo4j-Datenbank
    - `ha-sync`: Python-basiertes Sync-Skript
    - `semantic-enrichment`: Python-basiertes Enrichment-Skript mit OpenAI
- `ha-sync/Dockerfile`: Baut das Python-Image mit `requests` und dem offiziellen `neo4j`-Treiber.
- `ha-sync/sync.py`: Liest Home Assistant-States über die REST-API und schreibt sie per Bolt in Neo4j.
- `semantic-enrichment/Dockerfile`: Baut das Python-Image mit `openai` und `neo4j`-Treiber.
- `semantic-enrichment/semantic_enrich.py`: Bereichert Entities mit semantischen Klassifizierungen von OpenAI.
- `neo4j/data` und `neo4j/logs`: Persistente Daten- und Log-Verzeichnisse für Neo4j.

## Datenfluss

1. Der `ha-sync`-Container verbindet sich mit Home Assistant über die URL `HA_URL`.
2. Er ruft die Entitäten über den Endpunkt `/api/states` ab.
3. Für jede Entity wird geprüft, ob sie bereits in Neo4j existiert.
4. Entity-, Room-, DeviceClass- und Unit-Knoten werden angelegt oder aktualisiert.
5. Beziehungen wie `LOCATED_IN`, `HAS_DEVICE_CLASS` und `MEASURED_IN` werden aufgebaut.

## Systemdiagramm

```mermaid
flowchart LR
  HA[Home Assistant]
  Sync[ha-sync Container]
  Enrich[semantic-enrichment Container]
  Neo4j[Neo4j Container]
  OpenAI["OpenAI API"]
  Data[neo4j/data]
  Logs[neo4j/logs]

  HA -->|REST API /api/states| Sync
  Sync -->|Bolt: Write Entities| Neo4j
  Enrich -->|Bolt: Read Entities| Neo4j
  Enrich -->|Add Semantic Data| Neo4j
  Enrich -->|API Request| OpenAI
  OpenAI -->|Enrichment Response| Enrich
  Neo4j -->|speichert Daten| Data
  Neo4j -->|schreibt Logs| Logs
```

## Ablauf in `ha-sync/sync.py`

- `get_ha_states()` holt alle Entity-States von Home Assistant.
- `room_from_attributes()` bestimmt den Raum oder die Area des Geräts.
- `create_constraints()` definiert Neo4j-Constraints zur Vermeidung doppelter Knoten.
- `sync_entity()` schreibt oder aktualisiert eine einzelne Entity und deren Beziehungen.
- `run_sync()` führt die Synchronisation für alle Entities aus.
- `wait_for_neo4j()` stellt sicher, dass Neo4j erreichbar ist, bevor Daten geschrieben werden.

## Ablauf in `semantic-enrichment/semantic_enrich.py`

- `get_entities_for_enrichment()` holt alle Entities, die noch nicht semantisch angereichert wurden.
- Die Entities werden in Batches an OpenAI gesendet mit einem Prompt aus `prompts/semantic_roles.md`.
- OpenAI antwortet mit semantischen Klassifizierungen (Rollen, Kategorien, Criticality).
- Die Antworten werden nach dem Schema in `schemas/enrichment_schema.json` validiert.
- Neue `SemanticRole`, `SemanticCategory` und `Criticality` Knoten werden in Neo4j erstellt.
- Beziehungen zwischen Entities und diesen neuen Knoten werden aufgebaut.

## Datenfluss

1. Home Assistant erzeugt Events und States
2. `ha-sync` liest diese States und speichert sie als Entity-Knoten
3. `semantic-enrichment` liest die Entities und enreichert sie mit OpenAI-Klassifizierungen
4. Neo4j speichert alle Daten persistierend

## Vorteile dieser Architektur

- Einfaches Setup mit Docker Compose
- Trennung von Datenbank und Sync-Logik
- Persistente Neo4j-Daten ohne Commit in Git
- Flexible Konfiguration über Umgebungsvariablen

## Erweiterungsmöglichkeiten

- Zusätzliche Home Assistant-Endpoints synchronisieren
- Mehr Entitäten und Attribute abbilden
- Fehlerhandling und Metriken erweitern
- Optionaler Data-Export aus Neo4j
