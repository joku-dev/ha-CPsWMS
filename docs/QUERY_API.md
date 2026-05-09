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

### Simulation Readiness

```bash
curl http://localhost:8080/api/simulation-readiness
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

### What-if: Integration faellt aus

```bash
curl http://localhost:8080/api/what-if/integration/zigbee
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

### What-if: Capability faellt aus

```bash
curl http://localhost:8080/api/what-if/capability/lighting
```

Zeigt Entities und Automationen, die mit einer Capability wie `lighting`,
`presence_detection` oder `climate_control` verbunden sind.

Diese Query nutzt die vom `failure_impact`-Enricher geschriebenen
`affected_capability`-Felder sowie kausale Links auf `Capability`-Knoten.

Sie beantwortet: Welche Entities und Automationen haengen an einer Faehigkeit,
und welche operativen Folgen wurden bereits erkannt?

### Entity Impact

```bash
curl http://localhost:8080/api/entities/binary_sensor.motion/impact
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

## Query Parameter

Die Listen-Endpunkte akzeptieren `limit`:

```bash
curl "http://localhost:8080/api/simulation-readiness?limit=50"
```

`limit` wird serverseitig begrenzt, damit versehentliche sehr grosse Antworten
den Container oder Neo4j nicht unnoetig belasten.

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
