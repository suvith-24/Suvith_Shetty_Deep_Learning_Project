
from math import isfinite

from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker
from lexisync.retrieval.hybrid_retriever import HybridRetriever
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
from lexisync.retrieval.query_expander import (
    NoOpQueryExpander,
    QueryExpansionStrategy,
)
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class RetrievalPipeline:
    """
    Unified retrieval pipeline combining:

    1. Persistent FAISS semantic retrieval.
    2. BM25 keyword retrieval.
    3. Hybrid RRF for each search query.
    4. Weighted multi-query RRF across query rankings.
    5. Cross-encoder reranking against the original question.

    Query expansion is optional. Without an injected expander,
    the pipeline preserves the original single-query behavior.
    """

    def __init__(
        self,
        indexing_pipeline: DocumentIndexingPipeline | None = None,
        reranker: CrossEncoderReranker | None = None,
        candidate_k: int = 20,
        top_k: int = 5,
        query_expander: QueryExpansionStrategy | None = None,
        multi_query_rrf_k: int = 60,
        original_query_weight: float = 1.0,
        expanded_query_weight: float = 1.0,
    ) -> None:

        if candidate_k <= 0:
            raise ValueError("candidate_k must be greater than zero.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if multi_query_rrf_k <= 0:
            raise ValueError("multi_query_rrf_k must be greater than zero.")

        if (
            not isinstance(original_query_weight, (int, float))
            or not isfinite(original_query_weight)
            or original_query_weight <= 0
        ):
            raise ValueError(
                "original_query_weight must be a finite positive number."
            )

        if (
            not isinstance(expanded_query_weight, (int, float))
            or not isfinite(expanded_query_weight)
            or expanded_query_weight <= 0
        ):
            raise ValueError(
                "expanded_query_weight must be a finite positive number."
            )

        self.indexing_pipeline = (
            indexing_pipeline or DocumentIndexingPipeline()
        )

        self.reranker = reranker
        self.query_expander = (
            query_expander or NoOpQueryExpander()
        )

        self.candidate_k = candidate_k
        self.top_k = top_k
        self.multi_query_rrf_k = multi_query_rrf_k

        self.original_query_weight = float(original_query_weight)
        self.expanded_query_weight = float(expanded_query_weight)

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
            "Indexed chunks: %d | Candidate limit: %d | "
            "Final results: %d | Multi-query RRF k: %d | "
            "Original weight: %.2f | Expanded weight: %.2f",
            len(chunks),
            self.candidate_k,
            self.top_k,
            self.multi_query_rrf_k,
            self.original_query_weight,
            self.expanded_query_weight,
        )

    def _generate_queries(self, query: str) -> list[str]:
        """
        Generate unique search queries while preserving
        the original user question as the primary query.
        """

        expanded_queries = self.query_expander.expand(query)

        if not isinstance(expanded_queries, list):
            raise TypeError(
                "Query expander must return a list of strings."
            )

        queries = [query.strip()]
        seen = {query.strip().casefold()}

        for expanded_query in expanded_queries:

            if not isinstance(expanded_query, str):
                continue

            normalized = expanded_query.strip()

            if not normalized:
                continue

            key = normalized.casefold()

            if key not in seen:
                seen.add(key)
                queries.append(normalized)

        return queries

    def _fuse_query_results(
        self,
        query_results: list[list[tuple]],
        query_weights: list[float] | None = None,
    ) -> list[tuple]:
        """
        Fuse multiple hybrid rankings using weighted
        Reciprocal Rank Fusion.

        Each query contributes according to its configured
        weight and the rank of a chunk in that query's result list.

        Original BM25 and FAISS scores are not used directly.
        """

        if not query_results:
            return []

        if len(query_results) == 1:
            return query_results[0]

        if query_weights is None:
            query_weights = [1.0] * len(query_results)

        if len(query_weights) != len(query_results):
            raise ValueError(
                "query_weights must contain one weight per result list."
            )

        for weight in query_weights:
            if (
                not isinstance(weight, (int, float))
                or not isfinite(weight)
                or weight <= 0
            ):
                raise ValueError(
                    "All query weights must be finite positive numbers."
                )

        fused_scores: dict[str, float] = {}
        chunks_by_id = {}

        for results, weight in zip(query_results, query_weights):

            for rank, (chunk, _) in enumerate(
                results,
                start=1,
            ):

                chunk_id = chunk.chunk_id

                chunks_by_id[chunk_id] = chunk

                contribution = weight / (
                    self.multi_query_rrf_k + rank
                )

                fused_scores[chunk_id] = (
                    fused_scores.get(chunk_id, 0.0)
                    + contribution
                )

        ranked_results = sorted(
            fused_scores.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        return [
            (chunks_by_id[chunk_id], score)
            for chunk_id, score in ranked_results
        ]

    def search(
        self,
        query: str,
        top_k: int | None = None,
        candidate_k: int | None = None,
    ) -> list[tuple]:
        """
        Execute the complete retrieval pipeline.

        Args:
            query: User's original legal question.
            top_k: Optional override for final result count.
            candidate_k: Optional candidate limit per query.

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

        original_query = query.strip()

        logger.info(
            "Starting retrieval for query: '%s'.",
            original_query[:100],
        )

        # Step 1: Generate original and expanded queries.
        queries = self._generate_queries(original_query)

        logger.info(
            "Executing retrieval with %d search queries.",
            len(queries),
        )

        # Step 2: Execute hybrid retrieval for every query.
        query_results = []
        query_weights = []

        for query_index, search_query in enumerate(queries):

            candidates = self.hybrid_retriever.search(
                query=search_query,
                top_k=retrieval_candidate_k,
                candidate_k=retrieval_candidate_k,
            )

            if candidates:
                query_results.append(candidates)

                weight = (
                    self.original_query_weight
                    if query_index == 0
                    else self.expanded_query_weight
                )

                query_weights.append(weight)

        if not query_results:
            logger.warning(
                "No relevant candidates found for query: '%s'.",
                original_query[:100],
            )
            return []

        # Step 3: Fuse results from all query rankings.
        fused_candidates = self._fuse_query_results(
            query_results,
            query_weights=query_weights,
        )

        if not fused_candidates:
            logger.warning(
                "Multi-query fusion produced no candidates."
            )
            return []

        # Step 4: Rerank using the original user question.
        results = self.reranker.rerank(
            query=original_query,
            candidates=fused_candidates,
            top_k=final_top_k,
        )

        logger.info(
            "Retrieval completed: %d evidence chunks returned "
            "from %d search queries.",
            len(results),
            len(queries),
        )

        return results
