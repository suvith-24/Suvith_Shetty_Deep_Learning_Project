
"""
Backward-compatible configuration imports.

The canonical configuration is maintained in:
src/lexisync/config.py
"""

from lexisync.config import (
    PROJECT_ROOT,
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    UPLOADS_DIR,
    STORAGE_DIR,
    INDEX_DIR,
    LOG_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    EMBEDDING_MODEL,
    RERANKER_MODEL,
    RETRIEVAL_TOP_K,
    RERANK_TOP_K,
)


__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "RAW_DATA_DIR",
    "PROCESSED_DATA_DIR",
    "UPLOADS_DIR",
    "STORAGE_DIR",
    "INDEX_DIR",
    "LOG_DIR",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "EMBEDDING_MODEL",
    "RERANKER_MODEL",
    "RETRIEVAL_TOP_K",
    "RERANK_TOP_K",
]
