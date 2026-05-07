# Home Assistant to Neo4j Sync

Dieses Projekt enthält eine Docker-Compose-Konfiguration für Neo4j und einen Python-Sync-Container, der Home Assistant-States nach Neo4j schreibt.

## Inhalt

- `docker-compose.yml` - Startet Neo4j und den `ha-sync`-Container
- `ha-sync/Dockerfile` - Build-Definition für den Sync-Container
- `ha-sync/requirements.txt` - Python-Abhängigkeiten
- `ha-sync/sync.py` - Sync-Skript
- `neo4j/` - Neo4j-Daten- und Log-Verzeichnis (diese Ordner werden nicht ins Git übernommen)

## Vorbereitung für Git

- `neo4j/data/` und `neo4j/logs/` sind in `.gitignore` enthalten, damit lokale Daten und Logs nicht ins Repository gelangen.
- `.env`-Dateien sind ebenfalls ignoriert.

## Setup

1. `.gitignore` prüfen und sicherstellen, dass lokale Datenverzeichnisse nicht versioniert werden.
2. `docker-compose.yml` anpassen:
   - Setze `HA_TOKEN` auf das tatsächliche Home Assistant Long-Lived Access Token
   - Passe `HA_URL` an deine Home Assistant-URL an
   - Passe bei Bedarf `NEO4J_AUTH` an

3. Starte das Projekt:

```bash
docker compose up -d --build
```

## Hinweise

- Verwende niemals echte Passwörter oder Tokens im Repository.
- Für sensible Werte kannst du stattdessen eine lokale `.env`-Datei anlegen und in `docker-compose.yml` auf diese Werte verweisen.
- Der Neo4j-Datenordner bleibt lokal und wird nicht committet.
