# Separate Staging-Umgebung

Vom Maintainer am 16. September 2026 ausgewählt. Vorgesehener erster Umfang:
`query-api` und Neo4j, getrennt von Produktion, Home Assistant und LLM-Diensten.
Der vorbereitete Zielhost ist die Proxmox-VM `ha-cpswms-stg-01`
(`192.168.200.197`). Der erste reale Staging-Lauf wurde am **18. September 2026** erfolgreich
ausgeführt. Der deployte Softwarestand ist Commit
`5d5772d989b0080ae041969315742c8fbbca6dfe` aus dem L1-Lauf
`35351493542`. Beide Container sind aktiv und healthy; 19 von 19 Start-,
Funktions-, Persistenz-, Wiederanlauf- und Laufzeithärtungsprüfungen wurden
bestanden.

## Bereitstellungsprofil für die neue VM

Die Staging-VM besitzt **6 vCPU, 11 GiB RAM und 85 GiB virtuelle Disk**. Das
Ubuntu-Root-Dateisystem nutzt davon 82,5 GiB. Docker Engine 29.8.1 und Compose
5.5.1 sind aktiv; QEMU Guest Agent, Zeitsynchronisierung, automatische
Sicherheitsupdates und der Headless-Start über `multi-user.target` sind
eingerichtet. Das ist ein Profil für Testdaten, keine Kapazitätszusage für
produktive Graphen oder Last.

Eingehend wird nur SSH aus `192.168.1.0/24` benötigt; UFW ist auf dem Zielhost
aktiviert. HTTP wird zunächst
über einen SSH-Tunnel genutzt (`localhost:18080`); Datenbank und API werden nicht
öffentlich freigegeben. Backup-/Log-Aufbewahrung und Betreiberverantwortung
werden mit dem ersten Deployment-Nachweis festgelegt.

## Anforderungen an den Zielhost

- Dedizierter Linux-Host/VM mit Docker Engine und Compose v2, Python >= 3.11.
- SSH-Zugang mit einem eigenen Deployment-Konto; Docker-Zugriff besitzt weitgehende
  Host-Rechte und gehört daher auf die dedizierte Staging-Umgebung.
- Ausreichend Platz für zwei verifizierte Image-Archive und persistente Neo4j-Daten.
- Keine bestehenden produktiven Neo4j-Volumes oder Home-Assistant-Zugangsdaten.

Die API bindet nur `127.0.0.1:18080`. Zugriff erfolgt zunächst über SSH-Tunnel.
Neo4j hat keinen veröffentlichten Host-Port. Das Backend-Netzwerk ist intern;
die Query API hängt zusätzlich an einem separaten Bridge-Netz, damit Docker die
Loopback-Portbindung tatsächlich herstellen kann. Ohne dieses zweite Netz ist
eine Host-Portbindung bei `internal: true` nicht erreichbar;
Graphdaten und Datenbanklogs erhalten eigene Compose-Volumes. Das Projekt muss
stets `ha-cpswms-staging` heißen. Der Ablauf darf keine anderen Container stoppen.

Die Query API läuft zusätzlich mit einer numerischen Nicht-Root-Identität, einem
Read-only-Root-Dateisystem, ohne Linux-Capabilities und mit
`no-new-privileges`. Neo4j und Query API besitzen PID-Grenzen; auch Neo4j erhält
`no-new-privileges`. `docker compose up --wait` wartet auf einen echten
Query-API-Healthcheck, der zugleich die Verbindung zur Datenbank prüft. Diese
Laufzeitgrenzen reduzieren die Ausnutzbarkeit verbleibender Paketbefunde, ersetzen
aber weder deren Bewertung noch eine dokumentierte Staging-Freigabe.

## Vor einem Deployment

1. Einen erfolgreichen **push/main**-Lauf von `L1 Measured Evidence` auswählen.
2. `l1-image-query-api`, `l1-image-neo4j` und `l1-control-coverage` aus genau diesem
   Run und Versuch herunterladen; Run-ID und Commit gegen GitHub prüfen.
3. Beide Bundle-Manifeste und Archiv-Hashes prüfen. SBOM und Scan müssen zum
   Build-Config-Digest gehören; derselbe Digest und der deklarierte Transport-Tag
   müssen im Image-Archiv enthalten sein. Der Abdeckungsbericht muss ohne
   Evidenzfehler vorliegen.
4. Aktuelle Security-Findings bewerten. Der erste Messlauf enthält auch hohe und
   kritische CVE-Einträge; erfolgreicher Build/Scan ist keine Risikofreigabe.
5. Ein konkretes Freigabeprotokoll mit Ziel `staging`, beiden Image-IDs,
   Commit, Run, Entscheider, Zeitpunkt und verlinkter Befundbewertung erstellen.
   Die Auswahl von Staging im Gespräch ersetzt diese Artefaktfreigabe nicht.

## Geplanter Deployment-Ablauf

- Image-Archive auf dem benannten Host nachprüfen und mit `docker load` laden.
- Den im Nachweis deklarierten `archive_tag` nach dem Laden auflösen und die
  tatsächliche Zielhost-Laufzeit-ID protokollieren. Docker-Engines mit klassischem
  und containerd-basiertem Image-Speicher können dasselbe Archiv unter
  unterschiedlichen lokalen Laufzeit-IDs führen; der verifizierte
  Build-Config-Digest im Archiv bleibt die Bindung für SBOM und Scan.
- Ein zufälliges Neo4j-Passwort nur auf dem Zielhost in einer Datei mit Modus 0600
  erzeugen; keine Passwörter in Git, Workflow-Artefakten oder Logs speichern.
- Eine lokale Env-Datei mit `NEO4J_IMAGE`, `QUERY_IMAGE`, `NEO4J_PASSWORD` und
  `SOURCE_COMMIT` anlegen. Die Image-Werte sind die auf diesem Zielhost nach dem
  verifizierten Import beobachteten, exakten `sha256:...`-Laufzeit-IDs.
- Mit `docker compose --project-name ha-cpswms-staging --env-file <lokale Datei>
  -f deployment/staging/compose.yml up -d --wait` starten.
- `/health` über Loopback prüfen. Tatsächliche Container-Image-IDs,
  Deployment-Zeit, Freigabereferenz und Health-Ergebnis protokollieren.
- Betriebs- und Security-Ereignisse auf dem Zielhost sammeln; die konkreten
  Aufbewahrungs-/Zugriffsregeln hängen vom noch zu benennenden Host ab.

Rollback bedeutet Rückkehr zu einem zuvor freigegebenen Image-Paar; ein
Datenbank-Downgrade ist ohne gesonderte Kompatibilitäts-/Backup-Prüfung nicht
freigegeben. Volumes dürfen beim normalen Update oder Stoppen nicht gelöscht
werden. Es gibt hier absichtlich noch keine automatische Fern-Ausführung gegen
unbekannte Hosts oder eine erfundene Freigabe.

## L1-Zuordnung

- 013: benannte, überprüfbare Freigabe eines konkreten Staging-Deployments.
- 014: exakte freigegebene Image-IDs, `pull_policy: never`, Prüfung vor dem Start.
- 016: tatsächlich beobachtete Deployment-IDs, Betriebs- und Security-Ereignisse.

Die Compose-Datei allein erfüllt diese Kontrollen nicht. Erst der reale Lauf mit
seinen Nachweisen kann die offenen Kontrollbestandteile schließen.


## Ausgeführter Staging-Lauf vom 18. September 2026

Der versionierte Nachweis liegt unter
`deployment/staging/evidence/2026-09-18T16-05-03Z-run-35351493542/`.
Er enthält Freigabe, Deployment-Receipt, Prüfliste, HTTP-Antworten, Containerlogs
und relative SHA-256-Prüfsummen. Das Receipt bindet den Lauf an die exakten
Runtime-Image-IDs, den Source-Commit, den CI-Lauf und den Zielhost.

Geprüft wurden:

- beide Container-Healthchecks und die Neo4j-Verbindung,
- die fachlichen Endpunkte `capabilities`, `simulation-readiness` und eine
  What-if-Abfrage,
- Persistenz über einen Neo4j-Neustart mit anschließend gelöschtem Prüfdatensatz,
- Erkennung eines kontrollierten Datenbankausfalls und Wiederherstellung,
- Neustart und erneuter Healthcheck der Query API,
- exakte Runtime-Image-IDs, Non-root-/Read-only-/Capability-Grenzen,
- ausschließliche Loopback-Bindung der API und fehlende Neo4j-Portfreigabe.

Der Ausfall wird korrekt erkannt, `/health` antwortet dabei aktuell mit HTTP 500
statt 503. Das ist als `STG-OBS-001` dokumentiert und verhindert den
Staging-Betrieb nicht. Die vorhandenen Schwachstellen bleiben report-only und
sind durch diese Deployment-Freigabe nicht behoben oder allgemein akzeptiert.

Zugriff vom Admin-Rechner:

```bash
ssh -L 18080:127.0.0.1:18080 deploy@192.168.200.197
curl http://127.0.0.1:18080/health
```

Die Freigabe gilt ausschließlich für diese Staging-Umgebung und den im Receipt
genannten Softwarestand.
