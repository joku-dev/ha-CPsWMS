"""Runtime configuration for the world model chat service."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMAS_DIR = BASE_DIR / "schemas"

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

WORLD_MODEL_CHAT_HOST = os.getenv("WORLD_MODEL_CHAT_HOST", "0.0.0.0")
WORLD_MODEL_CHAT_PORT = int(os.getenv("WORLD_MODEL_CHAT_PORT", "8090"))

MAX_QUERY_ROWS = int(os.getenv("WORLD_MODEL_CHAT_MAX_QUERY_ROWS", "100"))
MIN_CYPHER_CONFIDENCE = float(os.getenv("WORLD_MODEL_CHAT_MIN_CYPHER_CONFIDENCE", "0.4"))
