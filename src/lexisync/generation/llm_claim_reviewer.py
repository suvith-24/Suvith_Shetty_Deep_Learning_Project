import re

from lexisync.generation.ollama_client import OllamaClient
from lexisync.generation.evidence_quote_validator import EvidenceQuoteValidator
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class LLMClaimReviewer:
    """
    Review an individual legal claim against supplied evidence.

    Supported and contradicted outcomes require an exact quotation.
    Malformed model output or an invalid quotation gets one corrective
    retry. The retry never relaxes the evidence or quotation checks.
    """

    SYSTEM_PROMPT = """
You are a strict legal evidence verification system.

Compare one factual claim against only the supplied evidence passage.

Rules:
1. Use only the supplied evidence; do not use external knowledge.
2. Evaluate every factual assertion in the claim.
3. SUPPORTED means the evidence establishes the complete claim.
4. CONTRADICTED means the evidence explicitly conflicts with at least
   one factual assertion.
5. INSUFFICIENT means the evidence neither establishes nor explicitly
   contradicts the complete claim.
6. Pay attention to qualifiers such as only, every, all, must, may,
   automatically, and unless.
7. Do not infer support from unrelated sentences.
8. For SUPPORTED or CONTRADICTED, copy one contiguous quotation
   verbatim from the evidence. Do not paraphrase it.
9. For INSUFFICIENT, return EVIDENCE: NONE.
10. Return exactly the three fields below. Do not add Markdown fences.

VERDICT: SUPPORTED / CONTRADICTED / INSUFFICIENT
EVIDENCE: Exact quotation or NONE
REASON: One concise explanation
"""

    RETRY_INSTRUCTION = """
Your previous response could not be validated.

Re-evaluate the same claim using only the evidence below. Return exactly:
VERDICT: SUPPORTED, CONTRADICTED, or INSUFFICIENT
EVIDENCE: For SUPPORTED or CONTRADICTED, copy a short contiguous
quotation character-for-character from the evidence. For INSUFFICIENT,
write NONE.
REASON: One concise explanation.

Do not paraphrase the quotation. Do not add any other fields.
"""

    VERDICT_MAP = {
        "SUPPORTED": "supported",
        "CONTRADICTED": "contradicted",
        "INSUFFICIENT": "insufficient",
    }

    def __init__(self, ollama_client=None, quote_validator=None):
        self.ollama_client = ollama_client or OllamaClient()
        self.quote_validator = quote_validator or EvidenceQuoteValidator()
        logger.info("LLM claim reviewer initialized.")

    @staticmethod
    def _remove_quote_wrappers(quotation: str) -> str:
        quotation = quotation.strip()
        wrappers = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
        for opening, closing in wrappers:
            if quotation.startswith(opening) and quotation.endswith(closing) and len(quotation) >= 2:
                return quotation[1:-1].strip()
        return quotation

    @classmethod
    def _parse_response(cls, response: str) -> dict:
        if not isinstance(response, str) or not response.strip():
            return {"valid": False, "reason": "Empty model response."}

        verdict_match = re.search(
            r"^\s*VERDICT:\s*(SUPPORTED|CONTRADICTED|INSUFFICIENT)\s*$",
            response, re.IGNORECASE | re.MULTILINE,
        )
        evidence_match = re.search(
            r"^\s*EVIDENCE:\s*(.*?)" r"(?=^\s*REASON:)",
            response, re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        reason_match = re.search(
            r"^\s*REASON:\s*(.+?)\s*$",
            response, re.IGNORECASE | re.MULTILINE,
        )

        if not all([verdict_match, evidence_match, reason_match]):
            return {
                "valid": False,
                "reason": "Model response does not follow the required format.",
            }

        quotation = cls._remove_quote_wrappers(evidence_match.group(1).strip())
        reason = reason_match.group(1).strip()
        if not reason:
            return {"valid": False, "reason": "Model response contains an empty explanation."}

        return {
            "valid": True,
            "verdict": verdict_match.group(1).upper(),
            "quotation": quotation,
            "reason": reason,
        }

    def _response_is_usable(self, parsed: dict, evidence: str) -> tuple[bool, str]:
        if not parsed.get("valid"):
            return False, parsed.get("reason", "Malformed model response.")

        if parsed["verdict"] == "INSUFFICIENT":
            if parsed["quotation"].casefold() == "none":
                return True, ""
            return False, "Insufficient verdict must use EVIDENCE: NONE."

        quotation = parsed["quotation"]
        if not quotation or quotation.casefold() == "none":
            return False, "A supporting or contradicting quotation is required."

        if not self.quote_validator.validate(evidence=evidence, quotation=quotation):
            return False, "Generated quotation failed exact evidence validation."

        return True, ""

    def verify(self, claim: str, evidence: str) -> dict:
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("Claim must be a non-empty string.")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("Evidence must be a non-empty string.")

        prompt = f"""
EVIDENCE:
{evidence.strip()}

CLAIM:
{claim.strip()}

Identify all factual assertions and decide whether the complete claim
is supported, contradicted, or insufficiently established.
Return the required structured response.
"""

        response = self.ollama_client.generate(
            prompt=prompt, system_prompt=self.SYSTEM_PROMPT, temperature=0.0,
        )
        parsed = self._parse_response(response)
        usable, failure_reason = self._response_is_usable(parsed, evidence)

        retry_attempted = False
        if not usable:
            retry_attempted = True
            logger.warning(
                "Claim review output was not verifiable; retrying once: %s",
                failure_reason,
            )
            retry_prompt = f"""
{self.RETRY_INSTRUCTION}

EVIDENCE:
{evidence.strip()}

CLAIM:
{claim.strip()}
"""
            response = self.ollama_client.generate(
                prompt=retry_prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.0,
            )
            parsed = self._parse_response(response)
            usable, failure_reason = self._response_is_usable(parsed, evidence)

        if not usable:
            logger.warning("Claim review remains inconclusive: %s", failure_reason)
            return {
                "claim": claim.strip(),
                "status": "inconclusive",
                "quotation": None,
                "reason": failure_reason,
                "quotation_valid": False,
                "retry_attempted": retry_attempted,
                "raw_response": response,
            }

        status = self.VERDICT_MAP[parsed["verdict"]]
        quotation = parsed["quotation"] if status != "insufficient" else None
        result = {
            "claim": claim.strip(),
            "status": status,
            "quotation": quotation,
            "reason": parsed["reason"],
            "quotation_valid": True,
            "retry_attempted": retry_attempted,
            "raw_response": response,
        }
        logger.info("LLM claim review completed: %s", status)
        return result
