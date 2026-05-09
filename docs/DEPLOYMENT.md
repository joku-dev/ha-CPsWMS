# Deployment-Checkliste

## 1. Vorbereitung

- Repository klonen
- Docker + Docker Compose installieren
- `.env` aus `.env.example` erzeugen

```bash
cp .env.example .env
```

## 2. Pflichtwerte setzen

- `HA_URL`
- `HA_TOKEN`
- `NEO4J_PASSWORD`

Fuer Semantic Enrichment zusaetzlich:

- `OPENAI_API_KEY`

Optionale Enrichment-Tuning-Parameter:

- `OPENAI_MODEL` (Default: `gpt-5.5`)
- `BATCH_SIZE` (Default: `20`)
- `SLEEP_SECONDS` (Default: `300`)
- `MIN_CONFIDENCE` (Default: `0.5`)

## 3. Start

```bash
docker compose up -d --build
```

## 4. Health-Checks

```bash
docker compose ps
docker compose logs -f neo4j
docker compose logs -f ha-sync
docker compose logs -f semantic-enrichment
```

Neo4j Browser: `http://localhost:7474`

## 5. Aktive Enricher verifizieren

Der Runtime-Orchestrator `semantic-enrichment/semantic_enrich.py` fuehrt folgende 13 Enricher aus:

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

Im Container-Log sollten pro Zyklus Eintraege wie `Running enricher: <name>` fuer diese Enricher erscheinen.

## 6. Fachlicher Check in Neo4j

```cypher
MATCH (e:Entity) RETURN count(e) AS entities;
```

```cypher
MATCH (:Entity)-[r:HAS_SEMANTIC_ROLE]->(:SemanticRole)
RETURN count(r) AS semantic_role_links;
```

```cypher
MATCH (:Entity)-[r:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
RETURN count(r) AS failure_impact_links;
```

```cypher
MATCH (:Entity)-[r:HAS_SEMANTIC_DESCRIPTION]->(:SemanticDescription)
RETURN count(r) AS semantic_description_links;
```

```cypher
MATCH (:Entity)-[r:HAS_RECOMMENDED_ACTION]->(:RecommendedActionType)
RETURN count(r) AS recommended_action_links;
```

Temporal Event Model (Detailchecks):

```cypher
MATCH (:Entity)-[r:HAS_OBSERVATION]->(:Observation)
RETURN count(r) AS has_observation_links;
```

```cypher
MATCH (:Entity)-[r:HAS_TIMELINE_EVENT]->(:TimelineEvent)
RETURN count(r) AS has_timeline_event_links;
```

```cypher
MATCH (:Entity)-[r:HAS_STATE_TRANSITION]->(:StateTransition)
RETURN count(r) AS has_state_transition_links;
```

```cypher
MATCH (:Entity)-[r:HAS_INCIDENT]->(:Incident)
RETURN count(r) AS has_incident_links;
```

Weitere Live-Queries: `docs/TEMPORAL_EVENT_MODEL_QUERIES.md`

## 7. Betriebshinweise

- Secrets nie committen
- `.env` lokal halten
- `neo4j/data` und `neo4j/logs` nicht versionieren
- Prompt/Schema-Aenderungen mit Container-Neustart ausrollen
