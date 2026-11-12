"""Evaluation metrics for retrieval, abstention and citations.

Relevance is judged at the provision level: a retrieved chunk is relevant
to a question when its section matches one of the question's
``expected_sections``. Matching uses word boundaries on the normalised
section key, so ``Article 8`` does **not** match ``Article 83``. The original
evaluation script used a substring test, which had exactly that bug.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable

from lexisync.schemas.document import Chunk


def section_matches(chunk: Chunk, expected_section: str) -> bool:
    """True when the chunk belongs to ``expected_section`` (e.g. "Article 83")."""

    expected = expected_section.strip().casefold()
    key = ((chunk.metadata or {}).get("section_key") or "").casefold()
    if key:
        return key == expected
    pattern = re.compile(rf"(?<![\w.]){re.escape(expected)}(?![\w])", re.IGNORECASE)
    return bool(pattern.search(chunk.section or ""))


def relevant_sections(chunk: Chunk, expected_sections: Iterable[str]) -> set[str]:
    return {s for s in expected_sections if section_matches(chunk, s)}


def hit_at_k(ranked: list[Chunk], expected: list[str], k: int) -> float | None:
    """1.0 if any expected provision appears in the top k (None if unanswerable)."""

    if not expected:
        return None
    return float(any(relevant_sections(chunk, expected) for chunk in ranked[:k]))


def full_recall_at_k(ranked: list[Chunk], expected: list[str], k: int) -> float | None:
    """Fraction of expected provisions found in the top k (multi-hop recall)."""

    if not expected:
        return None
    found: set[str] = set()
    for chunk in ranked[:k]:
        found |= relevant_sections(chunk, expected)
    return len(found) / len(set(expected))


def reciprocal_rank(ranked: list[Chunk], expected: list[str]) -> float | None:
    if not expected:
        return None
    for rank, chunk in enumerate(ranked, start=1):
        if relevant_sections(chunk, expected):
            return 1.0 / rank
    return 0.0


def page_hit_at_k(ranked: list[Chunk], expected_pages: list[int], k: int) -> float | None:
    if not expected_pages:
        return None
    pages = set(expected_pages)
    return float(any(pages & set(chunk.page_numbers) for chunk in ranked[:k]))


def mean(values: Iterable[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def latency_summary(values: Iterable[float | None]) -> dict:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return {"mean": None, "median": None, "p95": None, "max": None, "n": 0}
    p95_index = min(len(clean) - 1, max(0, round(0.95 * (len(clean) - 1))))
    return {
        "mean": round(sum(clean) / len(clean), 3),
        "median": round(statistics.median(clean), 3),
        "p95": round(clean[p95_index], 3),
        "max": round(clean[-1], 3),
        "n": len(clean),
    }


def abstention_metrics(records: list[dict]) -> dict:
    """Abstention accuracy and error rates.

    Each record needs ``answerable`` (bool) and ``abstained`` (bool or None
    when generation failed; such records are excluded and counted).
    """

    scored = [r for r in records if r.get("abstained") is not None]
    answerable = [r for r in scored if r["answerable"]]
    unanswerable = [r for r in scored if not r["answerable"]]

    correct = sum(r["abstained"] == (not r["answerable"]) for r in scored)
    false_abstentions = sum(r["abstained"] for r in answerable)
    unsupported_answers = sum(not r["abstained"] for r in unanswerable)

    return {
        "evaluated": len(scored),
        "failed_runs": len(records) - len(scored),
        "abstention_accuracy": correct / len(scored) if scored else None,
        "correct_abstentions_on_unanswerable": (
            (len(unanswerable) - unsupported_answers) / len(unanswerable) if unanswerable else None
        ),
        "false_abstention_rate": false_abstentions / len(answerable) if answerable else None,
        "unsupported_answer_rate": unsupported_answers / len(unanswerable) if unanswerable else None,
        "false_abstentions": false_abstentions,
        "unsupported_answers": unsupported_answers,
    }


def citation_section_precision(cited_sections: list[str | None], expected: list[str], chunks_by_section=None) -> float | None:
    """Share of cited passages whose section is one of the expected provisions.

    This is an *automated proxy* for citation precision. A passage from another
    article can still legitimately support a claim, so manual scoring remains
    the reference measure.
    """

    if not cited_sections or not expected:
        return None
    hits = 0
    for section in cited_sections:
        chunk = Chunk(chunk_id="_", document_id="_", text="", page_numbers=[], section=section)
        if relevant_sections(chunk, expected):
            hits += 1
    return hits / len(cited_sections)


def best_threshold(positive: list[float], negative: list[float]) -> dict:
    """Pick the abstention threshold that maximises accuracy on the given scores.

    Positives (answerable) should score >= threshold; negatives below it.
    Ties are broken by the largest margin to the nearest score.
    """

    candidates = sorted(set(positive) | set(negative))
    if not candidates:
        return {"threshold": None, "accuracy": None}
    midpoints = [(a + b) / 2 for a, b in zip(candidates, candidates[1:])]
    midpoints = [candidates[0] - 0.5] + midpoints + [candidates[-1] + 0.5]

    best = None
    for threshold in midpoints:
        correct = sum(p >= threshold for p in positive) + sum(n < threshold for n in negative)
        accuracy = correct / (len(positive) + len(negative))
        margin = min(abs(threshold - s) for s in candidates)
        key = (accuracy, margin)
        if best is None or key > best[0]:
            best = (key, threshold)
    return {"threshold": round(best[1], 3), "accuracy": best[0][0], "margin": round(best[0][1], 3)}
