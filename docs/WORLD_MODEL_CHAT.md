# World Model Chat

`world-model-chat` ist die natuerlichsprachliche Chat-Schicht ueber dem
Home-Assistant-Neo4j-World-Model. Sie laeuft als eigener Container und nutzt
OpenAI, um aus Fragen sichere read-only Cypher-Abfragen zu erzeugen.

## Start

```bash
docker compose up -d --build world-model-chat
```

Health-Check:

```bash
curl http://localhost:8090/health
```

FastAPI-Doku:

```text
http://localhost:8090/docs
```

## Anfrage

```bash
curl -X POST http://localhost:8090/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "Was passiert, wenn Zigbee ausfaellt?",
    "include_cypher": true
  }'
```

## Funktionsweise

Der Ablauf pro Chat-Frage:

1. `POST /chat` nimmt eine natuerlichsprachliche Frage entgegen.
2. OpenAI erzeugt anhand von `prompts/cypher_generation.md` eine strukturierte
   Cypher-Abfrage nach `schemas/cypher_query_schema.json`.
3. Die API validiert die Query als read-only.
4. Die Query wird gegen Neo4j ausgefuehrt.
5. OpenAI formuliert mit `prompts/answer_generation.md` eine Antwort aus Frage,
   Query und Ergebnisdaten.
6. Die API liefert Antwort, Intent, Confidence und optional Cypher zurueck.

## Sicherheitsmodell

Die Chat-Schicht blockiert schreibende oder administrative Cypher-Bestandteile:

- `CREATE`
- `MERGE`
- `SET`
- `DELETE`
- `DETACH`
- `REMOVE`
- `DROP`
- `CALL`
- `LOAD CSV`
- `FOREACH`
- `UNWIND`
- `APOC`
- `DBMS`

Erlaubt sind nur einzelne read-only Queries, die mit `MATCH` oder
`OPTIONAL MATCH` starten, `RETURN` enthalten und ein `LIMIT` setzen.

## Konfiguration

Wichtige Umgebungsvariablen:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (Standard: `gpt-5.5`)
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `WORLD_MODEL_CHAT_PORT` (Standard: `8090`)
- `WORLD_MODEL_CHAT_MAX_QUERY_ROWS` (Standard: `100`)
- `WORLD_MODEL_CHAT_MIN_CYPHER_CONFIDENCE` (Standard: `0.4`)

## Dateien

```text
world-model-chat/
├── app.py
├── config.py
├── requirements.txt
├── Dockerfile
├── prompts/
│   ├── cypher_generation.md
│   └── answer_generation.md
└── schemas/
    └── cypher_query_schema.json
```

## Rolle neben der Query API

- `query-api` stellt feste, stabile Endpoints fuer bekannte Fragen bereit.
- `world-model-chat` ist flexibler und beantwortet freie Fragen per
  LLM-generierter, validierter Read-Query.

Die Query API ist damit die robuste Maschinen-API, waehrend World Model Chat die
explorative Sprachschnittstelle ist.
