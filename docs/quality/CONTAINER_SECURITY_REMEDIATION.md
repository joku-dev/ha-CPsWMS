# Container-Schwachstellen: Patch- und Befundbewertung

Stand: 16. September 2026. Consumer-seitige Build-Korrektur und technische
Befundbewertung; keine Änderung der L1-Baseline, keine Risikofreigabe.

## Ausgangspunkt

Run [35128325507](https://github.com/joku-dev/ha-CPsWMS/actions/runs/35128325507),
Commit `9aa1806f40f5b0ac764bca4d51a58cd8846eb8fd`: 13 kritische und 373 hohe
Image-/Paketmeldungen, dedupliziert 4 kritische und 129 hohe CVE-IDs. Alle diese
Treffer betreffen OS-Pakete. Vier Python-Images teilen dieselbe Basis.

## Korrektur

Die Registry lieferte am 16. September noch die bereits gepinnten Python- und
Neo4j-Digests aus `quality/runtime-images.json`. Deshalb erhalten alle fünf
Images eine explizite Debian-Patch-Schicht mit festgelegten Versionen:

| Paket | Zielversion | Zugeordnete Befunde |
|---|---|---|
| perl-base | 5.40.1-6+deb13u1 | u.a. CVE-2026-13221, CVE-2026-42496, CVE-2026-8376 |
| gzip | 1.13-1+deb13u1 | CVE-2026-41992 |
| libpcre2-8-0 | 10.46-1~deb13u2 | CVE-2026-86145, CVE-2026-89161 |
| libsqlite3-0 | 3.46.1-7+deb13u2 | CVE-2026-11822, CVE-2026-11824 |

Debian-Referenzen: [Perl](https://security-tracker.debian.org/tracker/CVE-2026-13221),
[gzip](https://security-tracker.debian.org/tracker/CVE-2026-41992),
[PCRE2](https://security-tracker.debian.org/tracker/CVE-2026-86145),
[SQLite](https://security-tracker.debian.org/tracker/CVE-2026-11822).

Die Builds brechen ab, wenn diese Paketversionen nicht installiert werden können.
Die vier Python-Dockerfiles pinnen nun auch ihren Default-Basiswert. Lokales
Compose baut Neo4j aus `deployment/images/neo4j/Dockerfile`; bestehende Container
werden dadurch nicht automatisch aktualisiert. Keine Datenmigration wird ausgeführt.

Der CI-Integrationstest lädt für Query API **und Neo4j** die gescannten Archive
desselben Runs. Identität, Manifest und Hash werden geprüft, bevor Docker sie mit
`--pull=never` startet. Staging verwendet weiterhin explizit ausgewählte Image-IDs.

Ein Digest fixiert die Basis, nicht die gesamte Auflösung: APT-Transitivpakete und
Python-Abhängigkeiten sind weiterhin kein vollständiger reproduzierbarer Lock.
Build-Logs und SBOM dokumentieren die tatsächlichen Versionen. Für spätere Updates
müssen Paketpins kontrolliert angepasst werden; keine automatische Ausnahme.

## Verifikation und verbleibende Bewertung

Der zugehörige PR-Lauf muss alle fünf Builds, SBOMs und Scans sowie den echten
HTTP-/Neo4j-Test bestehen. Die Abschlussmessung und konkrete Restbefunde werden
nach dem Lauf ergänzt. Es werden keine Trivy-Ignores oder Schweregradfilter gesetzt.

Ein Pakettreffer belegt nicht automatisch einen erreichbaren Angriffspfad.
Die spätere eigene Staging-VM existiert noch nicht; ihre Konfiguration und ihr
Kernel sind nicht durch einen Container-Image-Scan bewertet.
