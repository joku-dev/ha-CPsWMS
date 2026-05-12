"""Semantic quality metric collection."""

from __future__ import annotations

from .metrics_collector import SemanticQualityMetrics, ratio
from .neo4j_metrics import SEMANTIC_RELATIONSHIP_TYPES, Neo4jBenchmarkClient


EXPLAINABILITY_PROPERTIES = [
    "reason",
    "rationale",
    "explanation",
    "evidence",
    "source",
    "prompt_version",
    "model",
]


class SemanticMetricsCollector:
    """Collect semantic coverage, confidence and explainability metrics."""

    def __init__(self, client: Neo4jBenchmarkClient, low_confidence_threshold: float = 0.5, high_confidence_threshold: float = 0.8):
        self.client = client
        self.low_confidence_threshold = low_confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold

    def collect(self) -> SemanticQualityMetrics:
        total_targets = self._target_count()
        metrics = SemanticQualityMetrics()
        metrics.semantic_role_coverage_ratio = self._coverage("HAS_SEMANTIC_ROLE", total_targets)
        metrics.semantic_category_coverage_ratio = self._coverage("HAS_SEMANTIC_CATEGORY", total_targets)
        metrics.criticality_coverage_ratio = self._coverage("HAS_CRITICALITY", total_targets)
        metrics.capability_coverage_ratio = self._coverage("PROVIDES_CAPABILITY", total_targets)
        metrics.dependency_coverage_ratio = self._coverage_any(["DEPENDS_ON", "IMPACTS", "DEGRADES", "RECOVERS"], total_targets)
        metrics.causal_relation_coverage_ratio = self._coverage_any(["CAUSES", "HAS_CAUSAL_DEPENDENCY"], total_targets)
        metrics.recommended_action_coverage_ratio = self._coverage("HAS_RECOMMENDED_ACTION", total_targets)
        metrics.simulation_readiness_coverage_ratio = self._simulation_readiness_coverage(total_targets)
        metrics.semantic_relationship_count = int(self.client.scalar("""
            MATCH ()-[r]->()
            WHERE type(r) IN $types
            RETURN count(r) AS value
        """, "value", 0, types=SEMANTIC_RELATIONSHIP_TYPES))

        confidence = self._confidence_summary()
        metrics.average_semantic_confidence = confidence["average"]
        metrics.confidence_relation_count = confidence["total"]
        metrics.low_confidence_ratio = ratio(confidence["low"], confidence["total"])
        metrics.high_confidence_ratio = ratio(confidence["high"], confidence["total"])

        explainability = self._explainability_summary()
        metrics.explainable_relation_count = explainability["explainable"]
        metrics.explainability_coverage_ratio = ratio(explainability["explainable"], explainability["total"])
        metrics.conflicting_semantics_count = self._conflicting_semantics_count()
        return metrics

    def _target_count(self) -> int:
        canonical_count = int(self.client.scalar("MATCH (c:CanonicalEntity) RETURN count(c) AS value", "value", 0))
        if canonical_count:
            return canonical_count
        return int(self.client.scalar("MATCH (e:Entity) RETURN count(e) AS value", "value", 0))

    def _target_label(self) -> str:
        canonical_count = int(self.client.scalar("MATCH (c:CanonicalEntity) RETURN count(c) AS value", "value", 0))
        return "CanonicalEntity" if canonical_count else "Entity"

    def _coverage(self, relationship_type: str, total_targets: int) -> float:
        if total_targets == 0:
            return 0.0
        label = self._target_label()
        count = int(self.client.scalar(f"""
            MATCH (target:{label})-[r:{relationship_type}]->()
            RETURN count(DISTINCT target) AS value
        """, "value", 0))
        return ratio(count, total_targets)

    def _coverage_any(self, relationship_types: list[str], total_targets: int) -> float:
        if total_targets == 0:
            return 0.0
        label = self._target_label()
        count = int(self.client.scalar(f"""
            MATCH (target:{label})-[r]-()
            WHERE type(r) IN $types
            RETURN count(DISTINCT target) AS value
        """, "value", 0, types=relationship_types))
        return ratio(count, total_targets)

    def _simulation_readiness_coverage(self, total_targets: int) -> float:
        if total_targets == 0:
            return 0.0
        count = int(self.client.scalar("""
            MATCH (scenario:SimulationScenario)-[:EVALUATES_TARGET]->(target)
            MATCH (scenario)-[:HAS_SIMULATION_READINESS]->(:SimulationReadinessLevel)
            RETURN count(DISTINCT target) AS value
        """, "value", 0))
        if count == 0:
            return self._coverage("HAS_SIMULATION_READINESS", total_targets)
        return ratio(count, total_targets)

    def _confidence_summary(self) -> dict[str, int | float | None]:
        rows = self.client.query("""
            MATCH ()-[r]->()
            WHERE type(r) IN $types AND r.confidence IS NOT NULL
            RETURN
              avg(toFloat(r.confidence)) AS average,
              count(r) AS total,
              sum(CASE WHEN toFloat(r.confidence) < $low THEN 1 ELSE 0 END) AS low,
              sum(CASE WHEN toFloat(r.confidence) >= $high THEN 1 ELSE 0 END) AS high
        """, types=SEMANTIC_RELATIONSHIP_TYPES, low=self.low_confidence_threshold, high=self.high_confidence_threshold)
        if not rows:
            return {"average": None, "total": 0, "low": 0, "high": 0}
        row = rows[0]
        return {
            "average": row.get("average"),
            "total": int(row.get("total") or 0),
            "low": int(row.get("low") or 0),
            "high": int(row.get("high") or 0),
        }

    def _explainability_summary(self) -> dict[str, int]:
        rows = self.client.query("""
            MATCH ()-[r]->()
            WHERE type(r) IN $types
            WITH r, [key IN keys(r) WHERE key IN $properties AND r[key] IS NOT NULL] AS explainability_keys
            RETURN
              count(r) AS total,
              sum(CASE WHEN size(explainability_keys) > 0 THEN 1 ELSE 0 END) AS explainable
        """, types=SEMANTIC_RELATIONSHIP_TYPES, properties=EXPLAINABILITY_PROPERTIES)
        if not rows:
            return {"total": 0, "explainable": 0}
        return {
            "total": int(rows[0].get("total") or 0),
            "explainable": int(rows[0].get("explainable") or 0),
        }

    def _conflicting_semantics_count(self) -> int:
        return int(self.client.scalar("""
            MATCH (target)-[:HAS_SEMANTIC_ROLE]->(role:SemanticRole)
            WITH target, count(DISTINCT role.name) AS role_count
            WHERE role_count > 1
            RETURN count(target) AS value
        """, "value", 0))

