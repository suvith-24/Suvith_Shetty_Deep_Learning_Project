import pytest

from lexisync.generation.llm_claim_reviewer import LLMClaimReviewer


class MockOllamaClient:
    def __init__(self, response):
        self.responses = response if isinstance(response, list) else [response]
        self.calls = []
        self.last_prompt = None
        self.last_system_prompt = None
        self.last_temperature = None

    def generate(self, prompt, system_prompt=None, temperature=0.1):
        self.calls.append(prompt)
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.last_temperature = temperature
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


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
    return f"VERDICT: {verdict}\nEVIDENCE: {evidence}\nREASON: {reason}"


@pytest.fixture
def supported_reviewer():
    quote = "The controller shall ensure that appropriate safeguards are in place."
    client = MockOllamaClient(make_response("SUPPORTED", quote))
    validator = MockQuoteValidator()
    reviewer = LLMClaimReviewer(ollama_client=client, quote_validator=validator)
    return reviewer, client, validator


def test_supported_claim_with_valid_quote(supported_reviewer):
    reviewer, client, validator = supported_reviewer
    result = reviewer.verify(
        claim="The controller must ensure appropriate safeguards.",
        evidence="The controller shall ensure that appropriate safeguards are in place.",
    )
    assert result["status"] == "supported"
    assert result["quotation_valid"] is True
    assert result["retry_attempted"] is False
    assert client.last_temperature == 0
    assert validator.last_quotation == result["quotation"]


def test_contradicted_claim_with_valid_quote():
    quote = "The controller shall ensure that appropriate safeguards are in place."
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(make_response("CONTRADICTED", quote)),
        quote_validator=MockQuoteValidator(),
    )
    result = reviewer.verify(
        claim="The controller has no responsibility for safeguards.",
        evidence=quote,
    )
    assert result["status"] == "contradicted"


def test_insufficient_evidence_verdict():
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(make_response(
            "INSUFFICIENT", "NONE", "The supplied passage does not establish the claim."
        )),
        quote_validator=MockQuoteValidator(),
    )
    result = reviewer.verify(
        claim="Consent is always mandatory.",
        evidence="The controller shall ensure appropriate safeguards.",
    )
    assert result["status"] == "insufficient"
    assert result["quotation"] is None


def test_invalid_quote_retries_and_accepts_exact_quote():
    exact_quote = "The controller shall ensure appropriate safeguards."
    client = MockOllamaClient([
        make_response("SUPPORTED", "A paraphrased quotation that is not exact."),
        make_response("SUPPORTED", exact_quote),
    ])
    class RetryQuoteValidator:
        def __init__(self):
            self.results = [False, True]

        def validate(self, evidence, quotation):
            return self.results.pop(0)

    reviewer = LLMClaimReviewer(
        ollama_client=client,
        quote_validator=RetryQuoteValidator(),
    )
    result = reviewer.verify(
        claim="The controller must ensure appropriate safeguards.",
        evidence=exact_quote,
    )
    assert result["status"] == "supported"
    assert result["retry_attempted"] is True
    assert len(client.calls) == 2
    assert "previous response could not be validated" in client.calls[1].casefold()


def test_invalid_quote_after_retry_remains_inconclusive():
    client = MockOllamaClient(make_response(
        "SUPPORTED", "This sentence does not appear in the supplied evidence."
    ))
    reviewer = LLMClaimReviewer(
        ollama_client=client,
        quote_validator=MockQuoteValidator(is_valid=False),
    )
    result = reviewer.verify(
        claim="The claim is supported.",
        evidence="The actual evidence says something else.",
    )
    assert result["status"] == "inconclusive"
    assert result["quotation_valid"] is False
    assert result["retry_attempted"] is True


@pytest.mark.parametrize("response", [
    "This is not a valid structured response.",
    "VERDICT: SUPPORTED\nREASON: Missing evidence field.",
    "VERDICT: MAYBE\nEVIDENCE: Some evidence.\nREASON: Invalid verdict.",
])
def test_malformed_response_retries_then_returns_inconclusive(response):
    reviewer = LLMClaimReviewer(
        ollama_client=MockOllamaClient(response),
        quote_validator=MockQuoteValidator(),
    )
    result = reviewer.verify("Some claim.", "Some evidence.")
    assert result["status"] == "inconclusive"
    assert result["retry_attempted"] is True


def test_insufficient_verdict_with_unexpected_quote_retries():
    client = MockOllamaClient([
        make_response("INSUFFICIENT", "Some quoted text."),
        make_response("INSUFFICIENT", "NONE"),
    ])
    reviewer = LLMClaimReviewer(
        ollama_client=client,
        quote_validator=MockQuoteValidator(),
    )
    result = reviewer.verify("Some claim.", "Some evidence.")
    assert result["status"] == "insufficient"
    assert result["retry_attempted"] is True


def test_empty_claim_is_rejected():
    reviewer = LLMClaimReviewer(ollama_client=MockOllamaClient(""))
    with pytest.raises(ValueError):
        reviewer.verify("", "Some evidence.")


def test_empty_evidence_is_rejected():
    reviewer = LLMClaimReviewer(ollama_client=MockOllamaClient(""))
    with pytest.raises(ValueError):
        reviewer.verify("Some claim.", "")
