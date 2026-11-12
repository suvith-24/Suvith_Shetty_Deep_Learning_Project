
import re

from lexisync.generation.ollama_client import OllamaClient
from lexisync.generation.evidence_quote_validator import (
    EvidenceQuoteValidator,
)
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class LLMClaimReviewer:
    """
    Review an individual legal claim against supplied evidence
    using a local Ollama model.

    Possible outcomes:
    - supported
    - contradicted
    - insufficient
    - inconclusive

    Supported and contradicted results require an exact
    quotation validated against the original evidence.
    """

    SYSTEM_PROMPT = """
You are a strict legal evidence verification system.

Your responsibility is to compare an individual factual claim
against the supplied evidence passage.

Rules:
1. Use only the supplied evidence.
2. Do not use external legal knowledge.
3. Evaluate every factual assertion in the claim.
4. SUPPORTED means the evidence establishes the complete claim.
5. CONTRADICTED means the evidence explicitly conflicts with
   at least one factual assertion.
6. INSUFFICIENT means the evidence neither establishes nor
   explicitly contradicts the complete claim.
7. Pay attention to qualifiers such as only, every, all,
   must, may, automatically, and unless.
8. A necessary condition must not automatically be treated
   as a sufficient condition.
9. Do not infer support from unrelated sentences.
10. Never invent, paraphrase, translate, or modify quotations.
11. Copy evidence quotations exactly, preserving wording,
    spelling, capitalization, and punctuation.
12. Return the quotation without surrounding quotation marks.

Return exactly these three fields:

VERDICT: SUPPORTED / CONTRADICTED / INSUFFICIENT
EVIDENCE: Exact quotation or NONE
REASON: One concise explanation
"""

    VERDICT_MAP = {
        "SUPPORTED": "supported",
        "CONTRADICTED": "contradicted",
        "INSUFFICIENT": "insufficient",
    }

    def __init__(
        self,
        ollama_client=None,
        quote_validator=None,
    ):
        self.ollama_client = ollama_client or OllamaClient()

        self.quote_validator = (
            quote_validator or EvidenceQuoteValidator()
        )

        logger.info("LLM claim reviewer initialized.")

    @staticmethod
    def _remove_quote_wrappers(quotation: str) -> str:
        """Remove one pair of surrounding quotation marks."""

        quotation = quotation.strip()

        wrappers = [
            ('"', '"'),
            ("'", "'"),
            ("“", "”"),
            ("‘", "’"),
        ]

        for opening, closing in wrappers:
            if (
                quotation.startswith(opening)
                and quotation.endswith(closing)
                and len(quotation) >= 2
            ):
                return quotation[1:-1].strip()

        return quotation

    @classmethod
    def _parse_response(cls, response: str) -> dict:
        """
        Parse a structured response from Ollama.

        Supports multi-line evidence quotations.
        """

        if not isinstance(response, str) or not response.strip():
            return {
                "valid": False,
                "reason": "Empty model response.",
            }

        verdict_match = re.search(
            r"^\s*VERDICT:\s*(SUPPORTED|CONTRADICTED|INSUFFICIENT)\s*$",
            response,
            re.IGNORECASE | re.MULTILINE,
        )

        evidence_match = re.search(
            r"^\s*EVIDENCE:\s*(.*?)"
            r"(?=^\s*REASON:)",
            response,
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )

        reason_match = re.search(
            r"^\s*REASON:\s*(.+?)\s*$",
            response,
            re.IGNORECASE | re.MULTILINE,
        )

        if not all(
            [verdict_match, evidence_match, reason_match]
        ):
            return {
                "valid": False,
                "reason": "Model response does not follow the required format.",
            }

        verdict = verdict_match.group(1).upper()

        quotation = cls._remove_quote_wrappers(
            evidence_match.group(1).strip()
        )

        reason = reason_match.group(1).strip()

        if not reason:
            return {
                "valid": False,
                "reason": "Model response contains an empty explanation.",
            }

        return {
            "valid": True,
            "verdict": verdict,
            "quotation": quotation,
            "reason": reason,
        }

    def verify(
        self,
        claim: str,
        evidence: str,
    ) -> dict:
        """
        Review a claim against one evidence passage.

        A supported or contradicted result is accepted only
        when its quotation passes exact validation.
        """

        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("Claim must be a non-empty string.")

        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("Evidence must be a non-empty string.")

        prompt = f"""
EVIDENCE:
{evidence.strip()}

CLAIM:
{claim.strip()}

Compare the claim against the evidence.

Identify all factual assertions and check whether each is
supported or contradicted by the supplied passage.

Return the required structured response.
"""

        response = self.ollama_client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.0,
        )

        parsed = self._parse_response(response)

        if not parsed["valid"]:
            logger.warning(
                "Claim review rejected: %s",
                parsed["reason"],
            )

            return {
                "claim": claim.strip(),
                "status": "inconclusive",
                "quotation": None,
                "reason": parsed["reason"],
                "quotation_valid": False,
                "raw_response": response,
            }

        verdict = parsed["verdict"]
        quotation = parsed["quotation"]
        reason = parsed["reason"]

        status = self.VERDICT_MAP[verdict]

        if status == "insufficient":
            if quotation.casefold() != "none":
                logger.warning(
                    "Insufficient verdict contained an unexpected quotation."
                )

                return {
                    "claim": claim.strip(),
                    "status": "inconclusive",
                    "quotation": None,
                    "reason": (
                        "Insufficient verdict must not contain "
                        "a supporting quotation."
                    ),
                    "quotation_valid": False,
                    "raw_response": response,
                }

            return {
                "claim": claim.strip(),
                "status": "insufficient",
                "quotation": None,
                "reason": reason,
                "quotation_valid": True,
                "raw_response": response,
            }

        if quotation.casefold() == "none" or not quotation:
            logger.warning(
                "Claim review rejected: missing evidence quotation."
            )

            return {
                "claim": claim.strip(),
                "status": "inconclusive",
                "quotation": None,
                "reason": (
                    "A supporting or contradicting quotation is required."
                ),
                "quotation_valid": False,
                "raw_response": response,
            }

        quotation_valid = self.quote_validator.validate(
            evidence=evidence,
            quotation=quotation,
        )

        if not quotation_valid:
            logger.warning(
                "Claim review rejected: quotation does not match evidence."
            )

            return {
                "claim": claim.strip(),
                "status": "inconclusive",
                "quotation": None,
                "reason": (
                    "Generated quotation failed exact evidence validation."
                ),
                "quotation_valid": False,
                "raw_response": response,
            }

        result = {
            "claim": claim.strip(),
            "status": status,
            "quotation": quotation,
            "reason": reason,
            "quotation_valid": True,
            "raw_response": response,
        }

        logger.info(
            "LLM claim review completed: %s",
            status,
        )

        return result
