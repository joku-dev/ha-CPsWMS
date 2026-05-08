import json
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
    name = "base"
    prompt_file = None
    schema_file = None
    response_key = None

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )

    def setup(self):
        self.create_constraints()

    def load_prompt(self):
        with open(PROMPTS_DIR / self.prompt_file, "r", encoding="utf-8") as file:
            return file.read()

    def load_schema(self):
        with open(SCHEMAS_DIR / self.schema_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def call_llm(self, payload):
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

        return json.loads(response.output_text)

    def validate_confidence(self, item):
        confidence = item.get("confidence", 0)

        if confidence < MIN_CONFIDENCE:
            return False

        if confidence < 0 or confidence > 1:
            return False

        return True

    def run_once(self):
        items = self.get_candidates(BATCH_SIZE)

        if not items:
            print(f"{self.name}: no candidates.")
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
        llm_items = result.get(self.response_key, [])

        valid_items = self.validate_items(llm_items, items)

        if not valid_items:
            print(f"{self.name}: no valid results.")
            return

        self.write_results(valid_items)
        print(f"{self.name}: wrote {len(valid_items)} results.")

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
    
