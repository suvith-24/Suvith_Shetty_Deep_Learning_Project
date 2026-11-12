
from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.faiss_retriever import FAISSRetriever
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class HybridRetriever:
    """
    Hybrid retrieval using BM25, FAISS, and Reciprocal Rank Fusion.

    BM25 contributes keyword-based rankings.
    FAISS contributes semantic-similarity rankings.
    RRF combines both rankings into a unified score.
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        faiss_retriever: FAISSRetriever,
        rrf_k: int = 60,
    ) -> None:

        if rrf_k <= 0:
            raise ValueError("rrf_k must be greater than zero.")

        self.bm25_retriever = bm25_retriever
        self.faiss_retriever = faiss_retriever
        self.rrf_k = rrf_k

        logger.info(
            "Hybrid retriever initialized with RRF constant %d.",
            self.rrf_k,
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
        candidate_k: int = 20,
    ) -> list[tuple[Chunk, float]]:
        """
        Retrieve and fuse candidates from BM25 and FAISS.

        Args:
            query: User's search query.
            top_k: Number of final results.
            candidate_k: Number of candidates requested from each retriever.

        Returns:
            List of (Chunk, RRF score), sorted by descending score.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if candidate_k <= 0:
            raise ValueError("candidate_k must be greater than zero.")

        bm25_results = self.bm25_retriever.search(
            query,
            top_k=candidate_k,
        )

        faiss_results = self.faiss_retriever.search(
            query,
            top_k=candidate_k,
        )

        fused_scores: dict[str, float] = {}
        chunks_by_id: dict[str, Chunk] = {}

        retrieval_results = [
            bm25_results,
            faiss_results,
        ]

        for results in retrieval_results:

            for rank, (chunk, _) in enumerate(results, start=1):

                chunk_id = chunk.chunk_id

                chunks_by_id[chunk_id] = chunk

                rrf_score = 1.0 / (
                    self.rrf_k + rank
                )

                fused_scores[chunk_id] = (
                    fused_scores.get(chunk_id, 0.0)
                    + rrf_score
                )

        ranked_results = sorted(
            fused_scores.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        final_results = [
            (
                chunks_by_id[chunk_id],
                score,
            )
            for chunk_id, score in ranked_results[:top_k]
        ]

        logger.info(
            "Hybrid retrieval returned %d chunks for query: '%s'.",
            len(final_results),
            query[:100],
        )

        return final_results
