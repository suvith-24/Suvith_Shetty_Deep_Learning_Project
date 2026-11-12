
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline
from lexisync.schemas.document import Chunk


@pytest.fixture
def sample_chunk():
    return Chunk(
        chunk_id="gdpr_article_44",
        document_id="gdpr",
        text="Personal data may only be transferred to a third country under the conditions laid down in this Chapter.",
        page_numbers=[60],
        section="CHAPTER V",
        subsection="Article 44",
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


@pytest.mark.parametrize("query", ["", "   ", None])
def test_search_rejects_empty_query(
    mock_dependencies,
    query,
):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    with pytest.raises(ValueError, match="query cannot be empty"):
        pipeline.search(query)


def test_search_rejects_invalid_top_k(mock_dependencies):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    with pytest.raises(ValueError, match="top_k"):
        pipeline.search("What is GDPR?", top_k=0)


def test_search_rejects_invalid_candidate_k(mock_dependencies):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    with pytest.raises(ValueError, match="candidate_k"):
        pipeline.search("What is GDPR?", candidate_k=0)


def test_search_executes_hybrid_retrieval_and_reranking(
    mock_dependencies,
    sample_chunk,
):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    candidates = [(sample_chunk, 0.03)]
    expected_results = [(sample_chunk, 6.5)]

    mock_dependencies.hybrid.search.return_value = candidates
    mock_dependencies.reranker.rerank.return_value = expected_results

    results = pipeline.search(
        "What conditions apply to international data transfers?"
    )

    mock_dependencies.hybrid.search.assert_called_once_with(
        query="What conditions apply to international data transfers?",
        top_k=20,
        candidate_k=20,
    )

    mock_dependencies.reranker.rerank.assert_called_once_with(
        query="What conditions apply to international data transfers?",
        candidates=candidates,
        top_k=5,
    )

    assert results == expected_results


def test_search_supports_custom_limits(
    mock_dependencies,
    sample_chunk,
):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
        candidate_k=20,
        top_k=5,
    )

    pipeline.initialize()

    mock_dependencies.hybrid.search.return_value = [
        (sample_chunk, 0.03)
    ]

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
        candidates=[(sample_chunk, 0.03)],
        top_k=3,
    )


def test_search_returns_empty_when_no_candidates(
    mock_dependencies,
):
    pipeline = RetrievalPipeline(
        indexing_pipeline=mock_dependencies.indexing_pipeline,
        reranker=mock_dependencies.reranker,
    )

    pipeline.initialize()

    mock_dependencies.hybrid.search.return_value = []

    results = pipeline.search("What is GDPR?")

    assert results == []

    mock_dependencies.reranker.rerank.assert_not_called()
