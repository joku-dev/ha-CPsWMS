# Canonical Entity Resolution & Semantic Identity Layer

## Ziel

Dieses Dokument beschreibt die neue semantische Identitätsschicht im Projekt `ha-CPsWMS`. Sie sorgt dafür, dass unterschiedliche Datenquellen wie Home Assistant, MQTT oder Radar-Objekterkennung nicht nur als Rohdaten gespeichert werden, sondern als stabile, wiedererkennbare semantische Identitäten im Weltmodell.

## Warum ist das wichtig?

Viele Sensoren und Geräte liefern Daten in unterschiedlichen Formaten. Wenn wir dieselbe physische Sache mehrmals mit verschiedenen Quellen oder Namen sehen, müssen wir trotzdem erkennen, dass es derselbe Sensor, dieselbe Person oder dasselbe Objekt ist.

Beispiele:

- `sensor.livingroom_temperature` und `sensor.livingroom_temp` können zum selben Temperatur-Sensor gehören.
- `binary_sensor.garage_motion` und `motion_sensor.garage` könnten dieselbe Bewegungserkennung im Garage-Bereich beschreiben.
- Später sollen auch Radar- oder Video-Erkennungen mit denselben Basis-Identitäten verknüpfbar sein.

## Architekturüberblick

Die neue Schicht besteht aus mehreren klaren Teilen:

1. `Observation`
   - Eine konkrete Messung oder ein Ereignis zu einem Zeitpunkt.
   - Beispiel: ein Home-Assistant-State-Update, ein Radar-Track, ein Video-Detektionsereignis.

2. `RawEntity`
   - Eine quellenspezifische Entität, wie sie aus Home Assistant oder anderen Datenquellen kommt.
   - Beispiel: `sensor.livingroom_temperature`, `mqtt/zigbee/door_sensor`.

3. `CanonicalEntity`
   - Eine stabile, semantische Identität im Weltmodell.
   - Beispiel: `canonical.sensor.living_room.temperature`.

4. `Evidence`
   - Ein Belegstück, warum eine Zuordnung getroffen wurde.
   - Beispiel: Name stimmt überein, gleiche Gerätetypklasse, gleiche Location.

5. `ResolutionDecision`
   - Das Ergebnis der Identitätsauflösung.
   - Beispiel: „Diese RawEntity gehört zur vorhandenen CanonicalEntity“ oder „Erstelle eine neue CanonicalEntity“.

## Implementierte Module

### Semantic Core

- `semantic_core/identity/models.py`
  - Definitionsdateien für `Observation`, `RawEntity`, `CanonicalEntity`, `Evidence`, `ResolutionDecision`, `SourceSystem`.

- `semantic_core/identity/canonical_registry.py`
  - Verwalten stabiler Canonical Entities.
  - Erzeugt neue Canonical IDs und speichert vorhandene Entitäten.

- `semantic_core/identity/confidence_model.py`
  - Bewertet, wie gut eine Quelle zu einer bestehenden Canonical Entity passt.
  - Nutzt gewichtete Ähnlichkeitswerte für Namen, Typ, Ort und Attribute.

- `semantic_core/identity/identity_resolver.py`
  - Entscheidet, ob ein Rohobjekt einer bestehenden Canonical Entity zugeordnet wird oder eine neue Entität entsteht.

- `semantic_core/identity/resolution_pipeline.py`
  - Steuert die gesamte Auflösungspipeline.

- `semantic_core/identity/review_queue.py`
  - Speichert unsichere Entscheidungen zur späteren manuellen Prüfung.

- `semantic_core/identity/evidence_model.py`
  - Architekturkonformes Modul für Evidence, das die Datenmodell-Definition kapselt.

### Normalisierung

- `semantic_core/normalization/normalizer.py`
  - Generiert Tokens aus Entitätsnamen, z. B. `livingroom_temperature`.

- `semantic_core/normalization/unit_normalizer.py`
  - Normalisiert Einheitensymbole und führt einfache Einheitenkonvertierungen durch.

- `semantic_core/normalization/schema_mapper.py`
  - Übersetzt Quellformate wie Home Assistant in das generische `RawEntity`-Modell.

### Ontologie

- `semantic_core/ontology/ontology_store.py`
  - Speichert semantische Konzepte und deren Beziehungshierarchien.

- `semantic_core/ontology/ontology_mapper.py`
  - Ordnet Rohentitäten Ontologie-Kategorien zu und bereichert sie mit konzeptuellen Labels.

### Zeitliche Modellierung

- `semantic_core/temporal/temporal_event_model.py`
  - Baut eine einfache Ereignis-Zeitleiste aus Beobachtungen auf.

- `semantic_core/temporal/state_evolution.py`
  - Erfasst Übergänge vom vorherigen Zustand zum neuen Zustand.

### Kausales Modell

- `semantic_core/causal/causal_dependency.py`
  - Modelliert, welche Entitäten oder Zustände andere Ursachen und Auswirkungen haben.

## Home Assistant als Quelle

Home Assistant ist nicht mehr das Kernmodell, sondern nur noch ein Adapter:

- `sources/homeassistant/adapter.py`
- Konvertiert Home-Assistant-Entitäten in das generische `RawEntity`.
- Dadurch bleibt der semantische Kern später erweiterbar für MQTT, Radar, Video usw.

## Integration in den Sync-Prozess

- `ha-sync/sync.py` nutzt die neue Pipeline, um Home-Assistant-Entitäten semantisch aufzulösen.
- Das Ergebnis wird in Neo4j als `RawEntity`, `CanonicalEntity`, `ResolutionDecision` und `Evidence` gespeichert.

## Für technisch weniger versierte Personen

Stellen Sie sich das System wie eine Inventarliste vor:

- Viele Sensoren liefern Beobachtungen.
- Manche Sensoren haben unterschiedliche Namen, aber beschreiben dieselbe Sache.
- Die semantische Schicht erkennt diese Zuordnungen und erstellt eine „einheitliche Identität“.
- Das macht spätere Fragen einfacher, z. B. „Welcher Sensor in der Küche meldet Bewegung?“ oder „Was passiert, wenn dieser Sensor ausfällt?“

## Wie es erweitert werden kann

Die neue Basis ist bewusst einfach gehalten, damit sie später erweitert werden kann:

- weitere Quellen: MQTT, Radar, Video, IoT
- bessere Ontologie-Modelle
- persistente Review-Workflows
- automatische Fehleranalyse und Ursache-Wirkungs-Ketten

## Neuerungen im Repository

- Neue Packages:
  - `semantic_core/normalization`
  - `semantic_core/ontology`
  - `semantic_core/temporal`
  - `semantic_core/causal`
- Neue Tests für die neuen Module im Ordner `tests/semantic_core`

## Wie testen?

```bash
pytest tests/semantic_core
```

> Hinweis: `pytest` muss im Arbeitsumfeld verfügbar sein.
