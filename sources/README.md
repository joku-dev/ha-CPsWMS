# sources

Dieser Ordner enthält Adapter für externe Datenquellen, die Rohdaten in das semantische System einspeisen.

Enthaltene Unterordner:
- `homeassistant/`: Adapter für Home Assistant-Daten.

## Funktionen

- Übersetzt Quellsystemdaten in ein einheitliches internes Format.
- Erzeugt `RawEntity`-Repräsentationen für semantische Auflösung.
- Sorgt dafür, dass unterschiedliche Quellen dieselbe semantische Pipeline nutzen können.

## Ziel

Externe Datenquellen zu kapseln und für die semantische Verarbeitung vorzubereiten.