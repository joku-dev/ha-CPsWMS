# Architektur

Dieses Repository implementiert eine Pipeline von Home Assistant nach Neo4j mit nachgelagerter semantischer Anreicherung.

## Systemkomponenten

1. `neo4j`
2. `ha-sync`
3. `semantic-enrichment`

## Datenfluss

1. `ha-sync` liest States und Registry-Daten aus Home Assistant.
2. `ha-sync` schreibt normalisierte Knoten/Relationen in Neo4j.
3. `semantic-enrichment` liest Kandidaten aus Neo4j.
4. OpenAI liefert schema-validierte semantische Ergebnisse.
5. `semantic-enrichment` persistiert neue Relationen/Knoten in Neo4j.

## Diagramm

```mermaid
flowchart LR
  HA[Home Assistant]
  Sync[ha-sync]
  Neo4j[(Neo4j)]
  Enrich[semantic-enrichment]
  OpenAI[OpenAI API]

  HA -->|REST + WebSocket| Sync
  Sync -->|Bolt Write| Neo4j
  Neo4j -->|Candidate Read| Enrich
  Enrich -->|Structured Output Request| OpenAI
  OpenAI -->|JSON by Schema| Enrich
  Enrich -->|Bolt Write| Neo4j
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
6. `failure_impact`
7. `semantic_descriptions`
8. `dependency_reasoning`
9. `recommended_actions`

Die Komponente nutzt einen gemeinsamen Basistyp (`enrichers/base.py`) mit einheitlichem Kontrollfluss: Kandidaten lesen, LLM aufrufen, Ergebnis validieren, Graph schreiben.

## Persistenz und Betrieb

- Persistenz: `neo4j/data`
- Logs: `neo4j/logs`
- Deployment-Orchestrierung: `docker-compose.yml`

## Designentscheidungen

- Enricher sind fachlich getrennt, damit Prompts/Schemas pro Aufgabe evolvieren koennen.
- JSON-Schema-Ausgabe erzwingt konsistente maschinenlesbare LLM-Antworten.
- Confidence-Grenze (`MIN_CONFIDENCE`) verhindert aggressives Schreiben unsicherer Ergebnisse.
