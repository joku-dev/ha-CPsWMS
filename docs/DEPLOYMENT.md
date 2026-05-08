# Deployment-Checkliste

Diese Checkliste hilft beim sicheren Aufbau und Betrieb des Home Assistant → Neo4j Sync-Projekts.

## 1. Lokale Vorbereitung

- [ ] Klone das Repository in dein Zielverzeichnis.
- [ ] Stelle sicher, dass Docker und Docker Compose installiert sind.
- [ ] Lege eine Datei `.env` im Projektstamm an, um sensible Werte nicht ins Repo zu schreiben.

Kopiere dazu `.env.example` und fülle die Werte aus:

```bash
cp .env.example .env
```

Beispiel `.env`:

```ini
HA_URL=http://homeassistant.local:8123
HA_TOKEN=DEIN_HOME_ASSISTANT_TOKEN
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=ChangeMe123!
NEO4J_AUTH=neo4j/ChangeMe123!
SYNC_INTERVAL_SECONDS=300
```

## 2. Konfiguration prüfen

- [ ] Öffne `docker-compose.yml` und prüfe, ob die Umgebungsvariablen korrekt referenziert werden.
- [ ] Stelle sicher, dass `neo4j/data` und `neo4j/logs` in `.gitignore` stehen.
- [ ] Verifiziere, dass `ha-sync/requirements.txt` die benötigten Pakete enthält.

## 3. Erststart

Führe im Projektstamm aus:

```bash
docker compose up -d --build
```

- [ ] Prüfe, ob der `neo4j`-Container startet.
- [ ] Prüfe, ob der `ha-sync`-Container startet.

## 4. Betrieb & Kontrolle

- [ ] Überwache die Logs des Sync-Containers:

```bash
docker compose logs -f ha-sync
```

- [ ] Öffne den Neo4j Browser unter `http://localhost:7474`.
- [ ] Prüfe, ob die Datenbank erreichbar ist und die Knoten geladen werden.

## 5. Fehlerbehebung

- Bei Verbindungsproblemen mit Home Assistant:
  - `HA_URL` prüfen
  - `HA_TOKEN` prüfen
  - Home Assistant API erreichbar?

- Bei Neo4j-Problemen:
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` prüfen
  - Neo4j-Logs unter `neo4j/logs` prüfen

## 6. Sicherer Betrieb

- [ ] Speichere keine echten Zugangsdaten im Git-Repository.
- [ ] Nutze `.env` für Secrets und achte darauf, dass diese Datei ignoriert wird.
- [ ] Dokumentiere Änderungen an `docker-compose.yml` und `ha-sync/sync.py` im Repository.
