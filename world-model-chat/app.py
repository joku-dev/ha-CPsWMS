"""Natural language chat layer for the Home Assistant world model."""

import json
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase
from openai import OpenAI
from pydantic import BaseModel, Field
import uvicorn

from config import (
    MAX_QUERY_ROWS,
    MIN_CYPHER_CONFIDENCE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROMPTS_DIR,
    SCHEMAS_DIR,
    WORLD_MODEL_CHAT_HOST,
    WORLD_MODEL_CHAT_PORT,
)


app = FastAPI(
    title="Home Assistant World Model Chat",
    description="Natural-language chat over the Home Assistant Neo4j world model.",
    version="0.1.0",
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
neo4j_driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)

BANNED_CYPHER_PATTERNS = [
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bSET\b",
    r"\bDELETE\b",
    r"\bDETACH\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bCALL\b",
    r"\bLOAD\s+CSV\b",
    r"\bFOREACH\b",
    r"\bUNWIND\b",
    r"\bAPOC\b",
    r"\bDBMS\b",
    r"\bSHOW\b",
    r"\bSTART\b",
    r"\bSTOP\b",
]


class ChatRequest(BaseModel):
    """Incoming chat request."""

    question: str = Field(..., min_length=1, max_length=2000)
    include_cypher: bool = False


class GeneratedCypher(BaseModel):
    """Structured Cypher generation result."""

    intent: str
    cypher: str
    parameters: dict[str, Any]
    confidence: float
    reason: str


class ChatResponse(BaseModel):
    """Chat response with optional execution details."""

    answer: str
    intent: str
    confidence: float
    row_count: int
    cypher: str | None = None
    parameters: dict[str, Any] | None = None
    reason: str | None = None


def load_text(path):
    """Load a UTF-8 text file."""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def load_json(path):
    """Load a UTF-8 JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def make_json_safe(value):
    """Convert Neo4j/Python-native values to JSON-compatible values."""
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


def generate_cypher(question):
    """Ask OpenAI for a structured read-only Cypher query."""
    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": load_text(PROMPTS_DIR / "cypher_generation.md"),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "cypher_query",
                "schema": load_json(SCHEMAS_DIR / "cypher_query_schema.json"),
            }
        },
    )

    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise HTTPException(status_code=502, detail="OpenAI returned no Cypher output")

    try:
        return GeneratedCypher(**json.loads(output_text))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Invalid Cypher generation output: {exc}") from exc


def validate_cypher(generated):
    """Reject unsafe or unsupported Cypher before it reaches Neo4j."""
    cypher = generated.cypher.strip()
    upper = cypher.upper()

    if generated.confidence < MIN_CYPHER_CONFIDENCE:
        raise HTTPException(
            status_code=422,
            detail=f"Cypher confidence too low: {generated.confidence}",
        )

    if ";" in cypher:
        raise HTTPException(status_code=422, detail="Cypher must contain exactly one statement without semicolons")

    if not re.match(r"^(MATCH|OPTIONAL\s+MATCH)\b", upper):
        raise HTTPException(status_code=422, detail="Cypher must start with MATCH or OPTIONAL MATCH")

    if not re.search(r"\bRETURN\b", upper):
        raise HTTPException(status_code=422, detail="Cypher must return data")

    if not re.search(r"\bLIMIT\b", upper):
        raise HTTPException(status_code=422, detail="Cypher must include LIMIT")

    for pattern in BANNED_CYPHER_PATTERNS:
        if re.search(pattern, upper):
            raise HTTPException(status_code=422, detail=f"Cypher contains banned pattern: {pattern}")

    return cypher


def bound_parameters(parameters):
    """Limit generated parameters to JSON-like scalar and scalar-list values."""
    safe = {}

    for key, value in parameters.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise HTTPException(status_code=422, detail=f"Invalid parameter name: {key}")

        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
            continue

        if isinstance(value, list) and all(
            isinstance(item, (str, int, float, bool)) or item is None
            for item in value
        ):
            safe[key] = value[:MAX_QUERY_ROWS]
            continue

        raise HTTPException(status_code=422, detail=f"Unsupported parameter value for: {key}")

    return safe


def execute_read_query(cypher, parameters):
    """Execute a validated read-only Cypher query."""
    with neo4j_driver.session() as session:
        records = session.run(cypher, **parameters)
        rows = [make_json_safe(dict(record)) for record in records]

    return rows[:MAX_QUERY_ROWS]


def generate_answer(question, generated, rows):
    """Ask OpenAI to turn query results into a natural-language answer."""
    payload = {
        "question": question,
        "intent": generated.intent,
        "cypher": generated.cypher,
        "parameters": generated.parameters,
        "row_count": len(rows),
        "rows": rows,
    }

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": load_text(PROMPTS_DIR / "answer_generation.md"),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ],
    )

    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise HTTPException(status_code=502, detail="OpenAI returned no answer output")

    return output_text.strip()


@app.get("/health")
def health():
    """Check Neo4j connectivity."""
    with neo4j_driver.session() as session:
        session.run("RETURN 1 AS ok").consume()

    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Answer a natural-language question against the world model graph."""
    generated = generate_cypher(request.question)
    cypher = validate_cypher(generated)
    parameters = bound_parameters(generated.parameters)
    rows = execute_read_query(cypher, parameters)
    answer = generate_answer(request.question, generated, rows)

    return ChatResponse(
        answer=answer,
        intent=generated.intent,
        confidence=generated.confidence,
        row_count=len(rows),
        cypher=cypher if request.include_cypher else None,
        parameters=parameters if request.include_cypher else None,
        reason=generated.reason if request.include_cypher else None,
    )


def main():
    """Start the FastAPI server."""
    uvicorn.run(app, host=WORLD_MODEL_CHAT_HOST, port=WORLD_MODEL_CHAT_PORT)


if __name__ == "__main__":
    main()
