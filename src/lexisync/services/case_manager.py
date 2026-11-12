"""Case management: isolated document bundles, each with its own persisted index.

Storage layout (unchanged from the original per-case design):

    data/uploads/<case_id>/<file>.pdf          uploaded PDFs
    storage/indexes/<case_id>/legal_documents.*  FAISS index + chunk metadata
    storage/cases/<case_id>/case.json          case metadata + document structure
    storage/cases/<case_id>/history.jsonl      question/answer history

A case's retrieval pipeline only ever loads that case's index, so switching
cases cannot expose another case's evidence. Models (embedder, reranker) are
loaded once and shared, which is safe because they hold no case data.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from lexisync import config
from lexisync.ingestion.pdf_loader import file_sha256
from lexisync.retrieval.index_store import IndexStore
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)

_CASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class CaseError(ValueError):
    """User-facing error for case operations."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return normalized[:48] or "case"


def safe_filename(name: str) -> str:
    base = Path(unquote(name)).name
    stem = re.sub(r"[^A-Za-z0-9 ._()-]+", "_", Path(base).stem).strip(" .") or "document"
    return f"{stem[:80]}.pdf"


@dataclass
class SharedModels:
    """Embedding model and reranker loaded once per process."""

    embedder: object
    reranker: object


class CaseManager:
    """Create, list, populate, index and delete cases."""

    def __init__(
        self,
        uploads_dir: Path = config.UPLOADS_DIR,
        index_dir: Path = config.INDEX_DIR,
        cases_dir: Path = config.CASES_DIR,
        models_factory=None,
    ) -> None:
        self.uploads_dir = Path(uploads_dir)
        self.index_dir = Path(index_dir)
        self.cases_dir = Path(cases_dir)
        for directory in (self.uploads_dir, self.index_dir, self.cases_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self._models_factory = models_factory or _load_shared_models
        self._models: SharedModels | None = None
        self._pipelines: dict[str, RetrievalPipeline] = {}
        self._lock = threading.RLock()
        self._case_locks: dict[str, threading.Lock] = {}
        self._progress: dict[str, dict] = {}
        self._import_legacy_cases()

    def _import_legacy_cases(self) -> None:
        """Register upload folders from the earlier Streamlit version as cases.

        Their old indexes were built with the previous chunker, so they are
        imported as "pending" and must be re-indexed; nothing is deleted.
        """

        for folder in sorted(p for p in self.uploads_dir.iterdir() if p.is_dir()):
            if not _CASE_ID.match(folder.name) or (self.cases_dir / folder.name / "case.json").exists():
                continue
            pdfs = sorted(folder.glob("*.pdf"))[: config.MAX_DOCUMENTS_PER_CASE]
            if not pdfs:
                continue
            documents = []
            for pdf in pdfs:
                documents.append({
                    "document_id": pdf.stem, "file_name": pdf.name, "sha256": file_sha256(pdf),
                    "size_bytes": pdf.stat().st_size, "added_at": _now(), "status": "pending",
                    "pages": None, "sections": None, "chunks": None, "scanned_pages": [],
                    "ocr_pages": [], "tables": None, "warnings": [],
                })
            self._save({
                "id": folder.name, "name": folder.name.replace("_", " ").replace("-", " "),
                "description": "Imported from the previous version; re-index to use the new pipeline.",
                "created_at": _now(), "updated_at": _now(), "status": "pending", "indexed_at": None,
                "error": None, "documents": documents,
                "settings": {
                    "contextual_headers": config.CONTEXTUAL_HEADERS,
                    "chunk_size": config.CHUNK_SIZE,
                    "chunk_overlap": config.CHUNK_OVERLAP,
                },
            })
            logger.info("Imported legacy case folder %s", folder.name)

    # ------------------------------------------------------------------
    # Paths and persistence
    # ------------------------------------------------------------------

    def _check_id(self, case_id: str) -> str:
        if not isinstance(case_id, str) or not _CASE_ID.match(case_id):
            raise CaseError("Invalid case identifier.")
        return case_id

    def _meta_path(self, case_id: str) -> Path:
        return self.cases_dir / self._check_id(case_id) / "case.json"

    def _history_path(self, case_id: str) -> Path:
        return self.cases_dir / self._check_id(case_id) / "history.jsonl"

    def upload_dir(self, case_id: str) -> Path:
        return self.uploads_dir / self._check_id(case_id)

    def index_store(self, case_id: str) -> IndexStore:
        return IndexStore(index_dir=self.index_dir / self._check_id(case_id), index_name="legal_documents")

    def _save(self, case: dict) -> None:
        path = self._meta_path(case["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        case["updated_at"] = _now()
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _case_lock(self, case_id: str) -> threading.Lock:
        with self._lock:
            return self._case_locks.setdefault(case_id, threading.Lock())

    # ------------------------------------------------------------------
    # Case CRUD
    # ------------------------------------------------------------------

    def list_cases(self) -> list[dict]:
        cases = []
        for path in sorted(self.cases_dir.glob("*/case.json")):
            try:
                cases.append(self._decorate(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError) as error:
                logger.warning("Skipping unreadable case metadata %s: %s", path, error)
        cases.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return cases

    def get_case(self, case_id: str) -> dict:
        path = self._meta_path(case_id)
        if not path.exists():
            raise CaseError(f"Case '{case_id}' does not exist.")
        return self._decorate(json.loads(path.read_text(encoding="utf-8")))

    def _raw_case(self, case_id: str) -> dict:
        path = self._meta_path(case_id)
        if not path.exists():
            raise CaseError(f"Case '{case_id}' does not exist.")
        return json.loads(path.read_text(encoding="utf-8"))

    def _decorate(self, case: dict) -> dict:
        case = dict(case)
        docs = case.get("documents", [])
        case["document_count"] = len(docs)
        case["page_count"] = sum(d.get("pages") or 0 for d in docs)
        case["section_count"] = sum(d.get("sections") or 0 for d in docs)
        case["chunk_count"] = sum(d.get("chunks") or 0 for d in docs)
        case["scanned_page_count"] = sum(len(d.get("scanned_pages") or []) for d in docs)
        case["progress"] = self._progress.get(case["id"])
        return case

    def update_settings(self, case_id: str, **settings) -> dict:
        """Change indexing settings (chunk size/overlap, contextual headers).

        The case must be re-indexed for new settings to take effect.
        """

        allowed = {"contextual_headers", "chunk_size", "chunk_overlap"}
        unknown = set(settings) - allowed
        if unknown:
            raise CaseError(f"Unknown settings: {', '.join(sorted(unknown))}")
        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            case.setdefault("settings", {}).update(settings)
            if case["documents"]:
                case["status"] = "pending"
            self._pipelines.pop(case_id, None)
            self._save(case)
        return self._decorate(case)

    def create_case(self, name: str, description: str = "") -> dict:
        if not isinstance(name, str) or not name.strip():
            raise CaseError("Case name cannot be empty.")
        base = slugify(name)
        with self._lock:
            case_id = base
            suffix = 2
            while self._meta_path(case_id).exists():
                case_id = f"{base[:44]}-{suffix}"
                suffix += 1
            case = {
                "id": case_id,
                "name": name.strip()[:120],
                "description": (description or "").strip()[:500],
                "created_at": _now(),
                "updated_at": _now(),
                "status": "empty",
                "indexed_at": None,
                "error": None,
                "documents": [],
                "settings": {
                    "contextual_headers": config.CONTEXTUAL_HEADERS,
                    "chunk_size": config.CHUNK_SIZE,
                    "chunk_overlap": config.CHUNK_OVERLAP,
                },
            }
            self._save(case)
        logger.info("Created case %s", case_id)
        return self._decorate(case)

    def delete_case(self, case_id: str) -> None:
        self._check_id(case_id)
        with self._case_lock(case_id):
            self._raw_case(case_id)  # raises if missing
            self._pipelines.pop(case_id, None)
            for directory in (self.upload_dir(case_id), self.index_dir / case_id, self.cases_dir / case_id):
                if directory.exists():
                    shutil.rmtree(directory)
        logger.info("Deleted case %s", case_id)

    def reset_case(self, case_id: str) -> dict:
        """Remove all documents and the index, keeping the case itself."""

        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            self._pipelines.pop(case_id, None)
            for directory in (self.upload_dir(case_id), self.index_dir / case_id):
                if directory.exists():
                    shutil.rmtree(directory)
            history = self._history_path(case_id)
            if history.exists():
                history.unlink()
            case.update({"documents": [], "status": "empty", "indexed_at": None, "error": None})
            self._save(case)
        return self._decorate(case)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def add_document(self, case_id: str, filename: str, content: bytes) -> dict:
        """Validate and store one uploaded PDF. The case must then be re-indexed."""

        if not filename or not filename.casefold().endswith(".pdf"):
            raise CaseError(f"'{filename}' is not a PDF file.")
        if not content:
            raise CaseError(f"'{filename}' is empty.")
        if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise CaseError(f"'{filename}' exceeds the {config.MAX_UPLOAD_MB} MB upload limit.")
        if b"%PDF" not in content[:1024]:
            raise CaseError(f"'{filename}' is not a valid PDF (missing %PDF signature).")

        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            documents = case["documents"]
            if len(documents) >= config.MAX_DOCUMENTS_PER_CASE:
                raise CaseError(f"A case can contain at most {config.MAX_DOCUMENTS_PER_CASE} documents.")

            name = safe_filename(filename)
            target_dir = self.upload_dir(case_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            temporary = target_dir / f".upload-{uuid.uuid4().hex}.tmp"
            temporary.write_bytes(content)
            digest = file_sha256(temporary)

            duplicate = next((d for d in documents if d.get("sha256") == digest), None)
            if duplicate:
                temporary.unlink(missing_ok=True)
                raise CaseError(f"'{filename}' is identical to '{duplicate['file_name']}', which is already in this case.")

            existing = {d["file_name"].casefold() for d in documents}
            stem, counter = Path(name).stem, 2
            while name.casefold() in existing:
                name = f"{stem} ({counter}).pdf"
                counter += 1

            target = target_dir / name
            temporary.replace(target)

            document = {
                "document_id": Path(name).stem,
                "file_name": name,
                "sha256": digest,
                "size_bytes": len(content),
                "added_at": _now(),
                "status": "pending",
                "pages": None,
                "sections": None,
                "chunks": None,
                "scanned_pages": [],
                "ocr_pages": [],
                "tables": None,
                "warnings": [],
            }
            documents.append(document)
            case["status"] = "pending"
            self._save(case)
        return document

    def add_url(self, case_id: str, url: str) -> dict:
        """Download a public PDF from an http(s) URL and add it to the case."""

        parsed = urlparse(url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CaseError("Only http(s) URLs are supported.")
        request = Request(url, headers={"User-Agent": "LexiSyncAI/1.0 (document ingestion)"})
        limit = config.MAX_UPLOAD_MB * 1024 * 1024
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read(limit + 1)
        except Exception as error:
            raise CaseError(f"Could not download the PDF: {error}") from error
        if len(content) > limit:
            raise CaseError(f"The document exceeds the {config.MAX_UPLOAD_MB} MB limit.")
        filename = Path(parsed.path).name or "downloaded.pdf"
        if not filename.casefold().endswith(".pdf"):
            filename += ".pdf"
        return self.add_document(case_id, filename, content)

    def remove_document(self, case_id: str, document_id: str) -> dict:
        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            document = next((d for d in case["documents"] if d["document_id"] == document_id), None)
            if document is None:
                raise CaseError(f"Document '{document_id}' is not in this case.")
            (self.upload_dir(case_id) / document["file_name"]).unlink(missing_ok=True)
            case["documents"] = [d for d in case["documents"] if d["document_id"] != document_id]
            self._pipelines.pop(case_id, None)
            index_folder = self.index_dir / case_id
            if index_folder.exists():
                shutil.rmtree(index_folder)
            case["status"] = "pending" if case["documents"] else "empty"
            case["indexed_at"] = None
            self._save(case)
        return self._decorate(case)

    def document_path(self, case_id: str, document_id: str) -> Path:
        case = self._raw_case(case_id)
        document = next((d for d in case["documents"] if d["document_id"] == document_id), None)
        if document is None:
            raise CaseError(f"Document '{document_id}' is not in this case.")
        path = self.upload_dir(case_id) / document["file_name"]
        if not path.exists():
            raise CaseError(f"The file for '{document_id}' is missing.")
        return path

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def models(self) -> SharedModels:
        with self._lock:
            if self._models is None:
                self._models = self._models_factory()
            return self._models

    def start_indexing(self, case_id: str) -> dict:
        """Index the case in a background thread; poll ``get_case`` for progress."""

        case = self._raw_case(case_id)
        if not case["documents"]:
            raise CaseError("Add at least one PDF before indexing.")
        if self._progress.get(case_id, {}).get("running"):
            raise CaseError("This case is already being indexed.")
        self._progress[case_id] = {"running": True, "message": "Queued", "started_at": time.time()}
        thread = threading.Thread(target=self._index_safely, args=(case_id,), daemon=True)
        thread.start()
        return self.get_case(case_id)

    def _index_safely(self, case_id: str) -> None:
        try:
            self.index_case(case_id)
        except Exception as error:  # reported to the UI through case.json
            logger.exception("Indexing failed for case %s", case_id)
            with self._case_lock(case_id):
                case = self._raw_case(case_id)
                case["status"] = "error"
                case["error"] = str(error)
                self._save(case)
        finally:
            progress = self._progress.get(case_id, {})
            progress["running"] = False
            progress["finished_at"] = time.time()

    def index_case(self, case_id: str) -> dict:
        """Extract, chunk, embed and persist the case index (blocking)."""

        def progress(message: str) -> None:
            self._progress.setdefault(case_id, {})["message"] = message
            logger.info("[%s] %s", case_id, message)

        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            case["status"] = "indexing"
            case["error"] = None
            self._save(case)
            settings = case.get("settings", {})
            paths = [self.upload_dir(case_id) / d["file_name"] for d in case["documents"]]

        models = self.models()
        started = time.perf_counter()
        indexer = DocumentIndexingPipeline(
            index_store=self.index_store(case_id),
            chunk_size=settings.get("chunk_size", config.CHUNK_SIZE),
            chunk_overlap=settings.get("chunk_overlap", config.CHUNK_OVERLAP),
            contextual=settings.get("contextual_headers", config.CONTEXTUAL_HEADERS),
            model=models.embedder,
        )
        retriever = indexer.build(paths, progress=progress)
        progress("Finalising document structure")

        chunks_by_document: dict[str, list] = {}
        for chunk in retriever.chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

        with self._case_lock(case_id):
            case = self._raw_case(case_id)
            for document in case["documents"]:
                loaded = next((d for d in indexer.documents if d.document_id == document["document_id"]), None)
                if loaded is None:
                    continue
                document.update(_document_summary(loaded, chunks_by_document.get(loaded.document_id, [])))
                document["status"] = "indexed"
            case["status"] = "indexed"
            case["indexed_at"] = _now()
            if case.get("description", "").startswith("Imported from the previous version"):
                case["description"] = "Imported from the previous version."
            case["index_seconds"] = round(time.perf_counter() - started, 2)
            self._save(case)
            self._pipelines.pop(case_id, None)

        progress(f"Indexed {len(retriever.chunks)} passages in {time.perf_counter() - started:.1f} s")
        return self.get_case(case_id)

    def get_pipeline(self, case_id: str) -> RetrievalPipeline:
        """Return the (cached) retrieval pipeline that reads only this case's index."""

        case = self._raw_case(case_id)
        if case.get("status") != "indexed":
            raise CaseError("This case has not been indexed yet.")
        with self._lock:
            pipeline = self._pipelines.get(case_id)
            if pipeline is None:
                models = self.models()
                contextual = case.get("settings", {}).get("contextual_headers", config.CONTEXTUAL_HEADERS)
                from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker

                pipeline = RetrievalPipeline(
                    indexing_pipeline=DocumentIndexingPipeline(
                        index_store=self.index_store(case_id),
                        contextual=contextual,
                        model=models.embedder,
                    ),
                    reranker=CrossEncoderReranker(model=models.reranker, contextual=contextual),
                    candidate_k=config.CANDIDATE_K,
                    top_k=config.FINAL_TOP_K,
                    rrf_k=config.RRF_K,
                    contextual=contextual,
                )
                pipeline.initialize()
                self._pipelines[case_id] = pipeline
            return pipeline

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def append_history(self, case_id: str, record: dict) -> None:
        path = self._history_path(case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def history(self, case_id: str, limit: int = 50) -> list[dict]:
        path = self._history_path(case_id)
        if not path.exists():
            return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(records))[:limit]


def _document_summary(document, chunks: list) -> dict:
    pages = []
    for page in document.pages:
        pages.append({
            "page": page.page_number,
            "characters": page.character_count,
            "scanned": page.is_scanned,
            "method": page.extraction_method,
            "ocr_confidence": page.ocr_confidence,
            "columns": page.column_count,
            "tables": len(page.tables),
            "footnotes": len(page.footnotes),
            "warnings": page.warnings,
        })
    sections = list(dict.fromkeys(c.section for c in chunks if c.section and c.section != "General"))
    meta = document.metadata
    return {
        "title": document.title,
        "author": document.author,
        "pages": document.total_pages,
        "sections": len(sections),
        "section_titles": sections[:300],
        "chunks": len(chunks),
        "table_chunks": sum(1 for c in chunks if (c.metadata or {}).get("chunk_type") == "table"),
        "scanned_pages": meta.get("scanned_pages", []),
        "ocr_pages": meta.get("ocr_pages", []),
        "ocr_available": meta.get("ocr_available"),
        "creation_date": meta.get("creation_date"),
        "tables": meta.get("table_count", 0),
        "multi_column_pages": meta.get("multi_column_pages", []),
        "running_heads_removed": meta.get("running_heads_removed", 0),
        "footnotes": meta.get("footnote_count", 0),
        "warnings": meta.get("warnings", []),
        "page_details": pages,
    }


def _load_shared_models() -> SharedModels:
    from sentence_transformers import CrossEncoder, SentenceTransformer

    logger.info("Loading shared embedding and reranker models.")
    return SharedModels(
        embedder=SentenceTransformer(config.EMBEDDING_MODEL, device="cpu"),
        reranker=CrossEncoder(config.RERANKER_MODEL, device="cpu"),
    )
