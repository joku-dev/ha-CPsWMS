# semantic-enrichment

Dieses Verzeichnis enthält den Enrichment-Orchestrator für das semantische World Model. Es führt LLM-basierte Enricher aus, validiert deren Ausgaben und schreibt semantische Beziehungen in den Graph.

Wichtige Komponenten:
- `Dockerfile`: Container-Build-Definition für den Enrichment-Service.
- `requirements.txt`: Python-Abhängigkeiten für die Enrichment-Worker.
- `semantic_enrich.py`: Einstiegspunkt und Orchestrierung für den Enrichment-Prozess.
- `config.py`: Laufzeitkonfiguration, inklusive `ENRICHMENT_TARGET_MODE` und Neo4j/OpenAI-Parameter.
- `enrichment_target_resolver.py`: Bestimmt, ob Ergebnisse auf `CanonicalEntity`, `Entity` oder beide geschrieben werden.
- `enrichers/`: Spezialisierte Enricher-Module für verschiedene semantische Aufgaben.
- `metadata/`: Versions- und Schema-Metadaten für Prompts und Enricher.
- `prompts/`: Textprompt-Templates für OpenAI-Aufrufe.
- `schemas/`: JSON-Schemas zur Validierung der LLM-Antworten.

## Funktionen

- Auswahl und Batch-Verarbeitung von Kandidaten aus Neo4j.
- Generierung strukturierter Prompt-Payloads für jeden Enricher.
- Prüfung von Modellantworten auf Konsistenz und Konfidenz.
- Schreiben von Enrichment-Ergebnissen in den Graphen, inklusive Canonical-First-Strategie.

## Ziel

Der Ordner bildet das Kernstück der LLM-gestützten semantischen Anreicherung und verbindet Rohdaten mit höheren semantischen Beziehungen.