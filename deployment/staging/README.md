# Separate Staging-Umgebung

Vom Maintainer am 16. September 2026 ausgewählt. Vorgesehener erster Umfang:
`query-api` und Neo4j, getrennt von Produktion, Home Assistant und LLM-Diensten.
Der Zielhost ist noch nicht benannt; diese Konfiguration ist **nicht deployt**.

## Bereitstellungsprofil für die neue VM

Ein geeigneter Host ist aktuell nicht vorhanden. Planungswert für diese kleine
Staging-Instanz: **4 vCPU, 8 GiB RAM, 60 GiB SSD**, Linux mit Sicherheitsupdates,
Docker Engine und Compose. Das ist ein Startprofil für Testdaten, keine
Kapazitätszusage für produktive Graphen oder Last.

Eingehend wird nur SSH aus dem administrativen Netz benötigt. HTTP wird zunächst
über einen SSH-Tunnel genutzt (`localhost:18080`); Datenbank und API werden nicht
öffentlich freigegeben. Eigener Hostname, Betreiber, Backup-/Log-Aufbewahrung
und Betriebsort sind vor Bereitstellung festzulegen. Bei Cloud-Betrieb kommt ein
freigegebener Kostenrahmen hinzu. Es wurde noch keine Infrastruktur bestellt.

## Anforderungen an den Zielhost

- Dedizierter Linux-Host/VM mit Docker Engine und Compose v2, Python >= 3.11.
- SSH-Zugang mit einem eigenen Deployment-Konto; Docker-Zugriff besitzt weitgehende
  Host-Rechte und gehört daher auf die dedizierte Staging-Umgebung.
- Ausreichend Platz für zwei verifizierte Image-Archive und persistente Neo4j-Daten.
- Keine bestehenden produktiven Neo4j-Volumes oder Home-Assistant-Zugangsdaten.

Die API bindet nur `127.0.0.1:18080`. Zugriff erfolgt zunächst über SSH-Tunnel.
Neo4j hat keinen veröffentlichten Host-Port. Das Docker-Netzwerk ist intern;
Graphdaten und Datenbanklogs erhalten eigene Compose-Volumes. Das Projekt muss
stets `ha-cpswms-staging` heißen. Der Ablauf darf keine anderen Container stoppen.

## Vor einem Deployment

1. Einen erfolgreichen **push/main**-Lauf von `L1 Measured Evidence` auswählen.
2. `l1-image-query-api`, `l1-image-neo4j` und `l1-control-coverage` aus genau diesem
   Run und Versuch herunterladen; Run-ID und Commit gegen GitHub prüfen.
3. Beide Bundle-Manifeste und Archiv-Hashes prüfen. SBOM und Scan müssen zur
   Image-ID gehören. Der Abdeckungsbericht muss ohne Evidenzfehler vorliegen.
4. Aktuelle Security-Findings bewerten. Der erste Messlauf enthält auch hohe und
   kritische CVE-Einträge; erfolgreicher Build/Scan ist keine Risikofreigabe.
5. Ein konkretes Freigabeprotokoll mit Ziel `staging`, beiden Image-IDs,
   Commit, Run, Entscheider, Zeitpunkt und verlinkter Befundbewertung erstellen.
   Die Auswahl von Staging im Gespräch ersetzt diese Artefaktfreigabe nicht.

## Geplanter Deployment-Ablauf

- Image-Archive auf dem benannten Host nachprüfen und mit `docker load` laden.
- Image-IDs unmittelbar nach dem Laden erneut mit den freigegebenen IDs vergleichen.
- Ein zufälliges Neo4j-Passwort nur auf dem Zielhost in einer Datei mit Modus 0600
  erzeugen; keine Passwörter in Git, Workflow-Artefakten oder Logs speichern.
- Eine lokale Env-Datei mit `NEO4J_IMAGE`, `QUERY_IMAGE`, `NEO4J_PASSWORD` und
  `SOURCE_COMMIT` anlegen. Die Image-Werte sind exakte `sha256:...`-IDs.
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
