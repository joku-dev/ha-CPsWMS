# Temporal Event Model: Neo4j-Checks

Diese Queries helfen beim Live-Check des Enrichers `temporal_event_model`.

## 1. Grundzaehlung der neuen Relationen

```cypher
MATCH (:Entity)-[r:HAS_OBSERVATION]->(:Observation)
RETURN count(r) AS has_observation_links;
```

```cypher
MATCH (:Entity)-[r:HAS_TIMELINE_EVENT]->(:TimelineEvent)
RETURN count(r) AS has_timeline_event_links;
```

```cypher
MATCH (:Entity)-[r:HAS_STATE_TRANSITION]->(:StateTransition)
RETURN count(r) AS has_state_transition_links;
```

```cypher
MATCH (:Entity)-[r:HAS_INCIDENT]->(:Incident)
RETURN count(r) AS has_incident_links;
```

## 2. Letzte Timeline-Events

```cypher
MATCH (e:Entity)-[:HAS_TIMELINE_EVENT]->(te:TimelineEvent)
RETURN e.entity_id AS entity_id,
       te.event_type AS event_type,
       te.summary AS summary,
       te.event_time AS event_time,
       te.created_at AS created_at
ORDER BY te.created_at DESC
LIMIT 50;
```

## 3. Incidents mit hoher Prioritaet

```cypher
MATCH (e:Entity)-[:HAS_INCIDENT]->(i:Incident)
WHERE i.severity IN ["high", "critical"]
RETURN e.entity_id AS entity_id,
       i.incident_type AS incident_type,
       i.severity AS severity,
       i.reason AS reason,
       i.opened_at AS opened_at
ORDER BY i.opened_at DESC
LIMIT 50;
```

## 4. State-Transitions pro Entity (Beispiel)

Setze oben eine konkrete `entity_id`.

```cypher
WITH "light.kitchen" AS target_entity_id
MATCH (e:Entity {entity_id: target_entity_id})-[:HAS_STATE_TRANSITION]->(st:StateTransition)
RETURN e.entity_id AS entity_id,
       st.from_state AS from_state,
       st.to_state AS to_state,
       st.transition_at AS transition_at,
       st.created_at AS created_at
ORDER BY coalesce(st.transition_at, st.created_at) DESC
LIMIT 100;
```

## 5. Vollstaendiger Zeitkontext je Entity

```cypher
MATCH (e:Entity)-[:HAS_TIMELINE_EVENT]->(te:TimelineEvent)
OPTIONAL MATCH (te)-[:HAS_OBSERVATION]->(obs:Observation)
OPTIONAL MATCH (te)-[:DESCRIBES_TRANSITION]->(st:StateTransition)
OPTIONAL MATCH (te)-[:INDICATES_INCIDENT]->(inc:Incident)
RETURN e.entity_id AS entity_id,
       te.event_type AS event_type,
       te.summary AS summary,
       te.event_time AS event_time,
       obs.text AS observation_text,
       st.from_state AS from_state,
       st.to_state AS to_state,
       inc.incident_type AS incident_type,
       inc.severity AS incident_severity
ORDER BY te.created_at DESC
LIMIT 100;
```
