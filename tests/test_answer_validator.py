
import pytest

from lexisync.generation.answer_validator import AnswerValidator


@pytest.fixture
def available_sources():
    return [
        {
            "source_id": "S1",
            "document_id": "gdpr",
            "pages": [60],
        },
        {
            "source_id": "S2",
            "document_id": "gdpr",
            "pages": [61],
        },
    ]


def test_normalize_source_citation_format():
    answer = "Article 44 establishes the general principle [Source S1]."

    result = AnswerValidator.normalize_citations(answer)

    assert result == "Article 44 establishes the general principle [S1]."


def test_normalize_multiple_citations():
    answer = "Transfers are governed by [Source S1] and [Source S2]."

    result = AnswerValidator.normalize_citations(answer)

    assert result == "Transfers are governed by [S1] and [S2]."


def test_extract_citations():
    answer = "Article 44 [S1] and Article 45 [S2] support this conclusion [S1]."

    result = AnswerValidator.extract_citations(answer)

    assert result == ["S1", "S2"]


def test_extract_citations_is_case_insensitive():
    answer = "Supported by [s1] and [s2]."

    result = AnswerValidator.extract_citations(answer)

    assert result == ["S1", "S2"]


def test_valid_answer_with_known_citations(available_sources):
    answer = "Article 44 establishes the general principle [S1]."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["is_valid"] is True
    assert result["has_citations"] is True
    assert result["citations_valid"] is True
    assert result["cited_source_ids"] == ["S1"]
    assert result["unknown_source_ids"] == []
    assert result["abstained"] is False


def test_unknown_citation_is_invalid(available_sources):
    answer = "The transfer is permitted under Article 47 [S3]."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["is_valid"] is False
    assert result["citations_valid"] is False
    assert result["unknown_source_ids"] == ["S3"]


def test_answer_without_citations_is_invalid(available_sources):
    answer = "Personal data transfers must follow GDPR requirements."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["is_valid"] is False
    assert result["has_citations"] is False
    assert result["citations_valid"] is False


def test_abstention_without_citations_is_valid(available_sources):
    answer = (
        "The retrieved documents do not provide sufficient evidence "
        "to answer this question reliably."
    )

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["is_valid"] is True
    assert result["abstained"] is True
    assert result["has_citations"] is False


def test_valid_answer_normalizes_citations(available_sources):
    answer = "Article 44 establishes the general principle [Source S1]."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["answer"] == (
        "Article 44 establishes the general principle [S1]."
    )


def test_duplicate_citations_are_removed(available_sources):
    answer = "Article 44 [S1], Article 45 [S1], and Article 46 [S2]."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["cited_source_ids"] == ["S1", "S2"]


def test_empty_answer_raises_error(available_sources):
    with pytest.raises(ValueError, match="cannot be empty"):
        AnswerValidator.validate(
            "",
            available_sources,
        )


def test_non_string_answer_raises_error(available_sources):
    with pytest.raises(ValueError, match="cannot be empty"):
        AnswerValidator.validate(
            None,
            available_sources,
        )


def test_invalid_sources_type_raises_error():
    with pytest.raises(TypeError, match="list"):
        AnswerValidator.validate(
            "Article 44 [S1].",
            None,
        )


def test_unknown_and_known_citations_are_detected(available_sources):
    answer = "Article 44 [S1] and Article 47 [S3]."

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["is_valid"] is False
    assert result["cited_source_ids"] == ["S1", "S3"]
    assert result["unknown_source_ids"] == ["S3"]


def test_source_format_with_extra_whitespace():
    answer = "Article 44 [ Source   S1 ]."

    result = AnswerValidator.normalize_citations(answer)

    assert result == "Article 44 [S1]."


def test_limitation_mention_does_not_trigger_abstention(
    available_sources,
):
    answer = """
    Answer:
    Article 44 establishes the general transfer principle [S1].

    Limitations:
    The retrieved documents do not provide sufficient evidence
    about every possible transfer mechanism.
    """

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["abstained"] is False
    assert result["is_valid"] is True
    assert result["citations_valid"] is True


def test_missing_citations_with_limitation_is_invalid(
    available_sources,
):
    answer = """
    Answer:
    Article 44 establishes the general transfer principle.

    Limitations:
    The retrieved documents do not provide sufficient evidence
    about every possible transfer mechanism.
    """

    result = AnswerValidator.validate(
        answer,
        available_sources,
    )

    assert result["abstained"] is False
    assert result["is_valid"] is False
    assert result["has_citations"] is False
