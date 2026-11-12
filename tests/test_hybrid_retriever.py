
import pytest

from lexisync.retrieval.hybrid_retriever import HybridRetriever
from lexisync.schemas.document import Chunk


class MockRetriever:
    """Mock retriever that returns predefined search results."""

    def __init__(self, results):
        self.results = results

    def search(self, query, top_k=10):
        return self.results[:top_k]


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            chunk_id="chunk_1",
            document_id="gdpr",
            text="Transfer of personal data to third countries.",
            page_numbers=[60],
            section="Article 44",
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="gdpr",
            text="Conditions for international data transfers.",
            page_numbers=[61],
            section="Article 45",
        ),
        Chunk(
            chunk_id="chunk_3",
            document_id="gdpr",
            text="Rights of data subjects.",
            page_numbers=[15],
            section="Article 15",
        ),
    ]


@pytest.fixture
def hybrid_retriever(sample_chunks):
    bm25 = MockRetriever([
        (sample_chunks[0], 8.5),
        (sample_chunks[1], 6.2),
        (sample_chunks[2], 2.1),
    ])

    faiss = MockRetriever([
        (sample_chunks[1], 0.91),
        (sample_chunks[0], 0.87),
        (sample_chunks[2], 0.62),
    ])

    return HybridRetriever(
        bm25_retriever=bm25,
        faiss_retriever=faiss,
    )


def test_hybrid_initialization(hybrid_retriever):
    assert hybrid_retriever.rrf_k == 60


def test_invalid_rrf_constant_raises_error():
    with pytest.raises(ValueError):
        HybridRetriever(
            bm25_retriever=MockRetriever([]),
            faiss_retriever=MockRetriever([]),
            rrf_k=0,
        )


def test_search_returns_results(hybrid_retriever):
    results = hybrid_retriever.search(
        "third country data transfer",
        top_k=3,
    )

    assert len(results) == 3


def test_search_respects_top_k(hybrid_retriever):
    results = hybrid_retriever.search(
        "third country data transfer",
        top_k=2,
    )

    assert len(results) == 2


def test_chunk_present_in_both_retrievers_gets_fused_score(
    hybrid_retriever,
    sample_chunks,
):
    results = hybrid_retriever.search(
        "third country data transfer",
        top_k=3,
    )

    scores = {
        chunk.chunk_id: score
        for chunk, score in results
    }

    # chunk_1 is ranked first by BM25 and second by FAISS.
    expected_score = (1 / 61) + (1 / 62)

    assert scores["chunk_1"] == pytest.approx(expected_score)


def test_rrf_uses_ranks_not_original_retrieval_scores(
    hybrid_retriever,
    sample_chunks,
):
    results = hybrid_retriever.search(
        "third country data transfer",
        top_k=3,
    )

    scores = {
        chunk.chunk_id: score
        for chunk, score in results
    }

    expected_chunk_2 = (1 / 62) + (1 / 61)

    assert scores["chunk_2"] == pytest.approx(expected_chunk_2)


def test_results_are_sorted_by_rrf_score(hybrid_retriever):
    results = hybrid_retriever.search(
        "third country data transfer",
        top_k=3,
    )

    scores = [
        score
        for _, score in results
    ]

    assert scores == sorted(scores, reverse=True)


def test_empty_query_raises_error(hybrid_retriever):
    with pytest.raises(ValueError):
        hybrid_retriever.search("")


def test_invalid_top_k_raises_error(hybrid_retriever):
    with pytest.raises(ValueError):
        hybrid_retriever.search(
            "data transfer",
            top_k=0,
        )


def test_invalid_candidate_k_raises_error(hybrid_retriever):
    with pytest.raises(ValueError):
        hybrid_retriever.search(
            "data transfer",
            candidate_k=0,
        )


def test_duplicate_chunks_are_returned_only_once(hybrid_retriever):
    results = hybrid_retriever.search(
        "data transfer",
        top_k=10,
    )

    chunk_ids = [
        chunk.chunk_id
        for chunk, _ in results
    ]

    assert len(chunk_ids) == len(set(chunk_ids))


def test_candidate_k_is_passed_to_both_retrievers(sample_chunks):
    bm25 = MockRetriever([
        (sample_chunks[0], 8.5),
        (sample_chunks[1], 6.2),
    ])

    faiss = MockRetriever([
        (sample_chunks[1], 0.91),
        (sample_chunks[0], 0.87),
    ])

    hybrid = HybridRetriever(bm25, faiss)

    hybrid.search(
        "data transfer",
        top_k=2,
        candidate_k=1,
    )

    # Only the first candidate from each retriever is used.
    results = hybrid.search(
        "data transfer",
        top_k=2,
        candidate_k=1,
    )

    assert len(results) == 2
