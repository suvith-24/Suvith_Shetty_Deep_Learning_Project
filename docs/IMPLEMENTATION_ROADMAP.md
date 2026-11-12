# LexiSyncAI — Implementation Roadmap

Phases were ordered by exam risk: anything visible in the five-minute demo came first. Status reflects the state at the end of the 12 November 2026 upgrade, verified by tests and a real evaluation run.

| Phase | Scope | Key deliverables | Status |
|---|---|---|---|
| A | Audit | `docs/PROJECT_AUDIT.md`, this roadmap, baseline test run (247 passed) | Done |
| B | Baseline hygiene | pytest `testpaths`; stale root `answer_generator.py`/`config.py` and the backup script removed; legacy scripts moved to `scripts/legacy/`; pinned dependencies (duplicate removed); `.gitignore` for app state and stray binaries | Done |
| C | Ingestion + chunking | Validation errors, gutter/column-aware reading order, paragraph rebuilding, running-head removal, footnote detection, Tesseract OCR with confidence, table extraction (ruling prefilter, spanning cells), extended heading grammar, clause IDs, table chunks, page-break fragment merging | Done |
| D | Retrieval + multi-hop | Clause-preserving BM25 tokens, contextual section headers, four retrieval modes with diagnostics, metadata filters, rule-based planner, per-sub-question retrieval with coverage, context expansion | Done |
| E | Grounded generation | Structured JSON claims; deterministic citation/quote/number/coverage/negation checks; LLM reviewer for inconclusive claims; bounded corrective retry with a log; calibrated evidence gate; explained abstention; rule-based confidence; `num_ctx` 8192 and a fixed seed | Done |
| F | Bonus | Cross-document conflict detection, bounding-box highlights, latency/token report, retrieval ablation | Done |
| G | UI | FastAPI + single-page app: dashboard, cases, library (drag and drop, URL, structure report), split-screen workspace with clickable citations and highlighted PDF pages, diagnostics, evaluation dashboard, settings, light/dark themes | Done (screenshots checked in headless Edge) |
| H | Evaluation | 25 held-out questions with expected sections and pages; separate dev calibration set; Recall@1/3/5/10, MRR, multi-hop recall; full generation run; legacy baseline; manual scoring template; report | Done. **Manual scoring pending: needs the author.** |
| I | Tests | 350 passing tests; all LLM calls mocked; synthetic-PDF integration tests | Done |
| J | Docs | README, architecture (+ SVG/PNG diagram), evaluation report, limitations, demo guide, theory Q&A | Done |

## Remaining manual tasks

1. Fill in `evaluation/manual_scoring_template.csv`: answer correctness (1 / 0.5 / 0) and supported citations per answer. The Evaluation dashboard picks it up automatically.
2. Rehearse the demo (`docs/DEMO_GUIDE.md`) with a PDF you have not seen.
3. Commit the work in reviewable steps and push to GitHub; put the repository link in the submitted documentation.

## Deliberately not implemented

| Feature | Reason |
|---|---|
| VLM chart/figure reading | No local vision model is installed, and a 3B text model cannot read figures. Adding one would make the demo machine-dependent. |
| Fine-tuned reranker/embedder | 25 labelled questions are far too few to train on without overfitting the evaluation set itself. |
| Autoencoder page-anomaly detector | Adds little to evidence grounding. The time was better spent on the false-abstention fix. |
| Public deployment | The design depends on a local Ollama model. A public host would need a hosted LLM API and handling of uploaded documents, which is outside the "local LLM" requirement. |
