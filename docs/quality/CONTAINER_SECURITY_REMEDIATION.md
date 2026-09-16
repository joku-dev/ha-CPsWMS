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

## Gemessene Verifikation

Der [PR-Prüflauf 35129799416](https://github.com/joku-dev/ha-CPsWMS/actions/runs/35129799416)
zum Implementierungsstand `b4080176d522ac74f0af8c21b3a38eb9e9e8f039` baut und scannt
alle fünf Images. **57 Tests bestehen**, einschließlich HTTP-/Neo4j-Integration,
Ausfall und Wiederanlauf. Der Bericht enthält keine Evidenzfehler.
Die Paketinventare bestätigen die vier Zielversionen in jedem
Image; die Rohdateien wurden gegen Manifest-Hashes und Image-IDs geprüft.

| Image | Kritisch vorher → nachher | Hoch vorher → nachher |
|---|---|---|
| ha-sync | 3 → 0 | 53 → 44 |
| query-api | 3 → 0 | 53 → 44 |
| semantic-enrichment | 3 → 0 | 53 → 44 |
| world-model-chat | 3 → 0 | 53 → 44 |
| neo4j | 1 → 1 | 161 → 156 |
| Gesamt (Image-/Paketmeldungen) | **13 → 1** | **373 → 332** |
| Unterschiedliche CVE-IDs | **4 → 1** | **129 → 120** |

12 kritische und 41 hohe Meldungen sind damit entfernt. Keine der verbleibenden
hohen/kritischen Meldungen nennt im Scan eine korrigierte Paketversion. Das ist
keine Aussage, dass es upstream generell keinen Fix gibt.

Die [vollständige Restliste](evidence/2026-09-16-remaining-container-findings.csv)
enthält CVE, Paket, Version und betroffene Images. Der
[Scan-Kontext](evidence/2026-09-16-container-scan-context.json) enthält Run-/Commit-
Bindung, Image-IDs, bestätigte Paketversionen und Rohbericht-Hashes. Die CSV zählt
zusammen 333 Image-/Paketmeldungen; sie ersetzt weder Rohberichte noch eine VEX-
Freigabe. Die GitHub-Image-Artefakte werden nach sieben Tagen gelöscht.

## Technische Bewertung sämtlicher Restgruppen

Alle Gruppen bleiben im Scanner sichtbar und im Bewertungsstatus offen. Die
folgende Einordnung ist eine technische Prüfung, keine unabhängige Freigabe.

| Restgruppe | Meldungen | Voraussetzung / Einordnung | Noch erforderlicher Schritt |
|---|---:|---|---|
| linux-libc-dev | 1 kritisch + 110 hoch | Linux-CVEs über ein Headerpaket im Neo4j-Image. Die erfassten Dateien liegen unter `/usr/include`, `/usr/lib/linux/uapi` und Dokumentation; sie sind kein laufender Kernel. | VM-Kernel und aktivierte Module separat prüfen; Headerzuordnung als begründeten Nicht-Laufzeit-Fall erfassen, bevor eine formale VEX-Aussage erfolgt. |
| util-linux-Paketfamilie | 180 hoch | Vier CVEs, neun Pakete, fünf Images. Lokale Mount-/Namespace-Funktionen und besondere privilegierte Aufrufkontexte sind Voraussetzung. Die isolierte Staging-Konfiguration fordert weder privilegierten Modus noch zusätzliche Capabilities oder Host-Namespaces an. | Tatsächliche VM-/Container-Rechte, SUID-Binaries, fstab und Mount-Konfiguration prüfen. Debian-Stable-Korrekturen beobachten. |
| ncurses | 20 hoch | CVE-2025-69720 betrifft `infocmp`; das Inventar enthält dieses CLI-Werkzeug. Kein Aufruf in den geprüften Anwendungsquellen gefunden, indirekte oder administrative Aufrufe bleiben möglich. | Verwendung und untrusted Eingaben prüfen; Update oder Entfernung nach Abhängigkeitsprüfung. |
| systemd-Bibliotheken | 10 hoch | CVE-2026-16742 betrifft systemd-homed. Die OS-Dateiinventare listen kein `systemd-homed`; die Treffer hängen an libsystemd0/libudev1. | Datei-/Prozessprüfung am finalen Image und Host getrennt durchführen; keine pauschale Host-Entwarnung. |
| libacl1 | 5 hoch | CVE-2026-54369 setzt privilegierte ACL-Operationen auf durch Angreifer beeinflussbaren Dateipfaden voraus. Direkter Angriffspfad in den geprüften Python-Diensten nicht gefunden. | Dateirechte, beschreibbare Verzeichnisse und transitive Aufrufer prüfen; Debian-Korrektur verfolgen. |
| perl-base | 5 hoch | CVE-2026-9538 betrifft Archive::Tar und Speichererschöpfung durch manipulierte Archive. `Archive/Tar.pm` fehlt im erfassten OS-Dateiinventar; das ist noch kein vollständiger Dateisystem-/Laufzeitbeweis. | Modulverfügbarkeit und Archivverarbeitung am finalen Image prüfen; kein automatischer Ausschluss. |
| wget (nur Neo4j) | 2 hoch | CVE-2026-58471/58472 betreffen manipulierte Antworten beim Abruf/Verarbeiten fremder Inhalte. Keine wget-Aufrufe in unseren Anwendungsquellen gefunden; Upstream-Startskripte und spätere Plugin-Downloads sind gesondert zu prüfen. | Tatsächliche Start-/Administrationspfade prüfen; bei Nichtbedarf Entfernung testen, sonst Patch verfolgen. |

Hersteller-/Distributionsquellen, geprüft am 16. September 2026:
[Linux-CVE](https://security-tracker.debian.org/tracker/CVE-2026-43185),
[Headerpaket](https://packages.debian.org/trixie/linux-libc-dev),
[util-linux](https://security-tracker.debian.org/tracker/CVE-2026-76642),
[ncurses](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[systemd](https://security-tracker.debian.org/tracker/CVE-2026-16742),
[ACL](https://security-tracker.debian.org/tracker/CVE-2026-54369),
[Perl](https://security-tracker.debian.org/tracker/CVE-2026-9538),
[wget 58471](https://security-tracker.debian.org/tracker/CVE-2026-58471),
[wget 58472](https://security-tracker.debian.org/tracker/CVE-2026-58472).

## Grenzen und nächste Prüfung

Die eigene Staging-VM ist vom Maintainer vorgesehen, aber noch nicht vorhanden.
Vor Bereitstellung sind Host-Kernel, Container-Rechte und erreichbare Dienste zu
prüfen. Diese Restbewertung ersetzt keine konkrete Artefakt-/Deployment-Freigabe.

Lokales Compose verwendet jetzt die geprüfte Neo4j-Linie 5.26 (gepinntes Image:
5.26.30). Wer zuvor `neo4j:latest` mit bestehenden Daten betrieben hat, muss vor
Start der neuen Compose-Konfiguration die bisherige Datenbankversion und
Store-Kompatibilität prüfen und ein Backup erstellen. Insbesondere wird kein
Datenbank-Downgrade gegen bestehende Volumes freigegeben. Das neue Staging startet
mit separaten Volumes. Der ältere allgemeine CI-Benchmark verwendet weiterhin
seinen separaten kurzlebigen `neo4j:latest`-Service; er ist keine Lieferartefakt-
oder Staging-Freigabe. Der L1-Integrationstest verwendet ausschließlich die beiden
geprüften Archive.

Es wurden keine Trivy-Ignores, CVE-Ausnahmen, Schweregradfilter oder
Produktionsänderungen eingerichtet. SAST-/Lint-Befunde sind von dieser OS-Patch-
Änderung nicht betroffen. L1-010 bleibt wegen verbleibender Befunde offen.
