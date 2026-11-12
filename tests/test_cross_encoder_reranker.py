
import numpy as np
import pytest

from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker
from lexisync.schemas.document import Chunk


class MockCrossEncoder:
    """Mock cross-encoder with deterministic relevance scores."""

    def predict(
        self,
        sentences,
        batch_size=16,
        show_progress_bar=False,
        convert_to_numpy=True,
    ):
        scores = []

        for query, passage in sentences:
            passage = passage.casefold()

            if "appropriate safeguards" in passage:
                score = 0.95

            elif "personal data transfer" in passage:
                score = 0.85

            elif "data subject access" in passage:
                score = 0.40

            else:
                score = 0.10

            scores.append(score)

        return np.asarray(
            scores,
            dtype=np.float32,
        )


class InvalidScoreModel:
    """Mock model that returns an invalid number of scores."""

    def predict(self, sentences, **kwargs):
        return np.asarray([0.5], dtype=np.float32)


@pytest.fixture
def sample_candidates():
    chunks = [
        Chunk(
            chunk_id="chunk_1",
            document_id="gdpr",
            text="The data subject has the right to access personal data.",
            page_numbers=[15],
            section="Article 15",
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="gdpr",
            text="Personal data transfer to a third country is regulated.",
            page_numbers=[60],
            section="Article 44",
        ),
        Chunk(
            chunk_id="chunk_3",
            document_id="gdpr",
            text="Transfers to a third country require appropriate safeguards.",
            page_numbers=[61],
            section="Article 46",
        ),
    ]

    return [
        (chunks[0], 0.025),
        (chunks[1], 0.024),
        (chunks[2], 0.023),
    ]


@pytest.fixture
def reranker():
    return CrossEncoderReranker(
        model=MockCrossEncoder(),
        batch_size=2,
    )


def test_reranker_initialization(reranker):
    assert reranker.batch_size == 2


def test_rerank_returns_results(reranker, sample_candidates):
    results = reranker.rerank(
        query="Can personal data be transferred to a third country?",
        candidates=sample_candidates,
    )

    assert len(results) == 3


def test_rerank_orders_by_relevance(reranker, sample_candidates):
    results = reranker.rerank(
        query="Can personal data be transferred to a third country?",
        candidates=sample_candidates,
    )

    chunk_ids = [
        chunk.chunk_id
        for chunk, _ in results
    ]

    assert chunk_ids == [
        "chunk_3",
        "chunk_2",
        "chunk_1",
    ]


def test_rerank_respects_top_k(reranker, sample_candidates):
    results = reranker.rerank(
        query="third country transfer",
        candidates=sample_candidates,
        top_k=2,
    )

    assert len(results) == 2


def test_empty_candidates_return_empty_list(reranker):
    results = reranker.rerank(
        query="third country transfer",
        candidates=[],
    )

    assert results == []


def test_empty_query_raises_error(reranker, sample_candidates):
    with pytest.raises(ValueError):
        reranker.rerank(
            query="",
            candidates=sample_candidates,
        )


def test_whitespace_query_raises_error(reranker, sample_candidates):
    with pytest.raises(ValueError):
        reranker.rerank(
            query="   ",
            candidates=sample_candidates,
        )


def test_invalid_top_k_raises_error(reranker, sample_candidates):
    with pytest.raises(ValueError):
        reranker.rerank(
            query="third country",
            candidates=sample_candidates,
            top_k=0,
        )


def test_invalid_batch_size_raises_error():
    with pytest.raises(ValueError):
        CrossEncoderReranker(
            model=MockCrossEncoder(),
            batch_size=0,
        )


def test_reranking_preserves_chunk_metadata(
    reranker,
    sample_candidates,
):
    results = reranker.rerank(
        query="third country transfer",
        candidates=sample_candidates,
        top_k=1,
    )

    chunk, score = results[0]

    assert chunk.page_numbers == [61]
    assert chunk.section == "Article 46"
    assert score == pytest.approx(0.95)


def test_invalid_score_count_raises_error(sample_candidates):
    reranker = CrossEncoderReranker(
        model=InvalidScoreModel(),
    )

    with pytest.raises(ValueError):
        reranker.rerank(
            query="third country transfer",
            candidates=sample_candidates,
        )


def test_tied_scores_preserve_original_order(sample_candidates):
    class TiedScoreModel:
        def predict(self, sentences, **kwargs):
            return np.asarray(
                [0.5] * len(sentences),
                dtype=np.float32,
            )

    reranker = CrossEncoderReranker(
        model=TiedScoreModel(),
    )

    results = reranker.rerank(
        query="personal data",
        candidates=sample_candidates,
    )

    chunk_ids = [
        chunk.chunk_id
        for chunk, _ in results
    ]

    assert chunk_ids == [
        "chunk_1",
        "chunk_2",
        "chunk_3",
    ]
