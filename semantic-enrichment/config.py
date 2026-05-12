"""Runtime configuration for semantic enrichment workers."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Diese Datei liegt im Arbeitsverzeichnis des Enrichment-Containers.
BASE_DIR = Path(__file__).parent

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "300"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.5"))

ENABLE_SEMANTIC_IDENTITY = os.getenv("ENABLE_SEMANTIC_IDENTITY", "true").lower() == "true"
DEFAULT_ENRICHMENT_TARGET_MODE = "canonical_first" if ENABLE_SEMANTIC_IDENTITY else "entity_first"
ENRICHMENT_TARGET_MODE = os.getenv("ENRICHMENT_TARGET_MODE", DEFAULT_ENRICHMENT_TARGET_MODE).lower()
if ENRICHMENT_TARGET_MODE not in {"canonical_first", "entity_first", "dual_write"}:
    print(
        f"WARNING: Unsupported ENRICHMENT_TARGET_MODE='{ENRICHMENT_TARGET_MODE}'. "
        f"Defaulting to '{DEFAULT_ENRICHMENT_TARGET_MODE}'."
    )
    ENRICHMENT_TARGET_MODE = DEFAULT_ENRICHMENT_TARGET_MODE

PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMAS_DIR = BASE_DIR / "schemas"
