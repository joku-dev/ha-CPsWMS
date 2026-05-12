# HA-CPsWMS Benchmark System

## Übersicht

Das Benchmark-System von HA-CPsWMS misst die Performance und Qualität des semantischen Weltmodells für Home Assistant. Es führt umfassende Tests durch, die technische Metriken, Graph-Struktur-Analysen, semantische Qualitätsbewertungen und Query-Performance umfassen.

## Benchmark-Komponenten

### 1. Technische Metriken (TechnicalMetrics)

Diese Metriken messen die grundlegende Systemperformance:

- **total_runtime_seconds**: Gesamtlaufzeit des Benchmark-Prozesses
- **entities_processed_total**: Anzahl der verarbeiteten Entitäten
- **entities_per_second**: Verarbeitungsgeschwindigkeit (Entitäten/Sekunde)
- **neo4j_read_duration_seconds**: Zeit für Neo4j-Leseoperationen
- **query_latency_***: Query-Latenzen (Durchschnitt, P50, P95, Maximum)

**Bedeutung von Änderungen:**
- `runtime` ↓ = Bessere Performance, effizientere Verarbeitung
- `entities_per_second` ↑ = Höhere Verarbeitungsgeschwindigkeit
- `query_latency_*` ↓ = Schnellere Datenbankabfragen

### 2. Graph-Struktur-Metriken (GraphStructureMetrics)

Analysiert die Struktur des Neo4j-Graphen:

- **node_count_total**: Gesamtanzahl der Knoten
- **relationship_count_total**: Gesamtanzahl der Beziehungen
- **node_count_by_label**: Knoten nach Label-Typ (z.B. Entity, SemanticDescription)
- **relationship_count_by_type**: Beziehungen nach Typ (z.B. AFFECTED_ENTITY, HAS_SEMANTIC_ROLE)
- **canonical_coverage_ratio**: Anteil kanonischer Entitäten (0.0-1.0)
- **raw_to_canonical_resolution_ratio**: Auflösungsrate Roh- zu Kanonische-Entitäten
- **semantic_relationship_count**: Anzahl semantischer Beziehungen

**Bedeutung von Änderungen:**
- `canonical_coverage_ratio` ↑ = Bessere Entitäten-Normalisierung
- `semantic_relationship_count` ↑ = Reicheres semantisches Modell
- `raw_to_canonical_resolution_ratio` ↑ = Bessere Duplikat-Behandlung

### 3. Semantische Qualitätsmetriken (SemanticQualityMetrics)

Bewertet die semantische Vollständigkeit und Qualität:

- **semantic_role_coverage_ratio**: Anteil Entitäten mit semantischen Rollen
- **semantic_category_coverage_ratio**: Anteil Entitäten mit semantischen Kategorien
- **criticality_coverage_ratio**: Anteil Entitäten mit Kritikalitätsbewertung
- **capability_coverage_ratio**: Anteil Entitäten mit Capability-Mapping
- **dependency_coverage_ratio**: Anteil Entitäten mit Abhängigkeitsbeziehungen
- **causal_relation_coverage_ratio**: Anteil Entitäten mit Kausalbeziehungen
- **recommended_action_coverage_ratio**: Anteil Entitäten mit empfohlenen Aktionen
- **simulation_readiness_coverage_ratio**: Anteil Entitäten mit Simulationsbereitschaft
- **average_semantic_confidence**: Durchschnittliche Konfidenz semantischer Beziehungen
- **explainability_coverage_ratio**: Anteil erklärbarer semantischer Beziehungen

**Bedeutung von Änderungen:**
- `*_coverage_ratio` ↑ = Vollständigeres semantisches Modell
- `average_semantic_confidence` ↑ = Höhere Zuverlässigkeit der Semantik
- `explainability_coverage_ratio` ↑ = Bessere Nachvollziehbarkeit

### 4. Query-Benchmark-Metriken (QueryBenchmarkMetrics)

Testet die Abfrageperformance des Graphen:

#### Baseline-Queries (Grundlegende HA-Funktionalität)
- **entity_count_by_domain**: Entitäten gruppiert nach Domain
- **unavailable_entities**: Nicht verfügbare Entitäten
- **automation_entity_links**: Automatisierungs-Entitäten-Verknüpfungen

#### Canonical-Queries (Entitäten-Normalisierung)
- **raw_to_canonical_resolution**: Roh- zu Kanonische-Entitäten Auflösung
- **canonical_entities_with_multiple_raw_representations**: Mehrfachrepräsentationen
- **canonical_semantic_roles**: Semantische Rollen kanonischer Entitäten

#### Semantic-Queries (Semantische Intelligenz)
- **critical_entities**: Kritische Entitäten nach Kritikalitätslevel
- **semantic_roles**: Semantische Rollen aller Entitäten
- **lighting_capabilities**: Beleuchtungs-Capabilities
- **dependency_links**: Abhängigkeitsbeziehungen zwischen Entitäten
- **recommended_actions**: Empfohlene Aktionen für Entitäten
- **simulation_readiness**: Simulationsbereitschaft von Szenarien

**Bedeutung von Änderungen:**
- `query_answerability_ratio` ↑ = Mehr Queries liefern Ergebnisse
- `query_success_ratio` ↑ = Weniger fehlgeschlagene Queries
- `query_latency_*` ↓ = Schnellere Antwortzeiten

### 5. Score-Berechnungen (ScoreMetrics)

Aggregierte Bewertungen der Systemqualität:

#### Semantic Score (Semantische Qualität)
Gewichtete Summe aller semantischen Coverage-Metriken:
```
semantic_score = 0.20 × semantic_role_coverage +
                 0.15 × semantic_category_coverage +
                 0.15 × capability_coverage +
                 0.15 × dependency_coverage +
                 0.10 × causal_relation_coverage +
                 0.10 × simulation_readiness_coverage +
                 0.10 × average_semantic_confidence +
                 0.05 × explainability_coverage
```

#### World Model Score (Gesamtmodell-Qualität)
Kombination aus kanonischer Coverage, semantischer Qualität und Query-Performance:
```
world_model_score = 0.25 × canonical_coverage +
                    0.20 × raw_to_canonical_resolution +
                    0.20 × semantic_score +
                    0.20 × query_answerability +
                    0.15 × explainability_coverage
```

#### Efficiency Scores (Wert-Effizienz)
- **semantic_value_per_second**: Semantischer Score pro Sekunde Laufzeit
- **world_model_value_per_second**: Weltmodell-Score pro Sekunde Laufzeit

**Bedeutung von Änderungen:**
- `semantic_score` ↑ = Höhere semantische Vollständigkeit
- `world_model_score` ↑ = Besseres Gesamtmodell
- `*_value_per_second` ↑ = Bessere Effizienz (mehr Qualität pro Zeit)

## Performance-Entwicklung interpretieren

### Positive Entwicklungen
- **Runtime ↓**: Effizientere Verarbeitung
- **Coverage-Ratios ↑**: Vollständigeres Modell
- **Confidence ↑**: Zuverlässigere Ergebnisse
- **Query Answerability ↑**: Mehr erfolgreiche Abfragen
- **Value per Second ↑**: Bessere Effizienz

### Negative Entwicklungen (können positiv sein)
- **Runtime ↑**: Kann durch komplexere Verarbeitung bedingt sein
- **Semantic Score ↓**: Kann durch strengere Qualitätskriterien bedingt sein

### Typische Entwicklungsmuster
1. **Initiale Phase**: Hohe Coverage, aber niedrige Confidence
2. **Optimierungsphase**: Confidence steigt, Runtime sinkt
3. **Stabilitätsphase**: Stabile Metriken mit hoher Qualität

## Benchmark-Ausführung

### Automatische Ausführung
```bash
.venv/bin/python3 -m benchmark.benchmark_runner
```

### Manuelle Konfiguration
- **NEO4J_URI**: Neo4j-Verbindungsstring (Standard: bolt://localhost:7687)
- **NEO4J_USER/PASSWORD**: Neo4j-Authentifizierung
- **Output-Formate**: JSON, Markdown, CSV

### Performance-Evolution
Nach jedem Lauf wird automatisch eine `performance_evolution_summary.md` generiert, die die Entwicklung über alle Läufe zeigt.

## Troubleshooting

### Häufige Probleme
- **Neo4j-Verbindungsfehler**: Überprüfen Sie NEO4J_URI und Container-Status
- **Leere Ergebnisse**: Datenbank enthält keine semantischen Daten
- **Hohe Latenzen**: Index- oder Hardware-Probleme

### Validierung
- **Graph-Metriken > 0**: Datenbank enthält Daten
- **Query Success Ratio > 0.8**: Grundlegende Funktionalität
- **Semantic Coverage > 0.1**: Semantische Anreicherung aktiv

## Metriken-Referenz

| Metrik | Bereich | Optimal | Bedeutung |
|--------|---------|---------|-----------|
| runtime | 0.1-60s | ↓ | Verarbeitungsgeschwindigkeit |
| semantic_score | 0.0-1.0 | ↑ | Semantische Vollständigkeit |
| world_model_score | 0.0-1.0 | ↑ | Gesamtmodell-Qualität |
| canonical_coverage | 0.0-1.0 | ↑ | Normalisierung |
| query_answerability | 0.0-1.0 | ↑ | Abfrage-Erfolgsrate |
| semantic_value_per_second | 0.0-∞ | ↑ | Effizienz |

Dieses Benchmark-System bietet umfassende Einblicke in die Qualität und Performance des semantischen Weltmodells und hilft bei der kontinuierlichen Verbesserung des Systems.