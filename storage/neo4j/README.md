# storage/neo4j

Dieser Ordner enthält die konkrete Neo4j-Implementierung des Storage-Layers.

Enthaltene Dateien:
- `__init__.py`: Paketinitialisierung für die Neo4j-Anbindung.
- `queries.py`: Wiederverwendbare Cypher-Statements und Query-Logik.
- `repository.py`: Repository-Klasse zur Speicherung und Abfrage von Graphdaten.
- `writer.py`: Writer-Klasse zur Persistierung von Domain-Objekten in Neo4j.

## Funktionen

- Stellt Repositories und Writer bereit, um semantische Kernmodelle konsistent zu speichern.
- Kapselt die Neo4j-spezifische Cypher-Logik von der restlichen Anwendung.

## Ziel

Eine schlanke Persistenz-Schicht zur Verfügung zu stellen, die das Graphdatenmodell sauber mit der Business-Logik verbindet.