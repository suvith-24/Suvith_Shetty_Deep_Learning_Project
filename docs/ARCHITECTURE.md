# LexiSyncAI — Architecture

One-page diagram: [architecture.svg](architecture.svg) (PNG export: [architecture.png](architecture.png)).

## Overview

LexiSyncAI is a local retrieval-augmented generation (RAG) system for public legal documents. One Python process (FastAPI + uvicorn) serves both the JSON API and a dependency-free single-page frontend. All models run on the local machine:

| Role | Model | Where it runs |
|---|---|---|
| Dense embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-d bi-encoder) | CPU, sentence-transformers |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | CPU, sentence-transformers |
| Answer generation + claim review | `qwen2.5:3b` (Q4_K_M) | Ollama |
| OCR | Tesseract 5 (LSTM engine) | CLI, only on scanned pages |

## Pipeline

### 1. Ingestion — `src/lexisync/ingestion/`

| Step | Module | Notes |
|---|---|---|
| Validation | `pdf_loader._validate_path`, `_open_pdf` | Extension, `%PDF` signature, empty file, corrupt file, password protection, zero pages. Each error is a user-facing `PDFIngestionError`. |
| Word-level extraction | `pdf_loader` | Words grouped into physical lines by y-coordinate; soft hyphens are re-joined. |
| Reading order | `layout.split_blocks_at_gutter`, `detect_columns`, `order_blocks` | A column gutter is detected from aligned horizontal gaps. Two-column pages are read column by column within bands separated by full-width blocks. |
| Paragraphs | `pdf_loader._join_blocks` | Blocks with a vertical gap under 35 % of the line height are continuation lines and are joined. |
| Running heads | `layout.margin_lines`, `recurring_signatures` | Lines in the top or bottom 8 % margin that recur (digits normalised) on ≥ 40 % of pages, plus bare page numbers, are removed and kept in `Page.header_lines/footer_lines`. |
| Footnotes | `pdf_loader._footnotes` | Numbered small-font lines in the lower part of the page are recorded. They stay in reading order at the page end. |
| Tables | `tables.extract_tables` | A cheap ruling-line prefilter, then PyMuPDF `find_tables`. Each cell is re-read from its bounding box, spanning cells are forward-filled, and the table is rendered as a pipe table in reading position. |
| Scanned pages / OCR | `ocr.py` | A page with < 50 extracted characters is flagged as scanned. If it contains an image, it is rendered at 300 DPI and OCR'd with Tesseract (TSV output gives a mean word confidence). Blank pages and disabled/missing OCR produce warnings. |

### 2. Legal-aware chunking — `src/lexisync/chunking/legal_chunker.py`

- **Sections** start at headings: Chapter, Part, Title, Article, Section, §, Schedule, Annex, Appendix, Exhibit, numbered CAPITAL headings, and short `7.2 Title` headings. A bare `Article 83` absorbs its title line.
- **Splitting** is paragraph-first: up to 1000 characters with 150 characters of overlap, cutting at the last paragraph break if it lies past 60 % of the window. The heading carries across pages.
- **Clause IDs**: GDPR-style `1.` paragraphs become `83(1)`, and dotted `3.1` / `7.2.1` clauses are recognised. The clause in force at the chunk start becomes `Chunk.subsection`.
- **Tables** are carved out before text splitting and become `chunk_type="table"` chunks. Large tables are split by row, with the header repeated in each part.
- **Page-break fragments** under 100 characters are merged into the next page's first chunk of the same section, which then cites both pages.
- **Metadata per chunk**: `document_id`, `file_name`, `page_numbers`, `section`, `section_key`, `subsection`/`clause_ids`, `chunk_type`, `extraction_method`, `ocr_confidence`, and character offsets.

### 3. Indexing — `src/lexisync/retrieval/`

- `BM25Retriever` (rank-bm25 `BM25Okapi`). The tokenizer adds whole clause tokens (`7.2`, `83(4)`) and reference tokens (`article:83`, `section:7.2`), because the plain tokenizer splits `7.2` into `7` and `2`.
- `FAISSRetriever`: normalised embeddings in `IndexFlatIP`, so the inner product equals cosine similarity and the search is exact.
- **Contextual section headers** (`LEXISYNC_CONTEXTUAL_HEADERS`, on by default): the section title is prepended to the text that is embedded, BM25-indexed and reranked. The stored chunk text is unchanged, so later paragraphs of a long article stay findable by its number and title.
- `IndexStore` persists `legal_documents.faiss` and `legal_documents_chunks.json` atomically under `storage/indexes/<case_id>/`.

### 4. Retrieval — `retrieval_pipeline.RetrievalPipeline`

`search_detailed(query, mode, filters)` supports four modes and returns every intermediate ranking (used by the diagnostics panel and the evaluation):

| Mode | Pipeline |
|---|---|
| `dense` | FAISS top-k |
| `bm25` | BM25 top-k |
| `hybrid` | BM25 top-20 ∪ FAISS top-20 → RRF (k = 60) |
| `hybrid_rerank` (system) | hybrid → cross-encoder → top-5 |

Filters (`RetrievalFilters`) restrict documents, sections (word-boundary match, so `Article 8` ≠ `Article 83`) and pages at every stage.

**Multi-hop** (`query_planner.QueryPlanner` + `multi_hop_search`):

1. The rule-based planner splits a question only when it has several questions, a coordinated second question ("…, and when may it be extended?"), or references to two or more provisions. Each provision's sub-query takes the words of its own segment of the question.
2. The full question and every sub-query are retrieved separately. Each sub-query is reranked against its own text, so each information need gets its own best passages.
3. Evidence is merged and de-duplicated. Each passage keeps the sub-queries it serves, and coverage per sub-query is recorded.

**Context expansion**: the chunk following each of the top three passages is added as a `context` source, which catches provisions that continue across chunk boundaries.

**Conflict detection** (`analysis/conflict_detector.py`): sentences from different documents that share a topic (Jaccard ≥ 0.3 over content words, with ≥ 3 shared terms) but state different dates, amounts, percentages or durations are reported as potential conflicts. Amendment wording and document dates are attached as version notes. The detector never picks a winner.

### 5. Grounded generation — `generation/grounded_answerer.py`

1. **Evidence gate**: if the best cross-encoder logit is < 0, the system abstains *without calling the LLM*. The threshold was calibrated on a separate dev set (see the evaluation report).
2. **Draft**: the prompt lists numbered sources `[S1]…` (file, section, clauses, pages) and any detected conflicts. The model returns JSON (Ollama `format: json`, temperature 0, seed 42, `num_ctx` 8192) with one fact per claim, the source IDs and a verbatim quote. The system prompt marks sources as untrusted text and forbids following instructions inside them.
3. **Verify every claim** (`claim_support.assess_claim`):
   - **Hard failures**: no citation, an unknown source ID, or a number (amount, deadline, article number; "€10 million" = "10 000 000 EUR") that is missing from the cited passages. These can never be overridden.
   - **Deterministic support**: the quote appears verbatim in a *cited* source (whitespace/typography normalised, case-sensitive except the first letter), ≥ 70 % of the claim's content words are in the cited text, and negation agrees. A quote found in an uncited source triggers a deterministic citation correction, which is shown to the user.
   - **Otherwise**: the existing `LLMClaimReviewer` returns SUPPORTED / CONTRADICTED / INSUFFICIENT, with its own exact-quote check. Malformed reviews become INCONCLUSIVE.
4. **Bounded corrective retry** (`LEXISYNC_MAX_RETRIES`, default 1): failed claims and their reasons go back to the model. Every attempt (draft, failed claims, corrective prompt) is logged and shown in the UI.
5. **Decision**: only SUPPORTED claims are displayed; removed claims are listed with their reason. A multi-hop part with no supported claim is reported as unanswered (`partial`). If nothing is supported, or no part is covered, the system abstains and lists the documents searched. The model's free-text explanation is shown only if it contains no number that is absent from the cited passages.
6. **Confidence** (`generation/confidence.py`, rule-based, *not* a calibrated probability):
   - **HIGH**: every claim was verified, every part is covered, there are no conflicts, and the top score is ≥ 3.
   - **LOW**: a part is unanswered, under half of the claims survived, or retrieval is weak.
   - **MEDIUM**: anything in between.
   - **INSUFFICIENT**: the system abstained.

The original free-text `AnswerGenerator` is kept, together with its tests, as the measured baseline (`scripts/evaluate.py --legacy-baseline`).

### 6. Services, API and UI

- `services/case_manager.py` handles case CRUD, validated uploads (size, signature, SHA-256 duplicates, maximum 5 documents), URL ingestion, background indexing with progress messages, cached per-case pipelines (shared model instances, isolated indexes), question history, and import of upload folders from the earlier Streamlit version.
- `services/qa_service.py` runs plan → retrieve → expand → detect conflicts → answer, and records timings and per-stage rankings.
- `api/server.py` exposes the REST API: cases, documents, indexing, ask, history, page images, highlight geometry, evaluation and system status. `api/highlight.py` matches the cited passage and quote against the page's words (`difflib`) and returns line-level bounding boxes.
- `frontend/` is the single-page app with these views:
  - Dashboard
  - My Cases
  - Document Library: drag-and-drop, URL fetch, structure report
  - Legal AI Workspace: split-screen answer and evidence viewer, clickable citations, highlighted PDF page, diagnostics
  - Evaluation & Analytics
  - Settings

## Case isolation

Each case has its own upload folder, index folder and metadata folder. `CaseManager.get_pipeline(case_id)` builds a `RetrievalPipeline` whose `IndexStore` points only at `storage/indexes/<case_id>/`. The embedding and reranker *models* are shared because they hold no case data. `tests/test_services_api.py::test_case_isolation` indexes two cases and asserts that neither can retrieve the other's text, including after re-indexing.

## Technology decision (frontend)

Streamlit was replaced by FastAPI and a framework-free frontend. The reasons:

- **Interaction:** a split-screen workspace with inline clickable citations that drive a PDF viewer does not fit Streamlit's rerun model.
- **Startup:** React would need a Node build at exam time.
- **Single source of logic:** the RAG services are called directly, so no business logic is duplicated in JavaScript.

`docs/PROJECT_AUDIT.md` gives the full comparison.
