
import re
import time
from dataclasses import dataclass, field
from math import isfinite

from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker
from lexisync.retrieval.hybrid_retriever import (
    HybridRetriever,
    reciprocal_rank_fusion,
)
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
from lexisync.retrieval.query_expander import (
    NoOpQueryExpander,
    QueryExpansionStrategy,
)
from lexisync.retrieval.query_planner import QueryPlan
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


RETRIEVAL_MODES = ("dense", "bm25", "hybrid", "hybrid_rerank")


@dataclass
class RetrievalFilters:
    """Optional metadata filters applied to every candidate list.

    ``section`` matches case-insensitively against the section heading or its
    normalised key (``"article 83"``) using boundaries, so ``Article 8`` does
    not match ``Article 83``.
    """

    document_ids: set[str] | None = None
    section: str | None = None
    pages: set[int] | None = None

    def is_active(self) -> bool:
        return bool(self.document_ids or self.section or self.pages)

    def matches(self, chunk: Chunk) -> bool:
        if self.document_ids and chunk.document_id not in self.document_ids:
            return False
        if self.pages and not (set(chunk.page_numbers) & self.pages):
            return False
        if self.section:
            pattern = re.compile(
                rf"(?<![\w.]){re.escape(self.section.strip())}(?![\w])",
                re.IGNORECASE,
            )
            haystacks = [
                chunk.section or "",
                (chunk.metadata or {}).get("section_key") or "",
            ]
            if not any(pattern.search(h) for h in haystacks):
                return False
        return True


@dataclass
class DetailedRetrieval:
    """Retrieval output plus every intermediate ranking for diagnostics."""

    query: str
    mode: str
    results: list[tuple[Chunk, float]]
    bm25: list[tuple[Chunk, float]] = field(default_factory=list)
    dense: list[tuple[Chunk, float]] = field(default_factory=list)
    fused: list[tuple[Chunk, float]] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    """A retrieved chunk, its best rerank score and the sub-queries it serves."""

    chunk: Chunk
    score: float
    sub_queries: list[int] = field(default_factory=list)


@dataclass
class MultiHopRetrieval:
    """Merged evidence for a (possibly multi-hop) query plan."""

    plan: QueryPlan
    evidence: list[EvidenceItem]
    per_sub_query: list[DetailedRetrieval]
    coverage: list[dict]
    timings: dict[str, float]


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
        rrf_k: int = 60,
        contextual: bool = False,
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
        self.rrf_k = rrf_k
        self.contextual = contextual

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
            chunks,
            contextual=self.contextual,
        )

        # Step 3: Combine BM25 and FAISS using RRF.
        self.hybrid_retriever = HybridRetriever(
            bm25_retriever=self.bm25_retriever,
            faiss_retriever=self.faiss_retriever,
            rrf_k=self.rrf_k,
        )

        # Step 4: Initialize cross-encoder reranker.
        if self.reranker is None:
            self.reranker = CrossEncoderReranker(contextual=self.contextual)

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

    # ------------------------------------------------------------------
    # Detailed / configurable retrieval (used by the app and evaluation)
    # ------------------------------------------------------------------

    @property
    def chunks(self) -> list[Chunk]:
        """All indexed chunks (available after initialisation)."""

        if not self._initialized:
            raise RuntimeError("Retrieval pipeline is not initialized.")
        return self.faiss_retriever.chunks

    def search_detailed(
        self,
        query: str,
        mode: str = "hybrid_rerank",
        top_k: int | None = None,
        candidate_k: int | None = None,
        filters: RetrievalFilters | None = None,
    ) -> DetailedRetrieval:
        """Run one retrieval configuration and keep every intermediate list.

        Modes:
            dense          FAISS cosine similarity only
            bm25           BM25 only
            hybrid         BM25 + dense fused with RRF (no reranking)
            hybrid_rerank  hybrid, then cross-encoder reranking (default)
        """

        if not self._initialized:
            raise RuntimeError(
                "Retrieval pipeline is not initialized. "
                "Call initialize() before searching."
            )
        if mode not in RETRIEVAL_MODES:
            raise ValueError(f"mode must be one of {RETRIEVAL_MODES}.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        query = query.strip()
        final_k = self.top_k if top_k is None else top_k
        pool_k = self.candidate_k if candidate_k is None else candidate_k
        if final_k <= 0 or pool_k <= 0:
            raise ValueError("top_k and candidate_k must be greater than zero.")

        filters = filters or RetrievalFilters()
        # Over-fetch when filtering so enough candidates survive the filter.
        fetch_k = pool_k * 5 if filters.is_active() else pool_k
        timings: dict[str, float] = {}

        def keep(results):
            return [item for item in results if filters.matches(item[0])][:pool_k]

        bm25: list[tuple[Chunk, float]] = []
        dense: list[tuple[Chunk, float]] = []
        if mode in ("bm25", "hybrid", "hybrid_rerank"):
            started = time.perf_counter()
            bm25 = keep(self.bm25_retriever.search(query, top_k=fetch_k))
            timings["bm25_seconds"] = time.perf_counter() - started
        if mode in ("dense", "hybrid", "hybrid_rerank"):
            started = time.perf_counter()
            dense = keep(self.faiss_retriever.search(query, top_k=fetch_k))
            timings["dense_seconds"] = time.perf_counter() - started

        fused: list[tuple[Chunk, float]] = []
        if mode == "dense":
            results = dense[:final_k]
        elif mode == "bm25":
            results = bm25[:final_k]
        else:
            fused = reciprocal_rank_fusion([bm25, dense], k=self.rrf_k)[:pool_k]
            if mode == "hybrid":
                results = fused[:final_k]
            else:
                started = time.perf_counter()
                results = (
                    self.reranker.rerank(
                        query=query,
                        candidates=fused,
                        top_k=final_k,
                    )
                    if fused
                    else []
                )
                timings["rerank_seconds"] = time.perf_counter() - started

        timings["total_seconds"] = sum(timings.values())

        return DetailedRetrieval(
            query=query,
            mode=mode,
            results=results,
            bm25=bm25,
            dense=dense,
            fused=fused,
            timings=timings,
        )

    def multi_hop_search(
        self,
        plan: QueryPlan,
        top_k: int | None = None,
        per_sub_query_k: int = 3,
        candidate_k: int | None = None,
        filters: RetrievalFilters | None = None,
        coverage_threshold: float = 0.0,
    ) -> MultiHopRetrieval:
        """Retrieve evidence for every sub-query of a plan and merge it.

        The original question is always searched. Each extra sub-query is
        reranked against its *own* text, so every information need gets its
        best passages even when the full question favours one of them.
        A sub-query counts as covered when its best rerank score reaches
        ``coverage_threshold``.
        """

        final_k = self.top_k if top_k is None else top_k
        started_total = time.perf_counter()

        queries = [plan.question]
        if plan.is_multi_hop:
            queries.extend(plan.sub_queries)

        merged: dict[str, EvidenceItem] = {}
        order: list[str] = []
        per_query: list[DetailedRetrieval] = []

        for query_index, query in enumerate(queries):
            limit = final_k if query_index == 0 else per_sub_query_k
            detailed = self.search_detailed(
                query,
                mode="hybrid_rerank",
                top_k=limit,
                candidate_k=candidate_k,
                filters=filters,
            )
            per_query.append(detailed)

            for chunk, score in detailed.results:
                item = merged.get(chunk.chunk_id)
                if item is None:
                    item = EvidenceItem(chunk=chunk, score=float(score))
                    merged[chunk.chunk_id] = item
                    order.append(chunk.chunk_id)
                else:
                    item.score = max(item.score, float(score))
                if query_index > 0:
                    item.sub_queries.append(query_index - 1)
                elif not plan.is_multi_hop:
                    item.sub_queries.append(0)

        evidence = sorted(
            (merged[chunk_id] for chunk_id in order),
            key=lambda item: -item.score,
        )

        targets = (
            list(enumerate(plan.sub_queries, start=1))
            if plan.is_multi_hop
            else [(0, plan.question)]
        )
        coverage = []
        for result_index, sub_query in targets:
            results = per_query[result_index].results
            best = max((float(score) for _, score in results), default=None)
            coverage.append({
                "sub_query": sub_query,
                "best_score": best,
                "covered": best is not None and best >= coverage_threshold,
                "chunk_ids": [chunk.chunk_id for chunk, _ in results],
            })

        return MultiHopRetrieval(
            plan=plan,
            evidence=evidence,
            per_sub_query=per_query,
            coverage=coverage,
            timings={"retrieval_seconds": time.perf_counter() - started_total},
        )
