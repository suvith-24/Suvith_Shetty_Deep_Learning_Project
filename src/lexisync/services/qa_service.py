"""Question answering over one case: plan → retrieve → expand → detect conflicts → answer."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from lexisync import config
from lexisync.analysis.conflict_detector import ConflictDetector
from lexisync.generation.grounded_answerer import GroundedAnswerer
from lexisync.generation.ollama_client import OllamaClient
from lexisync.retrieval.context_expander import ContextExpander
from lexisync.retrieval.query_planner import QueryPlanner
from lexisync.retrieval.retrieval_pipeline import RetrievalFilters
from lexisync.services.case_manager import CaseError, CaseManager
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)

# Context expansion is limited to the strongest passages to keep the prompt
# within a few thousand tokens (CPU prompt evaluation dominates latency).
CONTEXT_FOR_TOP_N = 3


def _ranking(results, limit: int = 10) -> list[dict]:
    return [
        {
            "rank": rank,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "pages": chunk.page_numbers,
            "section": chunk.section,
            "score": round(float(score), 4),
        }
        for rank, (chunk, score) in enumerate(results[:limit], start=1)
    ]


class QAService:
    """Answer questions for a case using only that case's index."""

    def __init__(
        self,
        case_manager: CaseManager,
        answerer: GroundedAnswerer | None = None,
        planner: QueryPlanner | None = None,
        conflict_detector: ConflictDetector | None = None,
    ) -> None:
        self.cases = case_manager
        self.answerer = answerer or GroundedAnswerer(
            ollama_client=OllamaClient(),
            evidence_gate=config.EVIDENCE_GATE_SCORE,
            high_confidence_score=config.HIGH_CONFIDENCE_SCORE,
            max_retries=config.MAX_CORRECTIVE_RETRIES,
            verifier_mode=config.VERIFIER_MODE,
        )
        self.planner = planner or QueryPlanner()
        self.conflict_detector = conflict_detector or ConflictDetector()

    def ask(
        self,
        case_id: str,
        question: str,
        document_ids: list[str] | None = None,
        section: str | None = None,
        top_k: int | None = None,
        save: bool = True,
    ) -> dict:
        if not isinstance(question, str) or not question.strip():
            raise CaseError("Please enter a question.")
        if len(question) > 1000:
            raise CaseError("Questions are limited to 1000 characters.")

        started = time.perf_counter()
        case = self.cases.get_case(case_id)
        pipeline = self.cases.get_pipeline(case_id)

        plan = self.planner.plan(question)
        filters = RetrievalFilters(
            document_ids=set(document_ids) if document_ids else None,
            section=section or None,
        )

        retrieval = pipeline.multi_hop_search(
            plan,
            top_k=top_k or config.FINAL_TOP_K,
            per_sub_query_k=config.PER_SUB_QUERY_K,
            candidate_k=config.CANDIDATE_K,
            filters=filters,
            coverage_threshold=config.EVIDENCE_GATE_SCORE,
        )
        retrieval_seconds = time.perf_counter() - started

        primary_chunks = [item.chunk for item in retrieval.evidence]
        context = []
        if config.CONTEXT_WINDOW > 0 and primary_chunks:
            context = ContextExpander(
                previous_chunks=0,
                next_chunks=config.CONTEXT_WINDOW,
            ).expand(primary_chunks[:CONTEXT_FOR_TOP_N], pipeline.chunks)

        conflicts = self.conflict_detector.detect(
            primary_chunks,
            document_dates={
                d["document_id"]: d.get("creation_date") or "" for d in case.get("documents", [])
            },
        )

        searched = [d["file_name"] for d in case.get("documents", [])
                    if not document_ids or d["document_id"] in document_ids]

        result = self.answerer.answer(
            question=question,
            evidence=[(item.chunk, item.score, item.sub_queries) for item in retrieval.evidence],
            context=context,
            plan=plan,
            conflicts=conflicts,
            documents_searched=searched,
        )

        total_seconds = time.perf_counter() - started
        result["id"] = uuid.uuid4().hex[:12]
        result["case_id"] = case_id
        result["asked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result["retrieval"] = {
            "plan": plan.to_dict(),
            "coverage": retrieval.coverage,
            "filters": {"document_ids": document_ids or [], "section": section},
            "per_query": [
                {
                    "query": detail.query,
                    "bm25": _ranking(detail.bm25),
                    "dense": _ranking(detail.dense),
                    "fused": _ranking(detail.fused),
                    "reranked": _ranking(detail.results),
                    "timings": {k: round(v, 4) for k, v in detail.timings.items()},
                }
                for detail in retrieval.per_sub_query
            ],
            "context_chunk_ids": [c.chunk_id for c in context],
        }
        result["timings"] = {
            "retrieval_seconds": round(retrieval_seconds, 3),
            "generation_seconds": result.get("timings", {}).get("generation_seconds"),
            "total_seconds": round(total_seconds, 3),
        }
        result["model"] = self.answerer.client.model

        if save:
            self.cases.append_history(case_id, result)
        logger.info(
            "Answered in %.1fs (status=%s, confidence=%s)",
            total_seconds,
            result["status"],
            result["confidence"]["level"],
        )
        return result
