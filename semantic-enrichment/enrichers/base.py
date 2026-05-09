import json
import time
from abc import ABC, abstractmethod

from neo4j import GraphDatabase
from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    BATCH_SIZE,
    MIN_CONFIDENCE,
    PROMPTS_DIR,
    SCHEMAS_DIR,
)


class BaseEnricher(ABC):
    """Shared enrichment workflow for all specialized enrichers.

    Subclasses define graph-specific candidate queries and write-back logic.
    This base class centralizes prompt/schema loading, LLM calls and validation.
    """

    name = "base"
    prompt_file = None
    schema_file = None
    response_key = None

    def __init__(self):
        """Create reusable OpenAI and Neo4j clients for one enricher instance."""
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )

    def setup(self):
        """Prepare shared and enricher-specific database constraints."""
        self.create_base_constraints()
        self.create_constraints()

    def create_base_constraints(self):
        """Create constraints needed across all enrichers."""
        with self.driver.session() as session:
            session.run("""
            CREATE CONSTRAINT semantic_enrichment_event_id_unique IF NOT EXISTS
            FOR (e:SemanticEnrichmentEvent)
            REQUIRE e.event_id IS UNIQUE
            """)

    def load_prompt(self):
        """Load the system prompt referenced by prompt_file."""
        path = PROMPTS_DIR / self.prompt_file
        print(f"[{self.name}] Loading prompt: {path}")

        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    def load_schema(self):
        """Load the JSON schema referenced by schema_file."""
        path = SCHEMAS_DIR / self.schema_file
        print(f"[{self.name}] Loading schema: {path}")

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def call_llm(self, payload):
        """Invoke OpenAI with structured-output schema and parse JSON response."""
        print(f"[{self.name}] CALLING OPENAI...")
        print(f"[{self.name}] Model: {OPENAI_MODEL}")
        print(f"[{self.name}] Payload items: {len(payload.get('items', []))}")

        try:
            response = self.client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": self.load_prompt(),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": self.name,
                        "schema": self.load_schema(),
                    }
                },
            )

            print(f"[{self.name}] OPENAI RESPONSE RECEIVED")
            print(f"[{self.name}] Raw response:")
            print(response)

            output_text = getattr(response, "output_text", None)

            if not output_text:
                print(f"[{self.name}] ERROR: response.output_text is empty or missing")
                return {self.response_key: []}

            print(f"[{self.name}] OUTPUT TEXT:")
            print(output_text)

            try:
                return json.loads(output_text)
            except json.JSONDecodeError as exc:
                print(f"[{self.name}] JSONDecodeError: {exc}")
                return {self.response_key: []}

        except Exception as exc:
            print(f"[{self.name}] OpenAI call failed: {exc}")
            return {self.response_key: []}

    def validate_confidence(self, item):
        """Validate confidence field against configured range and threshold."""
        confidence = item.get("confidence", 0)

        try:
            confidence = float(confidence)
        except Exception:
            return False

        if confidence < MIN_CONFIDENCE:
            print(
                f"[{self.name}] Skipped low confidence item: "
                f"{confidence} < {MIN_CONFIDENCE}"
            )
            return False

        if confidence < 0 or confidence > 1:
            print(f"[{self.name}] Skipped invalid confidence: {confidence}")
            return False

        return True

    def run_once(self):
        """Run one enrichment iteration for the current enricher."""
        print(f"[{self.name}] Selecting candidates...")

        items = self.get_candidates(BATCH_SIZE)

        print(f"[{self.name}] Candidates found: {len(items)}")

        if not items:
            print(f"[{self.name}] No candidates.")
            return

        payload = {
            "task": self.name,
            "items": items,
            "rules": {
                "do_not_invent_ids": True,
                "confidence_range": "0.0 to 1.0",
                "return_json_only": True,
            },
        }

        result = self.call_llm(payload)

        print(f"[{self.name}] Parsed LLM result:")
        print(result)

        llm_items = result.get(self.response_key, [])

        print(f"[{self.name}] LLM items returned: {len(llm_items)}")

        valid_items = self.validate_items(llm_items, items)

        print(f"[{self.name}] Valid items: {len(valid_items)}")

        if not valid_items:
            print(f"[{self.name}] No valid results.")
            return

        self.write_results(valid_items)

        print(f"[{self.name}] Wrote {len(valid_items)} results.")

    @abstractmethod
    def create_constraints(self):
        pass

    @abstractmethod
    def get_candidates(self, limit):
        pass

    @abstractmethod
    def validate_items(self, llm_items, input_items):
        pass

    @abstractmethod
    def write_results(self, items):
        pass
