# Query API

Die Query API ist eine schlanke HTTP-Schicht fuer vorbereitete Neo4j-Abfragen.
Sie ist read-only gedacht und beantwortet erste What-if-, Impact- und Readiness-Fragen.

## Funktionsweise

Die Query API ist ein eigener Container, der neben `neo4j`, `ha-sync` und
`semantic-enrichment` laeuft. Sie schreibt keine Daten in den Graph, sondern liest
die bereits synchronisierten und angereicherten Knoten/Relationen aus Neo4j.

Der Datenfluss ist:

1. `ha-sync` schreibt Rohdaten aus Home Assistant in Neo4j.
2. `semantic-enrichment` erzeugt semantische Rollen, Capabilities, Zeitereignisse,
   Failure Impacts, Kausalbeziehungen und Simulation-Readiness-Bewertungen.
3. `query-api` nimmt HTTP-Requests entgegen.
4. Der jeweilige Endpoint fuehrt eine vorbereitete Cypher-Abfrage aus.
5. Neo4j-Ergebnisse werden in JSON-kompatible Werte umgewandelt und als HTTP-JSON
   zurueckgegeben.

Die API nutzt bewusst keine freien Cypher-Requests von aussen. Stattdessen kapselt
sie feste Query-Funktionen in `query-api/app.py`. Dadurch bleibt die Oberflaeche
klein, stabil und einfacher fuer eine spaetere UI nutzbar.

## Voraussetzungen im Graph

Die Query API liefert die besten Antworten, wenn diese Enrichment-Schichten vorher
gelaufen sind:

- `semantic_roles`: Rollen, Kategorien und Kritikalitaet
- `failure_impact`: betroffene Capabilities und operative Folgen
- `temporal_event_model`: Timeline Events, State Transitions und Incidents
- `causal_dependency`: `CAUSES`, `DEPENDS_ON`, `IMPACTS`, `DEGRADES`, `RECOVERS`
- `simulation_readiness`: Bewertung, ob ein Szenario simulierbar ist

Wenn einzelne Schichten noch keine Daten erzeugt haben, antwortet die API trotzdem,
aber Felder wie `causal_links`, `simulation_readiness` oder `timeline_events` sind
dann leer.

## Start

```bash
docker compose up -d --build query-api
```

Health-Check:

```bash
curl http://localhost:8080/health
```

Intern prueft der Health-Check nur, ob Neo4j ueber Bolt erreichbar ist:

```cypher
RETURN 1 AS ok
```

## Quickstart

1. Stack starten:

```bash
docker compose up -d --build
```

2. Pruefen, ob die API Neo4j erreicht:

```bash
curl http://localhost:8080/health
```

Erwartete Antwort:

```json
{
  "status": "ok"
}
```

3. Erste fachliche Abfrage ausfuehren:

```bash
curl http://localhost:8080/api/capabilities
```

4. Optional JSON lesbarer formatieren:

```bash
curl -s http://localhost:8080/api/capabilities | jq
```

## Endpoint-Uebersicht

| Endpoint | Zweck |
| --- | --- |
| `GET /health` | Prueft Neo4j-Verbindung |
| `GET /api/capabilities` | Listet erkannte Capabilities und Dependency-Zaehler |
| `GET /api/simulation-readiness` | Zeigt, welche Simulationen schon moeglich sind |
| `GET /api/what-if/integration/{domain}` | Impact einer Integration, z. B. `zigbee` |
| `GET /api/what-if/capability/{name}` | Impact einer Capability, z. B. `lighting` |
| `GET /api/entities/{entity_id}/impact` | Detailkontext fuer eine konkrete Entity |

Alle Listen-Endpunkte akzeptieren `?limit=N`.

## Konfiguration

Der Container wird in `docker-compose.yml` als eigener Service gestartet und nutzt
dieselben Neo4j-Zugangsdaten wie die anderen Backend-Container.

Wichtige Variablen:

- `NEO4J_URI`: Bolt-Adresse, im Compose-Setup `bolt://neo4j:7687`
- `NEO4J_USER`: Neo4j-Benutzer, standardmaessig `neo4j`
- `NEO4J_PASSWORD`: Passwort aus `.env`
- `QUERY_API_PORT`: HTTP-Port im Container, standardmaessig `8080`
- `QUERY_API_DEFAULT_LIMIT`: Standardlimit fuer Listen, standardmaessig `25`
- `QUERY_API_MAX_LIMIT`: maximales Limit, standardmaessig `100`

## Request-Verarbeitung

Alle Endpoints sind `GET`-Endpoints. Der Request-Handler in `query-api/app.py`:

1. parst Pfad und Query-Parameter,
2. begrenzt `limit` auf `1..QUERY_API_MAX_LIMIT`,
3. waehlt anhand des Pfads die passende Query-Funktion,
4. fuehrt Cypher mit Parametern aus,
5. konvertiert Neo4j-Zeitwerte und andere Spezialtypen in JSON,
6. sendet eine JSON-Antwort.

Fehler werden als JSON zurueckgegeben:

```json
{
  "error": "query_failed",
  "detail": "..."
}
```

## Endpoints

### Capabilities

```bash
curl http://localhost:8080/api/capabilities
```

Mit Limit:

```bash
curl "http://localhost:8080/api/capabilities?limit=10"
```

Listet bekannte `Capability`-Knoten inklusive Dependency-Zaehlern und Simulation-Readiness-Bezug.

Diese Query beantwortet: Welche Faehigkeiten kennt der Graph bereits, wie stark
sind sie kausal verbunden, und gibt es schon Simulation-Readiness-Szenarien dazu?

Genutzte Graph-Elemente:

- `Capability`
- `DEPENDS_ON`, `IMPACTS`, `DEGRADES`, `RECOVERS`, `CAUSES`
- `SimulationScenario`
- `HAS_SIMULATION_READINESS`

Typische Antwortstruktur:

```json
{
  "capabilities": [
    {
      "capability": "lighting",
      "inbound_dependency_count": 3,
      "outbound_dependency_count": 0,
      "simulation_readiness": [
        {
          "scenario_id": "capability_loss:lighting",
          "readiness": "partial",
          "coverage_score": 0.62,
          "confidence": 0.78
        }
      ]
    }
  ]
}
```

Interpretation:

- `capability`: Name der modellierten Faehigkeit, z. B. `lighting`.
- `inbound_dependency_count`: wie viele Quellen auf diese Capability wirken.
- `outbound_dependency_count`: wie viele weitere Ziele von dieser Capability ausgehen.
- `simulation_readiness`: vorhandene Readiness-Bewertungen fuer passende Szenarien.

Wenn `capabilities` leer ist, sind wahrscheinlich noch keine `Capability`-Knoten
durch `failure_impact` oder `causal_dependency` entstanden.

### Simulation Readiness

```bash
curl http://localhost:8080/api/simulation-readiness
```

Mit Limit:

```bash
curl "http://localhost:8080/api/simulation-readiness?limit=20"
```

Listet `SimulationScenario`-Bewertungen mit Readiness-Level, Coverage Score, fehlenden Daten,
unterstuetzten Fragen und naechsten Datenanreicherungsschritten.

Diese Query beantwortet: Fuer welche Was-waere-wenn-Fragen ist der Graph schon
ausreichend vorbereitet?

Genutzte Graph-Elemente:

- `SimulationScenario`
- `SimulationReadinessLevel`
- `HAS_SIMULATION_READINESS`
- `EVALUATES_TARGET`

Wichtige Felder:

- `readiness`: `ready`, `partial`, `not_ready` oder `unknown`
- `coverage_score`: numerischer Abdeckungswert von `0..1`
- `missing_data`: fehlende Datenklassen
- `supported_questions`: Fragen, die aktuell beantwortbar sind
- `required_next_steps`: naechste sinnvolle Datenanreicherungen

Beispielantwort:

```json
{
  "readiness_assessments": [
    {
      "scenario_id": "integration_outage:zigbee",
      "scenario_type": "integration_outage",
      "target_type": "integration",
      "target_id": "zigbee",
      "target_name": "zigbee",
      "target_labels": ["Integration"],
      "readiness": "partial",
      "coverage_score": 0.58,
      "missing_data": ["causal dependencies for some entities"],
      "supported_questions": [
        "Which critical entities are provided by Zigbee?"
      ],
      "required_next_steps": [
        "Run causal dependency enrichment for Zigbee entities"
      ],
      "confidence": 0.74,
      "reason": "Capabilities and automations exist, but failure history is sparse.",
      "updated_at": "2026-05-09T19:30:00Z"
    }
  ]
}
```

Interpretation:

- `ready`: genug Daten fuer gute What-if-Antworten.
- `partial`: nutzbar, aber mit klaren Luecken.
- `not_ready`: zentrale Voraussetzungen fehlen.
- `coverage_score`: grobe Abdeckung der benoetigten Daten, nicht die Eintrittswahrscheinlichkeit.

### What-if: Integration faellt aus

```bash
curl http://localhost:8080/api/what-if/integration/zigbee
```

Weitere Beispiele:

```bash
curl http://localhost:8080/api/what-if/integration/zha
curl http://localhost:8080/api/what-if/integration/mqtt
curl http://localhost:8080/api/what-if/integration/esphome
```

Beantwortet Fragen wie: Welche Entities, Automationen, Kritikalitaeten und Kausalbeziehungen
sind betroffen, wenn eine Integration ausfaellt?

Diese Query nutzt die Beziehung `(:Entity)-[:PROVIDED_BY]->(:Integration)`.
Fuer ein Szenario wie `integration_outage:zigbee` werden alle Entities gesucht,
die von dieser Integration bereitgestellt werden.

Pro Entity werden dazu geladen:

- aktueller Zustand
- Kritikalitaet
- Failure Impact
- direkte Kausalbeziehungen
- betroffene Automationen ueber `TRIGGERED_BY`, `CONTROLS`, `HAS_CONDITION`

Das Ergebnis ist nach Kritikalitaet sortiert, damit kritische Treffer oben stehen.

Beispielantwort:

```json
{
  "scenario": "integration_outage:zigbee",
  "impacted_entities": [
    {
      "integration": "zigbee",
      "entity_id": "binary_sensor.flur_motion",
      "friendly_name": "Flur Bewegung",
      "state": "on",
      "criticality": "high",
      "failure_impact": "medium",
      "causal_links": [
        {
          "type": "DEGRADES",
          "related_labels": ["Capability"],
          "related_id": "presence_detection",
          "reason": "Motion sensor unavailable degrades presence detection.",
          "confidence": 0.81
        }
      ],
      "automations": [
        {
          "automation_id": "automation.flur_licht_bewegung",
          "name": "Flur Licht Bewegung"
        }
      ]
    }
  ]
}
```

Interpretation:

- `impacted_entities` sind Entities, die ueber `PROVIDED_BY` an der Integration haengen.
- `causal_links` zeigen bekannte Kausal- oder Dependency-Kanten.
- `automations` zeigt Automationen, in denen die Entity Trigger, Bedingung oder Ziel ist.

Wenn die Liste leer ist, kann das bedeuten:

- die Integration heisst im Graph anders,
- `ha-sync` hat noch keine `PROVIDED_BY`-Beziehung geschrieben,
- die betroffenen Entities existieren, sind aber nicht dieser Integration zugeordnet.

### What-if: Capability faellt aus

```bash
curl http://localhost:8080/api/what-if/capability/lighting
```

Weitere Beispiele:

```bash
curl http://localhost:8080/api/what-if/capability/presence_detection
curl http://localhost:8080/api/what-if/capability/climate_control
curl http://localhost:8080/api/what-if/capability/security_monitoring
```

Zeigt Entities und Automationen, die mit einer Capability wie `lighting`,
`presence_detection` oder `climate_control` verbunden sind.

Diese Query nutzt die vom `failure_impact`-Enricher geschriebenen
`affected_capability`-Felder sowie kausale Links auf `Capability`-Knoten.

Sie beantwortet: Welche Entities und Automationen haengen an einer Faehigkeit,
und welche operativen Folgen wurden bereits erkannt?

Beispielantwort:

```json
{
  "scenario": "capability_loss:presence_detection",
  "impacted_entities": [
    {
      "capability": "presence_detection",
      "entity_id": "binary_sensor.flur_motion",
      "friendly_name": "Flur Bewegung",
      "state": "unavailable",
      "criticality": "high",
      "operational_consequence": "Motion based lighting may not trigger.",
      "causal_sources": [
        {
          "type": "DEGRADES",
          "source_labels": ["Entity"],
          "source_id": "binary_sensor.flur_motion",
          "reason": "Unavailable motion sensor degrades presence detection.",
          "confidence": 0.84
        }
      ],
      "automations": [
        {
          "automation_id": "automation.flur_licht_bewegung",
          "name": "Flur Licht Bewegung"
        }
      ]
    }
  ]
}
```

Interpretation:

- Diese Query ist gut fuer fachliche Fragen wie "Welche Funktion faellt aus?"
- Sie arbeitet ueber `affected_capability` aus `HAS_FAILURE_IMPACT` und Kausal-Links.
- Wenn sie leer ist, fehlt meist ein sauberes Capability Mapping.

### Entity Impact

```bash
curl http://localhost:8080/api/entities/binary_sensor.motion/impact
```

Mit einer echten Home-Assistant-Entity:

```bash
curl http://localhost:8080/api/entities/binary_sensor.flur_motion/impact
```

Zeigt fuer eine Entity semantische Rolle, Criticality, Failure Impacts, Incidents,
Timeline Events, Causal Links und Automation-Kontext.

Diese Query ist die Detailansicht fuer eine einzelne Entity. Sie fuehrt mehrere
Enrichment-Schichten zusammen:

- semantische Rolle und Kategorie
- Kritikalitaet
- Failure Impacts und betroffene Capabilities
- Incidents
- Timeline Events
- Causal Links
- Automationsbeziehungen

Sie ist der beste Einstieg, wenn eine konkrete Entity erklaert werden soll.

Beispielantwort:

```json
{
  "entity_id": "binary_sensor.flur_motion",
  "friendly_name": "Flur Bewegung",
  "domain": "binary_sensor",
  "state": "unavailable",
  "semantic_role": "motion_sensor",
  "semantic_category": "presence",
  "criticality": "high",
  "failure_impacts": [
    {
      "level": "medium",
      "affected_capability": "presence_detection",
      "operational_consequence": "Motion triggered lighting may fail.",
      "confidence": 0.82
    }
  ],
  "incidents": [
    {
      "incident_id": "example-incident-id",
      "type": "unavailable",
      "severity": "medium",
      "reason": "Entity is unavailable.",
      "opened_at": "2026-05-09T19:30:00Z"
    }
  ],
  "timeline_events": [
    {
      "event_type": "sensor_unavailable",
      "summary": "Motion sensor became unavailable.",
      "event_time": "2026-05-09T19:30:00Z"
    }
  ],
  "causal_links": [
    {
      "type": "DEGRADES",
      "related_labels": ["Capability"],
      "related_id": "presence_detection",
      "reason": "Sensor unavailability degrades presence detection.",
      "confidence": 0.84
    }
  ],
  "automations": [
    {
      "automation_id": "automation.flur_licht_bewegung",
      "name": "Flur Licht Bewegung"
    }
  ]
}
```

Interpretation:

- `failure_impacts` beantwortet, welche Faehigkeit betroffen ist.
- `incidents` und `timeline_events` erklaeren den zeitlichen Kontext.
- `causal_links` zeigt, wie die Entity in Kausalketten eingebunden ist.
- `automations` zeigt direkte Automation-Abhaengigkeiten.

Wenn die Entity nicht gefunden wird:

```json
{
  "error": "entity_not_found",
  "entity_id": "binary_sensor.motion"
}
```

Dann zuerst im Neo4j Browser oder ueber Home Assistant pruefen, wie die Entity
tatsaechlich heisst.

## Query Parameter

Die Listen-Endpunkte akzeptieren `limit`:

```bash
curl "http://localhost:8080/api/simulation-readiness?limit=50"
```

`limit` wird serverseitig begrenzt, damit versehentliche sehr grosse Antworten
den Container oder Neo4j nicht unnoetig belasten.

## Typische Workflows

### 1. Herausfinden, ob Simulationen schon moeglich sind

```bash
curl -s http://localhost:8080/api/simulation-readiness | jq
```

Danach auf `readiness`, `coverage_score` und `missing_data` schauen.

### 2. Impact einer Integration abschaetzen

```bash
curl -s http://localhost:8080/api/what-if/integration/zigbee | jq
```

Diese Abfrage ist passend fuer Fragen wie:

- Welche Entities haengen an Zigbee?
- Welche kritischen Entities waeren betroffen?
- Welche Automationen koennten ausfallen?

### 3. Eine konkrete Entity untersuchen

```bash
curl -s http://localhost:8080/api/entities/binary_sensor.flur_motion/impact | jq
```

Diese Abfrage ist passend fuer Debugging:

- Warum ist diese Entity wichtig?
- Welche Faehigkeit haengt daran?
- Gibt es Incidents oder Timeline Events?
- Welche Automationen nutzen sie?

### 4. Capability-Luecken finden

```bash
curl -s http://localhost:8080/api/capabilities | jq
```

Wenn wichtige Capabilities fehlen, sollte zuerst `failure_impact` und danach
`causal_dependency` erneut laufen.

## Nutzung aus Python

Ein minimales Beispiel:

```python
import requests

response = requests.get(
    "http://localhost:8080/api/what-if/integration/zigbee",
    timeout=10,
)
response.raise_for_status()

data = response.json()

for entity in data["impacted_entities"]:
    print(entity["entity_id"], entity["criticality"], entity["failure_impact"])
```

## Troubleshooting

### `{"status":"ok"}` kommt nicht zurueck

Pruefen:

```bash
docker compose ps
docker compose logs -f query-api
```

Moegliche Ursachen:

- Neo4j ist noch nicht gestartet.
- `NEO4J_PASSWORD` fehlt oder passt nicht.
- Der Container wurde noch nicht neu gebaut.

### Endpoint liefert leere Listen

Das ist nicht automatisch ein API-Fehler. Haeufige Ursachen:

- Der passende Enricher ist noch nicht gelaufen.
- Es gibt noch keine `Capability`-Knoten.
- `simulation_readiness` hat noch keine Szenarien bewertet.
- Die abgefragte Integration oder Entity heisst anders als erwartet.

### `query_failed`

Dann ist die Cypher-Abfrage selbst fehlgeschlagen oder das Graph-Schema passt
nicht zur erwarteten Struktur. In dem Fall:

```bash
docker compose logs -f query-api
```

## Grenzen der aktuellen API

- Die API ist read-only und fuehrt keine Reparaturen oder Aktionen aus.
- Es gibt noch keine Authentifizierung vor der HTTP-API.
- Es gibt keine freie Cypher-Schnittstelle, nur vorbereitete Abfragen.
- Antwortqualitaet haengt direkt davon ab, ob die vorgelagerten Enricher bereits
  genug Daten geschrieben haben.
- Die API modelliert erste What-if-Antworten, aber noch keine echte Simulation mit
  Zustandsfortschreibung oder Wahrscheinlichkeitsmodell.

## Erweiterungsideen

Sinnvolle naechste Schritte:

- Endpoint fuer komplette Kausalpfade, z. B. `/api/causal-paths/{entity_id}`
- Endpoint fuer offene Datenluecken aus `simulation_readiness`
- einfache UI auf Basis der Query API
- Authentifizierung oder lokales Reverse-Proxy-Setup
- versionierte API-Pfade wie `/api/v1/...`
