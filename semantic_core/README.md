# semantic_core

Dieses Paket ist der Kern der semantischen Weltmodellierung und enthält die zentralen Logikmodule für Identitätsauflösung, Normalisierung, Ontologie und zeitbasiertes Verhalten.

Enthaltene Unterordner:
- `causal/`: Modelle und Logik zur Kausalanalyse und Abhängigkeitsbewertung.
- `identity/`: Canonical-Entity-Auflösung, Review-Pipeline, Vertrauensmodelle und Entscheidungslogik.
- `normalization/`: Name-, Einheiten- und Schema-Normalisierung für Eingabedaten.
- `ontology/`: Ontologie-Mapping und kontextuelle Wissenszuordnung.
- `temporal/`: Temporalitätsmodelle, Ereignisverarbeitung und Zeitreihenanalyse.

## Funktionen

- Bietet die semantische Kernlogik für identitätsvermitteltes Arbeiten.
- Stellt ‌eine zentrale Schicht für konsistente Datenvorverarbeitung und Normierung bereit.
- Erlaubt die Auflösung von Roh-Entitäten zu stabilen, systemübergreifenden Identitäten.

## Ziel

Den Hauptcode zur semantischen Modellierung zu bündeln und als wiederverwendbaren Kern für die gesamte Anwendung bereitzustellen.

## Rolle im Gesamtsystem

`semantic_core` bildet die Grundlage für den Canonical Entity Layer. Home Assistant liefert konkrete Quellobjekte wie `sensor.living_room_temperature` oder `light.kitchen_ceiling`. Diese Objekte werden nicht direkt als endgültige Wahrheit behandelt, sondern zuerst in eine quellenspezifische Rohform übersetzt und anschließend einer stabilen kanonischen Identität zugeordnet.

Der zentrale Ablauf lautet:

```text
Home Assistant Entity
  -> RawEntity
  -> ResolutionDecision
  -> CanonicalEntity
  -> Evidence
```

Dadurch kann das System später mehrere Quellen, umbenannte Entities, doppelte Repräsentationen oder unsichere Zuordnungen sauberer behandeln als ein rein entity_id-basierter Graph.

## Zentrale Objekte

### `SourceSystem`

Beschreibt die Datenquelle, aus der Rohobjekte stammen.

Beispiel:

```text
SourceSystem
  source_id: homeassistant
  source_type: homeassistant
  name: Home Assistant
  trust_level: 0.8
```

Neo4j-Knoten:

```text
(:SourceSystem)
```

### `RawEntity`

Beschreibt eine konkrete, quellenspezifische Entity. Für Home Assistant wird sie aus der HA-Entity erzeugt.

Beispiel:

```text
RawEntity
  raw_entity_id: homeassistant_sensor.living_room_temperature
  source_id: homeassistant
  source_entity_id: sensor.living_room_temperature
  entity_type: sensor
  name: Living Room Temperature
  domain: sensor
  device_class: temperature
  area: living_room
  attributes: {...}
```

Neo4j-Knoten:

```text
(:RawEntity)
```

### `CanonicalEntity`

Beschreibt eine stabile semantische Identität im World Model. Eine `CanonicalEntity` kann langfristig mehrere Rohrepräsentationen haben.

Beispiel:

```text
CanonicalEntity
  canonical_id: canonical.sensor.living_room.temperature
  entity_type: sensor
  canonical_name: Living Room Temperature
  lifecycle_state: active
  confidence_status: unknown
  attributes: {...}
```

Neo4j-Knoten:

```text
(:CanonicalEntity)
```

### `ResolutionDecision`

Beschreibt, wie eine `RawEntity` einer `CanonicalEntity` zugeordnet wurde.

Beispiel:

```text
ResolutionDecision
  decision_id: decision_homeassistant_sensor.living_room_temperature_...
  raw_entity_id: homeassistant_sensor.living_room_temperature
  canonical_id: canonical.sensor.living_room.temperature
  decision_type: created_new | resolved_existing | candidate_review | rejected
  method: no_candidates | low_confidence | confidence_scoring
  overall_confidence: 0.87
  review_required: false
```

Neo4j-Knoten:

```text
(:ResolutionDecision)
```

### `Evidence`

Beschreibt einzelne Begründungen für eine Auflösungsentscheidung. Das Confidence-Modell erzeugt typischerweise Evidence für:

- `identity_similarity`
- `name_similarity`
- `type_similarity`
- `location_similarity`
- `attribute_similarity`
- `source_trust`

Neo4j-Knoten:

```text
(:Evidence)
```

### `Observation`

Beschreibt eine konkrete Beobachtung oder Messung zu einem Zeitpunkt. Dieses Objekt gehört zum semantischen Modell, ist aber im aktuellen `ha-sync`-Pfad weniger zentral als `RawEntity`, `CanonicalEntity`, `ResolutionDecision` und `Evidence`.

## Erzeugte Neo4j-Relationen

Die Persistenz erfolgt über `storage/neo4j/repository.py` und `storage/neo4j/writer.py`. Dabei entstehen folgende semantische Relationen:

```text
(:RawEntity)-[:RESOLVED_TO]->(:CanonicalEntity)

(:ResolutionDecision)-[:DECIDED_FOR]->(:CanonicalEntity)

(:ResolutionDecision)-[:DECIDED_ON]->(:RawEntity)

(:ResolutionDecision)-[:BASED_ON]->(:Evidence)

(:Entity)-[:HAS_RAW_REPRESENTATION]->(:RawEntity)
```

Die Relation `HAS_RAW_REPRESENTATION` verbindet den klassischen Home-Assistant-Graphknoten `(:Entity)` mit der semantischen Rohrepräsentation `(:RawEntity)`.

## Ablauf bei Home-Assistant-Synchronisation

1. `ha-sync` liest eine Entity aus Home Assistant.
2. `sources/homeassistant/adapter.py` wandelt die HA-Entity in eine `RawEntity` um.
3. `ResolutionPipeline` sucht über `CanonicalRegistry` passende `CanonicalEntity`-Kandidaten.
4. `IdentityResolver` entscheidet anhand der Kandidaten und Confidence-Werte.
5. `ConfidenceModel` berechnet einen Gesamtscore und erzeugt `Evidence`-Objekte.
6. `SemanticCoreWriter` schreibt `SourceSystem`, `RawEntity`, `CanonicalEntity`, `ResolutionDecision` und `Evidence` nach Neo4j.
7. `ha-sync` verbindet die klassische `Entity` mit der `RawEntity`.

## Entscheidungslogik

Die Auflösung nutzt aktuell einfache Confidence-Schwellen:

```text
Keine Kandidaten:
  -> neue CanonicalEntity
  -> decision_type = created_new
  -> method = no_candidates

Beste Confidence >= 0.85:
  -> bestehende CanonicalEntity verwenden
  -> decision_type = resolved_existing
  -> method = confidence_scoring

Beste Confidence zwischen 0.60 und 0.85:
  -> Kandidat benötigt Review
  -> decision_type = candidate_review
  -> review_required = true

Beste Confidence < 0.60:
  -> neue CanonicalEntity erzeugen
  -> decision_type = created_new
  -> method = low_confidence
```

## Weitere Teilmodule

### `normalization`

Normalisiert Namen, Attribute und Einheiten. Beispiel:

```text
sensor.living_room_temperature
  -> ["sensor", "living", "room", "temperature"]
```

Zusätzlich können Einheiten wie `°C`, `F`, `kWh` oder `%` normalisiert und teilweise konvertiert werden.

### `ontology`

Erlaubt die Zuordnung von RawEntities zu Ontologie-Konzepten, zum Beispiel:

```text
ontology_type: concept.sensor
ontology_area: concept.area.kitchen
```

### `temporal`

Modelliert Beobachtungen und Zustandsübergänge:

```text
Observation
StateTransition
```

Damit können zeitbasierte Verläufe und einfache Ereignislabels aufgebaut werden.

### `causal`

Enthält einen einfachen in-memory Kausalgraphen:

```text
cause -> effect
```

Damit kann geprüft werden, ob ein kausaler Pfad zwischen zwei semantischen Objekten existiert.

## Einordnung

`semantic_core` erzeugt nicht die LLM-basierten Enrichment-Relationen wie `HAS_SEMANTIC_ROLE`, `PROVIDES_CAPABILITY` oder `HAS_RECOMMENDED_ACTION`. Diese entstehen im separaten Modul `semantic-enrichment`.

`semantic_core` erzeugt stattdessen die Identitätsgrundlage, auf der spätere Enrichment-Schichten stabiler arbeiten können:

```text
RawEntity
CanonicalEntity
ResolutionDecision
Evidence
SourceSystem
```
