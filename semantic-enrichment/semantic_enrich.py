
import time

from config import SLEEP_SECONDS
from enrichers.semantic_roles import SemanticRolesEnricher
from enrichers.semantic_descriptions import SemanticDescriptionsEnricher
from enrichers.failure_impact import FailureImpactEnricher
from enrichers.recommended_actions import RecommendedActionsEnricher


def wait_for_neo4j(enricher, retries=30, delay=5):
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
    print("Semantic enrichment orchestrator started.")

    enrichers = [
        SemanticRolesEnricher(),
        SemanticDescriptionsEnricher(),
        FailureImpactEnricher(),
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