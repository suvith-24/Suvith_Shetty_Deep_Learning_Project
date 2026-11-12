# LexiSyncAI — Project Audit (baseline before the November 2026 upgrade)

Audit date: 12 November 2026 · Branch: `fix/case-isolation-evaluation` · Baseline commit: `6db7798`

This audit records what the repository contained **before** the upgrade work, measured rather than assumed.

## Baseline facts (measured)

| Item | Measured value |
|---|---|
| Python | 3.11.9 (`.venv`) |
| Unit tests | `python -m pytest -q` → **247 passed** in 57 s |
| Ollama | Running locally, `qwen2.5:3b` (Q4_K_M, 3.1B) available |
| Tesseract | v5.5.0 installed at `C:\Program Files\Tesseract-OCR` (not used by the code) |
| Index | One shared GDPR index (`storage/indexes/legal_documents.*`, 535 chunks) plus per-case folders |
| Benchmark | 18 GDPR questions (14 answerable, 4 unanswerable); **no multi-hop questions, no page labels** |
| Generation results | `held_out_results.json` contains retrieval metrics only; every `retrieval_abstained` is `null` (generation never completed for the full set) |

### False-abstention reproduction

Question: *"What are the maximum administrative fines for the two tiers of GDPR infringements?"*

- Retrieval was correct: Article 83, pages 82–83, at reranked positions 1–2.
- The draft answer contained the correct figures (EUR 10M / 2 % and EUR 20M / 4 %).
- The final output was **"The retrieved documents do not provide sufficient evidence…"** (false abstention, 52 s).
- Root cause: `qwen2.5:3b` writes paragraph-style answers with one citation per paragraph. The sentence-level gate marked 11 of 13 sentences "inconclusive: no citation". The LLM reviewer's quotes also failed exact matching on the remaining cited claim. **This is a format failure, not a grounding failure.** Free-text generation cannot be relied on to place a citation after every sentence.

## Requirement-by-requirement audit

Status key: **Implemented**, **Partially implemented**, **Missing**, **Needs validation**.

| Assignment requirement | Existing implementation | Current status | Missing functionality | Planned implementation |
|---|---|---|---|---|
| Case creation, upload 2–5 PDFs | Streamlit sidebar: case name + uploader; files stored per case | Partially implemented | No case list, switching, deletion, reset, metadata, timestamps, URL ingest; re-uploading overwrote files silently | Case manager service with persisted `case.json`, CRUD, duplicate detection (SHA-256), URL ingestion |
| Show detected structure (pages, sections, tables, scanned) | Expander lists pages, scanned count, sections | Partially implemented | No tables, OCR status, warnings, chunk counts | Structure summary per document from the ingestion metadata |
| Reading order (columns, headers, footers, footnotes) | Word-coordinate line reconstruction, soft-hyphen repair, OJ header blanking in chunker | Partially implemented | No column detection, generic header/footer removal or footnote handling | Column-aware block ordering; recurring margin-line removal; footnote detection |
| Scanned-page flag | `len(text) < 50` | Implemented (flag only) | No OCR, no blank/scanned distinction | Tesseract OCR fallback on image pages with confidence; blank pages distinguished |
| Clause/section-aware chunking | Heading regex (Chapter/Article/Section/`7.2 Title`), paragraph-preferring splits, section carried across pages | Partially implemented | No Part/Schedule/Annex/Appendix headings, no clause IDs, no table chunks | Extended heading grammar; clause IDs in metadata; table chunks |
| BM25 + dense + RRF | `BM25Retriever`, `FAISSRetriever`, `HybridRetriever` (k=60), weighted multi-query RRF | Implemented | Clause numbers like `7.2` are split into `7`/`2` by the tokenizer; no metadata filters | Clause-preserving tokenisation; document/section/page filters |
| Cross-encoder reranking | `CrossEncoderReranker` (ms-marco-MiniLM-L-6-v2) | Implemented | Scores not exposed for confidence/diagnostics | Expose scores; use them for the evidence gate |
| Recall@k per configuration | `evaluate_held_out.py`: dense vs hybrid Recall@5 | Partially implemented | Only k=5; no BM25-only, no hybrid-without-rerank, no MRR, no page-level relevance | Recall@1/3/5/10 + MRR for four configurations |
| Local LLM answer with page citations | `AnswerGenerator` + Ollama | Needs validation → **failing** | False abstentions on correct answers (see above) | Structured per-claim JSON generation; deterministic citation validation |
| UI shows cited page | Page image rendered inside an expander | Partially implemented | No side-by-side answer/evidence, no clickable citations, no highlighting | Split-screen workspace with clickable citations and highlighted page regions |
| Abstention | Empty evidence or failed gate → fixed message | Partially implemented | No pre-generation evidence gate, no "documents searched" list, no missing-part explanation | Reranker-score evidence gate, sub-question coverage check, explained abstentions |
| Confidence badge | HIGH/MEDIUM/LOW from validation flags | Partially implemented | Not derived from retrieval/coverage signals | Rule-based confidence from reranker score, coverage, claim verification and conflicts |
| Conflicting sources | Not handled | Missing | — | Cross-document conflict detector (dates, amounts, percentages, durations) |
| ≥15 held-out questions incl. multi-hop and ≥3 unanswerable | 18 questions, 4 unanswerable, 0 multi-hop | Partially implemented | Multi-hop questions, page ground truth | Add multi-hop questions with page labels taken from the PDF |
| Answer correctness (manual), citation precision | Fields exist but empty | Missing | Manual scoring template | `evaluation/manual_scoring_template.csv` + automated proxies, clearly labelled |
| Abstention accuracy, latency | Code path exists; never completed | Missing (no results) | Full generation run | Run full generation evaluation and report |
| Mandatory comparison | Dense-only vs hybrid Recall@5 | Implemented | Extend to more k and configurations | See above |
| One-command run, pinned deps, fixed seeds | `run.ps1`, pinned deps (duplicate `rank-bm25`), no seeds | Partially implemented | Ollama/model checks, seeds, `.env.example` completeness | Rewritten `run.ps1`, seeded components |
| README, architecture diagram | README + `docs/architecture.svg` | Partially implemented | Demo guide, theory Q&A, evaluation report, limitations | Full documentation set |

### Bonus features (assignment §4)

| # | Feature | Baseline | Plan |
|---|---|---|---|
| 1 | OCR for scanned pages | Missing (flag only) | Tesseract fallback with per-page confidence and an "unavailable" fallback path |
| 2 | Table extraction | Missing | PyMuPDF `find_tables`, spanning-cell forward fill, tables as searchable chunks |
| 4 | Bounding-box citations | Missing | Highlight rectangles of the cited passage on the rendered page image |
| 5 | Planner + verifier loop | Partially (one citation repair, one reviewer retry) | Query planner (sub-questions) + verifier with bounded corrective retry and a retry log |
| 7 | Ablation table | Missing | Retrieval ablation (dense / BM25 / hybrid / hybrid+rerank); verifier on/off |
| 9 | Multi-document conflict detection | Missing | Conflict detector + UI panel |
| 11 | Latency and cost report | Missing | Per-stage timings and token counts from Ollama per question |
| 3, 6, 8, 10 | VLM figures, fine-tuning, autoencoder, public deployment | Missing | Not planned (see roadmap for reasons) |

## Code-quality findings

- `answer_generator.py` and `config.py` at the repository root are stale duplicates. The root `answer_generator.py` imports non-existent top-level packages and is dead code.
- `scripts/run_end_to_end_evaluation_backup.py` is a backup copy.
- `scripts/test_*.py` are manual scripts that call the live model. pytest has no `testpaths`, so they could be collected.
- `pyproject.toml` lists `rank-bm25` twice and does not declare `numpy`/`faiss` usage explicitly beyond `faiss-cpu`.
- `data/raw/` contains a `Claude Setup.exe` installer, which is not project material. It is git-ignored only by accident (`data/raw/*.pdf` covers PDFs only). The new `.gitignore` covers it.

## Frontend technology decision

The Streamlit app cannot produce a split-screen workspace with clickable inline citations that drive a PDF viewer without fighting the framework: each interaction reruns the whole script, and inline citation chips cannot trigger Python callbacks. The options were:

1. **Streamlit + CSS**: rejected. It keeps the rerun model and widget look, and citation clicks would still need custom components.
2. **React + TypeScript + Vite**: rejected for this delivery. It needs a Node toolchain and an `npm install` at exam time, and it adds a second build process on Windows.
3. **FastAPI backend + dependency-free single-page frontend (HTML/CSS/ES modules)**: **chosen**.
   - One Python process serves both the API and the UI, and `.\run.ps1` starts everything.
   - No Node build step is needed.
   - The RAG services stay in Python and are called directly; no business logic is duplicated in JavaScript.
   - It gives full control over the visual design: a dark-first theme, split-screen layout and inline SVG icons.

The Streamlit `app.py` is replaced, so only one frontend is maintained. `python app.py` still launches the application.
