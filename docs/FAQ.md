# FAQ

## Warum startet `ha-sync` nicht?

- `docker compose logs -f ha-sync` pruefen.
- Sind `HA_URL`, `HA_TOKEN`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` gesetzt?
- Ist `neo4j` bereits erreichbar?

## Warum startet `semantic-enrichment` nicht?

- `docker compose logs -f semantic-enrichment` pruefen.
- Sind `OPENAI_API_KEY` und Neo4j-Zugangsdaten vorhanden?
- Sind Prompt- und Schema-Dateien im Container vorhanden?

## Welche Enricher laufen aktuell?

Aktiv:

1. `semantic_roles`
2. `room_inference`
3. `automation_intent`
4. `fault_analysis`
5. `anomaly_detection`
6. `temporal_event_model`
7. `failure_impact`
8. `semantic_descriptions`
9. `dependency_reasoning`
10. `recommended_actions`

## Warum sehe ich keine neuen Enrichment-Knoten?

- Kandidaten koennen bereits als verarbeitet markiert sein.
- `MIN_CONFIDENCE` kann zu hoch sein.
- Das LLM kann leere oder ungueltige Ergebnisse liefern; diese werden verworfen.

## Wie kann ich pruefen, ob Daten in Neo4j ankommen?

```cypher
MATCH (e:Entity) RETURN count(e) AS entities;
```

```cypher
MATCH (:Entity)-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC;
```

## Kann ich Prompts und Schemas anpassen?

Ja.

- Prompts: `semantic-enrichment/prompts/*.md`
- Schemas: `semantic-enrichment/schemas/*_schema.json`

Nach Aenderungen den Enrichment-Container neu bauen/starten:

```bash
docker compose up -d --build semantic-enrichment
```

## Welche Dateien sollten nicht versioniert werden?

- `.env`
- `neo4j/data/`
- `neo4j/logs/`
