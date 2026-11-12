
import pytest

from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.schemas.document import Chunk


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            chunk_id="chunk_1",
            document_id="gdpr",
            text=(
                "Any transfer of personal data to a third country "
                "must comply with the GDPR."
            ),
            page_numbers=[60],
            section="Article 44",
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="gdpr",
            text=(
                "Personal data must be processed lawfully, fairly "
                "and transparently."
            ),
            page_numbers=[5],
            section="Article 5",
        ),
        Chunk(
            chunk_id="chunk_3",
            document_id="gdpr",
            text=(
                "The data subject has the right to access "
                "their personal data."
            ),
            page_numbers=[15],
            section="Article 15",
        ),
    ]


def test_bm25_initialization(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    assert retriever is not None
    assert len(retriever.chunks) == 3


def test_empty_chunks_raise_error():
    with pytest.raises(ValueError):
        BM25Retriever([])


def test_search_returns_relevant_result(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    results = retriever.search(
        "transfer personal data third country",
        top_k=3,
    )

    assert len(results) > 0
    assert results[0][0].chunk_id == "chunk_1"


def test_search_respects_top_k(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    results = retriever.search(
        "personal data",
        top_k=2,
    )

    assert len(results) <= 2


def test_empty_query_raises_error(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    with pytest.raises(ValueError):
        retriever.search("")


def test_whitespace_query_raises_error(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    with pytest.raises(ValueError):
        retriever.search("   ")


def test_invalid_top_k_raises_error(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    with pytest.raises(ValueError):
        retriever.search("personal data", top_k=0)


def test_no_matching_terms_returns_empty_list(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    results = retriever.search(
        "quantum blockchain cryptocurrency",
        top_k=5,
    )

    assert results == []


def test_results_are_sorted_by_score(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    results = retriever.search(
        "personal data transfer",
        top_k=3,
    )

    scores = [score for _, score in results]

    assert scores == sorted(scores, reverse=True)


def test_result_contains_original_chunk_metadata(sample_chunks):
    retriever = BM25Retriever(sample_chunks)

    results = retriever.search(
        "third country transfer",
        top_k=1,
    )

    chunk, score = results[0]

    assert chunk.page_numbers == [60]
    assert chunk.section == "Article 44"
    assert score > 0
