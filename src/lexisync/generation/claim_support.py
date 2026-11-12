"""Deterministic claim-support checks.

These checks run before (and instead of, when unambiguous) the LLM claim
reviewer. They are transparent, fast and reproducible:

1. **Citation check**: every cited source ID exists.
2. **Quotation check**: the claim's supporting quote occurs verbatim
   (whitespace/typography-normalised, case-sensitive) in a *cited* source.
3. **Numeric consistency**: every number in the claim (amounts,
   percentages, deadlines, article numbers, including "five" and
   "10 million") occurs in the cited evidence or its section/clause labels.
4. **Lexical coverage**: the share of the claim's content words (prefix
   stemmed) that occur in the cited evidence.
5. **Negation check**: the claim and its quote agree on negation.

Verdicts:

* ``supported``: checks 1–5 all pass with coverage >= ``SUPPORT_COVERAGE``.
* ``unsupported``: a cited ID is unknown, there is no citation, or a number
  in the claim is missing from the cited evidence. These are hard failures
  that an LLM opinion must not override.
* ``needs_review``: everything else; the LLM reviewer decides.

A relevant citation alone never makes a claim supported: the quote must be
in the cited text *and* the claim's own wording and numbers must be covered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lexisync.generation.evidence_quote_validator import (
    EvidenceQuoteValidator,
    normalize_whitespace,
)


SUPPORT_COVERAGE = 0.7
MIN_QUOTE_WORDS = 4

_CITATION = re.compile(r"\[\s*S\d+\s*\]", re.IGNORECASE)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "eighteen": 18, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100,
}

_UNIT_WORDS = (
    r"(?:calendar\s+|working\s+|business\s+|full\s+)?"
    r"(?:hours?|days?|weeks?|months?|years?|times|percent|per\s?cent|"
    r"million|billion|thousand|members?|instances?|copies)\b"
)

_SCALE = {"million": 1_000_000, "m": 1_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000}

_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "been", "being", "have", "has", "had", "its", "their", "there", "which",
    "who", "whom", "what", "when", "where", "how", "why", "will", "would",
    "shall", "should", "may", "might", "must", "can", "could", "also", "such",
    "any", "all", "each", "other", "than", "into", "onto", "upon", "under",
    "about", "these", "those", "them", "they", "his", "her", "not", "only",
    "per", "out", "our", "your", "you", "but", "both", "either", "within",
    "according", "accordance", "pursuant", "referred", "regulation", "article",
    "evidence", "source", "document", "states", "stated", "provides", "provide",
    "specifies", "specified", "says", "require", "requires", "required",
}

_NEGATIONS = {"not", "no", "never", "without", "cannot", "nor", "neither", "none"}


@dataclass
class ClaimAssessment:
    """Outcome of the deterministic checks for one claim."""

    verdict: str  # supported | unsupported | needs_review
    reasons: list[str] = field(default_factory=list)
    quote_valid: bool = False
    quote_source: str | None = None
    numbers_missing: list[str] = field(default_factory=list)
    coverage: float = 0.0
    negation_mismatch: bool = False
    suggested_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reasons": self.reasons,
            "quote_valid": self.quote_valid,
            "quote_source": self.quote_source,
            "numbers_missing": self.numbers_missing,
            "coverage": round(self.coverage, 3),
            "negation_mismatch": self.negation_mismatch,
            "suggested_sources": self.suggested_sources,
        }


def strip_citations(text: str) -> str:
    return _CITATION.sub("", text)


def _canonical_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def extract_numbers(text: str) -> set[str]:
    """Canonical numbers mentioned in text.

    ``10 000 000``, ``10,000,000`` and ``10 million`` all become
    ``"10000000"``; ``2 %`` becomes ``"2"``; ``five`` becomes ``"5"``;
    ``83(4)`` yields ``"83"`` and ``"4"``. Four-digit years are kept.
    """

    text = normalize_whitespace(strip_citations(text)).casefold()

    # Join thousands separators: "10 000 000" / "10,000,000" -> "10000000".
    text = re.sub(
        r"(?<!\d)(\d{1,3}(?:[ ,]\d{3})+)(?!\d)",
        lambda m: re.sub(r"[ ,]", "", m.group(1)),
        text,
    )

    numbers: set[str] = set()
    scaled_spans: set[tuple[int, int]] = set()

    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(million|billion|bn|m)\b", text):
        numbers.add(_canonical_number(float(match.group(1)) * _SCALE[match.group(2)]))
        scaled_spans.add(match.span(1))

    # Plain numbers. Dotted tokens ("7.2", "4.5.2016") are kept whole *and*
    # split into parts; the same rule applies to claim and evidence, so
    # "clause 7.2" matches evidence "7.2".
    for match in re.finditer(r"\d+(?:\.\d+)*", text):
        if match.span() in scaled_spans:
            continue
        token = match.group(0)
        numbers.add(token)
        for part in token.split("."):
            numbers.add(part.lstrip("0") or "0")

    # Number words count only as quantities ("five years", "seventy-two
    # hours"), not in phrases such as "tier one" or "one of the following".
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}(?:-\w+)?\s+(?:\(\d+\)\s+)?{_UNIT_WORDS}", text):
            numbers.add(str(value))
    for match in re.finditer(rf"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)-(one|two|three|four|five|six|seven|eight|nine)\s+{_UNIT_WORDS}", text):
        numbers.add(str(_NUMBER_WORDS[match.group(1)] + _NUMBER_WORDS[match.group(2)]))

    return numbers


def _stem(word: str) -> str:
    return word[:6] if len(word) > 6 else word


def content_stems(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z'-]+", normalize_whitespace(strip_citations(text)).casefold())
    return {_stem(w.strip("'-")) for w in words if len(w) > 2 and w not in _STOPWORDS}


def lexical_coverage(claim: str, evidence: str) -> float:
    """Share of the claim's content stems that occur in the evidence."""

    claim_stems = content_stems(claim)
    if not claim_stems:
        return 0.0
    evidence_stems = content_stems(evidence)
    return len(claim_stems & evidence_stems) / len(claim_stems)


def _negations(text: str) -> set[str]:
    words = set(re.findall(r"[a-z']+", text.casefold()))
    found = words & _NEGATIONS
    if re.search(r"n't\b", text.casefold()):
        found.add("not")
    return found


def assess_claim(
    claim: str,
    cited_ids: list[str],
    quote: str | None,
    sources: dict[str, dict],
) -> ClaimAssessment:
    """Run the deterministic checks for one claim.

    Args:
        claim: Claim text (citations may be embedded).
        cited_ids: Source IDs cited for the claim (``["S1", "S3"]``).
        quote: Verbatim quote offered by the model, or ``None``.
        sources: ``{"S1": {"text": ..., "labels": "Article 83 83(4) ..."}}``.
    """

    assessment = ClaimAssessment(verdict="needs_review")
    cited_ids = [cid.upper() for cid in cited_ids]

    if not cited_ids:
        assessment.verdict = "unsupported"
        assessment.reasons.append("The claim has no source citation.")
        return assessment

    unknown = [cid for cid in cited_ids if cid not in sources]
    if unknown:
        assessment.verdict = "unsupported"
        assessment.reasons.append(f"Unknown source identifiers: {', '.join(unknown)}.")
        return assessment

    cited_text = "\n\n".join(sources[cid]["text"] for cid in cited_ids)
    cited_labels = " ".join(sources[cid].get("labels", "") for cid in cited_ids)

    # Quote check (case-sensitive, typography-normalised). A quote taken from
    # the start of a sentence may have its first letter lower-cased when the
    # model embeds it; only that first character may differ in case.
    if quote and quote.strip() and quote.strip().casefold() != "none":
        quote = quote.strip()
        variants = [quote]
        if quote[0].isalpha():
            variants.append(quote[0].swapcase() + quote[1:])
        for cid in cited_ids:
            if any(EvidenceQuoteValidator.validate(sources[cid]["text"], v) for v in variants):
                assessment.quote_valid = True
                assessment.quote_source = cid
                break
        if not assessment.quote_valid:
            other = [
                sid for sid, data in sources.items()
                if sid not in cited_ids
                and any(EvidenceQuoteValidator.validate(data["text"], v) for v in variants)
            ]
            if other:
                assessment.suggested_sources = other
                assessment.reasons.append(
                    f"The quotation appears in {', '.join(other)}, not in the cited source(s)."
                )
            else:
                assessment.reasons.append("The quotation does not occur verbatim in the cited evidence.")
    else:
        assessment.reasons.append("No supporting quotation was provided.")

    # Numeric consistency.
    available_numbers = extract_numbers(cited_text) | extract_numbers(cited_labels)
    missing = sorted(extract_numbers(claim) - available_numbers, key=lambda n: (len(n), n))
    if missing:
        assessment.numbers_missing = missing
        assessment.verdict = "unsupported"
        assessment.reasons.append(
            "Number(s) not found in the cited evidence: " + ", ".join(missing) + "."
        )

    # Lexical coverage against the cited passages (and their labels).
    assessment.coverage = lexical_coverage(claim, cited_text + "\n" + cited_labels)

    if assessment.quote_valid:
        claim_neg = _negations(strip_citations(claim))
        quote_neg = _negations(quote or "")
        assessment.negation_mismatch = bool(claim_neg) != bool(quote_neg)
        if assessment.negation_mismatch:
            assessment.reasons.append("Negation differs between the claim and its quotation.")

    if assessment.verdict == "unsupported":
        return assessment

    quote_words = len((quote or "").split())
    if (
        assessment.quote_valid
        and quote_words >= MIN_QUOTE_WORDS
        and assessment.coverage >= SUPPORT_COVERAGE
        and not assessment.negation_mismatch
    ):
        assessment.verdict = "supported"
        assessment.reasons = [
            f"Quotation found verbatim in {assessment.quote_source}; "
            f"{assessment.coverage:.0%} of the claim's content words and all its numbers occur in the cited evidence."
        ]
    elif assessment.coverage < SUPPORT_COVERAGE:
        assessment.reasons.append(
            f"Only {assessment.coverage:.0%} of the claim's content words occur in the cited evidence."
        )

    return assessment
