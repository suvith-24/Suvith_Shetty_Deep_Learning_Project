
import os
from pathlib import Path

from dotenv import load_dotenv


# Project root: LexiSyncAI/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Load environment variables from the project root.
load_dotenv(PROJECT_ROOT / ".env")


# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
UPLOADS_DIR = DATA_DIR / "uploads"


# Storage directories
STORAGE_DIR = PROJECT_ROOT / "storage"
INDEX_DIR = STORAGE_DIR / "indexes"


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


# Retrieval models
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# Retrieval settings
RETRIEVAL_TOP_K = 10
RERANK_TOP_K = 5
