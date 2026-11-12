
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lexisync.retrieval import indexing_pipeline
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
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
        ),
        Chunk(
            chunk_id="chunk_2",
            document_id="privacy",
            text="Personal data must be processed lawfully.",
            page_numbers=[5],
            section="Article 5",
        ),
    ]


@pytest.fixture
def fake_pdf_files(tmp_path):
    pdf_one = tmp_path / "gdpr.pdf"
    pdf_two = tmp_path / "privacy.pdf"

    pdf_one.write_bytes(b"mock pdf content")
    pdf_two.write_bytes(b"mock pdf content")

    return [pdf_one, pdf_two]


@pytest.fixture
def pipeline():
    return DocumentIndexingPipeline(
        index_store=MagicMock(),
        model_name="test-model",
        batch_size=2,
    )


def test_pipeline_initialization(pipeline):
    assert pipeline.model_name == "test-model"
    assert pipeline.batch_size == 2


def test_invalid_batch_size_raises_error():
    with pytest.raises(ValueError):
        DocumentIndexingPipeline(
            batch_size=0,
        )


def test_build_rejects_empty_pdf_list(pipeline):
    with pytest.raises(ValueError):
        pipeline.build([])


def test_build_rejects_duplicate_pdf_paths(
    pipeline,
    fake_pdf_files,
):
    with pytest.raises(ValueError):
        pipeline.build([
            fake_pdf_files[0],
            fake_pdf_files[0],
        ])


def test_build_rejects_missing_pdf(pipeline, tmp_path):
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(FileNotFoundError):
        pipeline.build([missing_pdf])


def test_build_rejects_non_pdf_file(pipeline, tmp_path):
    text_file = tmp_path / "document.txt"
    text_file.write_text("Not a PDF.")

    with pytest.raises(ValueError):
        pipeline.build([text_file])


def test_build_rejects_directory(pipeline, tmp_path):
    pdf_directory = tmp_path / "document.pdf"
    pdf_directory.mkdir()

    with pytest.raises(ValueError):
        pipeline.build([pdf_directory])


def test_build_rejects_documents_without_chunks(
    pipeline,
    fake_pdf_files,
    monkeypatch,
):
    monkeypatch.setattr(
        indexing_pipeline,
        "load_pdf",
        lambda path: SimpleNamespace(
            file_name=path.name,
            total_pages=1,
        ),
    )

    monkeypatch.setattr(
        indexing_pipeline,
        "chunk_document",
        lambda document: [],
    )

    with pytest.raises(ValueError):
        pipeline.build([fake_pdf_files[0]])


def test_build_combines_chunks_from_multiple_pdfs(
    pipeline,
    fake_pdf_files,
    sample_chunks,
    monkeypatch,
):
    def mock_load_pdf(path):
        return SimpleNamespace(
            file_name=path.name,
            total_pages=1,
        )

    def mock_chunk_document(document):
        if document.file_name == "gdpr.pdf":
            return [sample_chunks[0]]

        return [sample_chunks[1]]

    mock_retriever = MagicMock()

    def mock_faiss_retriever(**kwargs):
        mock_retriever.kwargs = kwargs
        return mock_retriever

    monkeypatch.setattr(
        indexing_pipeline,
        "load_pdf",
        mock_load_pdf,
    )

    monkeypatch.setattr(
        indexing_pipeline,
        "chunk_document",
        mock_chunk_document,
    )

    monkeypatch.setattr(
        indexing_pipeline,
        "FAISSRetriever",
        mock_faiss_retriever,
    )

    result = pipeline.build(fake_pdf_files)

    assert result is mock_retriever

    retriever_chunks = mock_retriever.kwargs["chunks"]

    assert len(retriever_chunks) == 2
    assert retriever_chunks[0].chunk_id == "chunk_1"
    assert retriever_chunks[1].chunk_id == "chunk_2"

    assert mock_retriever.kwargs["model_name"] == "test-model"
    assert mock_retriever.kwargs["batch_size"] == 2
    assert (
        mock_retriever.kwargs["index_store"]
        is pipeline.index_store
    )


def test_load_restores_existing_index(
    pipeline,
    monkeypatch,
):
    mock_retriever = MagicMock()

    def mock_faiss_retriever(**kwargs):
        mock_retriever.kwargs = kwargs
        return mock_retriever

    monkeypatch.setattr(
        indexing_pipeline,
        "FAISSRetriever",
        mock_faiss_retriever,
    )

    result = pipeline.load()

    assert result is mock_retriever

    assert mock_retriever.kwargs["load_existing"] is True
    assert mock_retriever.kwargs["model_name"] == "test-model"
    assert mock_retriever.kwargs["batch_size"] == 2
    assert (
        mock_retriever.kwargs["index_store"]
        is pipeline.index_store
    )


def test_build_processes_all_documents(
    pipeline,
    fake_pdf_files,
    sample_chunks,
    monkeypatch,
):
    processed_documents = []

    def mock_load_pdf(path):
        return SimpleNamespace(
            file_name=path.name,
            total_pages=1,
        )

    def mock_chunk_document(document):
        processed_documents.append(document.file_name)

        if document.file_name == "gdpr.pdf":
            return [sample_chunks[0]]

        return [sample_chunks[1]]

    monkeypatch.setattr(
        indexing_pipeline,
        "load_pdf",
        mock_load_pdf,
    )

    monkeypatch.setattr(
        indexing_pipeline,
        "chunk_document",
        mock_chunk_document,
    )

    monkeypatch.setattr(
        indexing_pipeline,
        "FAISSRetriever",
        lambda **kwargs: kwargs,
    )

    pipeline.build(fake_pdf_files)

    assert processed_documents == [
        "gdpr.pdf",
        "privacy.pdf",
    ]
