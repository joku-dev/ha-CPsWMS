# storage

Dieser Ordner fasst Speicheradapter zusammen, die den Zugriff auf persistente Graphdaten handhaben.

Enthaltene Dateien und Unterordner:
- `__init__.py`: Paketinitialisierung für den Storage-Layer.
- `neo4j/`: Implementierung des Neo4j-Speichers.

## Funktionen

- Kapselt die Details des Graphspeichers hinter einem einheitlichen Interface.
- Sorgt für Repository- und Writer-Klassen, die Daten in Neo4j persistieren.

## Ziel

Die persistente Speicherung der semantischen Modelle von der Geschäftslogik zu trennen und wiederverwendbare Speicherkomponenten bereitzustellen.