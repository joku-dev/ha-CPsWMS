# FAQ

## Warum wird meine Verbindung zu Home Assistant abgelehnt?

- Prüfe, ob `HA_URL` korrekt ist und auf die Home Assistant-Instanz zeigt.
- Vergewissere dich, dass `HA_TOKEN` ein gültiger Long-Lived Access Token ist.
- Prüfe, ob die Home Assistant-API unter `http://<host>:8123/api/states` erreichbar ist.

## Warum startet der `ha-sync`-Container nicht?

- Schaue die Container-Logs mit:
  ```bash
docker compose logs -f ha-sync
```
- Stelle sicher, dass `HA_URL`, `HA_TOKEN`, `NEO4J_URI`, `NEO4J_USER` und `NEO4J_PASSWORD` gesetzt sind.
- Prüfe, ob der Neo4j-Container läuft und erreichbar ist.

## Warum kann die Anwendung keine Verbindung zu Neo4j herstellen?

- Der Neo4j-Service muss vor dem Sync bereit sein. Der Container wartet beim Start auf eine Verbindung.
- Stelle sicher, dass `NEO4J_URI` korrekt ist, z. B. `bolt://neo4j:7687` für Docker Compose.
- Überprüfe die Neo4j-Logs unter `neo4j/logs` oder mit:
  ```bash
docker compose logs -f neo4j
```

## Welche Dateien sollten nicht ins Git?

- `neo4j/data/` und `neo4j/logs/` enthalten lokale Daten und Logs und sollten nicht versioniert werden.
- `.env`-Dateien mit Secrets sollten ebenfalls ignoriert werden.

## Wie ändere ich das Sync-Intervall?

- Setze die Umgebungsvariable `SYNC_INTERVAL_SECONDS` in `.env` oder `docker-compose.yml`.
- Beispiel:
  ```ini
SYNC_INTERVAL_SECONDS=300
```

## Wie teste ich, ob die Sync-Daten in Neo4j angekommen sind?

- Öffne den Neo4j-Browser unter `http://localhost:7474`.
- Führe z. B. folgende Abfrage aus:
  ```cypher
MATCH (e:Entity) RETURN e LIMIT 25;
```

## Was macht `create_constraints()`?

- Es legt eindeutige Regeln für `Entity`, `Room`, `DeviceClass` und `Unit` in Neo4j an.
- Dadurch werden doppelte Knoten verhindert, wenn der Sync mehrmals läuft.
