"""Temporal event modeling for entity behavior over time."""

from enrichers.base import BaseEnricher


class TemporalEventModelEnricher(BaseEnricher):
    """Map time-based observations, transitions, timeline events and incidents."""

    name = "temporal_event_model"
    prompt_file = "temporal_event_model.md"
    schema_file = "temporal_event_model_schema.json"
    response_key = "temporal_events"

    def create_constraints(self):
        """Ensure temporal model nodes use stable unique identifiers."""
        with self.driver.session() as session:
            session.run(
                """
                CREATE CONSTRAINT observation_id_unique IF NOT EXISTS
                FOR (o:Observation)
                REQUIRE o.observation_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT state_transition_id_unique IF NOT EXISTS
                FOR (s:StateTransition)
                REQUIRE s.transition_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT timeline_event_id_unique IF NOT EXISTS
                FOR (t:TimelineEvent)
                REQUIRE t.timeline_event_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
                FOR (i:Incident)
                REQUIRE i.incident_id IS UNIQUE
                """
            )

    def get_candidates(self, limit):
        """Fetch entities that have not yet been transformed into temporal model nodes."""
        query = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[:HAS_RAW_REPRESENTATION]->(raw:RawEntity)
        OPTIONAL MATCH (raw)-[:RESOLVED_TO]->(c:CanonicalEntity)

        WHERE coalesce(e.temporal_event_modeled, false) = false

        OPTIONAL MATCH (ev:HomeAssistantEvent)-[:AFFECTED_ENTITY]->(e)
        WITH e, ev
        ORDER BY ev.when DESC
        WITH e, collect(DISTINCT {
            when: toString(ev.when),
            name: ev.name,
            message: ev.message
        })[0..10] AS recent_events

        OPTIONAL MATCH (a1:Automation)-[:TRIGGERED_BY]->(e)
        OPTIONAL MATCH (a2:Automation)-[:CONTROLS]->(e)

        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            toString(e.last_changed) AS last_changed,
            toString(e.last_updated) AS last_updated,
            e.is_problem AS is_problem,
            recent_events AS recent_events,
            collect(DISTINCT a1.name) AS triggered_automations,
            collect(DISTINCT a2.name) AS controlled_by_automations,
        
            raw.raw_entity_id AS raw_entity_id,
            raw.source_entity_id AS source_entity_id,
            c.canonical_id AS canonical_id
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep only in-batch entity ids with valid confidence."""
        allowed_ids = {item["entity_id"] for item in input_items}
        return [
            item
            for item in llm_items
            if item.get("entity_id") in allowed_ids and self.validate_confidence(item)
        ]

    def write_results(self, items):
        """Persist Observation, StateTransition, TimelineEvent and Incident nodes."""
        canonical_body = """
        CREATE (obs:Observation {
            observation_id: randomUUID(),
            text: $observation_text,
            observed_at: CASE
                WHEN $observed_at IS NULL OR $observed_at = "" THEN NULL
                ELSE datetime($observed_at)
            END,
            source: "openai",
            created_at: datetime()
        })
        MERGE (c)-[:HAS_OBSERVATION]->(obs)

        CREATE (te:TimelineEvent {
            timeline_event_id: randomUUID(),
            event_type: $timeline_event_type,
            summary: $timeline_summary,
            event_time: CASE
                WHEN $timeline_at IS NULL OR $timeline_at = "" THEN NULL
                ELSE datetime($timeline_at)
            END,
            source: "openai",
            created_at: datetime()
        })
        MERGE (c)-[:HAS_TIMELINE_EVENT]->(te)
        MERGE (te)-[:HAS_OBSERVATION]->(obs)

        FOREACH (_ IN CASE
            WHEN $transition_from IS NOT NULL OR $transition_to IS NOT NULL THEN [1]
            ELSE []
        END |
            CREATE (st:StateTransition {
                transition_id: randomUUID(),
                from_state: $transition_from,
                to_state: $transition_to,
                transition_at: CASE
                    WHEN $transition_at IS NULL OR $transition_at = "" THEN NULL
                    ELSE datetime($transition_at)
                END,
                source: "openai",
                created_at: datetime()
            })
            MERGE (c)-[:HAS_STATE_TRANSITION]->(st)
            MERGE (te)-[:DESCRIBES_TRANSITION]->(st)
        )

        FOREACH (_ IN CASE
            WHEN $incident_type IS NOT NULL
             AND $incident_type <> "none"
             AND $incident_type <> "unknown"
            THEN [1]
            ELSE []
        END |
            CREATE (inc:Incident {
                incident_id: randomUUID(),
                incident_type: $incident_type,
                severity: $incident_severity,
                reason: $reason,
                opened_at: CASE
                    WHEN $timeline_at IS NULL OR $timeline_at = "" THEN datetime()
                    ELSE datetime($timeline_at)
                END,
                source: "openai",
                created_at: datetime()
            })
            MERGE (c)-[:HAS_INCIDENT]->(inc)
            MERGE (te)-[:INDICATES_INCIDENT]->(inc)
        )

        SET e.temporal_event_modeled = true,
            e.temporal_event_modeled_at = datetime()
        """

        entity_body = """
        CREATE (obs:Observation {
            observation_id: randomUUID(),
            text: $observation_text,
            observed_at: CASE
                WHEN $observed_at IS NULL OR $observed_at = "" THEN NULL
                ELSE datetime($observed_at)
            END,
            source: "openai",
            created_at: datetime()
        })
        MERGE (e)-[:HAS_OBSERVATION]->(obs)

        CREATE (te:TimelineEvent {
            timeline_event_id: randomUUID(),
            event_type: $timeline_event_type,
            summary: $timeline_summary,
            event_time: CASE
                WHEN $timeline_at IS NULL OR $timeline_at = "" THEN NULL
                ELSE datetime($timeline_at)
            END,
            source: "openai",
            created_at: datetime()
        })
        MERGE (e)-[:HAS_TIMELINE_EVENT]->(te)
        MERGE (te)-[:HAS_OBSERVATION]->(obs)

        FOREACH (_ IN CASE
            WHEN $transition_from IS NOT NULL OR $transition_to IS NOT NULL THEN [1]
            ELSE []
        END |
            CREATE (st:StateTransition {
                transition_id: randomUUID(),
                from_state: $transition_from,
                to_state: $transition_to,
                transition_at: CASE
                    WHEN $transition_at IS NULL OR $transition_at = "" THEN NULL
                    ELSE datetime($transition_at)
                END,
                source: "openai",
                created_at: datetime()
            })
            MERGE (e)-[:HAS_STATE_TRANSITION]->(st)
            MERGE (te)-[:DESCRIBES_TRANSITION]->(st)
        )

        FOREACH (_ IN CASE
            WHEN $incident_type IS NOT NULL
             AND $incident_type <> "none"
             AND $incident_type <> "unknown"
            THEN [1]
            ELSE []
        END |
            CREATE (inc:Incident {
                incident_id: randomUUID(),
                incident_type: $incident_type,
                severity: $incident_severity,
                reason: $reason,
                opened_at: CASE
                    WHEN $timeline_at IS NULL OR $timeline_at = "" THEN datetime()
                    ELSE datetime($timeline_at)
                END,
                source: "openai",
                created_at: datetime()
            })
            MERGE (e)-[:HAS_INCIDENT]->(inc)
            MERGE (te)-[:INDICATES_INCIDENT]->(inc)
        )

        SET e.temporal_event_modeled = true,
            e.temporal_event_modeled_at = datetime()
        """

        for item in items:
            self.execute_targeted_write(canonical_body, entity_body, item)
