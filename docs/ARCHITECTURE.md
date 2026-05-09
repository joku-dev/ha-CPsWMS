# Architektur

Dieses Repository implementiert eine Pipeline von Home Assistant nach Neo4j mit nachgelagerter semantischer Anreicherung.

## Systemkomponenten

1. `neo4j`
2. `ha-sync`
3. `semantic-enrichment`
4. `query-api`

## Datenfluss

1. `ha-sync` liest States und Registry-Daten aus Home Assistant.
2. `ha-sync` schreibt normalisierte Knoten/Relationen in Neo4j.
3. `semantic-enrichment` liest Kandidaten aus Neo4j.
4. OpenAI liefert schema-validierte semantische Ergebnisse.
5. `semantic-enrichment` persistiert neue Relationen/Knoten in Neo4j.
6. `query-api` stellt vorbereitete HTTP-Abfragen fuer What-if- und Impact-Fragen bereit.

## Diagramm

```mermaid
flowchart LR
  HA[Home Assistant]
  Sync[ha-sync]
  Neo4j[(Neo4j)]
  Enrich[semantic-enrichment]
  Query[query-api]
  OpenAI[OpenAI API]

  HA -->|REST + WebSocket| Sync
  Sync -->|Bolt Write| Neo4j
  Neo4j -->|Candidate Read| Enrich
  Enrich -->|Structured Output Request| OpenAI
  OpenAI -->|JSON by Schema| Enrich
  Enrich -->|Bolt Write| Neo4j
  Query -->|Bolt Read| Neo4j
```

## `ha-sync` Verantwortung

- Home Assistant API-Zugriff (`/api/states`, Registry-Endpunkte)
- Normalisierung von Attributen
- Aufbau von Kernknoten wie `Entity`, `Area`, `Device`, `Domain`, `Automation`
- Erzeugen von Basisrelationen fuer Analysen und Enrichment

## `semantic-enrichment` Verantwortung

Aktive Enricher:

1. `semantic_roles`
2. `room_inference`
3. `automation_intent`
4. `fault_analysis`
5. `anomaly_detection`
6. `temporal_event_model`
7. `failure_impact`
8. `semantic_descriptions`
9. `dependency_reasoning`
10. `causal_dependency`
11. `recommended_actions`
12. `simulation_readiness`

Die Komponente nutzt einen gemeinsamen Basistyp (`enrichers/base.py`) mit einheitlichem Kontrollfluss: Kandidaten lesen, LLM aufrufen, Ergebnis validieren, Graph schreiben.

## `query-api` Verantwortung

- Bereitstellen stabiler HTTP-Endpunkte fuer wiederkehrende Graph-Fragen
- Kapseln von Cypher fuer Capabilities, Simulation Readiness, What-if-Szenarien und Entity Impact
- Read-only-Zugriff auf Neo4j ueber den Bolt-Treiber

## Persistenz und Betrieb

- Persistenz: `neo4j/data`
- Logs: `neo4j/logs`
- Deployment-Orchestrierung: `docker-compose.yml`

## Designentscheidungen

- Enricher sind fachlich getrennt, damit Prompts/Schemas pro Aufgabe evolvieren koennen.
- JSON-Schema-Ausgabe erzwingt konsistente maschinenlesbare LLM-Antworten.
- Confidence-Grenze (`MIN_CONFIDENCE`) verhindert aggressives Schreiben unsicherer Ergebnisse.
