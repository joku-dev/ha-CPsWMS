# neo4j

Dieses Verzeichnis enthält die lokale Neo4j-Datenbankumgebung und deren Log-Dateien.

Struktur:
- `logs/`: Verzeichnis mit Neo4j-Logdateien aus dem Datenbankbetrieb.

## Zweck

Der Ordner dient als Ablage für Neo4j-Laufzeitdaten und Monitoring-Informationen. In dieser Codebasis wird Neo4j als zentrales Graph-Repository genutzt, in dem Home Assistant-Entitäten, semantische Identitäten und Enrichment-Informationen gespeichert werden.

## Log-Dateien

Die Log-Dateien zeichnen Systemereignisse, Abfragen, Sicherheit und Debug-Informationen auf:
- `debug.log`
- `http.log`
- `neo4j.log`
- `query.log`
- `security.log`