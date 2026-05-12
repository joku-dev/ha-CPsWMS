# semantic_core/normalization

Dieser Ordner enthält die Normalisierungslogik für Eingabedaten und Schema-Mapping.

Enthaltene Dateien:
- `normalizer.py`: Basis-Klassen und allgemeine Normalisierungsfunktionen.
- `schema_mapper.py`: Zuordnung von Rohdatenfeldern zu standardisierten Schemas und Attributnamen.
- `unit_normalizer.py`: Normalisierung von Einheiten, Darstellung und Metrik-Konversion.

## Funktionen

- Vereinheitlicht unterschiedliche Namens- und Attributformate.
- Sichert, dass verschiedene Datenquellen vergleichbare Werte im Graph erhalten.
- Unterstützt Canonical-Entity-Logik mit standardisierten Darstellungen.

## Ziel

Die Datenvorverarbeitung so zu stabilisieren, dass die nachfolgenden semantischen Schichten auf einheitliche und saubere Eingaben zurückgreifen können.