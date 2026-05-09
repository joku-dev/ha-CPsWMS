# Enrichers Package

Stand: 2026-05-09

Dieser Ordner ist jetzt die aktive Laufzeitquelle fuer den Orchestrator `semantic_enrich.py`.

## Aktive Enricher

1. `semantic_roles.py`
2. `room_inference.py`
3. `automation_intent.py`
4. `fault_analysis.py`
5. `anomaly_detection.py`
6. `temporal_event_model.py`
7. `failure_impact.py`
8. `semantic_descriptions.py`
9. `dependency_reasoning.py`
10. `causal_dependency.py`
11. `recommended_actions.py`
12. `simulation_readiness.py`

## Basisklasse

- `base.py` enthaelt den gemeinsamen Workflow fuer alle Enricher.
- Jede Enricher-Klasse erbt von `BaseEnricher` und implementiert:
  - `create_constraints()`
  - `get_candidates(limit)`
  - `validate_items(llm_items, input_items)`
  - `write_results(items)`

## Import-Pfad

Der Orchestrator nutzt `from enrichers.<module> import <EnricherClass>`.
