
import pytest

from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.generation.answer_validator import AnswerValidator
from lexisync.schemas.document import Chunk


class SequenceOllamaClient:
    """Return predefined responses in sequence."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, prompt, system_prompt=None, temperature=0.1):
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
        })

        if not self.responses:
            raise RuntimeError("No mock responses remaining.")

        return self.responses.pop(0)


class MockClaimReviewer:
    def __init__(self, status="supported"):
        self.status = status
        self.calls = []

    def verify(self, claim, evidence):
        self.calls.append({
            "claim": claim,
            "evidence": evidence,
        })

        return {
            "claim": claim,
            "status": self.status,
            "quotation": "The controller shall ensure safeguards.",
            "reason": "Mock verification.",
            "quotation_valid": True,
            "raw_response": "Mock response",
        }


def make_chunk():
    text = "The controller shall ensure appropriate safeguards."

    return Chunk(
        chunk_id="chunk-1",
        document_id="gdpr",
        text=text,
        page_numbers=[60],
        section="Article 44",
        subsection=None,
        start_char=0,
        end_char=len(text),
        metadata={},
    )


def make_generator(responses):
    ollama = SequenceOllamaClient(responses)
    reviewer = MockClaimReviewer()

    generator = AnswerGenerator(
        ollama_client=ollama,
        answer_validator=AnswerValidator(),
        claim_reviewer=reviewer,
    )

    return generator, ollama, reviewer


def make_evidence():
    return [(make_chunk(), 6.5)]


def test_missing_citations_trigger_successful_repair():
    responses = [
        (
            "Answer:\n"
            "The controller must ensure appropriate safeguards."
        ),
        (
            "Answer:\n"
            "The controller must ensure appropriate safeguards [S1]."
        ),
    ]

    generator, ollama, reviewer = make_generator(responses)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=make_evidence(),
    )

    assert len(ollama.calls) == 2

    assert result["citation_repair"]["attempted"] is True
    assert result["citation_repair"]["succeeded"] is True

    assert result["validation"]["citations_valid"] is True
    assert result["validation"]["cited_source_ids"] == ["S1"]

    assert result["claim_verification"]["supported"] == 1
    assert len(reviewer.calls) == 1


def test_failed_repair_does_not_verify_uncited_claims():
    responses = [
        "The controller must ensure appropriate safeguards.",
        "The controller must ensure appropriate safeguards.",
    ]

    generator, ollama, reviewer = make_generator(responses)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=make_evidence(),
    )

    assert len(ollama.calls) == 2

    assert result["citation_repair"]["attempted"] is True
    assert result["citation_repair"]["succeeded"] is False

    assert result["validation"]["citations_valid"] is False

    assert result["claim_verification"]["inconclusive"] >= 1
    assert result["claim_verification"]["supported"] == 0

    assert len(reviewer.calls) == 0


def test_unknown_source_after_repair_is_rejected():
    responses = [
        "The controller must ensure appropriate safeguards.",
        "The controller must ensure appropriate safeguards [S99].",
    ]

    generator, ollama, reviewer = make_generator(responses)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=make_evidence(),
    )

    assert len(ollama.calls) == 2

    assert result["citation_repair"]["attempted"] is True
    assert result["citation_repair"]["succeeded"] is False

    assert result["validation"]["unknown_source_ids"] == ["S99"]

    assert result["claim_verification"]["inconclusive"] >= 1
    assert len(reviewer.calls) == 0


def test_valid_initial_citations_do_not_trigger_repair():
    responses = [
        "The controller must ensure appropriate safeguards [S1].",
    ]

    generator, ollama, reviewer = make_generator(responses)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=make_evidence(),
    )

    assert len(ollama.calls) == 1

    assert result["citation_repair"]["attempted"] is False
    assert result["citation_repair"]["succeeded"] is False

    assert result["validation"]["citations_valid"] is True
    assert len(reviewer.calls) == 1


def test_abstention_does_not_trigger_citation_repair():
    responses = [
        (
            "The retrieved documents do not provide sufficient "
            "evidence to answer this question reliably."
        ),
    ]

    generator, ollama, reviewer = make_generator(responses)

    result = generator.generate_answer(
        query="What is the requirement?",
        evidence=make_evidence(),
    )

    assert len(ollama.calls) == 1

    assert result["abstained"] is True
    assert result["citation_repair"]["attempted"] is False

    assert result["claim_verification"]["total_claims"] == 0
    assert len(reviewer.calls) == 0


def test_repair_prompt_contains_authoritative_source_mapping():
    responses = [
        "The controller must ensure appropriate safeguards.",
        "The controller must ensure appropriate safeguards [S1].",
    ]

    generator, ollama, _ = make_generator(responses)

    generator.generate_answer(
        query="What must the controller do?",
        evidence=make_evidence(),
    )

    repair_prompt = ollama.calls[1]["prompt"]

    assert "[S1]" in repair_prompt
    assert "Article 44" in repair_prompt
    assert "ORIGINAL GENERATED ANSWER" in repair_prompt
    assert "RETRIEVED LEGAL EVIDENCE" in repair_prompt
