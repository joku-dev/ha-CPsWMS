# L1 mit ausgeführten Tests und Werkzeugen

Dieser zusätzliche Workflow deckt die Nachweiserhebung für die 16 Anforderungen
von `l1-baseline-v1.1.3` ab. Er misst Anwendung und Lieferartefakte. Der Bericht
ist eine **Abdeckungsanalyse**, keine neue Baseline oder Produktionsfreigabe.

## Ausführung und Ergebnisse

`.github/workflows/l1-measured-evidence.yml` läuft bei PRs, Main-Pushes und manuell.
Der Lauf stellt `l1-control-coverage/l1-coverage.md` und `.json` bereit; die
GitHub-Zusammenfassung zeigt alle 16 Kontrollen. Ergebnisse sind:

- `measured`: der im Detail genannte technische Nachweis wurde erzeugt/geprüft;
- `partial`: technische Evidenz vorhanden, weitere Kontrollbestandteile offen;
- `findings`: Werkzeugbefunde brauchen Bewertung;
- `gap`: fehlende, ungültige oder nicht zugängliche Evidenz.

`measured` bedeutet nicht, dass die gesamte normative Anforderung unabhängig
abgenommen wurde. Der bestehende deklarationsbasierte L1-Report bleibt ein
getrennter Bericht. Dessen `pass` darf nicht als Freigabe dieser Messungen gelten.

Findings sind report-only. Testfehler, Tool-Abstürze, fehlende Ausgaben und
Integritätsfehler lassen den Prüflauf fehlschlagen. Der Main-Ruleset verlangt den
Check `L1 coverage report` zusammen mit den beiden Plattformvalidierungen und den
DevSecOps-/Architektur-Governance-Checks. Direkte Main-Pushes, Force-Pushes und
Branch-Löschung sind gesperrt. Der Solo-Maintainer-Workflow verlangt weiterhin
keine unabhängige Review-Freigabe; eine grüne Pipeline ist keine Deployment-Freigabe.

## Kontrollzuordnung

| L1-REQ | Echte Prüfung / Werkzeug | Verbleibende Grenze |
|---|---|---|
| 001 | Technische Anforderungen → ausgeführte pytest-Testfälle → JUnit | Vollständige freigegebene Systemanforderungen fehlen |
| 002 | GitHub Commit-, PR- und Review-API | Keine fingierte unabhängige Review-Freigabe |
| 003 | GitHub Ruleset-, Branch-Protection- und Rules-API | Aktiver Main-Ruleset ohne Bypass, PR-Pflicht und fünf Required Checks |
| 004 | Bandit, Ruff, Chat-Negativtests | Nullbefund wird als gemessene technische Prüfung ausgewiesen |
| 005 | Hash-gelockte Anwendungs-/CI-Inventare und Trivy-Inventar aller fünf Images | Laufzeit, Anwendung sowie Build-/Testwerkzeuge abgedeckt |
| 006 | CycloneDX-SBOM je tatsächlich archiviertem Image | Keine handgeschriebene Komponentenliste |
| 007 | Docker-Build-Protokolle, gepinnte Basisimages und Python-3.12-Locks mit SHA-256 | Images installieren ausschließlich aus den Locks |
| 008 | Image-ID, Commit, Archiv-SHA-256 | Identifiziert tatsächlichen Build |
| 009 | Trivy-CVE-Scan derselben Image-IDs | Toolfehler sind keine leeren Scans |
| 010 | Trivy- und `pip-audit`-Rohbefunde | Release-Risikobewertung bleibt offen |
| 011 | Archiv-/Nachweis-Hashes nach Download erneut prüfen | Zugriffsschutz, Aufbewahrung und unabhängige Provenienz separat |
| 012 | Inhaltsbasierte Artefaktidentität | Keine manuell behauptete Versionszuordnung |
| 013 | Erfassung vorhandener GitHub-Environments | Autorisierte Zielumgebung/Release-Freigabe fehlt |
| 014 | CI startet exakt die untersuchten Query-/Neo4j-Images | Freigegebene Artefaktauswahl im Zieldeployment fehlt |
| 015 | JSON, JUnit, Coverage, Rohberichte, Manifeste | Run-/Commit-Bindung und Byteprüfung |
| 016 | Echte CI-Deployment-IDs, HTTP-/DB-Logs, Ausfalltest | Produktionsregister und Security-Event-Aufbewahrung fehlen |

## Anwendungstests

Die bestehenden Tests werden zusammen mit `quality_tests/test_component_behavior.py`
ausgeführt. Das ergänzt Sync-Normalisierung, verschachtelte Entity-Verweise,
Abfragegrenzen und die Ablehnung unsicherer Chat-Cypher-Eingaben. Es finden keine
bezahlten LLM-Aufrufe oder Zugriffe auf eine reale Home-Assistant-Instanz statt.
Die bisherigen semantischen Unit-Tests bleiben als Unit-Tests gekennzeichnet.
Coverage wird für alle Anwendungsmodule erfasst; niedrige Abdeckung wird sichtbar.

Die Container-Integration lädt die archivierten Query-/Neo4j-Images, prüft
Run-/Commit-Bindung, Manifeste, SBOM-/Scan-Identität und Archiv-Digests und startet sie in einem nur für diesen Lauf erzeugten Docker-Netzwerk.
Neo4j erhält fünf deterministische Testknoten einschließlich tatsächlicher
Beziehungen. Geprüft werden HTTP-Health, Fähigkeiten, Integrations-/Entity-Auswirkung,
unbekannte Routen, parametrisierte Eingaben, eine echte kanonische Enrichment-
Schreiboperation sowie Datenbankausfall und anschließende Wiederherstellung.

Der Testbestand liegt nur im kurzlebigen Container. Es werden keine bestehenden
Datenbank-Volumes eingebunden oder reale Systeme gestoppt. Gemessene Ausfall-
antworten und Wiederanlauf sind technische CI-Nachweise, keine Produktions-SLOs.

## Lieferkette und Nachweisgrenzen

Alle fünf Images werden gebaut; Neo4j erhält eine eigene Patch-Schicht auf
dem gepinnten Drittanbieter-Image. `quality/runtime-images.json` bindet die Basisimages per Digest.
Jedes Image erhält eine echte CycloneDX-SBOM, Trivy-JSON und ein Docker-Archiv.
Die Integration verwendet beide heruntergeladenen Archive, keine zweite
unabhängige Neuauflösung der Abhängigkeiten. Python-Abhängigkeiten sind für jeden
Service sowie als gemeinsames Anwendungs- und CI-/Tool-Profil exakt gelockt. Jeder
Eintrag enthält SHA-256-Hashes; Docker und CI installieren mit
`pip --require-hashes`. `cyclonedx-py` erzeugt zusätzlich je eine reproduzierbare
CycloneDX-SBOM für Anwendung und CI/Tools. `pip-audit` prüft das Anwendungsprofil.
Locks, Inputs, ihre Hashes und Werkzeugausführungen werden im Source-Evidence-
Bundle gespeichert und nach dem Download erneut geprüft.

Direkte Anforderungen stehen in den `requirements.txt`- und `.in`-Dateien. Die
ausführbaren Stände stehen ausschließlich in den `requirements.lock`-Dateien.
Tool-Versionen stehen in `quality/tool-requirements.txt`; der vollständige
installierbare Stand steht in `quality/ci-requirements.lock`. Roh-
berichte, Exit-Codes, Laufzeiten und Befehle bleiben erhalten. Der Sammler trennt
Scanner-Findings (Exit 1 bei gültigem Report) von Werkzeugfehlern. Jedes Bundle
bindet Repository, Commit, Run und Versuch sowie SHA-256 aller enthaltenen Dateien.
Der Aggregator prüft nach dem Download erneut alle Bytes. Diese selbst erzeugten
Manifeste sind Integritätsnachweise und keine unabhängige Signatur/Attestation.

Image-Artefakte bleiben 7 Tage verfügbar, übrige Rohdaten 14 Tage und der Bericht
30 Tage. Eine dauerhafte Release-Archivierung ist damit noch nicht eingerichtet.
GitHub-API-Antworten enthalten keine Authentisierungstoken. Fehlende Rechte werden
sichtbar dokumentiert; PR-Code erhält keinen zusätzlichen privilegierten Token.

## Lokal

Python 3.12, Docker und die gelockten Werkzeuge verwenden. Ohne Docker können die
Unit- und Report-Negativtests ausgeführt werden:

```sh
python -m pip install --require-hashes -r quality/ci-requirements.lock
python -m pytest tests quality_tests --ignore=quality_tests/test_runtime.py -q
```

Nach einer bewussten Änderung einer direkten Anforderung werden alle Locks mit
dem festgelegten Resolver neu erzeugt und anschließend gemeinsam geprüft:

```sh
python -m pip install uv==0.8.22
./scripts/update_dependency_locks.sh
```

Ein Lock-Update ist eine überprüfbare Lieferkettenänderung und wird zusammen mit
den neuen SBOM-/Audit-Ergebnissen als Pull Request behandelt.

Die Integrationsprüfung benötigt ausdrücklich `L1_RUNTIME_TESTS=1`, eine
Commit-/Run-Identität und beide aus den Image-Jobs erzeugten Query-/Neo4j-Archive. Ein Skip
ersetzt keinen erfolgreichen Integrationstest im Bericht.

## Artefaktklassifikation und Release-Auswirkung

Consumer-seitige Tests, CI-Werkzeuge, Pipeline-Evidenz und Dokumentation; keine
neuen Governance-Quellen oder abgeleiteten Kontrollen. Keine Änderung des
veröffentlichten L1-Pakets, seiner OPA-Regeln, seiner Tags oder des akzeptierten
Consumer-Lifecycle-Vertrags. Die zentralen Statusindizes erhalten diese
Abdeckungsanalyse nicht als offiziellen Compliance-PASS.

## Separates Staging als nächstes Ziel

Der Maintainer hat separates Staging ausgewählt. Die
[vorbereitete Konfiguration](../../deployment/staging/README.md) begrenzt den
ersten Umfang auf Query API und Neo4j. Zielhost, konkrete Artefaktfreigabe und
Deployment-Nachweise stehen noch aus; L1-013/014/016 werden nicht vorab geschlossen.

## Behandlung der Container-Schwachstellen

Die [Patch- und Befundbewertung](CONTAINER_SECURITY_REMEDIATION.md) dokumentiert
die Debian-Korrekturen, Messläufe und noch offene Risiken. Rohbefunde werden
nicht unterdrückt; eine technische Bewertung ist keine Deployment-Freigabe.

## Central Typed Evidence Trust

A successful main push run now emits `typed-evidence-manifest.json` inside
`l1-control-coverage`. It declares the exact five image artifacts, image IDs,
archive digests and source run context. It is omitted for incomplete evidence.
Profile `ha-cpswms-container-evidence-v2` additionally declares the SHA-256 and
measured CycloneDX component count for every SBOM.

`Notify Typed Evidence Intake` runs only after that producer workflow completes
successfully on a main push. It sends `typed-evidence-trust-ready` to the central
governance repository using the existing `GH_RESULT_INTAKE_TOKEN`. It executes
no code from the triggering run. PR and manual runs do not trigger this intake.

The central collector downloads all five full image artifacts, checks archive
hashes, Docker config/layer identities, scanner output, CycloneDX SBOM bytes and
run context, then writes separate `vulnerability_scan` and `sbom` Trust records
and opens an operational intake PR. The central viewer updates after that PR merges.
Trust is report-only and does not grant release approval, accept vulnerabilities
or claim an independent scanner attestation. Collection failures are visible in
the notification/central intake workflow and must not be reported as successful
intake. A dispatch failure remains separate from the completed producer tests so
that an invalid token cannot turn valid test evidence into a failed assessment.
