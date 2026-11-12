
from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.generation.answer_validator import AnswerValidator
from lexisync.schemas.document import Chunk


class MockOllama:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def generate(self, prompt, system_prompt=None, temperature=0.1):
        self.last_prompt = prompt
        return self.response


class MockReviewer:
    def __init__(self):
        self.calls = []

    def verify(self, claim, evidence):
        self.calls.append({
            "claim": claim,
            "evidence": evidence,
        })

        return {
            "claim": claim,
            "status": "supported",
            "quotation": evidence,
            "reason": "Mock verification.",
            "quotation_valid": True,
        }


def make_chunk(chunk_id, text, section):
    return Chunk(
        chunk_id=chunk_id,
        document_id="gdpr",
        text=text,
        page_numbers=[60],
        section=section,
        subsection=None,
        start_char=0,
        end_char=len(text),
    )


def make_generator(response):
    ollama = MockOllama(response)
    reviewer = MockReviewer()

    generator = AnswerGenerator(
        ollama_client=ollama,
        answer_validator=AnswerValidator(),
        claim_reviewer=reviewer,
    )

    return generator, ollama, reviewer


def test_context_evidence_gets_separate_source_id():
    primary = make_chunk(
        "primary-1",
        "The controller shall ensure appropriate safeguards.",
        "Article 44",
    )

    context = make_chunk(
        "context-1",
        "Appropriate safeguards include enforceable rights.",
        "Article 46",
    )

    generator = AnswerGenerator(
        ollama_client=MockOllama("Unused"),
        answer_validator=AnswerValidator(),
        claim_reviewer=MockReviewer(),
    )

    evidence_text, sources = generator._format_evidence(
        evidence=[(primary, 0.95)],
        context_evidence=[context],
    )

    assert [source["source_id"] for source in sources] == [
        "S1",
        "S2",
    ]

    assert sources[0]["evidence_type"] == "primary"
    assert sources[1]["evidence_type"] == "context"

    assert "SOURCE ID: [S1]" in evidence_text
    assert "SOURCE ID: [S2]" in evidence_text
    assert "EVIDENCE TYPE: CONTEXT" in evidence_text


def test_contextual_citation_is_verified_against_context_chunk():
    primary = make_chunk(
        "primary-1",
        "The controller shall ensure appropriate safeguards.",
        "Article 44",
    )

    context_text = (
        "Data subjects must have enforceable rights "
        "and effective legal remedies."
    )

    context = make_chunk(
        "context-1",
        context_text,
        "Article 46",
    )

    answer = (
        "Answer:\n"
        "Data subjects must have enforceable rights "
        "and effective legal remedies [S2]."
    )

    generator, ollama, reviewer = make_generator(answer)

    result = generator.generate_answer(
        query="What rights must data subjects have?",
        evidence=[(primary, 0.95)],
        context_evidence=[context],
    )

    assert result["validation"]["citations_valid"] is True
    assert result["validation"]["cited_source_ids"] == ["S2"]

    assert len(reviewer.calls) == 1
    assert reviewer.calls[0]["evidence"] == context_text

    assert "EVIDENCE TYPE: CONTEXT" in ollama.last_prompt


def test_contextual_evidence_is_included_in_citation_repair():
    primary = make_chunk(
        "primary-1",
        "The controller shall ensure appropriate safeguards.",
        "Article 44",
    )

    context = make_chunk(
        "context-1",
        "Data subjects must have enforceable rights.",
        "Article 46",
    )

    class SequenceOllama:
        def __init__(self):
            self.responses = [
                "The data subjects must have enforceable rights.",
                "Data subjects must have enforceable rights [S2].",
            ]
            self.prompts = []

        def generate(self, prompt, system_prompt=None, temperature=0.1):
            self.prompts.append(prompt)
            return self.responses.pop(0)

    ollama = SequenceOllama()

    generator = AnswerGenerator(
        ollama_client=ollama,
        answer_validator=AnswerValidator(),
        claim_reviewer=MockReviewer(),
    )

    result = generator.generate_answer(
        query="What rights must data subjects have?",
        evidence=[(primary, 0.95)],
        context_evidence=[context],
    )

    assert result["citation_repair"]["attempted"] is True
    assert result["citation_repair"]["succeeded"] is True

    repair_prompt = ollama.prompts[1]

    assert "[S2]" in repair_prompt
    assert "Data subjects must have enforceable rights." in repair_prompt
    assert "EVIDENCE TYPE: CONTEXT" in repair_prompt
