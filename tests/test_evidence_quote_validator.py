
import pytest

from lexisync.generation.evidence_quote_validator import (
    EvidenceQuoteValidator,
)


@pytest.fixture
def evidence():
    return """
    Any transfer of personal data to a third country or to an
    international organisation shall take place only if the
    conditions laid down in this Chapter are complied with by
    the controller and processor.
    """


def test_exact_quote_is_valid(evidence):
    quotation = (
        "Any transfer of personal data to a third country or to an "
        "international organisation shall take place only if the "
        "conditions laid down in this Chapter are complied with by "
        "the controller and processor."
    )

    assert EvidenceQuoteValidator.validate(evidence, quotation)


def test_line_break_differences_are_allowed(evidence):
    quotation = (
        "Any transfer of personal data to a third country or to an\n"
        "international organisation shall take place only if the\n"
        "conditions laid down in this Chapter are complied with by\n"
        "the controller and processor."
    )

    assert EvidenceQuoteValidator.validate(evidence, quotation)


def test_changed_spelling_is_rejected(evidence):
    quotation = (
        "Any transfer of personal data to a third country or to an "
        "international organization shall take place only if the "
        "conditions laid down in this Chapter are complied with by "
        "the controller and processor."
    )

    assert not EvidenceQuoteValidator.validate(evidence, quotation)


def test_changed_capitalization_is_rejected(evidence):
    quotation = (
        "any transfer of personal data to a third country or to an "
        "international organisation"
    )

    assert not EvidenceQuoteValidator.validate(evidence, quotation)


def test_changed_word_is_rejected(evidence):
    quotation = (
        "Any transfer of personal data to a third country or to an "
        "international organisation shall take place only if the "
        "conditions are complied with by the controller and processor."
    )

    assert not EvidenceQuoteValidator.validate(evidence, quotation)


def test_empty_quotation_is_rejected(evidence):
    assert not EvidenceQuoteValidator.validate(evidence, "")


def test_empty_evidence_is_rejected():
    assert not EvidenceQuoteValidator.validate("", "Some quotation")


def test_non_string_inputs_are_rejected():
    assert not EvidenceQuoteValidator.validate(None, "Some quotation")
    assert not EvidenceQuoteValidator.validate("Some evidence", None)


def test_quote_found_in_multiple_passages():
    passages = [
        "Article 42 discusses certification.",
        "The controller and processor must comply with Chapter V.",
    ]

    quotation = "The controller and processor must comply with Chapter V."

    assert EvidenceQuoteValidator.validate_multiple(
        passages,
        quotation,
    )


def test_quote_missing_from_all_passages():
    passages = [
        "Article 42 discusses certification.",
        "Article 43 discusses certification bodies.",
    ]

    assert not EvidenceQuoteValidator.validate_multiple(
        passages,
        "The controller must notify the EDPB.",
    )
