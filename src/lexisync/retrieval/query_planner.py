"""Lightweight, deterministic query planning for multi-hop questions.

The planner decides whether a question has several information needs and,
if so, produces one retrieval sub-query per need. It is rule-based on
purpose: it is fast, testable and cannot hallucinate. A question is split
only when it has

* several questions (``?``-separated),
* a coordinated second question (``..., and when may it be extended?``),
* a comparison (``compare``, ``exceed``, ``versus`` ...) between two
  explicitly referenced provisions (``Section 7`` and ``Section 9``), or
* references to two or more distinct provisions (``Article 33 and Article 34``).

Simple questions are never split. Pronouns in later parts ("it", "they")
get the key terms of the first part appended, for retrieval only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "by", "with",
    "what", "which", "when", "where", "who", "whom", "how", "why", "whether",
    "is", "are", "was", "were", "be", "been", "do", "does", "did", "can", "could",
    "may", "might", "must", "shall", "should", "will", "would", "has", "have",
    "it", "its", "they", "them", "their", "this", "that", "these", "those",
    "under", "about", "there", "any", "all", "each", "if", "than", "as", "at",
    "from", "into", "such", "so", "not", "no", "gdpr",
}

_INTERROGATIVE = (
    r"what|which|when|where|who|whom|how|why|whether|does|do|is|are|can|may|must|"
    r"should|will|would|did|has|have"
)

_COORDINATED_SPLIT = re.compile(
    rf",?\s+(?:and|but|while)\s+(?=(?:{_INTERROGATIVE})\b)",
    re.IGNORECASE,
)

_REFERENCE = re.compile(
    r"\b(?:Article|Art\.|Section|Sec\.|Clause|Schedule|Annex|Table|§)\s*"
    r"\d+(?:\.\d+)*(?:\(\d+\))?[A-Za-z]?",
    re.IGNORECASE,
)

_COMPARISON = re.compile(
    r"\b(?:compare|comparison|exceed|exceeds|versus|vs\.?|differ|difference|"
    r"higher|lower|more than|less than|both|conflict|consistent|reconcile)\b",
    re.IGNORECASE,
)

_COMPARISON_WORDS = {
    "compare", "comparison", "exceed", "exceeds", "versus", "vs", "differ",
    "difference", "higher", "lower", "both", "conflict", "consistent", "reconcile",
}

_PRONOUN = re.compile(r"\b(?:it|they|them|this|that|these|those|its|their)\b", re.IGNORECASE)


@dataclass
class QueryPlan:
    """Result of planning: the original question plus retrieval sub-queries."""

    question: str
    sub_queries: list[str] = field(default_factory=list)
    strategy: str = "single"
    references: list[str] = field(default_factory=list)

    @property
    def is_multi_hop(self) -> bool:
        return len(self.sub_queries) > 1

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "sub_queries": self.sub_queries,
            "strategy": self.strategy,
            "is_multi_hop": self.is_multi_hop,
            "references": self.references,
        }


def content_terms(text: str) -> list[str]:
    """Lower-cased content words, in order, without duplicates."""

    words = re.findall(r"[A-Za-z][A-Za-z'-]+|\d+(?:\.\d+)*", text.casefold())
    return list(dict.fromkeys(w for w in words if w not in _STOPWORDS and len(w) > 1))


def _clean(part: str) -> str:
    part = part.strip().strip(",;:").strip()
    return part[:1].upper() + part[1:] if part else part


def _resolve_pronouns(parts: list[str]) -> list[str]:
    """Append the first part's key terms to later parts that use pronouns."""

    if len(parts) < 2:
        return parts

    anchor = " ".join(content_terms(parts[0])[:4])
    resolved = [parts[0]]
    for part in parts[1:]:
        if anchor and _PRONOUN.search(part):
            part = f"{part.rstrip('?')} ({anchor})"
        resolved.append(part)
    return resolved


class QueryPlanner:
    """Rule-based multi-hop query planner."""

    def __init__(self, max_sub_queries: int = 4) -> None:
        if max_sub_queries < 1:
            raise ValueError("max_sub_queries must be at least 1.")
        self.max_sub_queries = max_sub_queries

    def plan(self, question: str) -> QueryPlan:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question cannot be empty.")

        question = " ".join(question.split())
        references = list(dict.fromkeys(m.group(0) for m in _REFERENCE.finditer(question)))

        # 1. Several explicit questions.
        questions = [q for q in re.split(r"(?<=\?)\s+", question) if q.strip()]
        if len(questions) > 1:
            parts = [_clean(q) for q in questions]
            return self._finish(question, parts, "multiple_questions", references)

        # 2. Coordinated second question ("..., and how can it be withdrawn?").
        coordinated = [p for p in _COORDINATED_SPLIT.split(question) if p.strip()]
        if len(coordinated) > 1 and all(len(content_terms(p)) >= 1 for p in coordinated):
            parts = [_clean(p) for p in coordinated]
            return self._finish(question, parts, "coordinated_clauses", references)

        # 3/4. Two or more distinct provisions referenced.
        distinct = list(dict.fromkeys(r.casefold() for r in references))
        if len(distinct) >= 2:
            # Each provision gets the words of its own segment of the question
            # ("the liability cap in Section 7" / "the indemnity obligations in
            # Section 9"); segments with too few words borrow the shared topic.
            matches = list(_REFERENCE.finditer(question))
            topic = content_terms(_REFERENCE.sub(" ", question))[:6]
            parts, previous_end = [], 0
            for index, match in enumerate(matches):
                end = len(question) if index == len(matches) - 1 else match.end()
                segment = _REFERENCE.sub(" ", question[previous_end:end])
                terms = [t for t in content_terms(segment) if t not in _COMPARISON_WORDS]
                if len(terms) < 2:
                    terms = list(dict.fromkeys(terms + topic))
                parts.append(f"{match.group(0)} {' '.join(terms[:6])}".strip())
                previous_end = match.end()
            strategy = "comparison" if _COMPARISON.search(question) else "multi_reference"
            return self._finish(question, parts, strategy, references)

        return QueryPlan(question=question, sub_queries=[question], strategy="single", references=references)

    def _finish(
        self,
        question: str,
        parts: list[str],
        strategy: str,
        references: list[str],
    ) -> QueryPlan:
        parts = _resolve_pronouns(parts)
        parts = list(dict.fromkeys(p for p in parts if p))[: self.max_sub_queries]
        if len(parts) < 2:
            return QueryPlan(question=question, sub_queries=[question], strategy="single", references=references)
        return QueryPlan(question=question, sub_queries=parts, strategy=strategy, references=references)
