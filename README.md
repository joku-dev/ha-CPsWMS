# Home Assistant -> Neo4j Sync + Semantic Enrichment

Dieses Projekt synchronisiert Home-Assistant-Daten nach Neo4j und erweitert den Graph anschliessend mit LLM-basierten semantischen Beziehungen.

## Komponenten

1. `neo4j`: Graphdatenbank
2. `ha-sync`: Importiert States, Registry-Daten und Automationen
3. `semantic-enrichment`: Fuehrt mehrere spezialisierte Enricher mit OpenAI aus

## Repository-Struktur

- `docker-compose.yml`: Startet alle Services
- `ha-sync/`: Sync-Logik und Dockerfile
- `semantic-enrichment/`: Enrichment-Orchestrator, Enricher, Prompts und Schemas
- `docs/`: Architektur, Deployment, FAQ und Enrichment-Doku
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

## Aktive Semantic-Enricher

Der Orchestrator `semantic-enrichment/semantic_enrich.py` fuehrt folgende Enricher aus:

1. `semantic_roles`
2. `room_inference`
3. `automation_intent`
4. `fault_analysis`
5. `anomaly_detection`
6. `failure_impact`
7. `semantic_descriptions`
8. `dependency_reasoning`
9. `recommended_actions`

## Von Enrichment erzeugte Relationen

- `HAS_SEMANTIC_ROLE`
- `HAS_SEMANTIC_CATEGORY`
- `HAS_CRITICALITY`
- `HAS_AUTOMATION_INTENT`
- `HAS_FAULT_ANALYSIS`
- `HAS_ANOMALY`
- `INFERRED_LOCATION`
- `SEMANTICALLY_RELATED_TO`
- `HAS_FAILURE_IMPACT`
- `HAS_SEMANTIC_DESCRIPTION`
- `HAS_RECOMMENDED_ACTION`

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

## Dokumentation

- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/SEMANTIC_ENRICHMENT.md`
- `docs/FAQ.md`
- `docs/CODEBASE_RECHECK_2026-05-08.md`
- `Functional_Description.md`
- `semantic-enrichment/enrichers/README.md`

## Sicherheit

- Keine Secrets ins Repository committen.
- `.env` lokal halten.
- Neo4j-Daten (`neo4j/data`) und Logs (`neo4j/logs`) bleiben lokal.
