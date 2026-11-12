"""Centralised configuration. Every value can be overridden in ``.env``.

Secrets are never required: the application talks only to a local Ollama
server and to locally cached Hugging Face models.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


APP_VERSION = "1.0.0"

# Project root: LexiSyncAI/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Load environment variables from the project root.
load_dotenv(PROJECT_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
UPLOADS_DIR = DATA_DIR / "uploads"


# Storage directories
STORAGE_DIR = PROJECT_ROOT / "storage"
INDEX_DIR = STORAGE_DIR / "indexes"
CASES_DIR = STORAGE_DIR / "cases"


# Logging directory
LOG_DIR = PROJECT_ROOT / "logs"


# Local language model
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:3b",
)

# Ollama's default context window (2k–4k tokens depending on version) is
# smaller than a full evidence prompt; truncation would silently drop evidence.
OLLAMA_NUM_CTX = _int("OLLAMA_NUM_CTX", 8192)
OLLAMA_TIMEOUT_SECONDS = _int("OLLAMA_TIMEOUT_SECONDS", 180)

# Fixed seed for reproducible generation (temperature is 0 as well).
RANDOM_SEED = _int("LEXISYNC_SEED", 42)


# Retrieval models
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)


# Retrieval settings
RETRIEVAL_TOP_K = 10
RERANK_TOP_K = 5

CANDIDATE_K = _int("LEXISYNC_CANDIDATE_K", 20)
FINAL_TOP_K = _int("LEXISYNC_TOP_K", 5)
PER_SUB_QUERY_K = _int("LEXISYNC_PER_SUB_QUERY_K", 3)
RRF_K = _int("LEXISYNC_RRF_K", 60)
CONTEXT_WINDOW = _int("LEXISYNC_CONTEXT_WINDOW", 1)
CONTEXTUAL_HEADERS = _bool("LEXISYNC_CONTEXTUAL_HEADERS", True)
CHUNK_SIZE = _int("LEXISYNC_CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _int("LEXISYNC_CHUNK_OVERLAP", 150)


# Grounding / abstention (cross-encoder logits; see docs/EVALUATION_REPORT.md
# for how the thresholds were chosen on the benchmark).
EVIDENCE_GATE_SCORE = _float("LEXISYNC_EVIDENCE_GATE", 0.0)
HIGH_CONFIDENCE_SCORE = _float("LEXISYNC_HIGH_CONFIDENCE_SCORE", 3.0)
MAX_CORRECTIVE_RETRIES = _int("LEXISYNC_MAX_RETRIES", 1)
VERIFIER_MODE = os.getenv("LEXISYNC_VERIFIER_MODE", "hybrid")  # hybrid | llm


# Case limits
MIN_DOCUMENTS_PER_CASE = 1
MAX_DOCUMENTS_PER_CASE = 5
MAX_UPLOAD_MB = _int("LEXISYNC_MAX_UPLOAD_MB", 50)
