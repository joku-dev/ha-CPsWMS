# Functional Description

Diese Datei beschreibt, wie der Code funktioniert und wie die Abhaengigkeiten im Projekt aufgebaut sind.

## 1. Gesamtueberblick

Das Repository implementiert zwei Haupt-Pipelines und zwei Abfrageschichten:

1. `ha-sync`: Liest Daten aus Home Assistant und schreibt sie als Graph nach Neo4j.
2. `semantic-enrichment`: Liest Graph-Kandidaten aus Neo4j und reichert sie mit LLM-basierten Semantiken an.
3. `query-api`: Stellt feste read-only HTTP-Abfragen fuer What-if-, Impact- und Readiness-Fragen bereit.
4. `world-model-chat`: Beantwortet freie Fragen mit LLM-generierter, validierter read-only Cypher-Abfrage.

Die zentrale Laufzeitsequenz ist:

1. Home Assistant -> `ha-sync`
2. `ha-sync` -> Neo4j
3. `semantic-enrichment` -> liest aus Neo4j
4. `semantic-enrichment` -> OpenAI Responses API
5. `semantic-enrichment` -> schreibt Ergebnis nach Neo4j
6. `query-api` -> liest vorbereitete Sichten aus Neo4j
7. `world-model-chat` -> OpenAI erzeugt Cypher, Neo4j liefert Daten, OpenAI formuliert Antwort

## 1.1 Architekturdiagramm

```mermaid
flowchart LR
  HA[Home Assistant]
  Sync[ha-sync]
  Neo4j[(Neo4j)]
  Orch[semantic_enrich.py Orchestrator]
  QueryAPI[query-api]
  Chat[world-model-chat]
  OpenAI[OpenAI Responses API]

  E1[semantic_roles]
  E2[room_inference]
  E3[automation_intent]
  E4[fault_analysis]
  E5[anomaly_detection]
  E6[temporal_event_model]
  E7[failure_impact]
  E8[capability_mapping]
  E9[semantic_descriptions]
  E10[dependency_reasoning]
  E11[causal_dependency]
  E12[recommended_actions]
  E13[simulation_readiness]

  HA -->|REST + WebSocket| Sync
  Sync -->|Bolt write| Neo4j
  Neo4j -->|Candidate read| Orch

  Orch --> E1 --> E2 --> E3 --> E4 --> E5 --> E6 --> E7 --> E8 --> E9 --> E10 --> E11 --> E12 --> E13

  E1 -->|LLM request| OpenAI
  E2 -->|LLM request| OpenAI
  E3 -->|LLM request| OpenAI
  E4 -->|LLM request| OpenAI
  E5 -->|LLM request| OpenAI
  E6 -->|LLM request| OpenAI
  E7 -->|LLM request| OpenAI
  E8 -->|LLM request| OpenAI
  E9 -->|LLM request| OpenAI
  E10 -->|LLM request| OpenAI
  E11 -->|LLM request| OpenAI
  E12 -->|LLM request| OpenAI
  E13 -->|LLM request| OpenAI

  E1 -->|Graph write| Neo4j
  E2 -->|Graph write| Neo4j
  E3 -->|Graph write| Neo4j
  E4 -->|Graph write| Neo4j
  E5 -->|Graph write| Neo4j
  E6 -->|Graph write| Neo4j
  E7 -->|Graph write| Neo4j
  E8 -->|Graph write| Neo4j
  E9 -->|Graph write| Neo4j
  E10 -->|Graph write| Neo4j
  E11 -->|Graph write| Neo4j
  E12 -->|Graph write| Neo4j
  E13 -->|Graph write| Neo4j

  QueryAPI -->|Bolt read| Neo4j
  Chat -->|Cypher generation| OpenAI
  Chat -->|Bolt read| Neo4j
  Chat -->|Answer generation| OpenAI
```

## 2. Wichtige Einstiegspunkte

### 2.1 `ha-sync/sync.py`

Verantwortung:

- Abfragen gegen Home Assistant (`/api/states`, Registry-Endpunkte)
- Normalisierung von Attributen
- Persistenz in Neo4j (Knoten + Kanten)
- Wiederholter Sync in Intervallen

Direkte technische Abhaengigkeiten:

- `requests`
- `websocket-client`
- `pyyaml`
- `neo4j`

### 2.2 `semantic-enrichment/semantic_enrich.py`

Verantwortung:

- Startet den Enrichment-Orchestrator
- Wartet auf Neo4j-Verfuegbarkeit
- Initialisiert alle Enricher
- Fuehrt jeden Enricher zyklisch aus (`while True`)

### 2.3 `query-api/app.py`

Verantwortung:

- Stellt feste read-only HTTP-Endpunkte fuer haeufige Graph-Fragen bereit
- Kapselt Cypher fuer Capabilities, Simulation Readiness, What-if-Szenarien und Entity Impact
- Liest ausschliesslich aus Neo4j und schreibt keine Graphdaten
- Wandelt Neo4j-Datentypen in JSON-kompatible HTTP-Antworten um

Typische Endpunkte:

- `GET /health`
- `GET /api/capabilities`
- `GET /api/simulation-readiness`
- `GET /api/what-if/integration/{domain}`
- `GET /api/what-if/capability/{name}`
- `GET /api/entities/{entity_id}/impact`

### 2.4 `world-model-chat/app.py`

Verantwortung:

- Nimmt freie Fragen per `POST /chat` entgegen
- Laesst OpenAI eine strukturierte Cypher-Abfrage erzeugen
- Validiert, dass die Query read-only ist, `RETURN` und `LIMIT` enthaelt und keine Schreiboperation nutzt
- Fuehrt die Query gegen Neo4j aus
- Laesst OpenAI aus Frage, Query und Ergebnisdaten eine Antwort formulieren

Der Service ist bewusst getrennt von `query-api`: `query-api` ist die stabile Maschinen-API,
`world-model-chat` ist die flexible Sprachschnittstelle.

## 3. Enrichment-Architektur

### 3.1 Basisklasse: `semantic-enrichment/enrichers/base.py`

`BaseEnricher` kapselt den gemeinsamen Ablauf:

1. `setup()` -> ruft `create_constraints()`
2. `run_once()`:
   - `get_candidates(limit)`
   - `call_llm(payload)` mit JSON-Schema
   - `validate_items(...)`
   - `write_results(items)`

Damit muessen konkrete Enricher nur die fachspezifischen Teile implementieren.

### 3.2 Aktive Enricher

Die aktuell verdrahtete Reihenfolge in `semantic_enrich.py`:

1. `SemanticRolesEnricher`
2. `RoomInferenceEnricher`
3. `AutomationIntentEnricher`
4. `FaultAnalysisEnricher`
5. `AnomalyDetectionEnricher`
6. `TemporalEventModelEnricher`
7. `FailureImpactEnricher`
8. `CapabilityMappingEnricher`
9. `SemanticDescriptionsEnricher`
10. `DependencyReasoningEnricher`
11. `CausalDependencyEnricher`
12. `RecommendedActionsEnricher`
13. `SimulationReadinessEnricher`

## 4. Fachliche Abhaengigkeiten der Enricher

### 4.1 Fruehe Basis-Enricher

- `semantic_roles` liefert grundlegende Klassifikation (`Role`, `Category`, `Criticality`).
- `room_inference` liefert Lage-/Area-Kontext.

Diese Ergebnisse verbessern nachgelagerte Enricher.

### 4.2 Analyse-Enricher

- `automation_intent` analysiert Automationen.
- `fault_analysis` analysiert problematische Entities.
- `anomaly_detection` erkennt Anomalien aus Zustands- und Event-Kontext.
- `temporal_event_model` erzeugt zeitbezogene Ereignisstrukturen (`Observation`, `StateTransition`, `TimelineEvent`, `Incident`).

### 4.3 Abgeleitete Enricher

- `failure_impact` nutzt u. a. Semantik, Criticality, Area und Automationsbezug.
- `capability_mapping` erzeugt explizite `PROVIDES_CAPABILITY`-Beziehungen
  zwischen Entities und `Capability`-Knoten.
- `semantic_descriptions` nutzt vorhandenen semantischen Kontext fuer beschreibende Texte.
- `dependency_reasoning` erkennt Beziehungen zwischen Entities.
- `causal_dependency` leitet Kausalketten aus Faehigkeiten, Zeitdaten, Incidents
  und Automationsbeziehungen ab.

### 4.4 Abschluss-Enricher

- `recommended_actions` konsolidiert mehrere Voranalysen
  (z. B. Anomalien, Faults, Failure Impact, temporales Ereignismodell).
- `simulation_readiness` ist die spaeteste Schicht und bewertet, ob fuer
  Was-waere-wenn-Simulationen genug Faehigkeiten, Dependencies,
  Fehlerhistorie, Automationsbeziehungen und kritische Entities vorhanden sind.

## 5. Daten- und Dateiabhaengigkeiten

Jeder Enricher hat drei zentrale statische Angaben:

1. `prompt_file` -> Datei unter `semantic-enrichment/prompts/`
2. `schema_file` -> Datei unter `semantic-enrichment/schemas/`
3. `response_key` -> JSON-Feldname, der aus der LLM-Antwort gelesen wird

Beispiel:

- `TemporalEventModelEnricher`
  - Prompt: `prompts/temporal_event_model.md`
  - Schema: `schemas/temporal_event_model_schema.json`
  - Key: `temporal_events`

Wenn Prompt/Schema nicht existieren oder nicht zum `response_key` passen,
schlaegt der Lauf zur Laufzeit fehl.

## 6. Externe Abhaengigkeiten

### 6.1 Infrastruktur

- Neo4j (Bolt)
- Home Assistant API
- OpenAI Responses API

### 6.2 Python-Packages

`ha-sync/requirements.txt`:

- `requests`
- `neo4j`
- `websocket-client`
- `pyyaml`

`semantic-enrichment/requirements.txt`:

- `openai`
- `neo4j`
- `python-dotenv`

`query-api/requirements.txt`:

- `neo4j`

`world-model-chat/requirements.txt`:

- `fastapi`
- `uvicorn[standard]`
- `neo4j`
- `openai`
- `python-dotenv`

## 7. Konfiguration

Die Enrichment-Konfiguration sitzt in `semantic-enrichment/config.py`.

Wichtige Variablen:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `BATCH_SIZE`
- `SLEEP_SECONDS`
- `MIN_CONFIDENCE`

Pfadvariablen:

- `PROMPTS_DIR`
- `SCHEMAS_DIR`

Die Query-API-Konfiguration sitzt direkt in `query-api/app.py`.

Wichtige Variablen:

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `QUERY_API_PORT`
- `QUERY_API_DEFAULT_LIMIT`
- `QUERY_API_MAX_LIMIT`

Die World-Model-Chat-Konfiguration sitzt in `world-model-chat/config.py`.

Wichtige Variablen:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `WORLD_MODEL_CHAT_PORT`
- `WORLD_MODEL_CHAT_MAX_QUERY_ROWS`
- `WORLD_MODEL_CHAT_MIN_CYPHER_CONFIDENCE`

## 8. Laufzeitverhalten und Fehlertoleranz

- Der Orchestrator faengt Exceptions pro Enricher ab.
- Ein fehlerhafter Enricher stoppt nicht den gesamten Zyklus.
- Nach jedem vollen Durchlauf wird `SLEEP_SECONDS` gewartet.
- `query-api` beantwortet nur vorbereitete GET-Abfragen und ist read-only.
- `world-model-chat` blockiert schreibende oder administrative Cypher-Bestandteile,
  bevor eine LLM-generierte Query Neo4j erreicht.

## 9. CI-Absicherung

Die CI (`.github/workflows/ci.yml`) prueft unter Ubuntu und Debian u. a.:

1. Syntax (`compileall`)
2. Enricher-Wiring (`scripts/ci_validate_enrichment.py`)
3. Import-Smoketest
4. Docker-Compose-Konfiguration (Ubuntu-Job)

Damit werden Strukturfehler (fehlende Prompts/Schemas, falsche Verdrahtung,
leere Module, doppelte Legacy-Dateien) frueh erkannt.

## 10. Kurzfazit

Das System ist modular aufgebaut:

- `ha-sync` erstellt den operativen Graph.
- `semantic-enrichment` erweitert ihn in klar getrennten, wiederverwendbaren Enrichern.
- `query-api` kapselt stabile, vorbereitete Graph-Abfragen.
- `world-model-chat` erlaubt freie Fragen auf Basis validierter read-only Cypher-Abfragen.
- `BaseEnricher` sorgt fuer konsistente Ausfuehrung.
- Die Enricher-Reihenfolge ist bewusst entlang fachlicher Abhaengigkeiten gestaltet.
