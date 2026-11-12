"""Text helpers shared by the retrievers."""

from __future__ import annotations

import re

from lexisync.schemas.document import Chunk


_BASE_TOKEN = re.compile(r"\b[\w-]+\b")

# Legal identifiers that the base tokenizer would split: 7.2, 7.2.1, 83(4), 58(2)(a)
_CLAUSE_TOKEN = re.compile(r"\b\d+(?:\.\d+)+\b|\b\d+(?:\([0-9a-z]{1,3}\))+")

# "Article 83", "Art. 83", "Section 7.2", "clause 9", "§ 5"
_REFERENCE_TOKEN = re.compile(
    r"\b(article|art\.?|section|sec\.?|clause|paragraph|para\.?|schedule|annex|§)\s*"
    r"(\d+(?:\.\d+)*[a-z]?)",
    re.IGNORECASE,
)

_REFERENCE_KIND = {
    "art": "article",
    "art.": "article",
    "sec": "section",
    "sec.": "section",
    "para": "paragraph",
    "para.": "paragraph",
}


def legal_tokens(text: str) -> list[str]:
    """Tokenise text for BM25, keeping clause numbers intact.

    The base tokens are unchanged from the original tokenizer. Extra tokens
    are appended so exact references match exactly: ``7.2`` and ``83(4)``
    as whole tokens, plus ``article:83`` / ``section:7.2`` reference tokens.
    """

    lowered = text.casefold()
    tokens = _BASE_TOKEN.findall(lowered)
    tokens.extend(_CLAUSE_TOKEN.findall(lowered))

    for kind, number in _REFERENCE_TOKEN.findall(lowered):
        kind = _REFERENCE_KIND.get(kind, kind)
        tokens.append(f"{kind}:{number}")
        major = number.split(".")[0]
        if major != number:
            tokens.append(f"{kind}:{major}")

    return tokens


def index_text(chunk: Chunk, contextual: bool) -> str:
    """Text used for indexing/reranking a chunk.

    With ``contextual`` the section heading (and clause/table label) is
    prepended when it is not already at the start of the chunk. Later
    paragraphs of a long article are then still findable by the article's
    number and title.
    """

    if not contextual:
        return chunk.text

    labels = []
    if chunk.section and chunk.section != "General":
        labels.append(chunk.section)
    if chunk.subsection and chunk.subsection not in (chunk.section or ""):
        labels.append(f"({chunk.subsection})")

    header = " ".join(labels)
    if not header or chunk.text.startswith(header):
        return chunk.text

    first_line = chunk.text.split("\n", 1)[0].strip()
    if chunk.section and first_line and chunk.section.startswith(first_line):
        return chunk.text

    return f"{header}\n{chunk.text}"
