# ha-sync

Dieses Verzeichnis enthält den Home Assistant Sync-Adapter, der HA-Entitäten aus dem Home Assistant-System erfasst und in das semantische Graphmodell überführt.

Enthaltene Dateien:
- `Dockerfile`: Container-Build-Definition für den Sync-Worker.
- `requirements.txt`: Python-Abhängigkeiten für den Sync-Prozess.
- `sync.py`: Hauptskript für das Auslesen von Home Assistant-Entitäten, das Erzeugen von RawEntity-Objekten und das Verknüpfen mit dem semantischen Modell.

## Funktionen

- Verbindung zu Home Assistant aufbauen und Geräte-/Entitäten-Daten extrahieren.
- Rohdaten in `RawEntity`-Repräsentationen übersetzen.
- Erstellung und Aktualisierung von Graphknoten in Neo4j.
- Pflege der Beziehung `HAS_RAW_REPRESENTATION` zwischen `Entity` und `RawEntity`.

## Ziel

Der Adapter stellt sicher, dass aktuelle Home Assistant-Daten in die semantische Identitätsschicht eingespeist werden und damit spätere Enrichment- und Auflösungsprozesse in Echo-Systemen möglich werden.