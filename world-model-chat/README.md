# world-model-chat

Dieser Ordner enthält die Chat-Oberfläche für das semantische World Model.

Enthaltene Dateien:
- `Dockerfile`: Container-Build-Definition für den Chat-Service.
- `app.py`: Dienst, der Nutzeranfragen in Cypher-Abfragen umsetzt und Antworten liefert.
- `config.py`: Konfiguration für den Chat-Service sowie Neo4j- und Modellverbindungen.
- `requirements.txt`: Python-Abhängigkeiten für den Chat-Service.
- `prompts/`: Prompt-Templates zur Generierung von Chat-Antworten.
- `schemas/`: JSON-Schema zur Validierung der generierten Cypher-Abfragen.

## Funktionen

- Übersetzt natürliche Sprache in strukturierte Anfragen an das Graphmodell.
- Verwendet promptspezifische Regeln zur sicheren Query-Erzeugung.
- Validiert und führt generierte Cypher-Statements gegen Neo4j aus.

## Ziel

Eine interaktive Schnittstelle bereitzustellen, die den semantischen Graph über natürliche Sprache zugänglich macht.