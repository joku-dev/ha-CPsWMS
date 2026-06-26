# HA-CPsWMS: Semantic Identity Layer + Neo4j World Model

Dieses Projekt erweitert die bestehende Home-Assistant-zu-Neo4j-Synchronisation um eine
quelle-unabhängige semantische Identitätsschicht. Der neue Kern bildet Raw Entities,
Canonical Entities, Evidenzen und Review-Entscheidungen ab und ermöglicht damit
eine stabilere, wiedererkennbare Modellierung von Geräten, Sensoren und Beobachtungen.

Kurz gesagt: Dieses Repository baut ein semantisches World Model, das Home Assistant
als einen von mehreren möglichen Quellen behandelt. Es unterstützt die Zuordnung
von Rohdaten zu stabilen Identitäten und legt damit die Grundlage für spätere
Ontologie-, Zeit- und Kausalmodellierung.

> Testhinweis: Diese Änderung dient zum Auslösen des zentralen DevSecOps-Baseline-Workflows.

## Komponenten

1. `neo4j`: Graphdatenbank
2. `ha-sync`: Importiert States, Registry-Daten und Automationen
3. `semantic-enrichment`: Fuehrt mehrere spezialisierte Enricher mit OpenAI aus
4. `query-api`: Stellt vorbereitete Graph-Abfragen fuer What-if- und Impact-Fragen bereit
5. `world-model-chat`: Beantwortet freie Fragen per validierter read-only Cypher-Generierung

## Repository-Struktur

- `docker-compose.yml`: Startet alle Services
- `ha-sync/`: Sync-Logik und Dockerfile
- `semantic-enrichment/`: Enrichment-Orchestrator, Enricher, Prompts und Schemas
- `query-api/`: HTTP-API fuer semantische Graph-Abfragen
- `world-model-chat/`: FastAPI-Chat-Schicht ueber dem Neo4j-World-Model
- `docs/`: Architektur, Deployment, FAQ und Enrichment-Doku
- `docs/CANONICAL_ENTITY_LAYER.md`: Dokumentation der neuen semantischen Identitätsschicht
- `docs/GOVERNANCE_BASELINE_STATEMENT.md`: Offizielles Statement zur erfolgreichen L1-Governance-Baseline-Integration
- `docs/HOW_TO_USE_CENTRAL_GOVERNANCE_BASELINE.md`: Schritt-für-Schritt-Anleitung für andere Repositories zur Nutzung des zentralen Governance-as-Code-Repos
- `.env.example`: Beispielkonfiguration

## Schnellstart

1. `.env` anlegen:

```bash
cp .env.example .env
```

2. Zugangsdaten in `.env` setzen:

- `HA_URL`
- `HA_TOKEN`
- `NEO4J_PASSWORD`
- optional: `OPENAI_API_KEY`

3. Stack starten:

```bash
docker compose up -d --build
```

4. Logs pruefen:

```bash
docker compose logs -f ha-sync
docker compose logs -f semantic-enrichment
```

5. Neo4j Browser:

- `http://localhost:7474`

6. Query API:

- `http://localhost:8080/health`

## Von Scratch starten

Diese Schritte bauen das komplette System aus einem frischen Checkout oder nach einem lokalen Reset neu auf.

1. Repository vorbereiten:

```bash
git pull
cp .env.example .env
```

2. `.env` ausfuellen:

- `HA_URL`
- `HA_TOKEN`
- `NEO4J_PASSWORD`
- `NEO4J_AUTH`, zum Beispiel `neo4j/<NEO4J_PASSWORD>`
- optional: `OPENAI_API_KEY`, wenn `semantic-enrichment` laufen soll
- optional: `OPENAI_MODEL`

3. Falls ein komplett leerer Graph gewuenscht ist, lokale Neo4j-Daten entfernen:

```bash
docker compose down
rm -rf neo4j/data neo4j/logs
mkdir -p neo4j/logs
```

Dieser Schritt loescht den lokalen Graphen. Ohne diesen Schritt wird der bestehende Neo4j-Datenstand wiederverwendet.

4. Stack bauen und starten:

```bash
docker compose up -d --build
```

5. Status pruefen:

```bash
docker compose ps
```

6. Sync-Logs beobachten, bis ein erfolgreicher Lauf sichtbar ist:

```bash
docker compose logs -f ha-sync
```

Erwartete Erfolgsmeldung:

```text
Synced: ... states, ... entities, ... devices, ... areas, ...
```

7. Optional Enrichment-Logs beobachten:

```bash
docker compose logs -f semantic-enrichment
```

Wenn kein OpenAI-Budget oder kein gueltiger `OPENAI_API_KEY` verfuegbar ist, kann der Enrichment-Container gestoppt bleiben:

```bash
docker compose stop semantic-enrichment
```

Nach Freischaltung des LLM-Layers:

```bash
docker compose up -d semantic-enrichment
```

8. Neo4j Browser oeffnen:

- `http://localhost:7474`

Login:

- Benutzer: `neo4j`
- Passwort: Wert aus `NEO4J_PASSWORD`

9. Basisobjekte in Neo4j pruefen:

```cypher
MATCH (e:Entity)
RETURN count(e) AS entities;
```

Canonical Entity Layer pruefen:

```cypher
MATCH (r:RawEntity)
RETURN count(r) AS raw_entities;
```

```cypher
MATCH (c:CanonicalEntity)
RETURN count(c) AS canonical_entities;
```

```cypher
MATCH (:RawEntity)-[rel:RESOLVED_TO]->(:CanonicalEntity)
RETURN count(rel) AS resolutions;
```

10. APIs pruefen:

```bash
curl http://localhost:8080/health
curl http://localhost:8090/health
```

11. Optional Benchmark ausfuehren:

```bash
python -m benchmark.benchmark_runner \
  --target ha-CPsWMS \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password "$NEO4J_PASSWORD" \
  --output benchmark/reports \
  --format json,md,csv
```

Reports werden unter `benchmark/reports/` erzeugt. Diese Dateien sind lokale Laufartefakte und werden nicht versioniert.

## Herunterfahren

Services stoppen, aber Container und lokale Daten behalten:

```bash
docker compose stop
```

Services wieder starten:

```bash
docker compose start
```

Container entfernen, lokale Neo4j-Daten aber behalten:

```bash
docker compose down
```

Komplett herunterfahren und lokalen Graphen loeschen:

```bash
docker compose down
rm -rf neo4j/data neo4j/logs
mkdir -p neo4j/logs
```

Nur einzelne Services neu starten:

```bash
docker compose restart ha-sync
docker compose restart semantic-enrichment
docker compose restart query-api
docker compose restart world-model-chat
```

## Wichtige Umgebungsvariablen

Basis:

- `HA_URL`
- `HA_TOKEN`
- `NEO4J_URI` (Standard in Compose: `bolt://neo4j:7687`)
- `NEO4J_USER` (Standard: `neo4j`)
- `NEO4J_PASSWORD`
- `SYNC_INTERVAL_SECONDS` (Standard: `300`)

Semantic Enrichment:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (Standard: `gpt-5.5`)
- `BATCH_SIZE` (Standard: `20`)
- `SLEEP_SECONDS` (Standard: `300`)
- `MIN_CONFIDENCE` (Standard: `0.5`)

Query API:

- `QUERY_API_PORT` (Standard: `8080`)
- `QUERY_API_DEFAULT_LIMIT` (Standard: `25`)
- `QUERY_API_MAX_LIMIT` (Standard: `100`)

World Model Chat:

- `WORLD_MODEL_CHAT_PORT` (Standard: `8090`)
- `WORLD_MODEL_CHAT_MAX_QUERY_ROWS` (Standard: `100`)
- `WORLD_MODEL_CHAT_MIN_CYPHER_CONFIDENCE` (Standard: `0.4`)

## Aktive Semantic-Enricher

Der Orchestrator `semantic-enrichment/semantic_enrich.py` fuehrt folgende Enricher aus:

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

## Von Enrichment erzeugte Relationen

- `HAS_SEMANTIC_ROLE`
- `HAS_SEMANTIC_CATEGORY`
- `HAS_CRITICALITY`
- `HAS_AUTOMATION_INTENT`
- `HAS_FAULT_ANALYSIS`
- `HAS_ANOMALY`
- `HAS_OBSERVATION`
- `HAS_TIMELINE_EVENT`
- `HAS_STATE_TRANSITION`
- `HAS_INCIDENT`
- `INFERRED_LOCATION`
- `SEMANTICALLY_RELATED_TO`
- `PROVIDES_CAPABILITY`
- `CAUSES`
- `DEPENDS_ON`
- `IMPACTS`
- `DEGRADES`
- `RECOVERS`
- `HAS_FAILURE_IMPACT`
- `HAS_SEMANTIC_DESCRIPTION`
- `HAS_RECOMMENDED_ACTION`
- `HAS_SIMULATION_READINESS`
- `EVALUATES_TARGET`

## Beispielabfragen in Neo4j

Semantische Rollen:

```cypher
MATCH (e:Entity)-[r:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
RETURN e.entity_id, e.friendly_name, role.name, r.confidence
ORDER BY r.confidence DESC
LIMIT 25;
```

Anomalien mit hoher Prioritaet:

```cypher
MATCH (e:Entity)-[r:HAS_ANOMALY]->(a:AnomalyType)
WHERE r.severity IN ["high", "critical"]
RETURN e.entity_id, e.friendly_name, a.name, r.severity, r.confidence;
```

Empfohlene Aktionen:

```cypher
MATCH (e:Entity)-[r:HAS_RECOMMENDED_ACTION]->(a:RecommendedActionType)
RETURN e.entity_id, e.friendly_name, a.name, r.priority, r.effort, r.confidence
ORDER BY r.confidence DESC
LIMIT 25;
```

## Query API

Die Query API kapselt haeufige Neo4j-Abfragen fuer die spaetere UI oder externe Tools.

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/capabilities
curl http://localhost:8080/api/simulation-readiness
curl http://localhost:8080/api/what-if/integration/zigbee
curl http://localhost:8080/api/what-if/capability/lighting
curl http://localhost:8080/api/entities/binary_sensor.motion/impact
```

Eine ausfuehrliche Beschreibung mit Antwortbeispielen steht in `docs/QUERY_API.md`.

## World Model Chat

Der World Model Chat beantwortet freie Fragen ueber den Graph. Er erzeugt dafuer
eine read-only Cypher-Abfrage, validiert sie, liest Neo4j und formuliert daraus
eine Antwort.

```bash
curl -X POST http://localhost:8090/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Was passiert, wenn Zigbee ausfaellt?","include_cypher":true}'
```

FastAPI-Doku:

- `http://localhost:8090/docs`

## Dokumentation

- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/QUERY_API.md`
- `docs/SEMANTIC_ENRICHMENT.md`
- `docs/WORLD_MODEL_CHAT.md`
- `Semantic_World_Model4HomeAssistant.md`
- `docs/FAQ.md`
- `docs/CODEBASE_RECHECK_2026-05-08.md`
- `Functional_Description.md`
- `semantic-enrichment/enrichers/README.md`

## Sicherheit

- Keine Secrets ins Repository committen.
- `.env` lokal halten.
- Neo4j-Daten (`neo4j/data`) und Logs (`neo4j/logs`) bleiben lokal.
