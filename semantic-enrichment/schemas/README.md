# semantic-enrichment/schemas

Dieser Ordner enthält JSON-Schemas für die Validierung der Ausgaben von LLM-Enrichern.

Dateien:
- `anomaly_detection_schema.json`
- `automation_intent_schema.json`
- `capability_mapping_schema.json`
- `causal_dependency_schema.json`
- `dependency_reasoning_schema.json`
- `enrichment_schema.json`
- `failure_impact_schema.json`
- `fault_analysis_schema.json`
- `recommended_actions_schema.json`
- `room_inference_schema.json`
- `semantic_descriptions_schema.json`
- `semantic_roles_schema.json`
- `simulation_readiness_schema.json`
- `temporal_event_model_schema.json`

## Funktionen

- Validiert strukturierte JSON-Antworten der einzelnen Enricher.
- Verhindert, dass fehlerhafte oder nicht erwartete Felder in den Graph geschrieben werden.
- Unterstützt Typ- und Feldüberprüfungen vor der Persistierung.

## Ziel

Garantiert die Stabilität der Schnittstelle zwischen LLM-Ausgabe und Graphspeicherung.