
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline
from lexisync.retrieval.query_expander import StaticQueryExpander
from lexisync.schemas.document import Chunk


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------


@pytest.fixture
def sample_chunk():
    return Chunk(
        chunk_id="gdpr_article_44",
        document_id="gdpr",
        text=(
            "Personal data may only be transferred to a third "
            "country under the conditions laid down in this Chapter."
        ),
        page_numbers=[60],
        section="CHAPTER V",
        subsection="Article 44",
    )


@pytest.fixture
def second_chunk():
    return Chunk(
        chunk_id="gdpr_article_46",
        document_id="gdpr",
        text=(
            "Transfers may take place where appropriate "
            "safeguards are provided."
        ),
        page_numbers=[62],
        section="CHAPTER V",
        subsection="Article 46",
    )


@pytest.fixture
def mock_dependencies(monkeypatch, sample_chunk):
    import lexisync.retrieval.retrieval_pipeline as module

    fake_indexing_pipeline = MagicMock()
    fake_indexing_pipeline.load.return_value = SimpleNamespace(
        chunks=[sample_chunk]
    )

    fake_bm25 = MagicMock()
    fake_hybrid = MagicMock()
    fake_reranker = MagicMock()

    monkeypatch.setattr(
        module,
        "BM25Retriever",
        MagicMock(return_value=fake_bm25),
    )

    monkeypatch.setattr(
        module,
        "HybridRetriever",
        MagicMock(return_value=fake_hybrid),
    )

    monkeypatch.setattr(
        module,
        "CrossEncoderReranker",
        MagicMock(return_value=fake_reranker),
    )

    return SimpleNamespace(
        indexing_pipeline=fake_indexing_pipeline,
        bm25=fake_bm25,
        hybrid=fake_hybrid,
        reranker=fake_reranker,
    )


def create_pipeline(
    mock_dependencies,
    query_expander=None,
    **pipeline_kwargs,
):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
        query_expander=query_expander,
        **pipeline_kwargs,
    )

    pipeline.initialize()

    return pipeline


# ---------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------


def test_pipeline_starts_uninitialized():
    pipeline = RetrievalPipeline(
        indexing_pipeline=MagicMock(),
        reranker=MagicMock(),
    )

    assert pipeline.is_initialized is False


def test_search_before_initialization_raises_error():
    pipeline = RetrievalPipeline(
        indexing_pipeline=MagicMock(),
        reranker=MagicMock(),
    )

    with pytest.raises(RuntimeError, match="not initialized"):
        pipeline.search("What is GDPR?")


def test_initialize_loads_existing_index(mock_dependencies):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    mock_dependencies.indexing_pipeline.load.assert_called_once()

    assert pipeline.is_initialized is True


def test_initialize_creates_retrieval_components(mock_dependencies):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    assert pipeline.bm25_retriever is mock_dependencies.bm25
    assert pipeline.hybrid_retriever is mock_dependencies.hybrid
    assert pipeline.reranker is mock_dependencies.reranker


def test_initialize_is_idempotent(mock_dependencies):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()
    pipeline.initialize()

    mock_dependencies.indexing_pipeline.load.assert_called_once()


def test_initialize_rejects_empty_loaded_index(mock_dependencies):
    mock_dependencies.indexing_pipeline.load.return_value = (
        SimpleNamespace(chunks=[])
    )

    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    with pytest.raises(ValueError, match="no document chunks"):
        pipeline.initialize()

    assert pipeline.is_initialized is False


def test_initialize_creates_default_reranker(
    monkeypatch,
    mock_dependencies,
):
    import lexisync.retrieval.retrieval_pipeline as module

    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
    )

    pipeline.initialize()

    module.CrossEncoderReranker.assert_called_once()

    assert pipeline.reranker is not None


def test_invalid_constructor_parameters():
    with pytest.raises(ValueError, match="candidate_k"):
        RetrievalPipeline(candidate_k=0)

    with pytest.raises(ValueError, match="top_k"):
        RetrievalPipeline(top_k=0)

    with pytest.raises(ValueError, match="multi_query_rrf_k"):
        RetrievalPipeline(multi_query_rrf_k=0)


# ---------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", None])
def test_search_rejects_empty_query(
    mock_dependencies,
    query,
):
    pipeline = create_pipeline(mock_dependencies)

    with pytest.raises(ValueError, match="query cannot be empty"):
        pipeline.search(query)


def test_search_rejects_invalid_top_k(mock_dependencies):
    pipeline = create_pipeline(mock_dependencies)

    with pytest.raises(ValueError, match="top_k"):
        pipeline.search("What is GDPR?", top_k=0)


def test_search_rejects_invalid_candidate_k(mock_dependencies):
    pipeline = create_pipeline(mock_dependencies)

    with pytest.raises(ValueError, match="candidate_k"):
        pipeline.search("What is GDPR?", candidate_k=0)


# ---------------------------------------------------------
# Existing retrieval tests
# ---------------------------------------------------------


def test_search_executes_hybrid_retrieval_and_reranking(
    mock_dependencies,
    sample_chunk,
):
    pipeline = create_pipeline(mock_dependencies)

    candidates = [(sample_chunk, 0.03)]
    expected_results = [(sample_chunk, 6.5)]

    mock_dependencies.hybrid.search.return_value = candidates
    mock_dependencies.reranker.rerank.return_value = expected_results

    query = "What conditions apply to international data transfers?"

    results = pipeline.search(query)

    mock_dependencies.hybrid.search.assert_called_once_with(
        query=query,
        top_k=20,
        candidate_k=20,
    )

    mock_dependencies.reranker.rerank.assert_called_once_with(
        query=query,
        candidates=candidates,
        top_k=5,
    )

    assert results == expected_results


def test_search_supports_custom_limits(
    mock_dependencies,
    sample_chunk,
):
    pipeline = create_pipeline(mock_dependencies)

    candidates = [(sample_chunk, 0.03)]

    mock_dependencies.hybrid.search.return_value = candidates

    mock_dependencies.reranker.rerank.return_value = [
        (sample_chunk, 6.5)
    ]

    pipeline.search(
        "What is GDPR?",
        top_k=3,
        candidate_k=12,
    )

    mock_dependencies.hybrid.search.assert_called_once_with(
        query="What is GDPR?",
        top_k=12,
        candidate_k=12,
    )

    mock_dependencies.reranker.rerank.assert_called_once_with(
        query="What is GDPR?",
        candidates=candidates,
        top_k=3,
    )


def test_search_returns_empty_when_no_candidates(
    mock_dependencies,
):
    pipeline = create_pipeline(mock_dependencies)

    mock_dependencies.hybrid.search.return_value = []

    results = pipeline.search("What is GDPR?")

    assert results == []

    mock_dependencies.reranker.rerank.assert_not_called()


# ---------------------------------------------------------
# Multi-query retrieval tests
# ---------------------------------------------------------


def test_query_expander_preserves_original_query(
    mock_dependencies,
    sample_chunk,
):
    original_query = "What conditions apply to data transfers?"
    expanded_query = "appropriate safeguards third country"

    expander = StaticQueryExpander(
        lambda query: [expanded_query]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    # Both queries must return candidates to reach reranking.
    mock_dependencies.hybrid.search.return_value = [
        (sample_chunk, 0.03)
    ]

    pipeline.search(original_query)

    calls = mock_dependencies.hybrid.search.call_args_list

    assert len(calls) == 2

    assert calls[0].kwargs["query"] == original_query
    assert calls[1].kwargs["query"] == expanded_query

    # Cross-encoder must evaluate against the original question.
    assert (
        mock_dependencies.reranker.rerank.call_args.kwargs["query"]
        == original_query
    )


def test_query_expander_removes_duplicate_queries(
    mock_dependencies,
):
    original_query = "What is GDPR?"

    expander = StaticQueryExpander(
        lambda query: [
            "What is GDPR?",
            "  what is gdpr?  ",
            "GDPR legal requirements",
            "GDPR legal requirements",
        ]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    mock_dependencies.hybrid.search.return_value = []

    pipeline.search(original_query)

    calls = mock_dependencies.hybrid.search.call_args_list

    assert len(calls) == 2

    assert calls[0].kwargs["query"] == original_query

    assert (
        calls[1].kwargs["query"]
        == "GDPR legal requirements"
    )


def test_multi_query_rrf_combines_rankings(
    mock_dependencies,
    sample_chunk,
    second_chunk,
):
    expander = StaticQueryExpander(
        lambda query: ["appropriate safeguards"]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
        multi_query_rrf_k=60,
    )

    # Article 44 ranks first in both queries.
    first_query_results = [
        (sample_chunk, 0.9),
        (second_chunk, 0.8),
    ]

    second_query_results = [
        (sample_chunk, 0.95),
        (second_chunk, 0.7),
    ]

    mock_dependencies.hybrid.search.side_effect = [
        first_query_results,
        second_query_results,
    ]

    mock_dependencies.reranker.rerank.return_value = []

    pipeline.search(
        "What conditions apply to data transfers?"
    )

    reranker_candidates = (
        mock_dependencies.reranker.rerank.call_args.kwargs[
            "candidates"
        ]
    )

    expected_sample_score = (1 / 61) + (1 / 61)
    expected_second_score = (1 / 62) + (1 / 62)

    assert len(reranker_candidates) == 2

    assert (
        reranker_candidates[0][0].chunk_id
        == sample_chunk.chunk_id
    )

    assert (
        reranker_candidates[1][0].chunk_id
        == second_chunk.chunk_id
    )

    assert reranker_candidates[0][1] == pytest.approx(
        expected_sample_score
    )

    assert reranker_candidates[1][1] == pytest.approx(
        expected_second_score
    )

    assert (
        reranker_candidates[0][1]
        > reranker_candidates[1][1]
    )


def test_multi_query_rrf_deduplicates_chunks(
    mock_dependencies,
    sample_chunk,
    second_chunk,
):
    expander = StaticQueryExpander(
        lambda query: ["Article 46 safeguards"]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    mock_dependencies.hybrid.search.side_effect = [
        [
            (sample_chunk, 0.9),
            (second_chunk, 0.8),
        ],
        [
            (sample_chunk, 0.95),
        ],
    ]

    mock_dependencies.reranker.rerank.return_value = []

    pipeline.search("What conditions apply?")

    candidates = (
        mock_dependencies.reranker.rerank.call_args.kwargs[
            "candidates"
        ]
    )

    chunk_ids = [
        chunk.chunk_id
        for chunk, _ in candidates
    ]

    assert len(chunk_ids) == 2
    assert len(set(chunk_ids)) == 2


def test_multi_query_rrf_uses_deterministic_tie_breaking(
    mock_dependencies,
    sample_chunk,
    second_chunk,
):
    expander = StaticQueryExpander(
        lambda query: ["safeguards"]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    mock_dependencies.hybrid.search.side_effect = [
        [
            (second_chunk, 0.9),
            (sample_chunk, 0.8),
        ],
        [
            (sample_chunk, 0.9),
            (second_chunk, 0.8),
        ],
    ]

    mock_dependencies.reranker.rerank.return_value = []

    pipeline.search("What conditions apply?")

    candidates = (
        mock_dependencies.reranker.rerank.call_args.kwargs[
            "candidates"
        ]
    )

    assert [
        chunk.chunk_id
        for chunk, _ in candidates
    ] == [
        "gdpr_article_44",
        "gdpr_article_46",
    ]


def test_expanded_queries_with_no_results_do_not_break_search(
    mock_dependencies,
    sample_chunk,
):
    expander = StaticQueryExpander(
        lambda query: ["irrelevant query"]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    original_candidates = [(sample_chunk, 0.03)]

    mock_dependencies.hybrid.search.side_effect = [
        original_candidates,
        [],
    ]

    mock_dependencies.reranker.rerank.return_value = [
        (sample_chunk, 6.5)
    ]

    results = pipeline.search("What is GDPR?")

    assert results == [(sample_chunk, 6.5)]

    mock_dependencies.reranker.rerank.assert_called_once()

    assert (
        mock_dependencies.reranker.rerank.call_args.kwargs[
            "candidates"
        ]
        == original_candidates
    )


def test_all_expanded_queries_without_results_return_empty(
    mock_dependencies,
):
    expander = StaticQueryExpander(
        lambda query: ["expanded query"]
    )

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=expander,
    )

    mock_dependencies.hybrid.search.return_value = []

    results = pipeline.search("What is GDPR?")

    assert results == []

    mock_dependencies.reranker.rerank.assert_not_called()


def test_query_expander_must_return_a_list(
    mock_dependencies,
):
    class InvalidExpander:
        def expand(self, query):
            return "not a list"

    pipeline = create_pipeline(
        mock_dependencies,
        query_expander=InvalidExpander(),
    )

    with pytest.raises(TypeError, match="list of strings"):
        pipeline.search("What is GDPR?")
