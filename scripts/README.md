# scripts

Dieser Ordner enthält Hilfs- und Überprüfungsskripte für CI, Validierung und einmalige Aufgaben.

Enthaltene Dateien:
- `l1/evidence.py`: Erzeugt laufgebundene Test-, Scan-, SBOM-, Plattform- und
  Container-Nachweise. Container-Archive enthalten einen Transport-Tag; Build-
  Config-Digest und Zielhost-Laufzeit-ID werden bewusst getrennt behandelt.
- `l1/report.py`: Prüft die Nachweis-Bundles und bildet ihre gemessene Abdeckung
  auf die 16 Anforderungen der L1-Baseline ab.
- `ci_validate_enrichment.py`: Validiert Enricher-Konfigurationen, Prompt-/Schema-Konsistenz und ggf. strukturierte Ausgabeformate.
- `backfill_canonical_semantics.py`: Migriert bestehende semantische Beziehungen von `Entity` auf die zugeordnete `CanonicalEntity`.
- `backfill_dependency_edges.py`: Leitet deterministische `DEPENDS_ON`-, `IMPACTS`- und `DEGRADES`-Kanten aus vorhandenen Integrations-, Capability- und Failure-Impact-Fakten ab.
- `backfill_domain_semantics.py`: Ergänzt konservative Rollen, Kategorien und Capabilities aus Home-Assistant-Domains, wenn die Canonical-Ebene noch zu dünn ist.
- `backfill_causal_simulation_edges.py`: Materialisiert vorsichtige Causal- und Simulation-Readiness-Kanten aus `DEGRADES`, `HAS_FAILURE_IMPACT`, Incidents und Automation-/`CAN_CAUSE`-Beziehungen.

## Funktionen

- Automatisiert wiederkehrende Prüfungen, bevor neue Enricher oder Schemaänderungen in den Hauptzweig gemergt werden.
- Dient als Entwicklungswerkzeug zur Sicherstellung der Stabilität der semantischen Enrichment-Pipeline.

## Ziel

Der Ordner fasst kleine utility-Skripte zusammen, die keine dauerhaften Services darstellen, aber wichtige Qualitätsprüfungen liefern.
