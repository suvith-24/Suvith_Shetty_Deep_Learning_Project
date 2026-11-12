
from pathlib import Path

from lexisync.chunking.legal_chunker import chunk_document
from lexisync.config import EMBEDDING_MODEL
from lexisync.ingestion.pdf_loader import load_pdf
from lexisync.retrieval.faiss_retriever import FAISSRetriever
from lexisync.retrieval.index_store import IndexStore
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class DocumentIndexingPipeline:
    """
    Manage ingestion, chunking, embedding, and persistent indexing
    of multiple legal PDF documents.
    """

    def __init__(
        self,
        index_store: IndexStore | None = None,
        model_name: str = EMBEDDING_MODEL,
        batch_size: int = 32,
    ) -> None:

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        self.index_store = index_store or IndexStore()
        self.model_name = model_name
        self.batch_size = batch_size

    def build(
        self,
        pdf_paths: list[str | Path],
    ) -> FAISSRetriever:
        """
        Ingest PDFs, generate chunks, build embeddings,
        and persist the resulting FAISS index.

        Existing index files are overwritten.
        """

        if not pdf_paths:
            raise ValueError(
                "At least one PDF document is required."
            )

        normalized_paths = [
            Path(path).resolve()
            for path in pdf_paths
        ]

        if len(normalized_paths) != len(set(normalized_paths)):
            raise ValueError(
                "Duplicate PDF paths are not allowed."
            )

        all_chunks: list[Chunk] = []

        for pdf_path in normalized_paths:

            if not pdf_path.exists():
                raise FileNotFoundError(
                    f"PDF file not found: {pdf_path}"
                )

            if not pdf_path.is_file():
                raise ValueError(
                    f"Expected a PDF file, received: {pdf_path}"
                )

            if pdf_path.suffix.lower() != ".pdf":
                raise ValueError(
                    f"Only PDF documents are supported: {pdf_path}"
                )

            logger.info(
                "Processing legal document: %s",
                pdf_path.name,
            )

            document = load_pdf(pdf_path)

            chunks = chunk_document(document)

            if not chunks:
                raise ValueError(
                    f"No searchable chunks generated from: {pdf_path.name}"
                )

            all_chunks.extend(chunks)

            logger.info(
                "Processed %s: %d pages, %d chunks.",
                document.file_name,
                document.total_pages,
                len(chunks),
            )

        logger.info(
            "Building combined index from %d documents and %d chunks.",
            len(normalized_paths),
            len(all_chunks),
        )

        retriever = FAISSRetriever(
            chunks=all_chunks,
            model_name=self.model_name,
            batch_size=self.batch_size,
            index_store=self.index_store,
        )

        logger.info(
            "Document indexing completed successfully."
        )

        return retriever

    def load(self) -> FAISSRetriever:
        """
        Restore an existing persistent FAISS index.

        Document embeddings are not regenerated.
        """

        logger.info(
            "Loading existing document index."
        )

        retriever = FAISSRetriever(
            model_name=self.model_name,
            batch_size=self.batch_size,
            index_store=self.index_store,
            load_existing=True,
        )

        logger.info(
            "Document index loaded successfully: %d chunks.",
            len(retriever.chunks),
        )

        return retriever
