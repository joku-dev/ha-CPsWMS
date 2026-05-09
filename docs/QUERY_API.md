# Query API

Die Query API ist eine schlanke HTTP-Schicht fuer vorbereitete Neo4j-Abfragen.
Sie ist read-only gedacht und beantwortet erste What-if-, Impact- und Readiness-Fragen.

## Start

```bash
docker compose up -d --build query-api
```

Health-Check:

```bash
curl http://localhost:8080/health
```

## Endpoints

### Capabilities

```bash
curl http://localhost:8080/api/capabilities
```

Listet bekannte `Capability`-Knoten inklusive Dependency-Zaehlern und Simulation-Readiness-Bezug.

### Simulation Readiness

```bash
curl http://localhost:8080/api/simulation-readiness
```

Listet `SimulationScenario`-Bewertungen mit Readiness-Level, Coverage Score, fehlenden Daten,
unterstuetzten Fragen und naechsten Datenanreicherungsschritten.

### What-if: Integration faellt aus

```bash
curl http://localhost:8080/api/what-if/integration/zigbee
```

Beantwortet Fragen wie: Welche Entities, Automationen, Kritikalitaeten und Kausalbeziehungen
sind betroffen, wenn eine Integration ausfaellt?

### What-if: Capability faellt aus

```bash
curl http://localhost:8080/api/what-if/capability/lighting
```

Zeigt Entities und Automationen, die mit einer Capability wie `lighting`,
`presence_detection` oder `climate_control` verbunden sind.

### Entity Impact

```bash
curl http://localhost:8080/api/entities/binary_sensor.motion/impact
```

Zeigt fuer eine Entity semantische Rolle, Criticality, Failure Impacts, Incidents,
Timeline Events, Causal Links und Automation-Kontext.

## Query Parameter

Die Listen-Endpunkte akzeptieren `limit`:

```bash
curl "http://localhost:8080/api/simulation-readiness?limit=50"
```
