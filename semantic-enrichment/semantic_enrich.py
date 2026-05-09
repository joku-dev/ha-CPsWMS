"""Main orchestrator for semantic enrichment workers.

This module owns runtime ordering, startup checks, and resilient loop execution.
"""
import time

from config import SLEEP_SECONDS
from enrichers.semantic_roles import SemanticRolesEnricher
from enrichers.automation_intent import AutomationIntentEnricher
from enrichers.fault_analysis import FaultAnalysisEnricher
from enrichers.anomaly_detection import AnomalyDetectionEnricher
from enrichers.room_inference import RoomInferenceEnricher
from enrichers.semantic_descriptions import SemanticDescriptionsEnricher
from enrichers.failure_impact import FailureImpactEnricher
from enrichers.recommended_actions import RecommendedActionsEnricher
from enrichers.dependency_reasoning import DependencyReasoningEnricher


def wait_for_neo4j(enricher, retries=30, delay=5):
    """Block startup until Neo4j is reachable or retries are exhausted."""
    for attempt in range(1, retries + 1):
        try:
            with enricher.driver.session() as session:
                session.run("RETURN 1")
            print("Neo4j connection established.")
            return
        except Exception as exc:
            print(f"Waiting for Neo4j... attempt {attempt}/{retries}: {exc}")
            time.sleep(delay)

    raise RuntimeError("Neo4j not reachable.")


def main():
    """Initialize enrichers and execute them continuously in dependency order."""
    print("Semantic enrichment orchestrator started.")

    enrichers = [
        # Basis-Semantik zuerst, damit Folge-Enricher auf Rollen/Kategorien aufbauen koennen.
        SemanticRolesEnricher(),
        # Raumableitung frueh, weil Area-Kontext fuer spaetere Analysen hilfreich ist.
        RoomInferenceEnricher(),

        # Analyse von Automationen und Problemzustaenden.
        AutomationIntentEnricher(),
        FaultAnalysisEnricher(),
        AnomalyDetectionEnricher(),

        # Abgeleitete, hoehere Analysen auf Basis vorheriger Ergebnisse.
        FailureImpactEnricher(),
        SemanticDescriptionsEnricher(),
        DependencyReasoningEnricher(),

        # Empfohlene Aktionen zuletzt, da sie auf mehreren Voranalysen basieren.
        RecommendedActionsEnricher(),
    ]

    wait_for_neo4j(enrichers[0])

    for enricher in enrichers:
        enricher.setup()

    while True:
        for enricher in enrichers:
            try:
                print(f"Running enricher: {enricher.name}")
                enricher.run_once()
            except Exception as exc:
                print(f"Enricher failed: {enricher.name}: {exc}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
