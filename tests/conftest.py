"""Shared fakes and synthetic-PDF helpers. No test needs Ollama or model downloads."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pymupdf
import pytest


# --------------------------------------------------------------------- models


class HashEmbedder:
    """Deterministic bag-of-words embedder (hashing trick, 64 dimensions)."""

    dimension = 64

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True, **kwargs):
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9]+", text.casefold()):
                index = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dimension
                vectors[row, index] += 1.0
            vectors[row, -1] += 0.01  # never all-zero
        if normalize_embeddings:
            vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors


class OverlapCrossEncoder:
    """Scores a (query, passage) pair by shared tokens: a stand-in for ms-marco."""

    def predict(self, pairs, **kwargs):
        scores = []
        for query, passage in pairs:
            q = set(re.findall(r"[a-z0-9]+", query.casefold()))
            p = set(re.findall(r"[a-z0-9]+", passage.casefold()))
            scores.append(float(len(q & p)) - 2.0)
        return np.asarray(scores, dtype=np.float32)


class FakeOllama:
    """Scripted stand-in for ``OllamaClient``.

    ``responses`` is a list of strings (or callables receiving the prompt)
    returned in order. Reviewer prompts can be answered by ``reviewer``.
    """

    model = "fake-model"

    def __init__(self, responses=None, reviewer=None):
        self.responses = list(responses or [])
        self.reviewer = reviewer
        self.calls: list[dict] = []
        self.usage: list[dict] = []

    def reset_usage(self):
        self.usage = []

    def usage_summary(self):
        return {
            "llm_calls": len(self.usage),
            "prompt_tokens": 10 * len(self.usage),
            "completion_tokens": 5 * len(self.usage),
            "llm_seconds": 0.0,
            "calls": list(self.usage),
        }

    def generate(self, prompt, system_prompt=None, temperature=0.1, response_format=None, purpose="generate"):
        self.calls.append({"prompt": prompt, "system": system_prompt, "format": response_format, "purpose": purpose})
        self.usage.append({"purpose": purpose})
        if system_prompt and "legal evidence verification" in system_prompt and self.reviewer:
            return self.reviewer(prompt)
        if not self.responses:
            raise AssertionError("FakeOllama ran out of scripted responses")
        response = self.responses.pop(0)
        return response(prompt) if callable(response) else response


def answer_json(claims, status="answered", missing=None, explanation="", conflicts=""):
    return json.dumps({
        "status": status,
        "claims": claims,
        "explanation": explanation,
        "conflicts": conflicts,
        "missing": missing or [],
    })


@pytest.fixture
def hash_embedder():
    return HashEmbedder()


@pytest.fixture
def overlap_reranker():
    return OverlapCrossEncoder()


# --------------------------------------------------------------------- PDFs


def make_pdf(path: Path, pages: list[list[tuple]], metadata: dict | None = None) -> Path:
    """Write a PDF. Each page is a list of (x, y, text, fontsize) tuples."""

    document = pymupdf.open()
    for items in pages:
        page = document.new_page(width=595, height=842)
        for item in items:
            x, y, text = item[:3]
            size = item[3] if len(item) > 3 else 10
            page.insert_text((x, y), text, fontsize=size)
    if metadata:
        document.set_metadata(metadata)
    document.save(path)
    document.close()
    return path


def legal_lines(start_y: float, lines: list[str], size: float = 10, gap: float = 16) -> list[tuple]:
    return [(56, start_y + i * gap, line, size) for i, line in enumerate(lines)]


@pytest.fixture
def pdf_factory(tmp_path):
    def factory(name: str, pages: list[list[tuple]], metadata: dict | None = None) -> Path:
        return make_pdf(tmp_path / name, pages, metadata)
    return factory
