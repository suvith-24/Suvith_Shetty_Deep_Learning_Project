
from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker
from lexisync.retrieval.hybrid_retriever import HybridRetriever
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class RetrievalPipeline:
    """
    Unified retrieval pipeline combining:

    1. Persistent FAISS semantic retrieval.
    2. BM25 keyword retrieval.
    3. Reciprocal Rank Fusion.
    4. Cross-encoder reranking.

    The pipeline returns the most relevant evidence chunks
    for a given user query.
    """

    def __init__(
        self,
        indexing_pipeline: DocumentIndexingPipeline | None = None,
        reranker: CrossEncoderReranker | None = None,
        candidate_k: int = 20,
        top_k: int = 5,
    ) -> None:

        if candidate_k <= 0:
            raise ValueError(
                "candidate_k must be greater than zero."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        self.indexing_pipeline = (
            indexing_pipeline or DocumentIndexingPipeline()
        )

        self.reranker = reranker

        self.candidate_k = candidate_k
        self.top_k = top_k

        self.faiss_retriever = None
        self.bm25_retriever = None
        self.hybrid_retriever = None

        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Return whether the retrieval pipeline is ready."""

        return self._initialized

    def initialize(self) -> None:
        """
        Load the persistent FAISS index and initialize
        all retrieval components.

        Document embeddings are not regenerated.
        """

        if self._initialized:
            logger.info(
                "Retrieval pipeline is already initialized."
            )
            return

        logger.info(
            "Initializing unified retrieval pipeline."
        )

        # Step 1: Load persistent FAISS index.
        self.faiss_retriever = (
            self.indexing_pipeline.load()
        )

        chunks = self.faiss_retriever.chunks

        if not chunks:
            raise ValueError(
                "Loaded index contains no document chunks."
            )

        # Step 2: Initialize BM25 using restored chunks.
        self.bm25_retriever = BM25Retriever(
            chunks
        )

        # Step 3: Combine BM25 and FAISS using RRF.
        self.hybrid_retriever = HybridRetriever(
            bm25_retriever=self.bm25_retriever,
            faiss_retriever=self.faiss_retriever,
        )

        # Step 4: Initialize cross-encoder reranker.
        if self.reranker is None:
            self.reranker = CrossEncoderReranker()

        self._initialized = True

        logger.info(
            "Unified retrieval pipeline initialized successfully."
        )

        logger.info(
            "Indexed chunks: %d | Candidate limit: %d | Final results: %d",
            len(chunks),
            self.candidate_k,
            self.top_k,
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        candidate_k: int | None = None,
    ) -> list[tuple]:
        """
        Execute the complete retrieval pipeline.

        Args:
            query: User's legal question.
            top_k: Optional override for final result count.
            candidate_k: Optional override for hybrid candidates.

        Returns:
            List of (Chunk, cross_encoder_score) pairs,
            sorted by descending relevance.
        """

        if not self._initialized:
            raise RuntimeError(
                "Retrieval pipeline is not initialized. "
                "Call initialize() before searching."
            )

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        final_top_k = (
            self.top_k if top_k is None else top_k
        )

        retrieval_candidate_k = (
            self.candidate_k
            if candidate_k is None
            else candidate_k
        )

        if final_top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        if retrieval_candidate_k <= 0:
            raise ValueError(
                "candidate_k must be greater than zero."
            )

        logger.info(
            "Starting retrieval for query: '%s'.",
            query[:100],
        )

        # Step 1: Hybrid retrieval.
        candidates = self.hybrid_retriever.search(
            query=query,
            top_k=retrieval_candidate_k,
            candidate_k=retrieval_candidate_k,
        )

        if not candidates:
            logger.warning(
                "No relevant candidates found for query: '%s'.",
                query[:100],
            )
            return []

        # Step 2: Cross-encoder reranking.
        results = self.reranker.rerank(
            query=query,
            candidates=candidates,
            top_k=final_top_k,
        )

        logger.info(
            "Retrieval completed: %d final evidence chunks returned.",
            len(results),
        )

        return results
