# Semantic Benchmark Framework

Das Benchmark-Framework misst, welchen technischen und semantischen Mehrwert `ha-CPsWMS` gegenueber einem einfachen Home-Assistant-zu-Neo4j-Graphen erzeugt. Der Fokus liegt nicht nur auf Geschwindigkeit, sondern auf dem Verhaeltnis aus Laufzeit, Graph-Komplexitaet, semantischer Abdeckung, Query-Nutzwert und optionalem LLM-Aufwand.

## Architektur

Das Framework liegt im Paket `benchmark/` und ist modular aufgebaut:

- `config.py`: laedt YAML-Konfiguration, `.env`, Umgebungsvariablen und CLI-Parameter.
- `metrics_collector.py`: enthaelt JSON-serialisierbare Dataclasses und Hilfsfunktionen.
- `neo4j_metrics.py`: misst Graph-Struktur, Canonical Coverage und semantische Relationship-Anzahl.
- `semantic_metrics.py`: misst semantische Abdeckung, Confidence, Explainability und Konflikte.
- `query_benchmark.py`: fuehrt Cypher-Dateien aus `benchmark/queries/` aus und misst Latenz, Erfolg und Answerability.
- `llm_metrics.py`: liefert aktuell explizite Null-/Zero-Werte, weil strukturierte LLM-Telemetrie noch nicht persistiert wird.
- `score_calculator.py`: berechnet Semantic Score, World Model Score und Value-Efficiency-Metriken.
- `report_generator.py`: erzeugt JSON-, Markdown- und CSV-Reports.
- `benchmark_runner.py`: CLI-Einstiegspunkt.
- `compare_reports.py`: einfacher JSON-Report-Vergleich fuer Baseline-vs-Target-Auswertungen.

## Metriken

### Technical Performance

Erfasst werden Laufzeitfelder wie `sync_duration_seconds`, `enrichment_duration_seconds`, `total_runtime_seconds`, Query-Latenzen und daraus abgeleitete Werte wie `entities_per_second`. Sync- und Enrichment-Zeiten koennen ueber CLI-Parameter extern uebergeben werden.

### Graph Structure

Das Framework misst:

- Gesamtzahl von Nodes und Relationships
- Node-Anzahl pro Label
- Relationship-Anzahl pro Typ
- durchschnittliche Relationship-Anzahl pro Node
- Orphan Nodes
- Entity-, RawEntity-, CanonicalEntity-, ResolutionDecision- und Evidence-Anzahl
- Canonical Coverage
- Raw-to-Canonical Resolution Ratio
- Duplicate Candidates
- semantische Relationship-Anzahl

Wenn kein Canonical Layer vorhanden ist, bleiben die Canonical-Metriken bei `0` und der Report enthaelt eine Warnung.

### Semantic Quality

Gemessen werden unter anderem:

- Semantic Role Coverage
- Semantic Category Coverage
- Criticality Coverage
- Capability Coverage
- Dependency Coverage
- Causal Relation Coverage
- Recommended Action Coverage
- Simulation Readiness Coverage
- Average Semantic Confidence
- Low-/High-Confidence Ratio
- Explainability Coverage
- Conflicting Semantics Count

Die Collector-Queries sind so gebaut, dass fehlende Labels, Relationship-Typen oder Confidence-Properties den Benchmark nicht abbrechen.

### Query Benchmark

Die Query-Dateien liegen unter:

- `benchmark/queries/baseline_queries.cypher`
- `benchmark/queries/semantic_queries.cypher`
- `benchmark/queries/canonical_queries.cypher`

Eine Query gilt als beantwortbar, wenn sie erfolgreich ausgefuehrt wurde und mindestens eine Ergebniszeile liefert. Leere Ergebnisse werden nicht als Fehler behandelt, sondern als niedrige Answerability sichtbar.

### LLM Metrics

Aktuell persistieren die Enricher keine strukturierten Token-, Kosten- oder Latenzmetriken. Deshalb setzt `llm_metrics.py` diese Werte kontrolliert auf `null` oder `0` und schreibt eine Warnung in den Report. Die Schnittstelle ist vorbereitet, damit spaeter Logparser, Telemetrie-Dateien oder Provider-unabhaengige Metrikquellen angeschlossen werden koennen.

## Scores

Der `semantic_score` ist ein gewichteter Score aus semantischer Abdeckung, Confidence und Explainability:

```text
semantic_score =
  0.20 * semantic_role_coverage_ratio
+ 0.15 * semantic_category_coverage_ratio
+ 0.15 * capability_coverage_ratio
+ 0.15 * dependency_coverage_ratio
+ 0.10 * causal_relation_coverage_ratio
+ 0.10 * simulation_readiness_coverage_ratio
+ 0.10 * average_semantic_confidence
+ 0.05 * explainability_coverage_ratio
```

Der `world_model_score` bewertet zusaetzlich Canonical Coverage, Raw-to-Canonical Resolution und Query Answerability:

```text
world_model_score =
  0.25 * canonical_coverage_ratio
+ 0.20 * raw_to_canonical_resolution_ratio
+ 0.20 * semantic_score
+ 0.20 * query_answerability_ratio
+ 0.15 * explainability_coverage_ratio
```

Divisionen durch `0` erzeugen keine Exception. Value-Efficiency-Werte werden dann als `null` ausgegeben.

## CLI-Nutzung

Beispiel:

```bash
python -m benchmark.benchmark_runner \
  --target ha-CPsWMS \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password "$NEO4J_PASSWORD" \
  --output benchmark/reports \
  --format json,md,csv
```

Optionale Laufzeitwerte:

```bash
python -m benchmark.benchmark_runner \
  --sync-duration-seconds 12.4 \
  --enrichment-duration-seconds 180.0 \
  --total-runtime-seconds 192.4
```

Vergleich zweier Reports:

```bash
python -m benchmark.compare_reports \
  --baseline benchmark/reports/ha-neo4j.json \
  --target benchmark/reports/ha-CPsWMS.json
```

## Reports

Reports werden standardmaessig unter `benchmark/reports/` erzeugt:

- `<timestamp>_benchmark.json`
- `<timestamp>_benchmark.md`
- `<timestamp>_benchmark.csv`

Passwoerter und andere Secrets werden nicht in Reports geschrieben. Die Neo4j-Verbindungsdaten werden nur zur Laufzeit verwendet.

## Interpretation

Der Markdown-Report erzeugt eine vorsichtige, faktenbasierte Interpretation. Er behauptet keinen semantischen Gewinn ohne passende Metriken. Stattdessen wird sichtbar, ob Canonical Layer, semantische Relationen, Query Answerability und Confidence-Werte vorhanden sind.

## Grenzen

- Das Framework misst keine reale Sensorhardware.
- Es ersetzt keine Ground-Truth-basierte Expertenbewertung semantischer Korrektheit.
- LLM-Kosten und Token werden erst aussagekraeftig, wenn strukturierte LLM-Telemetrie angebunden ist.
- Query Answerability haengt davon ab, ob Sync und Enrichment vor dem Benchmark vollstaendig gelaufen sind.

## Erweiterbarkeit

Die Modulgrenzen sind darauf ausgelegt, spaeter Prometheus-Exporter, Grafana-Dashboards, CI-Regressionsbenchmarks, mehrere Git-Commits, mehrere LLM-Provider oder eine Ground-Truth-basierte Semantic-Accuracy-Evaluation zu ergaenzen.

