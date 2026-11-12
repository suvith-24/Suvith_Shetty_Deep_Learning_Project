
import re

from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class AnswerValidator:
    """
    Validate citation references in generated answers.

    Responsibilities:
    1. Normalize citation formatting.
    2. Extract cited source identifiers.
    3. Detect unknown source identifiers.
    4. Detect missing citations.
    5. Detect genuine abstention responses.

    This validates citation references, not semantic
    claim-to-evidence entailment.
    """

    CITATION_PATTERN = re.compile(
        r"\[(S\d+)\]",
        re.IGNORECASE,
    )

    SOURCE_FORMAT_PATTERN = re.compile(
        r"\[\s*Source\s+(S\d+)\s*\]",
        re.IGNORECASE,
    )

    ABSTENTION_PATTERN = re.compile(
        r"the retrieved documents do not provide sufficient evidence",
        re.IGNORECASE,
    )

    NON_ANSWER_HEADINGS_PATTERN = re.compile(
        r"(?im)^\s*(?:key conditions|limitations|sources)\s*:\s*"
    )

    @classmethod
    def normalize_citations(
        cls,
        answer: str,
    ) -> str:
        """Normalize [Source S1] into [S1]."""

        if not isinstance(answer, str):
            raise TypeError("Answer must be a string.")

        return cls.SOURCE_FORMAT_PATTERN.sub(
            lambda match: f"[{match.group(1).upper()}]",
            answer,
        )

    @classmethod
    def extract_citations(
        cls,
        answer: str,
    ) -> list[str]:
        """Extract unique source identifiers in appearance order."""

        citations = cls.CITATION_PATTERN.findall(answer)

        return list(
            dict.fromkeys(
                citation.upper()
                for citation in citations
            )
        )

    @classmethod
    def _is_abstained(
        cls,
        answer: str,
    ) -> bool:
        """
        Detect abstention only in the answer section.

        Mentions of insufficient evidence in Limitations
        must not turn a substantive answer into an abstention.
        """

        answer_section = cls.NON_ANSWER_HEADINGS_PATTERN.split(
            answer,
            maxsplit=1,
        )[0]

        answer_section = re.sub(
            r"(?im)^\s*answer\s*:\s*",
            "",
            answer_section,
            count=1,
        )

        return bool(
            cls.ABSTENTION_PATTERN.search(answer_section)
        )

    @classmethod
    def validate(
        cls,
        answer: str,
        sources: list[dict],
    ) -> dict:
        """
        Validate generated citations against available sources.
        """

        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Generated answer cannot be empty.")

        if not isinstance(sources, list):
            raise TypeError("Sources must be provided as a list.")

        normalized_answer = cls.normalize_citations(
            answer.strip()
        )

        cited_source_ids = cls.extract_citations(
            normalized_answer
        )

        available_source_ids = {
            source.get("source_id", "").upper()
            for source in sources
            if isinstance(source, dict)
            and isinstance(source.get("source_id"), str)
        }

        unknown_source_ids = [
            source_id
            for source_id in cited_source_ids
            if source_id not in available_source_ids
        ]

        is_abstained = cls._is_abstained(
            normalized_answer
        )

        has_citations = bool(cited_source_ids)

        citations_valid = (
            has_citations
            and not unknown_source_ids
        )

        is_valid = (
            citations_valid
            or is_abstained
        )

        if unknown_source_ids:
            logger.warning(
                "Generated answer contains unknown citations: %s",
                unknown_source_ids,
            )

        if not has_citations and not is_abstained:
            logger.warning(
                "Generated answer contains no source citations."
            )

        return {
            "answer": normalized_answer,
            "is_valid": is_valid,
            "has_citations": has_citations,
            "citations_valid": citations_valid,
            "cited_source_ids": cited_source_ids,
            "unknown_source_ids": unknown_source_ids,
            "abstained": is_abstained,
        }
