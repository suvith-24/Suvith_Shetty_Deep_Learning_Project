
import numpy as np
import pytest

from lexisync.retrieval.faiss_retriever import FAISSRetriever
from lexisync.retrieval.index_store import IndexStore
from lexisync.schemas.document import Chunk


class MockEmbeddingModel:
    """Deterministic embedding model for unit tests."""

    def __init__(self):
        self.encode_calls = []

    def encode(
        self,
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        **kwargs,
    ):
        self.encode_calls.append(texts)

        vectors = []

        for text in texts:
            text = text.casefold()

            if "transfer" in text or "third country" in text:
                vector = [1.0, 0.0, 0.0]

            elif "access" in text:
                vector = [0.0, 1.0, 0.0]

            else:
                vector = [0.0, 0.0, 1.0]

            vectors.append(vector)

        embeddings = np.asarray(
            vectors,
            dtype=np.float32,
        )

        if normalize_embeddings:
            norms = np.linalg.norm(
                embeddings,
                axis=1,
                keepdims=True,
            )
            embeddings = embeddings / norms

        return embeddings


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            chunk_id="chunk_1",
            document_id="gdpr",
            text="Transfer of personal data to a third country.",
            page_numbers=[60],
            section="Article 44",
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="gdpr",
            text="The data subject has the right to access personal data.",
            page_numbers=[15],
            section="Article 15",
        ),
        Chunk(
            chunk_id="chunk_3",
            document_id="gdpr",
            text="Personal data must be processed lawfully.",
            page_numbers=[5],
            section="Article 5",
        ),
    ]


@pytest.fixture
def mock_model():
    return MockEmbeddingModel()


@pytest.fixture
def retriever(sample_chunks):
    return FAISSRetriever(
        chunks=sample_chunks,
        model=MockEmbeddingModel(),
        batch_size=2,
    )


@pytest.fixture
def index_store(tmp_path):
    return IndexStore(
        index_dir=tmp_path,
        index_name="test_index",
    )


# ---------------------------------------------------------
# Basic FAISS tests
# ---------------------------------------------------------


def test_faiss_initialization(retriever):
    assert retriever.index.ntotal == 3
    assert retriever.embedding_dimension == 3


def test_empty_chunks_raise_error():
    with pytest.raises(ValueError):
        FAISSRetriever(
            chunks=[],
            model=MockEmbeddingModel(),
        )


def test_invalid_batch_size_raises_error(sample_chunks):
    with pytest.raises(ValueError):
        FAISSRetriever(
            chunks=sample_chunks,
            model=MockEmbeddingModel(),
            batch_size=0,
        )


def test_search_returns_relevant_result(retriever):
    results = retriever.search(
        "Transfer to a third country",
        top_k=3,
    )

    assert len(results) == 3
    assert results[0][0].chunk_id == "chunk_1"


def test_search_respects_top_k(retriever):
    results = retriever.search(
        "personal data",
        top_k=2,
    )

    assert len(results) == 2


def test_empty_query_raises_error(retriever):
    with pytest.raises(ValueError):
        retriever.search("")


def test_whitespace_query_raises_error(retriever):
    with pytest.raises(ValueError):
        retriever.search("   ")


def test_invalid_top_k_raises_error(retriever):
    with pytest.raises(ValueError):
        retriever.search(
            "personal data",
            top_k=0,
        )


def test_results_are_sorted_by_similarity(retriever):
    results = retriever.search(
        "Transfer to a third country",
        top_k=3,
    )

    scores = [
        score
        for _, score in results
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_result_preserves_chunk_metadata(retriever):
    results = retriever.search(
        "Transfer to a third country",
        top_k=1,
    )

    chunk, score = results[0]

    assert chunk.page_numbers == [60]
    assert chunk.section == "Article 44"
    assert score == pytest.approx(1.0)


def test_top_k_larger_than_index_returns_available_chunks(retriever):
    results = retriever.search(
        "personal data",
        top_k=100,
    )

    assert len(results) == 3


# ---------------------------------------------------------
# Persistent indexing tests
# ---------------------------------------------------------


def test_build_mode_saves_index_automatically(
    sample_chunks,
    index_store,
):
    FAISSRetriever(
        chunks=sample_chunks,
        model=MockEmbeddingModel(),
        index_store=index_store,
    )

    assert index_store.index_path.exists()
    assert index_store.chunks_path.exists()


def test_load_mode_restores_existing_index(
    sample_chunks,
    index_store,
):
    # First build and save the index.
    FAISSRetriever(
        chunks=sample_chunks,
        model=MockEmbeddingModel(),
        index_store=index_store,
    )

    # Load the saved index using a fresh model.
    loaded_model = MockEmbeddingModel()

    loaded_retriever = FAISSRetriever(
        model=loaded_model,
        index_store=index_store,
        load_existing=True,
    )

    assert loaded_retriever.index.ntotal == 3
    assert loaded_retriever.embedding_dimension == 3
    assert len(loaded_retriever.chunks) == 3

    # Loading must not regenerate document embeddings.
    assert len(loaded_model.encode_calls) == 0

    # Query encoding should still work.
    results = loaded_retriever.search(
        "Transfer to a third country",
        top_k=1,
    )

    assert results[0][0].chunk_id == "chunk_1"
    assert len(loaded_model.encode_calls) == 1


def test_load_mode_without_existing_index_raises_error(
    tmp_path,
):
    store = IndexStore(
        index_dir=tmp_path / "missing",
    )

    with pytest.raises(FileNotFoundError):
        FAISSRetriever(
            model=MockEmbeddingModel(),
            index_store=store,
            load_existing=True,
        )


def test_load_mode_rejects_provided_chunks(sample_chunks):
    with pytest.raises(ValueError):
        FAISSRetriever(
            chunks=sample_chunks,
            model=MockEmbeddingModel(),
            load_existing=True,
        )


def test_build_mode_requires_chunks():
    with pytest.raises(ValueError):
        FAISSRetriever(
            model=MockEmbeddingModel(),
            load_existing=False,
        )


def test_load_mode_preserves_chunk_metadata(
    sample_chunks,
    index_store,
):
    FAISSRetriever(
        chunks=sample_chunks,
        model=MockEmbeddingModel(),
        index_store=index_store,
    )

    loaded_retriever = FAISSRetriever(
        model=MockEmbeddingModel(),
        index_store=index_store,
        load_existing=True,
    )

    chunk = loaded_retriever.chunks[0]

    assert chunk.chunk_id == "chunk_1"
    assert chunk.document_id == "gdpr"
    assert chunk.page_numbers == [60]
    assert chunk.section == "Article 44"
