# Zeitliche und funktionale Projektbeschreibung

Dieses Dokument beschreibt, wie das Projekt `HA-CPsWMS` zeitlich und funktional arbeitet. Es verbindet Home-Assistant-Daten, eine semantische Identitaetsschicht, Neo4j-Persistenz, LLM-basierte Anreicherung und Abfrageoberflaechen zu einem semantischen World Model fuer Smart-Home-Systeme.

## Zielbild

Das System behandelt Home Assistant nicht als einzige Wahrheit, sondern als Datenquelle fuer ein dauerhaftes semantisches Modell. Rohdaten aus Home Assistant werden in Neo4j gespeichert, zu stabilen kanonischen Identitaeten aufgeloest, semantisch angereichert und anschliessend ueber feste APIs oder natuerlichsprachliche Fragen auswertbar gemacht.

```mermaid
flowchart LR
  HA[Home Assistant]
  Sync[ha-sync]
  Identity[Semantic Identity Layer]
  Neo4j[(Neo4j World Model)]
  Enrichment[semantic-enrichment]
  OpenAI[OpenAI API]
  Query[query-api]
  Chat[world-model-chat]
  User[Benutzer / Tool / UI]

  HA -->|States, Registries, Events, Automations| Sync
  Sync -->|RawEntity + Entity + Topologie| Identity
  Identity -->|CanonicalEntity, Evidence, Decisions| Neo4j
  Sync -->|Basisgraph| Neo4j
  Neo4j -->|Kandidaten lesen| Enrichment
  Enrichment -->|Schema-validierte Aufgaben| OpenAI
  OpenAI -->|JSON-Ergebnisse| Enrichment
  Enrichment -->|Semantische Knoten und Relationen| Neo4j
  User -->|Vorbereitete HTTP-Abfragen| Query
  Query -->|Read-only Cypher| Neo4j
  User -->|Natuerliche Sprache| Chat
  Chat -->|Cypher-Generierung + Antwort| OpenAI
  Chat -->|Validierte read-only Cypher-Abfrage| Neo4j
```

## Laufzeitstart

Der Stack wird ueber `docker-compose.yml` gestartet. Neo4j ist die zentrale Persistenzschicht. Die Worker und APIs verbinden sich per Bolt mit Neo4j.

Zeitlich passiert beim Start Folgendes:

1. `neo4j` startet und stellt Browser UI auf Port `7474` sowie Bolt auf Port `7687` bereit.
2. `ha-sync` startet, wartet auf Neo4j, legt Constraints fuer die wichtigsten Knotentypen an und beginnt den zyklischen Import.
3. `semantic-enrichment` startet, wartet ebenfalls auf Neo4j, initialisiert alle Enricher und legt gemeinsame sowie enricher-spezifische Constraints an.
4. `query-api` startet als HTTP-API auf Port `8080` und liest bei Anfragen aus Neo4j.
5. `world-model-chat` startet als FastAPI-Service auf Port `8090` und beantwortet natuerlichsprachliche Fragen ueber validierte Cypher-Abfragen.

```mermaid
sequenceDiagram
  participant Compose as docker compose
  participant Neo4j as neo4j
  participant Sync as ha-sync
  participant Enrich as semantic-enrichment
  participant Query as query-api
  participant Chat as world-model-chat

  Compose->>Neo4j: Container starten
  Compose->>Sync: Container starten
  Compose->>Enrich: Container starten
  Compose->>Query: Container starten
  Compose->>Chat: Container starten
  Sync->>Neo4j: Warten bis RETURN 1 erfolgreich ist
  Sync->>Neo4j: Constraints fuer Basis- und Identitaetsknoten anlegen
  Enrich->>Neo4j: Warten bis RETURN 1 erfolgreich ist
  Enrich->>Neo4j: Enrichment-Constraints anlegen
  Query->>Neo4j: Read-only Zugriff bei HTTP-Requests
  Chat->>Neo4j: Read-only Zugriff bei Chat-Requests
```

## Zeitlicher Hauptablauf

Das Projekt besteht aus zwei kontinuierlichen Schreibschleifen und zwei lesenden Schnittstellen.

### 1. Home-Assistant-Synchronisation

`ha-sync/sync.py` laeuft dauerhaft. Nach dem Start wartet es auf Neo4j, erstellt Constraints und fuehrt dann alle `SYNC_INTERVAL_SECONDS` einen kompletten Synchronisationslauf aus. Standardwert ist `300` Sekunden.

In einem Synchronisationslauf werden zuerst die aktuellen Daten aus Home Assistant gelesen:

- States ueber `/api/states`
- Entity-, Device-, Area-, Floor- und Config-Entry-Registry ueber Home-Assistant-WebSocket-Kommandos
- Event-Typen und Logbook-Eintraege, sofern `ENABLE_EVENT_HISTORY=true`
- Automationen aus dem konfigurierten YAML-Pfad `AUTOMATIONS_YAML_PATH`

Danach schreibt `ha-sync` die Daten in fester Reihenfolge in Neo4j:

1. Floors
2. Areas
3. Integrations
4. Devices
5. SourceSystem fuer die semantische Identitaetsschicht
6. Entities mit Domain, State, DeviceClass, Unit, Area, Device und Integration
7. RawEntity, CanonicalEntity, Evidence und ResolutionDecision, sofern `ENABLE_SEMANTIC_IDENTITY=true`
8. Automationen aus States und YAML
9. Event-Typen und Logbook-Ereignisse
10. Problem-Knoten fuer `unavailable`, `unknown`, `none` oder fehlende States
11. MQTT- und Zigbee-Modell, sofern aktiviert
12. Abgeleitete Shortcut-Relationen wie `CAN_CAUSE` und `EFFECTIVE_LOCATION`

```mermaid
sequenceDiagram
  participant Sync as ha-sync
  participant HA as Home Assistant
  participant Identity as Identity Pipeline
  participant Neo4j as Neo4j

  loop Alle SYNC_INTERVAL_SECONDS
    Sync->>HA: /api/states lesen
    Sync->>HA: Registries via WebSocket lesen
    Sync->>HA: Events und Logbook lesen
    Sync->>Sync: automations.yaml parsen
    Sync->>Neo4j: Floors, Areas, Integrations schreiben
    Sync->>Neo4j: Devices schreiben
    Sync->>Neo4j: Entity-Basisgraph schreiben
    alt Semantische Identitaet aktiv
      Sync->>Identity: Home-Assistant-Entity in RawEntity konvertieren
      Identity->>Identity: CanonicalEntity aufloesen oder erzeugen
      Identity->>Neo4j: RawEntity, CanonicalEntity, Evidence, Decision schreiben
      Sync->>Neo4j: Entity mit RawEntity verknuepfen
    end
    Sync->>Neo4j: Automationen, Events, Probleme schreiben
    Sync->>Neo4j: MQTT, Zigbee und Shortcut-Relationen schreiben
  end
```

### 2. Semantische Anreicherung

`semantic-enrichment/semantic_enrich.py` laeuft ebenfalls dauerhaft. Nach der Initialisierung fuehrt es alle Enricher in einer bewusst gewaehlten Reihenfolge aus und schlaeft danach `SLEEP_SECONDS` Sekunden. Standardwert ist ebenfalls `300` Sekunden.

Der Ablauf eines einzelnen Enrichers ist immer gleich:

1. Kandidaten aus Neo4j lesen.
2. Payload mit Taskname, Kandidaten und Regeln erzeugen.
3. OpenAI mit Prompt und JSON-Schema aufrufen.
4. JSON-Antwort parsen.
5. Ergebnisse validieren, inklusive Confidence-Pruefung gegen `MIN_CONFIDENCE`.
6. Gueltige Ergebnisse als semantische Knoten und Relationen in Neo4j schreiben.

Die Enricher laufen in dieser Reihenfolge:

1. `semantic_roles`
2. `room_inference`
3. `automation_intent`
4. `fault_analysis`
5. `anomaly_detection`
6. `temporal_event_model`
7. `failure_impact`
8. `capability_mapping`
9. `semantic_descriptions`
10. `dependency_reasoning`
11. `causal_dependency`
12. `recommended_actions`
13. `simulation_readiness`

Die Reihenfolge ist funktional wichtig: Basissemantik und Raumkontext werden zuerst erzeugt, danach folgen Automations-, Fehler-, Anomalie- und Zeitmodelle. Hoehere Analysen wie Impact, Capabilities, Abhaengigkeiten, empfohlene Aktionen und Simulation Readiness bauen auf diesen frueheren Schichten auf.

```mermaid
flowchart TB
  Start([Enrichment-Zyklus])
  Roles[semantic_roles]
  Room[room_inference]
  Automation[automation_intent]
  Fault[fault_analysis]
  Anomaly[anomaly_detection]
  Temporal[temporal_event_model]
  Impact[failure_impact]
  Capability[capability_mapping]
  Description[semantic_descriptions]
  Dependency[dependency_reasoning]
  Causal[causal_dependency]
  Actions[recommended_actions]
  Readiness[simulation_readiness]
  Sleep[SLEEP_SECONDS warten]

  Start --> Roles --> Room --> Automation --> Fault --> Anomaly --> Temporal
  Temporal --> Impact --> Capability --> Description --> Dependency --> Causal
  Causal --> Actions --> Readiness --> Sleep --> Start
```

## Funktionale Architektur

### `ha-sync`

`ha-sync` ist die Quelle der aktuellen Home-Assistant-Sicht. Es erzeugt den Basisgraphen mit Entitaeten, Geraeten, Bereichen, Stockwerken, Integrationen, Automationen, Events und Problemzustaenden.

Wichtige funktionale Aufgaben:

- Home-Assistant-REST- und WebSocket-Zugriff.
- Normalisierung komplexer Attributwerte in string- oder JSON-kompatible Werte.
- Aufbau von `Entity`, `Device`, `Area`, `Floor`, `Domain`, `DeviceClass`, `Unit`, `Integration`, `Automation`, `EventType` und `Problem`.
- Ableitung von Automationsbeziehungen wie `TRIGGERED_BY`, `CONTROLS` und `HAS_CONDITION`.
- Modellierung technischer Infrastruktur wie MQTT-Themen und Zigbee-Knoten.
- Einspeisung in die semantische Identitaetsschicht.

### Semantische Identitaetsschicht

Die semantische Identitaetsschicht entkoppelt Rohdaten von stabilen Identitaeten. Home Assistant liefert konkrete Quellobjekte, die als `RawEntity` gespeichert werden. Die Identity Pipeline loest sie gegen eine kanonische Sicht auf und erzeugt bei Bedarf `CanonicalEntity`-Knoten.

Wichtige Knotentypen:

- `SourceSystem`: beschreibt die Quelle, hier `homeassistant`.
- `RawEntity`: quellenspezifische Rohdarstellung.
- `CanonicalEntity`: stabile semantische Identitaet.
- `Evidence`: Begruendung fuer eine Zuordnung.
- `ResolutionDecision`: Entscheidung der Aufloesungspipeline.

```mermaid
classDiagram
  class SourceSystem {
    source_id
    source_type
    name
    trust_level
  }
  class RawEntity {
    raw_entity_id
    source_entity_id
    attributes
  }
  class CanonicalEntity {
    canonical_id
    name
    entity_type
  }
  class Evidence {
    evidence_id
    confidence
    reason
  }
  class ResolutionDecision {
    decision_id
    canonical_id
    decision_type
  }
  class Entity {
    entity_id
    friendly_name
    domain
    state
  }

  SourceSystem --> RawEntity : PROVIDES
  Entity --> RawEntity : HAS_RAW_REPRESENTATION
  RawEntity --> ResolutionDecision : HAS_RESOLUTION_DECISION
  ResolutionDecision --> CanonicalEntity : RESOLVES_TO
  ResolutionDecision --> Evidence : SUPPORTED_BY
```

### `semantic-enrichment`

`semantic-enrichment` liest den vorhandenen Graphen, erzeugt semantische Zusatzinformationen und schreibt sie zurueck. Jeder Enricher ist fachlich getrennt und besitzt eigene Prompts und JSON-Schemas. Dadurch koennen einzelne Analysearten unabhaengig weiterentwickelt werden.

Typische Ergebnisrelationen sind:

- `HAS_SEMANTIC_ROLE`
- `HAS_SEMANTIC_CATEGORY`
- `HAS_CRITICALITY`
- `HAS_AUTOMATION_INTENT`
- `HAS_ANOMALY`
- `HAS_OBSERVATION`
- `HAS_TIMELINE_EVENT`
- `HAS_STATE_TRANSITION`
- `HAS_INCIDENT`
- `PROVIDES_CAPABILITY`
- `CAUSES`
- `DEPENDS_ON`
- `IMPACTS`
- `DEGRADES`
- `RECOVERS`
- `HAS_FAILURE_IMPACT`
- `HAS_RECOMMENDED_ACTION`
- `HAS_SIMULATION_READINESS`

### `query-api`

`query-api/app.py` ist eine feste HTTP-Schicht fuer wiederkehrende Auswertungen. Sie generiert keine Cypher-Abfragen mit LLMs, sondern kapselt vorbereitete read-only Cypher-Queries.

Wichtige Endpunkte:

- `GET /health`
- `GET /api/capabilities`
- `GET /api/simulation-readiness`
- `GET /api/what-if/integration/{domain}`
- `GET /api/what-if/capability/{name}`
- `GET /api/entities/{entity_id}/impact`

Diese API eignet sich fuer UIs, Dashboards, Automatisierungen und externe Tools, die stabile Antwortformate benoetigen.

### `world-model-chat`

`world-model-chat/app.py` ist die natuerlichsprachliche Abfrageschicht. Bei `POST /chat` passiert folgender Ablauf:

1. Die Frage wird an OpenAI gesendet.
2. OpenAI liefert eine strukturierte Cypher-Beschreibung gemaess JSON-Schema.
3. Der Service validiert die Cypher-Abfrage.
4. Nur read-only Abfragen mit `MATCH` oder `OPTIONAL MATCH`, `RETURN` und `LIMIT` werden akzeptiert.
5. Schreibende oder administrative Cypher-Muster wie `CREATE`, `MERGE`, `SET`, `DELETE`, `DROP`, `CALL`, `LOAD CSV` oder `APOC` werden abgelehnt.
6. Die validierte Abfrage wird gegen Neo4j ausgefuehrt.
7. Die Ergebniszeilen werden an OpenAI gegeben, um eine lesbare Antwort zu formulieren.

```mermaid
sequenceDiagram
  participant User as Benutzer
  participant Chat as world-model-chat
  participant OpenAI as OpenAI
  participant Neo4j as Neo4j

  User->>Chat: POST /chat mit Frage
  Chat->>OpenAI: Cypher aus Frage generieren
  OpenAI-->>Chat: intent, cypher, parameters, confidence
  Chat->>Chat: Cypher read-only validieren
  Chat->>Neo4j: Validierte Cypher-Abfrage
  Neo4j-->>Chat: Ergebniszeilen
  Chat->>OpenAI: Antwort aus Frage und Zeilen formulieren
  OpenAI-->>Chat: Natuerliche Antwort
  Chat-->>User: Antwort, Intent, Confidence, Row Count
```

## Datenmodell in Schichten

Das World Model entsteht nicht in einem einzigen Schritt, sondern in Schichten:

```mermaid
flowchart TB
  Source[Quelldaten aus Home Assistant]
  Raw[RawEntity und Registry-Rohdaten]
  Base[Basisgraph: Entity, Device, Area, Integration, Automation]
  Identity[Canonical Entity Layer]
  Operational[Operationaler Kontext: Events, Problems, MQTT, Zigbee]
  Semantic[Semantik: Rollen, Kategorien, Kritikalitaet]
  Temporal[Zeitmodell: Observations, Timeline Events, State Transitions]
  Causal[Kausalitaet und Abhaengigkeiten]
  Simulation[Simulation Readiness und What-if-Kontext]
  Access[Query API und World Model Chat]

  Source --> Raw --> Base --> Identity
  Base --> Operational
  Identity --> Semantic
  Operational --> Semantic
  Semantic --> Temporal --> Causal --> Simulation --> Access
  Base --> Access
```

## Zeitliche Konsistenz und Aktualisierung

Das System ist eventual-consistent. `ha-sync` und `semantic-enrichment` laufen unabhaengig voneinander in Intervallen. Dadurch kann es kurze Zeitfenster geben, in denen neue Home-Assistant-Entities bereits im Basisgraphen vorhanden sind, aber noch keine semantischen Rollen, Impact-Analysen oder Simulation-Readiness-Bewertungen besitzen.

Die typische zeitliche Entwicklung einer neuen Entity ist:

1. Home Assistant stellt eine neue Entity bereit.
2. Beim naechsten `ha-sync`-Lauf wird sie als `Entity` in Neo4j geschrieben.
3. Falls semantische Identitaet aktiv ist, wird eine `RawEntity` erzeugt und einer `CanonicalEntity` zugeordnet.
4. Beim naechsten `semantic-enrichment`-Zyklus erscheint sie als Kandidat fuer passende Enricher.
5. Nach erfolgreichen LLM-Antworten und Confidence-Pruefung entstehen semantische Relationen.
6. Query API und Chat koennen die neue Entity zunehmend reichhaltiger beantworten.

## Betriebs- und Sicherheitsgrenzen

- Schreibzugriffe erfolgen durch `ha-sync` und `semantic-enrichment`.
- `query-api` liest ausschliesslich vorbereitete Graphabfragen.
- `world-model-chat` validiert LLM-generierte Cypher-Abfragen streng vor der Ausfuehrung.
- Secrets wie `HA_TOKEN`, `NEO4J_PASSWORD` und `OPENAI_API_KEY` werden ueber Umgebungsvariablen bereitgestellt.
- Neo4j-Daten liegen lokal unter `neo4j/data`, Logs unter `neo4j/logs`.

## Zusammenfassung

Funktional baut das Projekt aus Home-Assistant-Daten ein semantisches, abfragbares Smart-Home-Weltmodell. Zeitlich arbeitet es in wiederkehrenden Zyklen: zuerst werden aktuelle HA-Daten importiert und identitaetsstabil gespeichert, danach werden semantische und kausale Schichten angereichert. Lesende Schnittstellen greifen jederzeit auf den jeweils aktuellen Stand des Graphen zu.
