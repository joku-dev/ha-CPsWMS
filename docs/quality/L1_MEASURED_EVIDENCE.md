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
Integritätsfehler lassen den neuen Prüflauf fehlschlagen. Es wird kein neuer
Required Check eingerichtet und der bisherige Blocking-Modus wird nicht geändert.

## Kontrollzuordnung

| L1-REQ | Echte Prüfung / Werkzeug | Verbleibende Grenze |
|---|---|---|
| 001 | Technische Anforderungen → ausgeführte pytest-Testfälle → JUnit | Vollständige freigegebene Systemanforderungen fehlen |
| 002 | GitHub Commit-, PR- und Review-API | Keine fingierte unabhängige Review-Freigabe |
| 003 | GitHub Branch-Protection und Rules-API | 403 bleibt Lücke; Bypass-/Direktpush-Regeln bewerten |
| 004 | Bandit, Ruff, Chat-Negativtests | Findings müssen bewertet werden |
| 005 | Trivy-Paketinventar aller fünf Laufzeitimages | Build-/Entwicklungswerkzeuge sind separater Scope |
| 006 | CycloneDX-SBOM je tatsächlich archiviertem Image | Keine handgeschriebene Komponentenliste |
| 007 | Docker-Build-Protokolle, gepinnte Basisimages | Aufgelöste Python-Versionen erfasst; Lockfiles/reproduzierbarer Neubau offen |
| 008 | Image-ID, Commit, Archiv-SHA-256 | Identifiziert tatsächlichen Build |
| 009 | Trivy-CVE-Scan derselben Image-IDs | Toolfehler sind keine leeren Scans |
| 010 | CVE-Rohbefunde und Schweregrade | Release-Risikobewertung bleibt offen |
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
unabhängige Neuauflösung der Abhängigkeiten. Python-Abhängigkeiten sind noch
nicht gelockt; die SBOM dokumentiert die im jeweiligen Build installierten Versionen.

Tool-Versionen stehen in `quality/tool-requirements.txt` und im Workflow. Roh-
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

Python 3.12, Docker und die im Workflow gepinnten Werkzeuge verwenden. Ohne
Docker können die Unit- und Report-Negativtests ausgeführt werden:

```sh
python -m pip install -r quality/tool-requirements.txt -r ha-sync/requirements.txt \
  -r query-api/requirements.txt -r semantic-enrichment/requirements.txt \
  -r world-model-chat/requirements.txt
python -m pytest tests quality_tests --ignore=quality_tests/test_runtime.py -q
```

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
