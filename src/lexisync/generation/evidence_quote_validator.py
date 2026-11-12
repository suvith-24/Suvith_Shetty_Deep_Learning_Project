
import re


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace without modifying the actual wording.

    Preserves:
    - Capitalization
    - Punctuation
    - Spelling
    - Word order
    """

    return re.sub(r"\s+", " ", text).strip()


class EvidenceQuoteValidator:
    """
    Validate whether a generated quotation exists verbatim
    in the original evidence passage.

    Only whitespace differences are tolerated.
    """

    @staticmethod
    def validate(
        evidence: str,
        quotation: str,
    ) -> bool:
        """
        Return True only if the quotation occurs in the evidence.

        Line breaks and repeated whitespace are normalized,
        but wording and punctuation must match.
        """

        if not isinstance(evidence, str) or not evidence.strip():
            return False

        if not isinstance(quotation, str) or not quotation.strip():
            return False

        normalized_evidence = normalize_whitespace(evidence)
        normalized_quotation = normalize_whitespace(quotation)

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
