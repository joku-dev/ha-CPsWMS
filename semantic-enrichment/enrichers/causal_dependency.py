"""Causal dependency enrichment using capabilities and temporal context."""

from enrichers.base import BaseEnricher


class CausalDependencyEnricher(BaseEnricher):
    """Infer causal chains between entities, automations, incidents and capabilities."""

    name = "causal_dependency"
    prompt_file = "causal_dependency.md"
    schema_file = "causal_dependency_schema.json"
    response_key = "causal_links"

    relationship_types = {
        "CAUSES",
        "DEPENDS_ON",
        "IMPACTS",
        "DEGRADES",
        "RECOVERS",
    }

    node_matchers = {
        "entity": "MATCH ({var}:Entity {{entity_id: ${param}}})",
        "automation": "MATCH ({var}:Automation {{automation_id: ${param}}})",
        "capability": "MERGE ({var}:Capability {{name: ${param}}})",
        "incident": "MATCH ({var}:Incident {{incident_id: ${param}}})",
    }

    def create_constraints(self):
        """Ensure capabilities can be referenced by stable names."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT capability_name_unique IF NOT EXISTS
            FOR (c:Capability)
            REQUIRE c.name IS UNIQUE
            """)

    def get_candidates(self, limit):
        """Fetch entities with both semantic capability and temporal evidence."""
        query = """
        MATCH (e:Entity)
        WHERE coalesce(e.causal_dependency_enriched, false) = false
        MATCH (e)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        MATCH (e)-[:HAS_SEMANTIC_CATEGORY]->(category:SemanticCategory)
        MATCH (e)-[:HAS_TIMELINE_EVENT]->(:TimelineEvent)

        MATCH (e)-[impact_rel:HAS_FAILURE_IMPACT]->(impact:FailureImpactLevel)
        WHERE impact_rel.affected_capability IS NOT NULL
        OPTIONAL MATCH (e)-[provides_rel:PROVIDES_CAPABILITY]->(provided_capability:Capability)
        OPTIONAL MATCH (e)-[:EFFECTIVE_LOCATION]->(area:Area)
        WITH
            e,
            role,
            category,
            area,
            impact,
            collect(DISTINCT impact_rel.affected_capability) + collect(DISTINCT provided_capability.name) AS raw_capabilities

        CALL {
            WITH e
            OPTIONAL MATCH (e)-[:HAS_TIMELINE_EVENT]->(te:TimelineEvent)
            RETURN collect(DISTINCT {
                event_type: te.event_type,
                summary: te.summary,
                event_time: toString(te.event_time)
            })[0..8] AS timeline_events
        }

        CALL {
            WITH e
            OPTIONAL MATCH (e)-[:HAS_INCIDENT]->(inc:Incident)
            RETURN collect(DISTINCT {
                incident_id: inc.incident_id,
                incident_type: inc.incident_type,
                severity: inc.severity,
                opened_at: toString(inc.opened_at),
                reason: inc.reason
            })[0..5] AS incidents
        }

        CALL {
            WITH e
            OPTIONAL MATCH (e)<-[:TRIGGERED_BY]-(a:Automation)
            OPTIONAL MATCH (a)-[:CONTROLS]->(target:Entity)
            OPTIONAL MATCH (target)-[:HAS_SEMANTIC_ROLE]->(target_role:SemanticRole)
            OPTIONAL MATCH (target)-[target_impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
            OPTIONAL MATCH (target)-[:PROVIDES_CAPABILITY]->(target_provided:Capability)
            RETURN collect(DISTINCT {
                automation_id: a.automation_id,
                name: a.name,
                relation: "triggered_by_entity",
                target_entity_id: target.entity_id,
                target_friendly_name: target.friendly_name,
                target_role: target_role.name,
                target_capability: coalesce(target_provided.name, target_impact.affected_capability)
            })[0..8] AS triggered_automations
        }

        CALL {
            WITH e
            OPTIONAL MATCH (e)<-[:CONTROLS]-(a:Automation)
            OPTIONAL MATCH (a)-[:TRIGGERED_BY]->(trigger:Entity)
            OPTIONAL MATCH (trigger)-[:HAS_SEMANTIC_ROLE]->(trigger_role:SemanticRole)
            OPTIONAL MATCH (trigger)-[trigger_impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
            OPTIONAL MATCH (trigger)-[:PROVIDES_CAPABILITY]->(trigger_provided:Capability)
            RETURN collect(DISTINCT {
                automation_id: a.automation_id,
                name: a.name,
                relation: "controls_entity",
                trigger_entity_id: trigger.entity_id,
                trigger_friendly_name: trigger.friendly_name,
                trigger_role: trigger_role.name,
                trigger_capability: coalesce(trigger_provided.name, trigger_impact.affected_capability)
            })[0..8] AS controlling_automations
        }

        CALL {
            WITH e
            OPTIONAL MATCH (e)-[:CAN_CAUSE]->(caused:Entity)
            OPTIONAL MATCH (caused)-[:HAS_SEMANTIC_ROLE]->(caused_role:SemanticRole)
            OPTIONAL MATCH (caused)-[caused_impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
            OPTIONAL MATCH (caused)-[:PROVIDES_CAPABILITY]->(caused_provided:Capability)
            RETURN collect(DISTINCT {
                entity_id: caused.entity_id,
                friendly_name: caused.friendly_name,
                semantic_role: caused_role.name,
                affected_capability: coalesce(caused_provided.name, caused_impact.affected_capability)
            })[0..8] AS can_cause_entities
        }

        RETURN
            e.entity_id AS entity_id,
            e.friendly_name AS friendly_name,
            e.domain AS domain,
            e.state AS state,
            e.is_problem AS is_problem,
            role.name AS semantic_role,
            category.name AS semantic_category,
            area.name AS area,
            impact.level AS failure_impact_level,
            [capability IN raw_capabilities WHERE capability IS NOT NULL] AS capabilities,
            timeline_events AS timeline_events,
            incidents AS incidents,
            triggered_automations AS triggered_automations,
            controlling_automations AS controlling_automations,
            can_cause_entities AS can_cause_entities
        LIMIT $limit
        """

        with self.driver.session() as session:
            return [dict(r) for r in session.run(query, limit=limit)]

    def validate_items(self, llm_items, input_items):
        """Keep causal links that only reference known in-batch context ids."""
        allowed_ids = self.allowed_node_ids(input_items)
        context_ids = {item["entity_id"] for item in input_items}
        valid = []

        for item in llm_items:
            relationship_type = item.get("relationship_type")
            source_type = item.get("source_type")
            target_type = item.get("target_type")

            if item.get("context_entity_id") not in context_ids:
                continue

            if relationship_type not in self.relationship_types:
                continue

            if source_type not in allowed_ids:
                continue

            if target_type not in allowed_ids:
                continue

            if item.get("source_id") not in allowed_ids[source_type]:
                continue

            if item.get("target_id") not in allowed_ids[target_type]:
                continue

            if item.get("source_id") == item.get("target_id") and source_type == target_type:
                continue

            if not self.validate_confidence(item):
                continue

            valid.append(item)

        return valid

    def allowed_node_ids(self, input_items):
        """Build a lookup of graph identifiers exposed to the LLM."""
        allowed = {
            "entity": set(),
            "automation": set(),
            "capability": set(),
            "incident": set(),
        }

        for item in input_items:
            allowed["entity"].add(item["entity_id"])

            for capability in item.get("capabilities", []):
                if capability:
                    allowed["capability"].add(capability)

            for incident in item.get("incidents", []):
                incident_id = incident.get("incident_id")
                if incident_id:
                    allowed["incident"].add(incident_id)

            for automation in item.get("triggered_automations", []):
                automation_id = automation.get("automation_id")
                target_id = automation.get("target_entity_id")
                target_capability = automation.get("target_capability")

                if automation_id:
                    allowed["automation"].add(automation_id)
                if target_id:
                    allowed["entity"].add(target_id)
                if target_capability:
                    allowed["capability"].add(target_capability)

            for automation in item.get("controlling_automations", []):
                automation_id = automation.get("automation_id")
                trigger_id = automation.get("trigger_entity_id")
                trigger_capability = automation.get("trigger_capability")

                if automation_id:
                    allowed["automation"].add(automation_id)
                if trigger_id:
                    allowed["entity"].add(trigger_id)
                if trigger_capability:
                    allowed["capability"].add(trigger_capability)

            for related in item.get("can_cause_entities", []):
                entity_id = related.get("entity_id")
                capability = related.get("affected_capability")

                if entity_id:
                    allowed["entity"].add(entity_id)
                if capability:
                    allowed["capability"].add(capability)

        return allowed

    def write_results(self, items):
        """Persist causal relationship edges and mark source context entities."""
        with self.driver.session() as session:
            for item in items:
                session.run(self.build_write_query(item), **item)

    def build_write_query(self, item):
        """Build a Cypher statement with validated label and relationship tokens."""
        relationship_type = item["relationship_type"]
        source_type = item["source_type"]
        target_type = item["target_type"]

        source_clause = self.node_matchers[source_type].format(
            var="source",
            param="source_id",
        )
        target_clause = self.node_matchers[target_type].format(
            var="target",
            param="target_id",
        )

        return f"""
        MATCH (context:Entity {{entity_id: $context_entity_id}})
        {source_clause}
        {target_clause}

        MERGE (source)-[r:{relationship_type}]->(target)
        SET r.causal_stage = $causal_stage,
            r.event_time = CASE
                WHEN $event_time IS NULL OR $event_time = "" THEN NULL
                ELSE datetime($event_time)
            END,
            r.confidence = $confidence,
            r.reason = $reason,
            r.source = "openai",
            r.updated_at = datetime()

        SET context.causal_dependency_enriched = true,
            context.causal_dependency_enriched_at = datetime()
        """
