import os
import json
import time
from pathlib import Path

from neo4j import GraphDatabase
from openai import OpenAI


OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "300"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.50"))

BASE_DIR = Path(__file__).parent
PROMPT_PATH = BASE_DIR / "prompts" / "semantic_roles.md"
SCHEMA_PATH = BASE_DIR / "schemas" / "enrichment_schema.json"


client = OpenAI(api_key=OPENAI_API_KEY)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def create_constraints():
    constraints = [
        """
        CREATE CONSTRAINT semantic_role_name_unique IF NOT EXISTS
        FOR (r:SemanticRole)
        REQUIRE r.name IS UNIQUE
        """,
        """
        CREATE CONSTRAINT semantic_category_name_unique IF NOT EXISTS
        FOR (c:SemanticCategory)
        REQUIRE c.name IS UNIQUE
        """,
        """
        CREATE CONSTRAINT criticality_level_unique IF NOT EXISTS
        FOR (c:Criticality)
        REQUIRE c.level IS UNIQUE
        """
    ]

    with driver.session() as session:
        for constraint in constraints:
            session.run(constraint)


def get_entities_for_enrichment(limit: int):
    query = """
    MATCH (e:Entity)
    WHERE e.semantic_enriched IS NULL
       OR e.semantic_enriched = false
    RETURN
        e.entity_id AS entity_id,
        e.friendly_name AS friendly_name,
        e.domain AS domain,
        e.state AS state,
        e.icon AS icon,
        e.entity_category AS entity_category,
        e.platform AS platform,
        e.is_problem AS is_problem
    LIMIT $limit
    """

    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(record) for record in result]


def enrich_entities_with_llm(entities, system_prompt, schema):
    payload = {
        "task": "Semantic enrichment of Home Assistant entities",
        "entities": entities,
        "rules": {
            "do_not_invent_entity_ids": True,
            "confidence_range": "0.0 to 1.0",
            "return_json_only": True,
            "use_unknown_if_unsure": True
        }
    }

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "home_assistant_semantic_enrichment",
                "schema": schema,
            }
        },
    )

    return json.loads(response.output_text)


def validate_enrichments(enrichments, input_entities):
    allowed_entity_ids = {entity["entity_id"] for entity in input_entities}
    valid = []

    for item in enrichments:
        entity_id = item.get("entity_id")
        confidence = item.get("confidence", 0)

        if entity_id not in allowed_entity_ids:
            print(f"Skipped unknown entity_id from LLM: {entity_id}")
            continue

        if confidence < MIN_CONFIDENCE:
            print(f"Skipped low confidence enrichment for {entity_id}: {confidence}")
            continue

        if confidence < 0 or confidence > 1:
            print(f"Skipped invalid confidence for {entity_id}: {confidence}")
            continue

        valid.append(item)

    return valid


def write_enrichments(enrichments):
    query = """
    MATCH (e:Entity {entity_id: $entity_id})

    MERGE (role:SemanticRole {name: $semantic_role})
    MERGE (category:SemanticCategory {name: $semantic_category})
    MERGE (criticality:Criticality {level: $criticality})

    MERGE (e)-[r1:HAS_SEMANTIC_ROLE]->(role)
    SET r1.confidence = $confidence,
        r1.reason = $reason,
        r1.source = "openai",
        r1.updated_at = datetime()

    MERGE (e)-[r2:HAS_SEMANTIC_CATEGORY]->(category)
    SET r2.confidence = $confidence,
        r2.source = "openai",
        r2.updated_at = datetime()

    MERGE (e)-[r3:HAS_CRITICALITY]->(criticality)
    SET r3.confidence = $confidence,
        r3.source = "openai",
        r3.updated_at = datetime()

    SET e.semantic_enriched = true,
        e.semantic_enriched_at = datetime()
    """

    with driver.session() as session:
        for item in enrichments:
            session.run(query, **item)


def mark_entities_as_checked_without_result(entities):
    query = """
    MATCH (e:Entity {entity_id: $entity_id})
    SET e.semantic_enriched = false,
        e.semantic_checked_at = datetime()
    """

    with driver.session() as session:
        for entity in entities:
            session.run(query, entity_id=entity["entity_id"])


def run_once():
    system_prompt = load_text(PROMPT_PATH)
    schema = load_json(SCHEMA_PATH)

    entities = get_entities_for_enrichment(BATCH_SIZE)

    if not entities:
        print("No entities require semantic enrichment.")
        return

    print(f"Sending {len(entities)} entities to LLM for enrichment.")

    result = enrich_entities_with_llm(
        entities=entities,
        system_prompt=system_prompt,
        schema=schema,
    )

    enrichments = result.get("enrichments", [])
    valid_enrichments = validate_enrichments(enrichments, entities)

    if valid_enrichments:
        write_enrichments(valid_enrichments)
        print(f"Enriched {len(valid_enrichments)} entities.")
    else:
        mark_entities_as_checked_without_result(entities)
        print("No valid enrichments returned.")


def wait_for_neo4j(retries=30, delay=5):
    for attempt in range(1, retries + 1):
        try:
            with driver.session() as session:
                session.run("RETURN 1")
            print("Neo4j connection established.")
            return
        except Exception as exc:
            print(f"Waiting for Neo4j... attempt {attempt}/{retries}: {exc}")
            time.sleep(delay)

    raise RuntimeError("Neo4j not reachable.")


def main():
    print("Semantic enrichment service started.")
    print(f"Model: {OPENAI_MODEL}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Sleep seconds: {SLEEP_SECONDS}")
    print(f"Minimum confidence: {MIN_CONFIDENCE}")

    wait_for_neo4j()
    create_constraints()

    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"Semantic enrichment failed: {exc}")

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
    