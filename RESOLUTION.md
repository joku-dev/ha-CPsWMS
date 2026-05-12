# Resolution und Lessons Learned

Dieses Dokument beschreibt die wichtigsten Probleme, Ursachen, Loesungswege und Erkenntnisse aus der Stabilisierung der Canonical- und Semantic-Enrichment-Pipeline.

## Ausgangslage

Das Projekt hatte bereits eine Canonical-Identity-Schicht, semantische Enricher und Benchmarking. Trotzdem waren die Ergebnisse in Neo4j und im Benchmark unbefriedigend:

- Semantische Beziehungen waren teilweise vorhanden, aber nicht dort, wo die Benchmark- und Query-Schicht sie erwartete.
- Canonical Entities existierten, hatten aber anfangs kaum eigene Semantik.
- Einige Enricher fanden in `canonical_first` keine sinnvollen Kandidaten.
- Dependency-, Causal- und Simulation-Readiness-Coverage waren praktisch leer.
- Neo4j zeigte Warnungen zu fehlenden Relationship Types und deprecated Cypher-Subqueries.
- LLM-Ausgaben waren fuer einige Layer nicht belastbar genug oder lieferten leere Ergebnisse.

## Problem 1: Semantik lag auf Entity statt CanonicalEntity

### Symptom

Im Graph waren viele `Entity`-Knoten semantisch angereichert, aber die Benchmark-Metriken zaehlten bei vorhandener Canonical-Schicht primaer `CanonicalEntity`. Dadurch sah die semantische Coverage deutlich schlechter aus als die vorhandenen Daten eigentlich waren.

### Ursache

Die erste Enrichment-Generation schrieb Beziehungen wie `HAS_SEMANTIC_ROLE`, `HAS_SEMANTIC_CATEGORY`, `HAS_CRITICALITY`, `HAS_FAILURE_IMPACT`, `HAS_RECOMMENDED_ACTION` und `PROVIDES_CAPABILITY` direkt an `Entity`. Nach Einfuehrung der Canonical-Pipeline wurden diese Beziehungen nicht automatisch auf die zugehoerige `CanonicalEntity` gespiegelt.

### Loesung

Es wurde ein Backfill-Skript eingefuehrt:

- `scripts/backfill_canonical_semantics.py`

Das Skript kopiert bestehende semantische Beziehungen von `Entity` auf die verknuepfte `CanonicalEntity`, inklusive Relationship-Properties wie `confidence`, `reason`, `source` und Zeitstempel.

### Ergebnis

Der erste Backfill verbesserte den Semantic Score um `+14.7%`, den World Model Score um `+4.9%` und die Query Answerability um `+11.1%`.

### Lesson Learned

Canonical Identity ist nur dann wertvoll, wenn die semantischen Beziehungen ebenfalls canonical-aware sind. Es reicht nicht, Raw- und Canonical-Knoten zu verbinden; alle Auswertungs- und Enrichment-Layer muessen auf dieselbe Zielschicht schreiben.

## Problem 2: Canonical-first Candidate-Auswahl filterte zu frueh

### Symptom

Einige Enricher liefen zwar, fanden aber nach der Canonical-Filterung keine oder zu wenige Kandidaten. Dadurch entstanden keine neuen Canonical-Semantiken.

### Ursache

Die Pipeline holte zuerst nur eine kleine Menge Kandidaten aus Neo4j und filterte danach auf Canonical-Tauglichkeit. Wenn die ersten Kandidaten keine Canonical-Ziele hatten, blieb der Enricher leer, obwohl im Graph spaeter passende Kandidaten vorhanden gewesen waeren.

### Loesung

In `semantic-enrichment/enrichers/base.py` wurde die Candidate-Auswahl angepasst:

- In `canonical_first` wird ein groesserer Kandidatenpool geladen.
- Danach wird auf gueltige Canonical-Ziele gefiltert.
- Erst danach wird auf die eigentliche Batch-Groesse begrenzt.

Zusaetzlich wurden Cypher-Kontextfehler in Enrichern behoben:

- `automation_intent.py`: falsche `raw`-/`c`-Rueckgaben entfernt.
- `anomaly_detection.py`: `raw` und `c` ueber `WITH` erhalten.
- `temporal_event_model.py`: `raw` und `c` ueber Zwischenschritte erhalten.

### Ergebnis

Nach diesem Schritt stieg der Semantic Score nochmals um `+6.6%`. Die Runtime sank um `-30.3%`, und der Semantic Value per Second stieg um `+53.1%`.

### Lesson Learned

Filtering gehoert an die richtige Stelle. Bei Canonical-first muss die Pipeline erst genug Rohkandidaten sehen, bevor sie entscheiden kann, welche davon canonical-ready sind.

## Problem 3: Dependency Coverage war fast null

### Symptom

Simulation Readiness meldete konsequent fehlende Dependency- und Impact-Pfade. Der Benchmark zeigte `dependency_coverage_ratio` nahe `0`.

### Ursache

Im Graph existierten viele belastbare Fakten:

- `Entity -> Integration` ueber `PROVIDED_BY`
- `Entity -> Capability` ueber `PROVIDES_CAPABILITY`
- Failure-Impact-Informationen ueber `HAS_FAILURE_IMPACT`

Diese Fakten waren aber nicht als explizite Dependency-/Impact-Kanten materialisiert. Die Simulation- und Benchmark-Schicht sucht jedoch gezielt nach Kanten wie:

- `DEPENDS_ON`
- `IMPACTS`
- `DEGRADES`
- `RECOVERS`

### Loesung

Es wurde ein deterministischer Dependency-Backfill eingefuehrt:

- `scripts/backfill_dependency_edges.py`

Das Skript erzeugt aus vorhandenen Fakten explizite Kanten:

- `Entity` und `CanonicalEntity` `DEPENDS_ON` `Integration`
- `Entity` und `CanonicalEntity` `IMPACTS` `Capability`
- `Entity` und `CanonicalEntity` `DEGRADES` `Capability`, wenn Failure-Impact-Evidence vorhanden ist

Dabei wird bewusst keine neue inhaltliche Behauptung erfunden. Die Kanten sind nur eine materialisierte Form bereits vorhandener Graph-Fakten.

### Ergebnis

Der Backfill erzeugte:

- `1223` Integration-Dependency-Signale
- `20` Capability-Impact-Signale
- `20` Failure-Degradation-Signale

Der Benchmark danach:

- Semantic Score: `0.1510` -> `0.3124`
- Dependency Coverage: `0.0034` -> `0.9696`
- World Model Score: `0.7668` -> `0.8187`

### Lesson Learned

Nicht jede Semantik muss durch ein LLM entstehen. Viele hochwertige semantische Kanten lassen sich deterministisch aus bereits vorhandenen Graph-Fakten ableiten. Das ist guenstiger, reproduzierbarer und besser testbar.

## Problem 4: Rollen, Kategorien und Capabilities waren zu duenn

### Symptom

Trotz Canonical-Schicht und einzelner LLM-Enrichment-Ergebnisse lagen `semantic_role_coverage_ratio`, `semantic_category_coverage_ratio` und `capability_coverage_ratio` nur im niedrigen einstelligen Prozentbereich.

### Ursache

Die LLM-Enricher arbeiteten batchweise und konnten wegen Budget, Candidate-Auswahl und Validierung nur einen kleinen Ausschnitt des Graphen anreichern. Gleichzeitig tragen Home-Assistant-Domains bereits stabile Basissemanik, zum Beispiel:

- `sensor` -> Messung/Monitoring
- `switch` -> binaere Steuerung
- `light` -> Lichtsteuerung
- `automation` -> Automation Execution
- `scene` -> Scene Activation

Diese einfache Semantik wurde noch nicht breit genutzt.

### Loesung

Es wurde ein konservativer Domain-Semantik-Backfill eingefuehrt:

- `scripts/backfill_domain_semantics.py`

Das Skript mappt Home-Assistant-Domains auf Basisrollen, Kategorien und Capabilities. Beispiele:

- `sensor` -> `sensor`, `measurement`, `state_monitoring`
- `binary_sensor` -> `sensor`, `status_monitoring`, `binary_state_monitoring`
- `light` -> `actuator`, `lighting`, `lighting_control`
- `automation` -> `automation`, `automation`, `automation_execution`
- `tts` -> `speech_service`, `voice`, `text_to_speech`

Die Confidence wurde bewusst konservativ gesetzt, weil Domain-Semantik korrekt, aber weniger spezifisch ist als eine echte LLM- oder Integrationsanalyse.

### Ergebnis

Der Backfill ergaenzte `589` Canonical Entities mit Rollen, Kategorien und Capabilities.

Der Benchmark danach:

- Semantic Score: `0.3124` -> `0.7827`
- World Model Score: `0.8187` -> `0.9363`
- Query Answerability: `0.8333` -> `0.9167`
- Semantic Role Coverage: `0.9949`
- Capability Coverage: `0.9949`
- Dependency Coverage: `0.9696`

### Lesson Learned

Eine gute Semantic Pipeline braucht Layer:

1. Deterministische Basissemantik aus stabilen Fakten.
2. Canonical Backfill fuer Konsistenz.
3. LLM-Enrichment fuer spezifische, kontextreiche Aussagen.
4. Benchmarking als Kontrollmechanismus.

LLMs sollten nicht fuer triviale, stabile Klassifikation verbrannt werden.

## Problem 5: Causal Coverage bleibt niedrig

### Symptom

Auch nach den grossen Verbesserungen bleibt `causal_relation_coverage_ratio` bei `0.0017`.

### Ursache

Causal-Links sind anspruchsvoller als Rollen, Kategorien oder Dependencies. Ein `DEPENDS_ON` aus `PROVIDED_BY` ist strukturell sicher. Ein echtes `CAUSES` braucht dagegen Ereignisse, Zeitbezug, Failure Evidence oder Automation-Zusammenhaenge.

Der Causal-Enricher bekommt inzwischen Kandidaten, aber die LLM-Ausgabe war oft leer oder nicht stark genug, um valide Links zu schreiben.

### Aktueller Stand

Die Pipeline ist jetzt vorbereitet:

- Canonical-Ziele sind vorhanden.
- Basisrollen, Kategorien und Capabilities sind vorhanden.
- Dependency-, Impact- und Degradation-Kanten sind vorhanden.
- Simulation Readiness kann konkreter sagen, welche Daten fehlen.

Der naechste Hebel ist nicht mehr allgemeine Semantik, sondern gezielte Kausalmodellierung.

### Lesson Learned

Causal Semantics sollte nicht direkt aus rohen Entities geraten werden. Sie braucht zuerst:

- Canonical Identity
- Capabilities
- Failure Impact
- Timeline Events
- Incidents
- Dependency- und Impact-Kanten

Erst danach lohnt sich ein LLM- oder regelbasierter Causal Layer.

## Methoden, die funktioniert haben

### Schrittweises Benchmarking

Nach jedem Eingriff wurde ein Benchmark erzeugt und mit dem vorherigen Stand verglichen. Dadurch konnten Verbesserungen und Rueckschritte sichtbar getrennt werden.

Wichtige Report-Dateien:

- `benchmark/reports/2026-05-12T17-36-04.751008+00-00_benchmark.md`
- `benchmark/reports/performance_evolution_summary.md`

### Deterministische Backfills

Die groessten Spruenge kamen nicht aus neuen Prompts, sondern aus materialisierten Graph-Fakten:

- Canonical-Semantik spiegeln
- Dependency-Kanten aus `PROVIDED_BY` ableiten
- Capability-Kanten aus Domains und vorhandenen Capabilities ableiten

### Canonical-first reparieren statt umgehen

Die Canonical-Pipeline wurde nicht deaktiviert. Stattdessen wurde die Candidate-Auswahl angepasst, damit Canonical-first wirklich funktionieren kann.

### LLM budgetschonend einsetzen

Da das LLM-Budget begrenzt war, wurden robuste und guenstige Basisschichten zuerst gebaut. Das reduziert spaeter LLM-Kosten und verbessert die Qualitaet der Prompts, weil das LLM mehr Kontext bekommt.

## Aktueller Zielzustand

Der letzte Benchmark zeigt:

- Semantic Score: `0.7827`
- World Model Score: `0.9363`
- Canonical Coverage: `1.0000`
- Raw-to-Canonical Resolution: `1.0000`
- Semantic Role Coverage: `0.9949`
- Capability Coverage: `0.9949`
- Dependency Coverage: `0.9696`
- Causal Relation Coverage: `0.0017`
- Query Answerability: `0.9167`

Damit ist die Semantik-Basis stabil. Der verbleibende Engpass ist Causal/Simulation Readiness.

## Naechste empfohlene Schritte

1. Automation-Definitionen in explizite Kanten ueberfuehren:
   - `TRIGGERED_BY`
   - `CONTROLS`
   - `HAS_CONDITION`

2. Aus vorhandenen `DEGRADES`, `HAS_FAILURE_IMPACT`, `HAS_INCIDENT` und `HAS_TIMELINE_EVENT` vorsichtige Causal-Kandidaten ableiten.

3. Causal-Enricher mit besserem Kontext versorgen:
   - vorhandene Dependency-Pfade
   - Capability-Pfade
   - Incidents
   - zeitliche Reihenfolge

4. Simulation Readiness erneut laufen lassen und pruefen, ob `not_ready` in Richtung `partial` steigt.

5. Neo4j-Warnungen bereinigen:
   - deprecated `CALL { WITH ... }` Syntax auf moderne Variable-Scope-Subqueries umstellen
   - fehlende Relationship Types nicht abfragen oder vorher deterministisch erzeugen

## Wichtigste Erkenntnis

Die schwache Performance war nicht ein einzelner Bug. Es war eine Schichten-Frage:

- Die Canonical-Schicht war da, aber nicht voll semantisch verbunden.
- Die Daten enthielten viele Fakten, aber nicht in den Relationship Types, die Benchmark und Simulation erwarteten.
- LLM-Enrichment allein war zu teuer und zu schmal, um den ganzen Graphen zu tragen.

Die erfolgreiche Strategie war deshalb:

1. Erst Canonical-Konsistenz herstellen.
2. Dann vorhandene Fakten deterministisch materialisieren.
3. Danach breite Basissemantik aus stabilen Home-Assistant-Domains ableiten.
4. Erst danach Causal und Simulation gezielt verbessern.
