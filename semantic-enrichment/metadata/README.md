# semantic-enrichment/metadata

Dieser Ordner enthält Metadaten für das Enrichment-System.

Enthaltene Dateien:
- `model_versions.json`: Versionsinformationen für die verwendeten LLM-Modelle.
- `prompt_versions.json`: Versionierung der Prompt-Templates.
- `schema_versions.json`: Versionierung der JSON-Schemas, die für strukturierte Antworten genutzt werden.

## Funktionen

- Dokumentiert, welche Prompt- und Schema-Versionen für welche Enricher gültig sind.
- Unterstützt Reproduzierbarkeit und deterministische Updates in der Enrichment-Pipeline.

## Ziel

Sicherstellung, dass Enricher-Ausgaben und Modellkonfigurationen nachvollziehbar bleiben und bei Änderungen geprüft werden können.