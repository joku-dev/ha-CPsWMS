# scripts

Dieser Ordner enthält Hilfs- und Überprüfungsskripte für CI, Validierung und einmalige Aufgaben.

Enthaltene Dateien:
- `ci_validate_enrichment.py`: Validiert Enricher-Konfigurationen, Prompt-/Schema-Konsistenz und ggf. strukturierte Ausgabeformate.

## Funktionen

- Automatisiert wiederkehrende Prüfungen, bevor neue Enricher oder Schemaänderungen in den Hauptzweig gemergt werden.
- Dient als Entwicklungswerkzeug zur Sicherstellung der Stabilität der semantischen Enrichment-Pipeline.

## Ziel

Der Ordner fasst kleine utility-Skripte zusammen, die keine dauerhaften Services darstellen, aber wichtige Qualitätsprüfungen liefern.