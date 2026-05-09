# Semantic World Model for Home Assistant

Ein semantisches World Model fuer Home Assistant ist eine strukturierte,
abfragbare und interpretierbare Repraesentation eines Smart-Home-Systems. Es
beschreibt nicht nur, welche Entities aktuell existieren und welchen Zustand sie
haben, sondern auch, welche Rolle sie spielen, welche Faehigkeiten sie
ermoeglichen, welche Automationen von ihnen abhaengen und welche Folgen ein
Ausfall haette.

Kurz gesagt: Es macht aus Home-Assistant-Rohdaten ein Modell der Wirklichkeit im
Haus.

## Warum Home Assistant allein noch kein World Model ist

Home Assistant kennt sehr viele technische Fakten:

- Entity IDs
- aktuelle States
- Attribute
- Automationen
- Integrationen
- Geraete, Raeume und Bereiche

Diese Daten sind wichtig, aber sie beantworten viele fachliche Fragen noch nicht
direkt:

- Welche Funktion faellt aus, wenn ein Sensor nicht erreichbar ist?
- Welche Automationen haengen an Zigbee?
- Ist ein Bewegungsmelder kritisch oder nur informativ?
- Welche Kausalkette entsteht aus einem unavailable State?
- Kann ich simulieren, was bei einem Ausfall passiert?

Ein semantisches World Model fuegt genau diese Bedeutungsschicht hinzu.

## Kernidee

Das Modell verbindet technische Objekte mit fachlicher Bedeutung.

Beispiel:

```text
binary_sensor.flur_motion
→ ist ein motion_sensor
→ gehoert zur Capability presence_detection
→ triggert automation.flur_licht_bewegung
→ beeinflusst lighting
→ ein unavailable State degradiert presence_detection
→ dadurch kann lighting automation betroffen sein
```

Damit wird aus einem einzelnen Home-Assistant-State ein interpretierbarer
Wirkzusammenhang.

## Zentrale Bausteine

### 1. Operativer Graph

Die Basis ist ein Neo4j-Graph mit Home-Assistant-Objekten:

- `Entity`
- `Automation`
- `Device`
- `Area`
- `Integration`
- `Domain`

Diese Ebene beantwortet:

- Was existiert?
- Wo befindet es sich?
- Von welcher Integration kommt es?
- Welche Automation nutzt welche Entity?

### 2. Semantische Klassifikation

Entities bekommen eine fachliche Rolle:

- Bewegungsmelder
- Lichtaktor
- Temperatursensor
- Schalter
- Batterie-Sensor
- Diagnose-Entity

Im Graph wird das ueber Knoten und Beziehungen wie diese sichtbar:

```text
(Entity)-[:HAS_SEMANTIC_ROLE]->(SemanticRole)
(Entity)-[:HAS_SEMANTIC_CATEGORY]->(SemanticCategory)
(Entity)-[:HAS_CRITICALITY]->(Criticality)
```

Diese Ebene beantwortet:

- Was bedeutet diese Entity fachlich?
- Ist sie kritisch?
- Gehoert sie eher zu Komfort, Sicherheit, Klima, Energie oder Diagnose?

### 3. Capabilities

Capabilities beschreiben, welche Smart-Home-Faehigkeiten durch Entities,
Automationen und Integrationen bereitgestellt werden.

Beispiele:

- `lighting`
- `presence_detection`
- `climate_control`
- `security_monitoring`
- `energy_monitoring`
- `connectivity`

Eine Capability ist abstrakter als eine Entity. Viele Entities koennen gemeinsam
eine Capability ermoeglichen.

Beispiel:

```text
binary_sensor.flur_motion
automation.flur_licht_bewegung
light.flur
→ lighting
```

Diese Ebene beantwortet:

- Welche Funktionen hat das Haus?
- Welche Entities tragen zu welcher Funktion bei?
- Welche Funktion wird degradiert, wenn ein Objekt ausfaellt?

### 4. Zeitmodell

Ein World Model braucht Zeit, weil Ursache und Wirkung nicht nur strukturell,
sondern auch zeitlich zusammenhaengen.

Das Temporal Event Model erzeugt:

- `Observation`
- `TimelineEvent`
- `StateTransition`
- `Incident`

Diese Ebene beantwortet:

- Wann ist etwas passiert?
- War es eine Zustandsaenderung oder ein Incident?
- Gab es vorher oder nachher relevante Events?
- Hat sich ein Zustand erholt?

Beispiel:

```text
motion sensor became unavailable
→ TimelineEvent
→ Incident unavailable
→ later recovered to on
```

### 5. Fehler- und Anomalieebene

Ein semantisches World Model soll nicht nur Normalzustand beschreiben, sondern
auch Abweichungen verstehen.

Relevante Konzepte:

- `HAS_ANOMALY`
- `HAS_FAULT_ANALYSIS`
- `HAS_FAILURE_IMPACT`
- `HAS_INCIDENT`

Diese Ebene beantwortet:

- Was ist auffaellig?
- Welche Art Fehler liegt vor?
- Welche operative Folge hat der Fehler?
- Welche Capability ist betroffen?

### 6. Kausalitaetsmodell

Die wichtigste Schicht fuer ein World Model ist Kausalitaet. Sie beschreibt,
warum ein Ereignis relevant ist und was daraus folgen kann.

Beziehungen:

- `CAUSES`
- `DEPENDS_ON`
- `IMPACTS`
- `DEGRADES`
- `RECOVERS`

Beispiel:

```text
motion sensor unavailable
→ DEGRADES presence_detection
→ IMPACTS light automation
→ DEGRADES lighting
```

Diese Ebene beantwortet:

- Was verursacht was?
- Welche Entity haengt von welcher anderen ab?
- Welche Capability wird degradiert?
- Welche Automation ist betroffen?
- Hat sich ein Problem wieder erholt?

### 7. Simulation Readiness

Nicht jede Frage ist sofort simulierbar. Deshalb bewertet eine spaete Schicht,
ob genug Daten fuer Was-waere-wenn-Fragen vorhanden sind.

Simulation Readiness prueft:

- Gibt es Capabilities?
- Gibt es Dependencies?
- Gibt es Fehlerhistorie?
- Gibt es Automationsbeziehungen?
- Gibt es kritische Entities?
- Gibt es zeitliche Ereignisse?

Beispiel:

```text
integration_outage:zigbee
→ readiness: partial
→ missing_data: causal dependencies for some entities
→ supported_questions: Which critical entities are provided by Zigbee?
```

Diese Ebene beantwortet:

- Kann das System eine Was-waere-wenn-Frage sinnvoll beantworten?
- Welche Daten fehlen noch?
- Welche Fragen sind bereits belastbar?

## Query- und Chat-Schicht

Ein World Model muss nicht nur Daten speichern, sondern auch nutzbar sein.

Dieses Repository hat dafuer zwei Schichten:

### Query API

Die Query API stellt feste, vorbereitete read-only Endpoints bereit.

Beispiele:

```text
GET /api/capabilities
GET /api/simulation-readiness
GET /api/what-if/integration/zigbee
GET /api/what-if/capability/lighting
GET /api/entities/binary_sensor.motion/impact
```

Diese API ist gut fuer:

- UIs
- Dashboards
- Automatisierte Tools
- stabile Integrationen

### World Model Chat

Der World Model Chat ist die flexible Sprachschnittstelle.

Er nimmt Fragen wie diese an:

```text
Was passiert, wenn Zigbee ausfaellt?
Warum geht das Licht im Flur nicht automatisch an?
Welche kritischen Capabilities haengen an diesem Sensor?
```

Der Ablauf:

1. OpenAI erzeugt eine read-only Cypher-Abfrage.
2. Die API validiert die Query.
3. Neo4j liefert die Daten.
4. OpenAI formuliert daraus eine Antwort.

Damit wird das World Model interaktiv befragbar.

## Was dieses Modell leisten kann

Ein semantisches World Model fuer Home Assistant kann:

- technische Home-Assistant-Daten fachlich interpretieren
- Abhaengigkeiten zwischen Entities und Automationen sichtbar machen
- Capabilities und deren Degradation modellieren
- Fehlerfolgen erklaeren
- kritische Entities hervorheben
- zeitliche Ereignisse mit Semantik verbinden
- What-if-Fragen vorbereiten
- Antworten fuer Menschen und APIs bereitstellen

Beispiele:

```text
Welche Entities sind kritisch?
Welche Automationen haengen an Zigbee?
Welche Faehigkeit wird durch diesen Sensor bereitgestellt?
Was wird degradiert, wenn diese Entity unavailable ist?
Ist das System bereit, einen Zigbee-Ausfall zu simulieren?
```

## Was es noch nicht automatisch ist

Ein semantisches World Model ist nicht automatisch eine vollstaendige Simulation
oder ein autonomes Steuerungssystem.

Grenzen:

- Es fuehrt keine Aktionen in Home Assistant aus.
- Es repariert keine Fehler automatisch.
- Es simuliert aktuell noch keine probabilistische Zustandsfortschreibung.
- Es ist von der Qualitaet der Sync- und Enrichment-Daten abhaengig.
- Kausalitaet ist teilweise inferiert und muss mit Confidence bewertet werden.

Der aktuelle Stand ist deshalb am besten beschrieben als:

```text
Semantic Operational World Model
```

Nicht als:

```text
vollautonomer digitaler Zwilling
```

## Zielbild

Das langfristige Ziel ist ein System, das Fragen dieser Art belastbar beantworten
kann:

```text
Wenn Zigbee ausfaellt, welche Raeume, Automationen und Capabilities sind betroffen?
Welche kritischen Funktionen haengen an diesem Geraet?
Welche Fehlerkette erklaert, warum das Licht nicht angeht?
Welche Daten fehlen, um diesen Ausfall sicher zu simulieren?
```

Dafuer kombiniert das Repository:

- Home-Assistant-Sync
- Neo4j als Graphspeicher
- LLM-basierte semantische Enrichment-Schichten
- Zeit- und Fehlermodellierung
- Kausalitaetsbeziehungen
- Simulation-Readiness-Bewertung
- Query API
- World Model Chat

Das Ergebnis ist eine zunehmend erklaerbare, abfragbare und erweiterbare
Repraesentation des Smart Homes.
