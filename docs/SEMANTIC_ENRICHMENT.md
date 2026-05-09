# Semantic Enrichment

Die Komponente `semantic-enrichment` erweitert Home-Assistant-Daten in Neo4j mit LLM-basierten semantischen Beziehungen.

## Ziel

Nach dem Roh-Sync (`ha-sync`) werden Entities und Automationen in spezialisierten Enrichern bewertet. Das Ergebnis sind zusaetzliche Knoten, Relationen und Diagnosehinweise im Graph.

## Aktueller Stand

Aktiv im Orchestrator (`semantic_enrich.py`):

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

## Architektur in der Komponente

- `semantic_enrich.py`: Orchestriert alle Enricher in einem Endlos-Loop
- `enrichers/base.py`: Gemeinsamer Workflow (Kandidaten lesen, LLM aufrufen, validieren, schreiben)
- `enrichers/*.py`: konkrete Enricher-Implementierungen
- `config.py`: Umgebungsvariablen und Pfadkonfiguration
- `prompts/*.md`: System-Prompts pro Enricher
- `schemas/*.json`: JSON-Schemas fuer strukturierte LLM-Antworten

Detailstatus: `semantic-enrichment/enrichers/README.md`

## Laufablauf pro Enricher

1. `setup()` legt benoetigte Constraints an (falls definiert).
2. `get_candidates(limit)` liest einen Batch aus Neo4j.
3. `call_llm(payload)` ruft OpenAI mit Prompt + JSON-Schema auf.
4. `validate_items(...)` filtert ungueltige IDs und zu niedrige Confidence.
5. `write_results(items)` schreibt Relationen/Knoten nach Neo4j.

## Wichtige Umgebungsvariablen

- `OPENAI_API_KEY` (erforderlich)
- `OPENAI_MODEL` (Standard: `gpt-5.5`)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (erforderlich)
- `BATCH_SIZE` (Standard: `20`)
- `SLEEP_SECONDS` (Standard: `300`)
- `MIN_CONFIDENCE` (Standard: `0.5`)

## Von den aktiven Enrichern erzeugte Relationen

- `HAS_SEMANTIC_ROLE`, `HAS_SEMANTIC_CATEGORY`, `HAS_CRITICALITY`
- `HAS_AUTOMATION_INTENT`
- `HAS_FAULT_ANALYSIS`
- `HAS_ANOMALY`
- `HAS_OBSERVATION`, `HAS_TIMELINE_EVENT`, `HAS_STATE_TRANSITION`, `HAS_INCIDENT`
- `INFERRED_LOCATION`
- `SEMANTICALLY_RELATED_TO`
- `PROVIDES_CAPABILITY`
- `CAUSES`, `DEPENDS_ON`, `IMPACTS`, `DEGRADES`, `RECOVERS`
- `HAS_FAILURE_IMPACT`
- `HAS_SEMANTIC_DESCRIPTION`
- `HAS_RECOMMENDED_ACTION`
- `HAS_SIMULATION_READINESS`, `EVALUATES_TARGET`

## Betrieb

Container starten:

```bash
docker compose up -d --build semantic-enrichment
```

Logs:

```bash
docker compose logs -f semantic-enrichment
```

Temporal Live-Checks:

- Siehe `docs/TEMPORAL_EVENT_MODEL_QUERIES.md` fuer direkte Neo4j-Browser-Queries zu `Observation`, `StateTransition`, `TimelineEvent` und `Incident`.
