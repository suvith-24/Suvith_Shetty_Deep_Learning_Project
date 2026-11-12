"""Cross-document conflict detection (bonus feature 9).

Finds *potential* conflicts between provisions from different documents that
talk about the same thing but state different values of the same kind:

* dates (``31 December 2026`` vs ``31 March 2027``)
* money (``EUR 2.0M`` vs ``EUR 3.5M``)
* percentages
* durations (``five years`` vs ``seven years``, ``72 hours`` vs ``48 hours``)

Two sentences are "about the same thing" when, after removing the values,
they share at least ``MIN_SHARED_TERMS`` content words and their Jaccard
similarity reaches ``TOPIC_SIMILARITY``. Different values on *different*
topics are not conflicts, and equal values on the same topic are recorded as
consistent. The detector never decides which document wins. It reports both
passages and any version signals it can see (amendment wording, document
dates) so the answer can explain the conflict or abstain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations

from lexisync.schemas.document import Chunk


TOPIC_SIMILARITY = 0.3
MIN_SHARED_TERMS = 3

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)
_MONTH_INDEX = {name: index for index, name in enumerate(_MONTHS.split("|"), start=1)}

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty-eight": 48, "sixty": 60,
    "seventy-two": 72, "ninety": 90, "twenty-four": 24, "thirty-six": 36,
    "forty-five": 45, "sixty": 60,
}

_DATE_PATTERNS = [
    re.compile(rf"\b(\d{{1,2}})\s+({_MONTHS})\s+(\d{{4}})\b", re.IGNORECASE),
    re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]

_MONEY = re.compile(
    r"(?:(EUR|USD|GBP|€|\$|£)\s*(\d[\d ,.]*\d|\d)\s*(million|billion|m|bn|k)?\b"
    r"|(\d[\d ,.]*\d|\d)\s*(million|billion|m|bn)?\s*(EUR|USD|GBP|euros?|dollars?|pounds?)\b)",
    re.IGNORECASE,
)

_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|per\s?cent|percent)", re.IGNORECASE)

_DURATION = re.compile(
    r"\b(\d+|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
    r"\s*(?:\(\d+\)\s*)?(?:calendar\s+|business\s+|working\s+)?"
    r"(hours?|days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

_AMENDMENT = re.compile(r"\b(amend\w*|supersed\w*|replac\w*|restat\w*|revis\w*)\b", re.IGNORECASE)

_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "been", "have", "has", "its", "their", "which", "shall", "must", "may",
    "will", "would", "should", "any", "all", "each", "such", "than", "into",
    "under", "within", "after", "before", "not", "only", "other", "upon",
    "where", "when", "unless", "per", "longer", "later", "least", "more", "less",
}

_SCALE = {"k": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
_CURRENCY = {"€": "EUR", "$": "USD", "£": "GBP", "euro": "EUR", "euros": "EUR",
             "dollar": "USD", "dollars": "USD", "pound": "GBP", "pounds": "GBP"}


@dataclass
class Value:
    kind: str          # date | money | percent | duration
    normalized: str    # comparable form
    surface: str       # text as written


@dataclass
class Conflict:
    """A potential conflict between two passages from different documents."""

    kind: str
    value_a: str
    value_b: str
    chunk_a: Chunk
    chunk_b: Chunk
    sentence_a: str
    sentence_b: str
    similarity: float
    shared_terms: list[str] = field(default_factory=list)
    version_note: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "document_a": self.chunk_a.document_id,
            "document_b": self.chunk_b.document_id,
            "chunk_a": self.chunk_a.chunk_id,
            "chunk_b": self.chunk_b.chunk_id,
            "pages_a": self.chunk_a.page_numbers,
            "pages_b": self.chunk_b.page_numbers,
            "section_a": self.chunk_a.section,
            "section_b": self.chunk_b.section,
            "sentence_a": self.sentence_a,
            "sentence_b": self.sentence_b,
            "similarity": round(self.similarity, 3),
            "shared_terms": self.shared_terms,
            "version_note": self.version_note,
        }


def _number(text: str) -> float | None:
    text = text.strip().casefold()
    if text in _NUMBER_WORDS:
        return float(_NUMBER_WORDS[text])
    cleaned = text.replace(" ", "")
    # "3,500,000" thousands commas vs "2,5" decimal comma.
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_values(sentence: str) -> list[Value]:
    """Typed values mentioned in a sentence."""

    values: list[Value] = []
    covered: list[tuple[int, int]] = []

    def free(span):
        return all(span[1] <= s or span[0] >= e for s, e in covered)

    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(sentence):
            groups = match.groups()
            try:
                if pattern is _DATE_PATTERNS[0]:
                    day, month, year = int(groups[0]), _MONTH_INDEX[groups[1].casefold()], int(groups[2])
                elif pattern is _DATE_PATTERNS[1]:
                    month, day, year = _MONTH_INDEX[groups[0].casefold()], int(groups[1]), int(groups[2])
                else:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            except (KeyError, ValueError):
                continue
            values.append(Value("date", f"{year:04d}-{month:02d}-{day:02d}", match.group(0)))
            covered.append(match.span())

    for match in _MONEY.finditer(sentence):
        if not free(match.span()):
            continue
        currency = (match.group(1) or match.group(6) or "").casefold()
        amount = _number(match.group(2) or match.group(4) or "")
        scale = (match.group(3) or match.group(5) or "").casefold()
        if amount is None:
            continue
        amount *= _SCALE.get(scale, 1)
        code = _CURRENCY.get(currency, currency.upper())
        values.append(Value("money", f"{code} {amount:,.0f}", match.group(0).strip()))
        covered.append(match.span())

    for match in _PERCENT.finditer(sentence):
        if not free(match.span()):
            continue
        amount = _number(match.group(1))
        if amount is not None:
            values.append(Value("percent", f"{amount:g}%", match.group(0)))
            covered.append(match.span())

    for match in _DURATION.finditer(sentence):
        if not free(match.span()):
            continue
        amount = _number(match.group(1))
        if amount is None:
            continue
        unit = match.group(2).casefold().rstrip("s")
        values.append(Value("duration", f"{amount:g} {unit}", match.group(0)))
        covered.append(match.span())

    return values


def _topic_terms(sentence: str) -> set[str]:
    stripped = sentence
    for pattern in [*_DATE_PATTERNS, _MONEY, _PERCENT, _DURATION]:
        stripped = pattern.sub(" ", stripped)
    words = re.findall(r"[a-z][a-z-]+", stripped.casefold())
    return {w[:7] for w in words if len(w) > 3 and w not in _STOPWORDS}


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.;:])\s+(?=[A-Z(\d])", text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


class ConflictDetector:
    """Detect potential value conflicts between passages of different documents."""

    def __init__(
        self,
        topic_similarity: float = TOPIC_SIMILARITY,
        min_shared_terms: int = MIN_SHARED_TERMS,
        same_document: bool = False,
    ) -> None:
        self.topic_similarity = topic_similarity
        self.min_shared_terms = min_shared_terms
        self.same_document = same_document

    def detect(
        self,
        chunks: list[Chunk],
        document_dates: dict[str, str] | None = None,
    ) -> list[Conflict]:
        """Return potential conflicts, at most one per (chunk pair, value kind)."""

        document_dates = document_dates or {}
        sentences = []
        for chunk in chunks:
            for sentence in split_sentences(chunk.text):
                values = extract_values(sentence)
                if values:
                    sentences.append((chunk, sentence, values, _topic_terms(sentence)))

        conflicts: list[Conflict] = []
        seen: set[tuple[str, str, str]] = set()

        for (chunk_a, sent_a, vals_a, terms_a), (chunk_b, sent_b, vals_b, terms_b) in combinations(sentences, 2):
            if chunk_a.chunk_id == chunk_b.chunk_id:
                continue
            if not self.same_document and chunk_a.document_id == chunk_b.document_id:
                continue

            shared = terms_a & terms_b
            union = terms_a | terms_b
            similarity = len(shared) / len(union) if union else 0.0
            if len(shared) < self.min_shared_terms or similarity < self.topic_similarity:
                continue

            for kind in ("date", "money", "percent", "duration"):
                a_values = {v.normalized: v for v in vals_a if v.kind == kind}
                b_values = {v.normalized: v for v in vals_b if v.kind == kind}
                if not a_values or not b_values:
                    continue
                if set(a_values) & set(b_values):
                    continue  # at least one value agrees: consistent, not a conflict
                key = tuple(sorted((chunk_a.chunk_id, chunk_b.chunk_id))) + (kind,)
                if key in seen:
                    continue
                seen.add(key)

                value_a = next(iter(a_values.values())).surface
                value_b = next(iter(b_values.values())).surface
                conflicts.append(
                    Conflict(
                        kind=kind,
                        value_a=value_a,
                        value_b=value_b,
                        chunk_a=chunk_a,
                        chunk_b=chunk_b,
                        sentence_a=sent_a,
                        sentence_b=sent_b,
                        similarity=similarity,
                        shared_terms=sorted(shared)[:8],
                        version_note=self._version_note(chunk_a, chunk_b, document_dates),
                    )
                )

        return conflicts

    @staticmethod
    def _version_note(chunk_a: Chunk, chunk_b: Chunk, dates: dict[str, str]) -> str | None:
        notes = []
        for chunk in (chunk_a, chunk_b):
            if _AMENDMENT.search(chunk.text) or _AMENDMENT.search(chunk.document_id):
                notes.append(f"'{chunk.document_id}' contains amendment/replacement wording")
        date_a, date_b = dates.get(chunk_a.document_id), dates.get(chunk_b.document_id)
        if date_a and date_b and date_a != date_b:
            later = chunk_a.document_id if date_a > date_b else chunk_b.document_id
            notes.append(f"'{later}' has the later document date")
        return "; ".join(notes) or None
