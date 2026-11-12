"""FastAPI application: JSON API + the single-page LexiSyncAI frontend.

Run with ``python app.py`` (or ``.\\run.ps1``). Everything is served from one
local process; the RAG services are called directly, never re-implemented.
"""

from __future__ import annotations

import csv
import json
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lexisync import config
from lexisync.api.highlight import page_highlights, render_page_png
from lexisync.generation.ollama_client import OllamaClient
from lexisync.ingestion.ocr import find_tesseract, ocr_mode
from lexisync.services.case_manager import CaseError, CaseManager
from lexisync.services.qa_service import QAService
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)

FRONTEND_DIR = config.PROJECT_ROOT / "frontend"
RESULTS_DIR = config.PROJECT_ROOT / "evaluation" / "results"


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class UrlUpload(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    document_ids: list[str] | None = None
    section: str | None = Field(default=None, max_length=120)


def _number(value) -> float | None:
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None


def summarize_manual_scores(path: Path) -> dict:
    """Aggregate the manual scoring sheet; empty cells mean "not scored yet".

    Answer correctness is the mean of 0/1 scores. Citation precision is
    micro-averaged: total supported cited claims / total cited claims
    over rows where supported claims were entered.
    """

    manual = {
        "rows": 0, "draft_rows": 0, "scored_correctness": 0, "scored_citations": 0, "scored_abstention": 0,
        "answer_correctness": None, "citation_precision": None, "abstention_accuracy": None,
    }
    if not path.exists():
        return manual

    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    manual["rows"] = len(rows)

    correctness = [v for v in (_number(r.get("manual_answer_correct_0_or_1")) for r in rows) if v is not None]
    abstention = [v for v in (_number(r.get("abstention_correct_0_or_1")) for r in rows) if v is not None]
    cited = [
        (_number(r.get("supported_cited_claims")), _number(r.get("claims_total")))
        for r in rows
        if _number(r.get("supported_cited_claims")) is not None
    ]

    manual["draft_rows"] = sum(1 for r in rows if "assistant draft" in (r.get("reviewer_notes") or "").casefold())
    manual["scored_correctness"] = len(correctness)
    manual["scored_abstention"] = len(abstention)
    manual["scored_citations"] = len(cited)
    if correctness:
        manual["answer_correctness"] = sum(correctness) / len(correctness)
    if abstention:
        manual["abstention_accuracy"] = sum(abstention) / len(abstention)
    total = sum(t or 0 for _, t in cited)
    if total:
        manual["citation_precision"] = sum(s for s, _ in cited) / total
    return manual


def create_app(case_manager: CaseManager | None = None, qa_service: QAService | None = None) -> FastAPI:
    cases = case_manager or CaseManager()

    def warm_up() -> None:
        """Load models (and the most recent case index) in the background."""
        try:
            cases.models()
            indexed = [c for c in cases.list_cases() if c["status"] == "indexed"]
            if indexed:
                cases.get_pipeline(indexed[0]["id"])
            logger.info("Models warmed up.")
        except Exception as error:  # warm-up is best effort
            logger.warning("Model warm-up skipped: %s", error)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        threading.Thread(target=warm_up, daemon=True).start()
        yield

    app = FastAPI(
        title="LexiSyncAI",
        version=config.APP_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    state = {"qa": qa_service}
    qa_lock = threading.Lock()

    def qa() -> QAService:
        with qa_lock:
            if state["qa"] is None:
                state["qa"] = QAService(cases)
            return state["qa"]

    @app.exception_handler(CaseError)
    async def case_error(_: Request, error: CaseError):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    # ------------------------------------------------------------------ system

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": config.APP_VERSION}

    def ollama_status() -> dict:
        client = OllamaClient(timeout=5)
        return client.status()

    @app.get("/api/system")
    def system():
        return {
            "version": config.APP_VERSION,
            "ollama": ollama_status(),
            "models": {
                "llm": config.OLLAMA_MODEL,
                "embedding": config.EMBEDDING_MODEL,
                "reranker": config.RERANKER_MODEL,
                "claim_reviewer": f"{config.OLLAMA_MODEL} (LLM reviewer) + deterministic checks",
            },
            "retrieval": {
                "candidate_k": config.CANDIDATE_K,
                "final_top_k": config.FINAL_TOP_K,
                "per_sub_query_k": config.PER_SUB_QUERY_K,
                "rrf_k": config.RRF_K,
                "context_window": config.CONTEXT_WINDOW,
                "contextual_headers": config.CONTEXTUAL_HEADERS,
                "chunk_size": config.CHUNK_SIZE,
                "chunk_overlap": config.CHUNK_OVERLAP,
            },
            "grounding": {
                "evidence_gate": config.EVIDENCE_GATE_SCORE,
                "high_confidence_score": config.HIGH_CONFIDENCE_SCORE,
                "max_corrective_retries": config.MAX_CORRECTIVE_RETRIES,
                "verifier_mode": config.VERIFIER_MODE,
                "num_ctx": config.OLLAMA_NUM_CTX,
                "seed": config.RANDOM_SEED,
            },
            "ocr": {"mode": ocr_mode(), "tesseract_found": find_tesseract() is not None},
        }

    @app.get("/api/dashboard")
    def dashboard():
        all_cases = cases.list_cases()
        recent_queries = []
        for case in all_cases:
            for record in cases.history(case["id"], limit=5):
                recent_queries.append({
                    "case_id": case["id"],
                    "case_name": case["name"],
                    "question": record.get("question"),
                    "status": record.get("status"),
                    "confidence": (record.get("confidence") or {}).get("level"),
                    "asked_at": record.get("asked_at"),
                    "seconds": (record.get("timings") or {}).get("total_seconds"),
                    "id": record.get("id"),
                })
        recent_queries.sort(key=lambda r: r.get("asked_at") or "", reverse=True)
        return {
            "totals": {
                "cases": len(all_cases),
                "documents": sum(c["document_count"] for c in all_cases),
                "pages": sum(c["page_count"] for c in all_cases),
                "sections": sum(c["section_count"] for c in all_cases),
                "chunks": sum(c["chunk_count"] for c in all_cases),
                "scanned_pages": sum(c["scanned_page_count"] for c in all_cases),
                "indexed_cases": sum(1 for c in all_cases if c["status"] == "indexed"),
            },
            "recent_cases": all_cases[:6],
            "recent_queries": recent_queries[:8],
            "ollama": ollama_status(),
        }

    # ------------------------------------------------------------------ cases

    @app.get("/api/cases")
    def list_cases():
        return cases.list_cases()

    @app.post("/api/cases", status_code=201)
    def create_case(body: CaseCreate):
        return cases.create_case(body.name, body.description)

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        return cases.get_case(case_id)

    @app.delete("/api/cases/{case_id}", status_code=204)
    def delete_case(case_id: str):
        cases.delete_case(case_id)
        return Response(status_code=204)

    @app.post("/api/cases/{case_id}/reset")
    def reset_case(case_id: str):
        return cases.reset_case(case_id)

    @app.post("/api/cases/{case_id}/documents")
    async def upload_documents(case_id: str, files: list[UploadFile] = File(...)):
        results = []
        for upload in files:
            content = await upload.read()
            try:
                document = cases.add_document(case_id, upload.filename or "document.pdf", content)
                results.append({"file_name": upload.filename, "ok": True, "document": document})
            except CaseError as error:
                results.append({"file_name": upload.filename, "ok": False, "error": str(error)})
        return {"results": results, "case": cases.get_case(case_id)}

    @app.post("/api/cases/{case_id}/documents/url")
    def upload_url(case_id: str, body: UrlUpload):
        document = cases.add_url(case_id, body.url)
        return {"document": document, "case": cases.get_case(case_id)}

    @app.delete("/api/cases/{case_id}/documents/{document_id}")
    def remove_document(case_id: str, document_id: str):
        return cases.remove_document(case_id, document_id)

    @app.post("/api/cases/{case_id}/index")
    def index_case(case_id: str):
        return cases.start_indexing(case_id)

    @app.get("/api/cases/{case_id}/documents/{document_id}/file")
    def document_file(case_id: str, document_id: str):
        path = cases.document_path(case_id, document_id)
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @lru_cache(maxsize=256)
    def _page_png(path: str, mtime: float, page: int) -> bytes:
        return render_page_png(path, page)

    @app.get("/api/cases/{case_id}/documents/{document_id}/pages/{page}/image")
    def page_image(case_id: str, document_id: str, page: int):
        path = cases.document_path(case_id, document_id)
        try:
            png = _page_png(str(path), path.stat().st_mtime, page)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})

    @app.get("/api/cases/{case_id}/documents/{document_id}/pages/{page}/highlights")
    def highlights(case_id: str, document_id: str, page: int, chunk_id: str | None = None, quote: str | None = None):
        path = cases.document_path(case_id, document_id)
        passage = None
        if chunk_id:
            pipeline = cases.get_pipeline(case_id)
            chunk = next((c for c in pipeline.chunks if c.chunk_id == chunk_id), None)
            if chunk is None or chunk.document_id != document_id:
                raise HTTPException(status_code=404, detail="Cited passage not found in this case.")
            passage = chunk.text
        try:
            return page_highlights(str(path), page, passage, quote)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    # ------------------------------------------------------------------ QA

    @app.post("/api/cases/{case_id}/ask")
    def ask(case_id: str, body: AskRequest):
        try:
            return qa().ask(case_id, body.question, document_ids=body.document_ids, section=body.section)
        except ConnectionError as error:
            raise HTTPException(status_code=503, detail=f"{error} Start Ollama and try again.") from error
        except TimeoutError as error:
            raise HTTPException(status_code=504, detail=str(error)) from error

    @app.get("/api/cases/{case_id}/history")
    def history(case_id: str, limit: int = 30):
        cases.get_case(case_id)
        return cases.history(case_id, limit=min(max(limit, 1), 200))

    # ------------------------------------------------------------------ evaluation

    @app.get("/api/evaluation")
    def evaluation():
        def load(name: str):
            path = RESULTS_DIR / name
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        template = config.PROJECT_ROOT / "evaluation" / "manual_scoring_template.csv"
        manual = summarize_manual_scores(template)

        questions_path = config.PROJECT_ROOT / "evaluation" / "held_out_questions.json"
        questions = json.loads(questions_path.read_text(encoding="utf-8")) if questions_path.exists() else []
        retrieval = load("retrieval_metrics.json")
        return {
            "summary": load("summary.json"),
            "calibration": load("calibration.json"),
            "generation": load("generation_results.json"),
            "retrieval_rows": {
                variant: {mode: data[mode]["rows"] for mode in ("dense", "bm25", "hybrid", "hybrid_rerank")}
                for variant, data in (retrieval or {}).items()
                if isinstance(data, dict) and "dense" in data
            },
            "manual": manual,
            "dataset": {
                "questions": len(questions),
                "factual": sum(q.get("type") == "factual" for q in questions),
                "multi_hop": sum(q.get("type") == "multi_hop" for q in questions),
                "unanswerable": sum(q.get("type") == "unanswerable" for q in questions),
                "document": "gdpr.pdf (Regulation (EU) 2016/679, 88 pages)",
            },
        }

    # ------------------------------------------------------------------ frontend

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app
