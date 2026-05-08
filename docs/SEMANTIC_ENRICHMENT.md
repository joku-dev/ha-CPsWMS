# Semantic Enrichment

Die `semantic-enrichment`-Komponente erweitert die Home Assistant Entities in Neo4j mit semantischen Informationen, die über OpenAI generiert werden.

## Zweck

Nach der Synchronisation von Home Assistant Entities nach Neo4j können diese Entities weiter angereichert werden:

1. **Semantische Rollen**: Klassifizierung der Entities (z. B. Sensor, Aktor, Schalter)
2. **Semantische Kategorien**: Kategorisierung nach Funktion (z. B. Temperatur, Licht, Heizung)
3. **Criticality Level**: Einstufung nach Wichtigkeit (z. B. kritisch, hoch, normal)

## Komponenten

- `semantic_enrich.py`: Hauptskript, das Entities abruft und mit OpenAI anreichert
- `prompts/semantic_roles.md`: System-Prompt für OpenAI mit Anweisungen
- `schemas/enrichment_schema.json`: JSON-Schema für die erwarteten Antworten

## Workflow

1. `semantic_enrich.py` startet beim Container-Start
2. Ruft Entities ab, die noch nicht angereichert wurden (`semantic_enriched = false`)
3. Sendet diese in Batches an OpenAI mit einem definierten System-Prompt
4. Speichert die Antworten als neue Knoten und Beziehungen in Neo4j:
   - `SemanticRole` Knoten
   - `SemanticCategory` Knoten
   - `Criticality` Knoten
   - Beziehungen wie `HAS_ROLE`, `IN_CATEGORY`, `HAS_CRITICALITY`

## Umgebungsvariablen

- `OPENAI_API_KEY`: OpenAI API Key (erforderlich)
- `NEO4J_URI`: Neo4j Bolt-URI (Standard: `bolt://neo4j:7687`)
- `NEO4J_USER`: Neo4j Benutzer (Standard: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j Passwort (erforderlich)
- `OPENAI_MODEL`: Verwendetes OpenAI-Modell (Standard: `gpt-5.5`)
- `BATCH_SIZE`: Anzahl der Entities pro API-Aufruf (Standard: `20`)
- `SLEEP_SECONDS`: Wartezeit zwischen Sync-Durchläufen (Standard: `300`)
- `MIN_CONFIDENCE`: Minimales Confidence-Level für Antworten (Standard: `0.50`)

## Abhängigkeiten

- `openai`: OpenAI Python Client
- `neo4j`: Neo4j Python Driver

## Constraints

Das System erstellt automatisch folgende Neo4j Constraints:

- `SemanticRole.name` unique
- `SemanticCategory.name` unique
- `Criticality.level` unique

Dies verhindert doppelte Knoten bei wiederholtem Enrichment.

## Fehlerhandling

- Das System überspringt Entities, die nicht als JSON erkannt werden
- Falls OpenAI nicht erreichbar ist, wird die Anfrage wiederholt
- Batches werden in regelmäßigen Abständen verarbeitet

## Erweiterungen

- Weitere Enrichment-Kriterien können in `prompts/semantic_roles.md` hinzugefügt werden
- Das Schema in `schemas/enrichment_schema.json` kann erweitert werden
- Benutzerdefinierte Kategorien können in der Prompt definiert werden
