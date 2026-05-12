# semantic_core/identity

Dieser Ordner enthält die Identitätsauflösung und das Canonical-Entity-Management.

Enthaltene Dateien:
- `canonical_registry.py`: Verwaltung bestehender CanonicalEntity-Instanzen und Matching-Mechanismen.
- `confidence_model.py`: Scoring-Modelle für Vertrauensbewertungen bei Auflösungsentscheidungen.
- `evidence_model.py`: Datenmodelle für Evidenz und Entscheidungsunterstützung.
- `identity_resolver.py`: Hauptlogik zur Verbindung von RawEntity-Daten mit CanonicalEntity-Instanzen.
- `models.py`: Dataklassen für RawEntity, CanonicalEntity, ResolutionDecision, Evidence und verwandte Modelle.
- `resolution_pipeline.py`: Pipeline zur Verarbeitung von Auflösungen, Regeln und Persistierungsschritten.
- `review_queue.py`: Mechanismen zur Erwerbung von menschlicher Überprüfung und Freigabe für unsichere Entscheidungen.

## Funktionen

- Definiert Datenstrukturen für semantische Identitäten.
- Sorgt für konsistente Auflösung von Rohdaten zu Canonical-Entitäten.
- Bewertet und protokolliert Entscheidungspfad, Evidenz und Zuverlässigkeit.

## Ziel

Eine stabile semantische Identitätsschicht zu liefern, die Entitäten aus unterschiedlichen Quellen zusammenführt und über mehrere Verarbeitungsschritte hinweg konsistent hält.