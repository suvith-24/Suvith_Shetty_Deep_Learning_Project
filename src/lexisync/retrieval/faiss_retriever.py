
import numpy as np
import faiss

from sentence_transformers import SentenceTransformer

from lexisync.config import EMBEDDING_MODEL
from lexisync.retrieval.index_store import IndexStore
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class FAISSRetriever:
    """
    Semantic retrieval using SentenceTransformer and FAISS.

    Supports two modes:

    1. Build mode:
       Generate document embeddings and optionally persist the index.

    2. Load mode:
       Restore an existing FAISS index without regenerating
       document embeddings.
    """

    def __init__(
        self,
        chunks: list[Chunk] | None = None,
        model_name: str = EMBEDDING_MODEL,
        batch_size: int = 32,
        model: SentenceTransformer | None = None,
        index_store: IndexStore | None = None,
        load_existing: bool = False,
    ) -> None:

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        if load_existing and chunks is not None:
            raise ValueError(
                "Do not provide chunks when loading an existing index."
            )

        if not load_existing and not chunks:
            raise ValueError(
                "Chunks are required when building a new FAISS index."
            )

        self.batch_size = batch_size
        self.index_store = index_store

        # The embedding model is needed for query encoding
        # in both build and load modes.
        self.model = model or SentenceTransformer(
            model_name,
            device="cpu",
        )

        if load_existing:
            self._load_index()
        else:
            self._build_index(chunks)

            # Persist automatically when a store is provided.
            if self.index_store is not None:
                self.index_store.save(
                    self.index,
                    self.chunks,
                )

    def _build_index(
        self,
        chunks: list[Chunk],
    ) -> None:
        """Generate embeddings and build the FAISS index."""

        self.chunks = chunks

        texts = [
            chunk.text
            for chunk in self.chunks
        ]

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        if embeddings.ndim != 2:
            raise ValueError(
                "Generated embeddings must be a 2D array."
            )

        if embeddings.shape[0] != len(self.chunks):
            raise ValueError(
                "Embedding count does not match the number of chunks."
            )

        if embeddings.shape[1] == 0:
            raise ValueError(
                "Embedding dimension cannot be zero."
            )

        if not np.isfinite(embeddings).all():
            raise ValueError(
                "Generated embeddings contain invalid numeric values."
            )

        embeddings = np.ascontiguousarray(
            embeddings,
            dtype=np.float32,
        )

        self.embedding_dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(
            self.embedding_dimension
        )

        self.index.add(embeddings)

        logger.info(
            "FAISS index initialized: %d vectors, %d dimensions.",
            self.index.ntotal,
            self.embedding_dimension,
        )

    def _load_index(self) -> None:
        """Load an existing FAISS index and its chunk metadata."""

        if self.index_store is None:
            self.index_store = IndexStore()

        self.index, self.chunks = self.index_store.load()

        self.embedding_dimension = self.index.d

        logger.info(
            "Existing FAISS index loaded: %d vectors, %d dimensions.",
            self.index.ntotal,
            self.embedding_dimension,
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[Chunk, float]]:
        """
        Retrieve semantically relevant chunks.

        Returns:
            List of (Chunk, cosine_similarity_score).
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        query_embedding = self.model.encode(
            [query.strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        if query_embedding.ndim != 2:
            raise ValueError(
                "Query embedding must be a 2D array."
            )

        if query_embedding.shape != (
            1,
            self.embedding_dimension,
        ):
            raise ValueError(
                "Query embedding dimension does not match the FAISS index."
            )

        if not np.isfinite(query_embedding).all():
            raise ValueError(
                "Query embedding contains invalid numeric values."
            )

        query_embedding = np.ascontiguousarray(
            query_embedding,
            dtype=np.float32,
        )

        result_count = min(
            top_k,
            self.index.ntotal,
        )

        scores, indices = self.index.search(
            query_embedding,
            result_count,
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):

            if index < 0:
                continue

            results.append(
                (
                    self.chunks[int(index)],
                    float(score),
                )
            )

        logger.info(
            "FAISS retrieved %d chunks for query: '%s'.",
            len(results),
            query[:100],
        )

        return results
