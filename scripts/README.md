# scripts

Dieser Ordner enthält Hilfs- und Überprüfungsskripte für CI, Validierung und einmalige Aufgaben.

Enthaltene Dateien:
- `ci_validate_enrichment.py`: Validiert Enricher-Konfigurationen, Prompt-/Schema-Konsistenz und ggf. strukturierte Ausgabeformate.
- `backfill_canonical_semantics.py`: Migriert bestehende semantische Beziehungen von `Entity` auf die zugeordnete `CanonicalEntity`.
- `backfill_dependency_edges.py`: Leitet deterministische `DEPENDS_ON`-, `IMPACTS`- und `DEGRADES`-Kanten aus vorhandenen Integrations-, Capability- und Failure-Impact-Fakten ab.
- `backfill_domain_semantics.py`: Ergänzt konservative Rollen, Kategorien und Capabilities aus Home-Assistant-Domains, wenn die Canonical-Ebene noch zu dünn ist.

## Funktionen

- Automatisiert wiederkehrende Prüfungen, bevor neue Enricher oder Schemaänderungen in den Hauptzweig gemergt werden.
- Dient als Entwicklungswerkzeug zur Sicherstellung der Stabilität der semantischen Enrichment-Pipeline.

## Ziel

Der Ordner fasst kleine utility-Skripte zusammen, die keine dauerhaften Services darstellen, aber wichtige Qualitätsprüfungen liefern.
