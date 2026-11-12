import re
import unicodedata


_TYPOGRAPHIC = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "‒": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
    "­": None,
})


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace and typography without modifying the wording.

    Preserves:
    - Capitalization
    - Spelling
    - Word order

    Normalizes only characters that print identically or near-identically:
    curly vs straight quotes, en/em dashes vs hyphens, non-breaking spaces,
    soft hyphens and Unicode compatibility forms (e.g. the "fi" ligature).
    """

    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHIC)
    return re.sub(r"\s+", " ", text).strip()


def _strip_edge_punctuation(text: str) -> str:
    """Remove sentence punctuation a model may add at the quote's edges."""

    return text.strip().strip(".,;:").strip()


class EvidenceQuoteValidator:
    """
    Validate whether a generated quotation exists verbatim
    in the original evidence passage.

    Only whitespace, typographic and edge-punctuation differences are tolerated.
    """

    @staticmethod
    def validate(
        evidence: str,
        quotation: str,
    ) -> bool:
        """
        Return True only if the quotation occurs in the evidence.

        Line breaks and repeated whitespace are normalized,
        but wording, capitalization and inner punctuation must match.
        """

        if not isinstance(evidence, str) or not evidence.strip():
            return False

        if not isinstance(quotation, str) or not quotation.strip():
            return False

        normalized_evidence = normalize_whitespace(evidence)
        normalized_quotation = _strip_edge_punctuation(
            normalize_whitespace(quotation)
        )

        if not normalized_quotation:
            return False

        return normalized_quotation in normalized_evidence

    @staticmethod
    def validate_multiple(
        evidence_passages: list[str],
        quotation: str,
    ) -> bool:
        """
        Check whether a quotation occurs in at least one
        supplied evidence passage.
        """

        if not isinstance(evidence_passages, list):
            return False

        return any(
            EvidenceQuoteValidator.validate(passage, quotation)
            for passage in evidence_passages
        )
