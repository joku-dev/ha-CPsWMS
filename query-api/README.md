# query-api

Dieser Ordner enthält die API-Schicht für sprachorientierte und strukturierte Abfragen gegen den Graph.

Enthaltene Dateien:
- `Dockerfile`: Container-Build-Definition für den Query-API-Service.
- `app.py`: Flask-/FastAPI-ähnliche App, die Abfragen entgegennimmt und an Neo4j weiterleitet.
- `requirements.txt`: Python-Abhängigkeiten für den API-Service.

## Funktionen

- Exponiert eine Abfrage-API, die die semantischen Graphdaten mit Clientanfragen verbindet.
- Verwaltet Verbindungen zu Neo4j und leitet Cypher-Abfragen weiter.
- Formatiert Ergebnisse für externe Systeme und Chat-Interfaces.

## Ziel

Der Service ermöglicht es Clients, schnell strukturierte Informationen aus dem semantischen World Model zu lesen, ohne direkt Neo4j ansprechen zu müssen.