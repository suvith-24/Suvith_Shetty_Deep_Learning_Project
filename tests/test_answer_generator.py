
import pytest

from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.schemas.document import Chunk


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


class MockAnswerValidator:
    def __init__(self, answer=None, abstained=False):
        self.answer = answer
        self.abstained = abstained
        self.last_sources = None

    def validate(self, answer, sources):
        self.last_sources = sources

        normalized_answer = self.answer if self.answer is not None else answer

        citations = AnswerGenerator.CITATION_PATTERN.findall(
            normalized_answer
        )

        known_ids = {
            source["source_id"]
            for source in sources
        }

        unknown_ids = [
            source_id.upper()
            for source_id in citations
            if source_id.upper() not in known_ids
        ]

        return {
            "answer": normalized_answer,
            "is_valid": not unknown_ids,
            "has_citations": bool(citations),
            "citations_valid": not unknown_ids and bool(citations),
            "cited_source_ids": list(
                dict.fromkeys(
                    source_id.upper()
                    for source_id in citations
                )
            ),
            "unknown_source_ids": unknown_ids,
            "abstained": self.abstained,
        }


class MockClaimReviewer:
    def __init__(self, status="supported", raise_error=False):
        self.status = status
        self.raise_error = raise_error
        self.calls = []

    def verify(self, claim, evidence):
        self.calls.append({
            "claim": claim,
            "evidence": evidence,
        })

        if self.raise_error:
            raise RuntimeError("Mock reviewer failure")

        return {
            "claim": claim,
            "status": self.status,
            "quotation": "Mock evidence quotation",
            "reason": "Mock verification result",
            "quotation_valid": True,
            "raw_response": "Mock response",
        }


def make_chunk(
    chunk_id="chunk-1",
    document_id="document-1",
    text="The controller shall ensure appropriate safeguards.",
    section="Article 44",
):
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        page_numbers=[10],
        section=section,
        subsection=None,
        start_char=0,
        end_char=len(text),
        metadata={},
    )


def make_generator(
    answer,
    reviewer=None,
    validator=None,
):
    ollama = MockOllamaClient(answer)

    answer_validator = validator or MockAnswerValidator()

    claim_reviewer = reviewer or MockClaimReviewer()

    generator = AnswerGenerator(
        ollama_client=ollama,
        answer_validator=answer_validator,
        claim_reviewer=claim_reviewer,
    )

    return generator, ollama, answer_validator, claim_reviewer


def test_extract_claims_with_single_citation():
    answer = (
        "Answer:\n"
        "The controller must ensure appropriate safeguards [S1].\n"
        "Key Conditions:\n"
        "Appropriate safeguards must be implemented [S1].\n"
        "Limitations:\n"
        "The retrieved excerpt does not explain every safeguard [S1]."
    )

    claims = AnswerGenerator._extract_claims(answer)

    assert len(claims) == 3

    assert claims[0]["source_ids"] == ["S1"]
    assert claims[1]["source_ids"] == ["S1"]
    assert claims[2]["source_ids"] == ["S1"]


def test_extract_claims_with_multiple_citations():
    answer = (
        "The controller must ensure safeguards [S1][S2]."
    )

    claims = AnswerGenerator._extract_claims(answer)

    assert len(claims) == 1
    assert claims[0]["source_ids"] == ["S1", "S2"]


def test_extract_claims_without_citation():
    answer = "The controller must ensure safeguards."

    claims = AnswerGenerator._extract_claims(answer)

    assert len(claims) == 1
    assert claims[0]["source_ids"] == []


def test_detects_uncited_claim_among_cited_claims():
    answer = (
        "The controller must ensure safeguards [S1].\\n"
        "The processor must follow instructions."
    )

    assert AnswerGenerator._has_uncited_claims(answer) is True


def test_all_claims_cited_passes_uncited_claim_check():
    answer = (
        "The controller must ensure safeguards [S1].\\n"
        "The processor must follow instructions [S2]."
    )

    assert AnswerGenerator._has_uncited_claims(answer) is False


def test_extract_claims_removes_markdown_list_markers():
    answer = (
        "Key Conditions:\n"
        "- The controller must ensure safeguards [S1].\n"
        "- Appropriate protection must be maintained [S2]."
    )

    claims = AnswerGenerator._extract_claims(answer)

    assert len(claims) == 2
    assert claims[0]["source_ids"] == ["S1"]
    assert claims[1]["source_ids"] == ["S2"]


def test_supported_claim_is_verified():
    answer = (
        "Answer:\n"
        "The controller must ensure safeguards [S1]."
    )

    generator, _, _, reviewer = make_generator(answer)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["claim_verification"]["total_claims"] == 1
    assert result["claim_verification"]["supported"] == 1
    assert result["claim_verification"]["all_claims_supported"] is True
    assert len(reviewer.calls) == 1


@pytest.mark.parametrize(
    "status",
    [
        "supported",
        "contradicted",
        "insufficient",
        "inconclusive",
    ],
)
def test_all_claim_verification_statuses_are_counted(status):
    answer = "The controller must ensure safeguards [S1]."

    reviewer = MockClaimReviewer(status=status)

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["claim_verification"][status] == 1
    assert result["claim_verification"]["total_claims"] == 1


def test_claim_is_checked_against_its_cited_source_only():
    answer = (
        "The controller must ensure safeguards [S1].\n"
        "The processor must follow instructions [S2]."
    )

    reviewer = MockClaimReviewer()

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    first_chunk = make_chunk(
        chunk_id="chunk-1",
        text="The controller shall ensure appropriate safeguards.",
    )

    second_chunk = make_chunk(
        chunk_id="chunk-2",
        document_id="document-2",
        text="The processor shall follow documented instructions.",
        section="Article 28",
    )

    generator.generate_answer(
        query="Explain the obligations.",
        evidence=[
            (first_chunk, 0.95),
            (second_chunk, 0.90),
        ],
    )

    assert len(reviewer.calls) == 2

    assert reviewer.calls[0]["evidence"] == first_chunk.text
    assert reviewer.calls[1]["evidence"] == second_chunk.text


def test_multiple_cited_sources_are_combined():
    answer = "The claim is supported by both passages [S1][S2]."

    reviewer = MockClaimReviewer()

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    first_chunk = make_chunk(
        chunk_id="chunk-1",
        text="First evidence passage.",
    )

    second_chunk = make_chunk(
        chunk_id="chunk-2",
        text="Second evidence passage.",
    )

    generator.generate_answer(
        query="What do the documents establish?",
        evidence=[
            (first_chunk, 0.95),
            (second_chunk, 0.90),
        ],
    )

    assert len(reviewer.calls) == 1

    assert reviewer.calls[0]["evidence"] == (
        "First evidence passage.\n\nSecond evidence passage."
    )


def test_uncited_claim_is_marked_inconclusive():
    answer = "The controller must ensure safeguards."

    reviewer = MockClaimReviewer()

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["claim_verification"]["inconclusive"] == 1
    assert result["claim_verification"]["supported"] == 0

    # The reviewer must not be called without a source mapping.
    assert len(reviewer.calls) == 0


def test_unknown_source_identifier_is_inconclusive():
    answer = "The controller must ensure safeguards [S99]."

    reviewer = MockClaimReviewer()

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["claim_verification"]["inconclusive"] == 1
    assert len(reviewer.calls) == 0


def test_reviewer_exception_does_not_crash_generation():
    answer = "The controller must ensure safeguards [S1]."

    reviewer = MockClaimReviewer(raise_error=True)

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
    )

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["claim_verification"]["inconclusive"] == 1
    assert result["claim_verification"]["supported"] == 0


def test_abstained_answer_skips_claim_verification():
    answer = (
        "The retrieved documents do not provide sufficient "
        "evidence to answer this question reliably."
    )

    validator = MockAnswerValidator(abstained=True)

    reviewer = MockClaimReviewer()

    generator, _, _, _ = make_generator(
        answer,
        reviewer=reviewer,
        validator=validator,
    )

    result = generator.generate_answer(
        query="What is the legal requirement?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["abstained"] is True
    assert result["claim_verification"]["total_claims"] == 0
    assert len(reviewer.calls) == 0


def test_empty_evidence_returns_abstention():
    generator, _, _, reviewer = make_generator(
        "Unused response."
    )

    result = generator.generate_answer(
        query="What are the requirements?",
        evidence=[],
    )

    assert result["abstained"] is True
    assert result["sources"] == []
    assert result["claim_verification"]["total_claims"] == 0
    assert len(reviewer.calls) == 0


def test_original_generated_answer_is_preserved():
    answer = (
        "Answer:\n"
        "The controller must ensure safeguards [S1]."
    )

    generator, _, _, _ = make_generator(answer)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert result["answer"] == answer


def test_claim_verification_is_included_in_validation():
    answer = "The controller must ensure safeguards [S1]."

    generator, _, _, _ = make_generator(answer)

    result = generator.generate_answer(
        query="What must the controller do?",
        evidence=[
            (make_chunk(), 0.95),
        ],
    )

    assert "all_claims_supported" in result["validation"]
    assert "claim_verification" in result


def test_duplicate_citations_are_removed():
    answer = "The controller must ensure safeguards [S1][S1]."

    claims = AnswerGenerator._extract_claims(answer)

    assert len(claims) == 1
    assert claims[0]["source_ids"] == ["S1"]
