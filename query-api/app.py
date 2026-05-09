"""HTTP query API for Home Assistant semantic graph questions."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from neo4j import GraphDatabase


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
QUERY_API_HOST = os.getenv("QUERY_API_HOST", "0.0.0.0")
QUERY_API_PORT = int(os.getenv("QUERY_API_PORT", "8080"))
DEFAULT_LIMIT = int(os.getenv("QUERY_API_DEFAULT_LIMIT", "25"))
MAX_LIMIT = int(os.getenv("QUERY_API_MAX_LIMIT", "100"))


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)


def make_json_safe(value):
    """Convert Neo4j/Python values into JSON-compatible output."""
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    if hasattr(value, "iso_format"):
        return value.iso_format()

    if hasattr(value, "to_native"):
        return make_json_safe(value.to_native())

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def parse_limit(query):
    """Read a bounded limit query parameter."""
    raw_limit = query.get("limit", [str(DEFAULT_LIMIT)])[0]

    try:
        limit = int(raw_limit)
    except ValueError:
        limit = DEFAULT_LIMIT

    return max(1, min(limit, MAX_LIMIT))


def run_query(query, **params):
    """Execute a read query and return JSON-safe records."""
    with driver.session() as session:
        records = session.run(query, **params)
        return [make_json_safe(dict(record)) for record in records]


def health():
    """Check that the API can reach Neo4j."""
    run_query("RETURN 1 AS ok")
    return {"status": "ok"}


def capabilities(limit):
    """List modeled capabilities and their current graph evidence."""
    rows = run_query(
        """
        MATCH (cap:Capability)
        OPTIONAL MATCH (source)-[rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]->(cap)
        OPTIONAL MATCH (cap)-[out:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]->(target)
        OPTIONAL MATCH (scenario:SimulationScenario)-[:EVALUATES_TARGET]->(cap)
        OPTIONAL MATCH (scenario)-[ready:HAS_SIMULATION_READINESS]->(level:SimulationReadinessLevel)
        RETURN
            cap.name AS capability,
            count(DISTINCT source) AS inbound_dependency_count,
            count(DISTINCT target) AS outbound_dependency_count,
            collect(DISTINCT {
                scenario_id: scenario.scenario_id,
                readiness: level.name,
                coverage_score: ready.coverage_score,
                confidence: ready.confidence
            })[0..5] AS simulation_readiness
        ORDER BY capability
        LIMIT $limit
        """,
        limit=limit,
    )
    return {"capabilities": rows}


def simulation_readiness(limit):
    """List scenario readiness assessments."""
    rows = run_query(
        """
        MATCH (scenario:SimulationScenario)-[rel:HAS_SIMULATION_READINESS]->(level:SimulationReadinessLevel)
        OPTIONAL MATCH (scenario)-[:EVALUATES_TARGET]->(target)
        RETURN
            scenario.scenario_id AS scenario_id,
            scenario.scenario_type AS scenario_type,
            scenario.target_type AS target_type,
            scenario.target_id AS target_id,
            scenario.target_name AS target_name,
            labels(target) AS target_labels,
            level.name AS readiness,
            rel.coverage_score AS coverage_score,
            rel.missing_data AS missing_data,
            rel.supported_questions AS supported_questions,
            rel.required_next_steps AS required_next_steps,
            rel.confidence AS confidence,
            rel.reason AS reason,
            toString(rel.updated_at) AS updated_at
        ORDER BY rel.coverage_score DESC, scenario.scenario_id
        LIMIT $limit
        """,
        limit=limit,
    )
    return {"readiness_assessments": rows}


def what_if_integration(domain, limit):
    """Describe impact evidence for an integration outage."""
    rows = run_query(
        """
        MATCH (integration:Integration {domain: $domain})
        OPTIONAL MATCH (entity:Entity)-[:PROVIDED_BY]->(integration)
        OPTIONAL MATCH (entity)-[:HAS_CRITICALITY]->(criticality:Criticality)
        OPTIONAL MATCH (entity)-[:HAS_FAILURE_IMPACT]->(impact:FailureImpactLevel)
        OPTIONAL MATCH (entity)-[cause:CAUSES|DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS]-(related)
        OPTIONAL MATCH (entity)<-[:TRIGGERED_BY|CONTROLS|HAS_CONDITION]-(automation:Automation)
        RETURN
            integration.domain AS integration,
            entity.entity_id AS entity_id,
            entity.friendly_name AS friendly_name,
            entity.state AS state,
            criticality.level AS criticality,
            impact.level AS failure_impact,
            collect(DISTINCT {
                type: type(cause),
                related_labels: labels(related),
                related_id: coalesce(related.entity_id, related.automation_id, related.name, related.incident_id),
                reason: cause.reason,
                confidence: cause.confidence
            })[0..10] AS causal_links,
            collect(DISTINCT {
                automation_id: automation.automation_id,
                name: automation.name
            })[0..10] AS automations
        ORDER BY
            CASE criticality.level
                WHEN "critical" THEN 0
                WHEN "high" THEN 1
                WHEN "medium" THEN 2
                ELSE 3
            END,
            entity.entity_id
        LIMIT $limit
        """,
        domain=domain,
        limit=limit,
    )
    return {"scenario": f"integration_outage:{domain}", "impacted_entities": rows}


def what_if_capability(name, limit):
    """Describe impact evidence for a capability loss."""
    rows = run_query(
        """
        MATCH (capability:Capability {name: $name})
        OPTIONAL MATCH (entity)-[impact:HAS_FAILURE_IMPACT]->(:FailureImpactLevel)
        WHERE impact.affected_capability = $name
        OPTIONAL MATCH (entity)-[:HAS_CRITICALITY]->(criticality:Criticality)
        OPTIONAL MATCH (entity)<-[:TRIGGERED_BY|CONTROLS|HAS_CONDITION]-(automation:Automation)
        OPTIONAL MATCH (source)-[rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]->(capability)
        WHERE source = entity OR source IS NULL
        RETURN
            capability.name AS capability,
            entity.entity_id AS entity_id,
            entity.friendly_name AS friendly_name,
            entity.state AS state,
            criticality.level AS criticality,
            impact.operational_consequence AS operational_consequence,
            collect(DISTINCT {
                type: type(rel),
                source_labels: labels(source),
                source_id: coalesce(source.entity_id, source.automation_id, source.name, source.incident_id),
                reason: rel.reason,
                confidence: rel.confidence
            })[0..10] AS causal_sources,
            collect(DISTINCT {
                automation_id: automation.automation_id,
                name: automation.name
            })[0..10] AS automations
        ORDER BY
            CASE criticality.level
                WHEN "critical" THEN 0
                WHEN "high" THEN 1
                WHEN "medium" THEN 2
                ELSE 3
            END,
            entity.entity_id
        LIMIT $limit
        """,
        name=name,
        limit=limit,
    )
    return {"scenario": f"capability_loss:{name}", "impacted_entities": rows}


def entity_impact(entity_id):
    """Return the semantic, temporal and causal impact context for one entity."""
    rows = run_query(
        """
        MATCH (entity:Entity {entity_id: $entity_id})
        OPTIONAL MATCH (entity)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
        OPTIONAL MATCH (entity)-[:HAS_SEMANTIC_CATEGORY]->(category:SemanticCategory)
        OPTIONAL MATCH (entity)-[:HAS_CRITICALITY]->(criticality:Criticality)
        OPTIONAL MATCH (entity)-[impact:HAS_FAILURE_IMPACT]->(impact_level:FailureImpactLevel)
        OPTIONAL MATCH (entity)-[:HAS_INCIDENT]->(incident:Incident)
        OPTIONAL MATCH (entity)-[:HAS_TIMELINE_EVENT]->(timeline:TimelineEvent)
        OPTIONAL MATCH (entity)-[rel:DEPENDS_ON|IMPACTS|DEGRADES|RECOVERS|CAUSES]-(related)
        OPTIONAL MATCH (entity)<-[:TRIGGERED_BY|CONTROLS|HAS_CONDITION]-(automation:Automation)
        RETURN
            entity.entity_id AS entity_id,
            entity.friendly_name AS friendly_name,
            entity.domain AS domain,
            entity.state AS state,
            role.name AS semantic_role,
            category.name AS semantic_category,
            criticality.level AS criticality,
            collect(DISTINCT {
                level: impact_level.level,
                affected_capability: impact.affected_capability,
                operational_consequence: impact.operational_consequence,
                confidence: impact.confidence
            }) AS failure_impacts,
            collect(DISTINCT {
                incident_id: incident.incident_id,
                type: incident.incident_type,
                severity: incident.severity,
                reason: incident.reason,
                opened_at: toString(incident.opened_at)
            })[0..10] AS incidents,
            collect(DISTINCT {
                event_type: timeline.event_type,
                summary: timeline.summary,
                event_time: toString(timeline.event_time)
            })[0..10] AS timeline_events,
            collect(DISTINCT {
                type: type(rel),
                related_labels: labels(related),
                related_id: coalesce(related.entity_id, related.automation_id, related.name, related.incident_id),
                reason: rel.reason,
                confidence: rel.confidence
            })[0..10] AS causal_links,
            collect(DISTINCT {
                automation_id: automation.automation_id,
                name: automation.name
            })[0..10] AS automations
        """,
        entity_id=entity_id,
    )
    return rows[0] if rows else {"error": "entity_not_found", "entity_id": entity_id}


class QueryHandler(BaseHTTPRequestHandler):
    """Route HTTP GET requests to graph query functions."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        limit = parse_limit(query)

        try:
            if path == "/health":
                self.send_json(health())
                return

            if path == "/api/capabilities":
                self.send_json(capabilities(limit))
                return

            if path == "/api/simulation-readiness":
                self.send_json(simulation_readiness(limit))
                return

            if path.startswith("/api/what-if/integration/"):
                domain = unquote(path.rsplit("/", 1)[-1])
                self.send_json(what_if_integration(domain, limit))
                return

            if path.startswith("/api/what-if/capability/"):
                name = unquote(path.rsplit("/", 1)[-1])
                self.send_json(what_if_capability(name, limit))
                return

            if path.startswith("/api/entities/") and path.endswith("/impact"):
                entity_id = unquote(path.removeprefix("/api/entities/").removesuffix("/impact"))
                self.send_json(entity_impact(entity_id))
                return

            self.send_json(
                {
                    "error": "not_found",
                    "routes": [
                        "/health",
                        "/api/capabilities",
                        "/api/simulation-readiness",
                        "/api/what-if/integration/{domain}",
                        "/api/what-if/capability/{name}",
                        "/api/entities/{entity_id}/impact",
                    ],
                },
                status=404,
            )

        except Exception as exc:
            self.send_json({"error": "query_failed", "detail": str(exc)}, status=500)

    def send_json(self, payload, status=200):
        """Write a JSON HTTP response."""
        body = json.dumps(make_json_safe(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    """Start the query API server."""
    server = ThreadingHTTPServer((QUERY_API_HOST, QUERY_API_PORT), QueryHandler)
    print(f"Query API listening on {QUERY_API_HOST}:{QUERY_API_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
