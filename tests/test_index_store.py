
import json

import faiss
import numpy as np
import pytest

from lexisync.retrieval.index_store import IndexStore
from lexisync.schemas.document import Chunk


@pytest.fixture
def sample_chunks():
    return [
        Chunk(
            chunk_id="chunk_1",
            document_id="gdpr",
            text="Personal data transfers must follow GDPR requirements.",
            page_numbers=[60],
            section="Article 44",
            subsection=None,
            start_char=100,
            end_char=155,
            metadata={"source": "gdpr.pdf"},
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="gdpr",
            text="Appropriate safeguards must be provided.",
            page_numbers=[62],
            section="Article 46",
            subsection="Paragraph 1",
            start_char=200,
            end_char=242,
            metadata={"source": "gdpr.pdf"},
        ),
    ]


@pytest.fixture
def sample_index():
    index = faiss.IndexFlatIP(3)

    embeddings = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )

    index.add(embeddings)

    return index


@pytest.fixture
def index_store(tmp_path):
    return IndexStore(
        index_dir=tmp_path,
        index_name="test_index",
    )


def test_index_store_creates_directory(tmp_path):
    storage_path = tmp_path / "indexes"

    store = IndexStore(
        index_dir=storage_path,
    )

    assert storage_path.exists()
    assert store.index_path.name == "legal_documents.faiss"
    assert store.chunks_path.name == "legal_documents_chunks.json"


def test_save_creates_index_and_metadata_files(
    index_store,
    sample_index,
    sample_chunks,
):
    index_store.save(
        sample_index,
        sample_chunks,
    )

    assert index_store.index_path.exists()
    assert index_store.chunks_path.exists()


def test_load_restores_index_and_chunks(
    index_store,
    sample_index,
    sample_chunks,
):
    index_store.save(
        sample_index,
        sample_chunks,
    )

    loaded_index, loaded_chunks = index_store.load()

    assert loaded_index.ntotal == 2
    assert loaded_index.d == 3
    assert len(loaded_chunks) == 2


def test_load_preserves_chunk_metadata(
    index_store,
    sample_index,
    sample_chunks,
):
    index_store.save(
        sample_index,
        sample_chunks,
    )

    _, loaded_chunks = index_store.load()

    first_chunk = loaded_chunks[0]
    second_chunk = loaded_chunks[1]

    assert first_chunk.chunk_id == "chunk_1"
    assert first_chunk.document_id == "gdpr"
    assert first_chunk.page_numbers == [60]
    assert first_chunk.section == "Article 44"
    assert first_chunk.start_char == 100
    assert first_chunk.end_char == 155
    assert first_chunk.metadata == {"source": "gdpr.pdf"}

    assert second_chunk.chunk_id == "chunk_2"
    assert second_chunk.section == "Article 46"
    assert second_chunk.subsection == "Paragraph 1"


def test_loaded_index_preserves_vectors(
    index_store,
    sample_index,
    sample_chunks,
):
    index_store.save(
        sample_index,
        sample_chunks,
    )

    loaded_index, _ = index_store.load()

    query = np.asarray(
        [[1.0, 0.0, 0.0]],
        dtype=np.float32,
    )

    scores, indices = loaded_index.search(query, 1)

    assert indices[0][0] == 0
    assert scores[0][0] == pytest.approx(1.0)


def test_save_rejects_empty_chunks(
    index_store,
    sample_index,
):
    with pytest.raises(ValueError):
        index_store.save(
            sample_index,
            [],
        )


def test_save_rejects_mismatched_vector_count(
    index_store,
    sample_chunks,
):
    index = faiss.IndexFlatIP(3)

    with pytest.raises(ValueError):
        index_store.save(
            index,
            sample_chunks,
        )


def test_save_rejects_duplicate_chunk_ids(
    index_store,
    sample_index,
    sample_chunks,
):
    duplicate_chunks = [
        sample_chunks[0],
        sample_chunks[0],
    ]

    with pytest.raises(ValueError):
        index_store.save(
            sample_index,
            duplicate_chunks,
        )


def test_load_raises_error_when_index_is_missing(index_store):
    with pytest.raises(FileNotFoundError):
        index_store.load()


def test_load_detects_mismatched_chunk_metadata(
    index_store,
    sample_index,
    sample_chunks,
):
    index_store.save(
        sample_index,
        sample_chunks,
    )

    # Deliberately remove one chunk from the metadata file.
    with index_store.chunks_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [
                {
                    "chunk_id": "chunk_1",
                    "document_id": "gdpr",
                    "text": "Personal data transfers.",
                    "page_numbers": [60],
                }
            ],
            file,
        )

    with pytest.raises(ValueError):
        index_store.load()


def test_invalid_index_name_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        IndexStore(
            index_dir=tmp_path,
            index_name="../invalid",
        )
