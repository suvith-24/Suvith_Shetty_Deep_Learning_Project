
import pytest

from lexisync.generation.llm_claim_reviewer import LLMClaimReviewer


class MockOllamaClient:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None
        self.last_system_prompt = None
        self.last_temperature = None

    def generate(self, prompt, system_prompt=None, temperature=0.1):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.last_temperature = temperature
        return self.response


class MockQuoteValidator:
    def __init__(self, is_valid=True):
        self.is_valid = is_valid
        self.last_evidence = None
        self.last_quotation = None

    def validate(self, evidence, quotation):
        self.last_evidence = evidence
        self.last_quotation = quotation
        return self.is_valid


def make_response(verdict, evidence, reason="Test explanation"):
    return (
        f"VERDICT: {verdict}\n"
        f"EVIDENCE: {evidence}\n"
        f"REASON: {reason}"
    )


@pytest.fixture
def supported_reviewer():
    response = make_response(
        "SUPPORTED",
        "The controller shall ensure that appropriate safeguards are in place.",
    )
    client = MockOllamaClient(response)
    validator = MockQuoteValidator()

    reviewer = LLMClaimReviewer(
        ollama_client=client,
        quote_validator=validator,
    )
    return reviewer, client, validator


def test_supported_claim_with_valid_quote(supported_reviewer):
    reviewer, client, validator = supported_reviewer

    result = reviewer.verify(
        claim="The controller must ensure appropriate safeguards.",
        evidence=(
            "The controller shall ensure that appropriate safeguards are in place."
        ),
    )

    assert result["status"] == "supported"
    assert result["quotation_valid"] is True
    assert result["quotation"] == (
        "The controller shall ensure that appropriate safeguards are in place."
    )
    assert client.last_temperature == 0
    assert validator.last_quotation == result["quotation"]


def test_contradicted_claim_with_valid_quote():
    response = make_response(
        "CONTRADICTED",
        "The controller shall ensure that appropriate safeguards are in place.",
    )
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="The controller has no responsibility for safeguards.",
        evidence=(
            "The controller shall ensure that appropriate safeguards are in place."
        ),
    )

    assert result["status"] == "contradicted"
    assert result["quotation_valid"] is True


def test_insufficient_evidence_verdict():
    response = make_response(
        "INSUFFICIENT",
        "NONE",
        "The supplied passage does not establish the claim.",
    )
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="Consent is always mandatory.",
        evidence="The controller shall ensure appropriate safeguards.",
    )

    assert result["status"] == "insufficient"
    assert result["quotation"] is None


def test_invalid_quote_returns_inconclusive():
    response = make_response(
        "SUPPORTED",
        "This sentence does not appear in the supplied evidence.",
    )
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(is_valid=False),
    )

    result = reviewer.verify(
        claim="The claim is supported.",
        evidence="The actual evidence says something else.",
    )

    assert result["status"] == "inconclusive"
    assert result["quotation_valid"] is False


def test_malformed_response_returns_inconclusive():
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient("This is not a valid structured response."),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="Some claim.",
        evidence="Some evidence.",
    )

    assert result["status"] == "inconclusive"


def test_missing_evidence_field_returns_inconclusive():
    response = (
        "VERDICT: SUPPORTED\n"
        "REASON: The evidence supports the claim."
    )
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="Some claim.",
        evidence="Some evidence.",
    )

    assert result["status"] == "inconclusive"


def test_invalid_verdict_returns_inconclusive():
    response = make_response("MAYBE", "Some evidence.")
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="Some claim.",
        evidence="Some evidence.",
    )

    assert result["status"] == "inconclusive"


def test_insufficient_verdict_with_unexpected_quote_returns_inconclusive():
    response = make_response(
        "INSUFFICIENT",
        "Some quoted text.",
    )
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )

    result = reviewer.verify(
        claim="Some claim.",
        evidence="Some evidence.",
    )

    assert result["status"] == "inconclusive"


def test_empty_claim_is_rejected():
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(""),
        quote_validator=MockQuoteValidator(),
    )

    with pytest.raises(ValueError):
        reviewer.verify("", "Some evidence.")


def test_empty_evidence_is_rejected():
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(""),
        quote_validator=MockQuoteValidator(),
    )

    with pytest.raises(ValueError):
        reviewer.verify("Some claim.", "")
