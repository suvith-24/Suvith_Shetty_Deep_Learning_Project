
import pytest

from lexisync.retrieval.query_expander import (
    NoOpQueryExpander,
    StaticQueryExpander,
)


def test_noop_expander_returns_no_additional_queries():
    expander = NoOpQueryExpander()

    assert expander.expand("What is GDPR?") == []


@pytest.mark.parametrize("query", ["", "   ", None])
def test_noop_expander_rejects_invalid_query(query):
    expander = NoOpQueryExpander()

    with pytest.raises(ValueError):
        expander.expand(query)


def test_static_expander_returns_additional_queries():
    expander = StaticQueryExpander(
        lambda query: [
            "appropriate safeguards",
            "effective legal remedies",
        ]
    )

    results = expander.expand("What is GDPR?")

    assert results == [
        "appropriate safeguards",
        "effective legal remedies",
    ]


def test_static_expander_removes_duplicate_queries():
    expander = StaticQueryExpander(
        lambda query: [
            "GDPR transfers",
            "gdpr transfers",
            "GDPR transfers ",
        ]
    )

    results = expander.expand("What is GDPR?")

    assert results == ["GDPR transfers"]


def test_static_expander_removes_original_query():
    expander = StaticQueryExpander(
        lambda query: [
            "What is GDPR?",
            "Additional legal requirements",
        ]
    )

    results = expander.expand("What is GDPR?")

    assert results == ["Additional legal requirements"]


def test_static_expander_strips_whitespace():
    expander = StaticQueryExpander(
        lambda query: ["  Article 46 safeguards  "]
    )

    results = expander.expand("What is GDPR?")

    assert results == ["Article 46 safeguards"]


def test_static_expander_ignores_invalid_items():
    expander = StaticQueryExpander(
        lambda query: [
            "Valid query",
            "",
            "   ",
            None,
            123,
        ]
    )

    results = expander.expand("What is GDPR?")

    assert results == ["Valid query"]


def test_static_expander_requires_callable():
    with pytest.raises(TypeError):
        StaticQueryExpander("not callable")


def test_static_expander_requires_list_result():
    expander = StaticQueryExpander(
        lambda query: "not a list"
    )

    with pytest.raises(TypeError):
        expander.expand("What is GDPR?")


@pytest.mark.parametrize("query", ["", "   ", None])
def test_static_expander_rejects_invalid_query(query):
    expander = StaticQueryExpander(lambda query: [])

    with pytest.raises(ValueError):
        expander.expand(query)
