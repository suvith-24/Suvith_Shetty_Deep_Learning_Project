# LexiSyncAI — Five-Minute Demo Guide

Exam format: 5 minutes of live demo on one **unseen public PDF** with three unseen questions (prose, two-page multi-hop, unanswerable), plus the one-page architecture diagram ([architecture.svg](architecture.svg) / [architecture.png](architecture.png)).

## Before the exam (10 minutes, do not skip)

1. Start Ollama and check the model: `ollama list` must show `qwen2.5:3b`.
2. Start the app: `.\run.ps1 -SkipInstall` (or `.\run.ps1` on a new machine). The browser opens at http://127.0.0.1:8000.
3. Check that the sidebar footer shows **Ollama connected**.
4. **Warm-up**: open the indexed GDPR case and ask one question. The first answer loads the models (about 10 s extra). Later answers are faster.
5. Open the architecture diagram in a second tab.
6. Close other heavy programs, especially GPU-heavy ones. Ollama shares the 4 GB laptop GPU and can hit out-of-memory errors.

## Timeline

| Time | Action | What to say |
|---|---|---|
| 0:00–0:30 | Show the diagram | "LexiSyncAI answers only from uploaded legal PDFs. Hybrid BM25 + dense retrieval, RRF, cross-encoder reranking, a local 3B LLM. Every claim is verified against the cited passage; if the evidence is missing, the system abstains." |
| 0:30–1:30 | **Dashboard → Create New Case** (name it after the PDF) → **Document Library** → drop the unseen PDF (or paste its URL) → **Index documents** | While it indexes (a progress line appears): "Text is extracted in reading order, running headers removed, scanned pages OCR'd, then chunked by Article/Section with clause IDs." Then open the **structure** icon (layers) and point at pages, sections, passages, tables and scanned pages. |
| 1:30–2:20 | **Legal AI Workspace** → question 1 (prose / factual) | Point at: the **confidence badge**, "n/n claims verified", the clickable citation chip `S1 · p.X`, and the original PDF page on the right with the **highlighted passage** and the yellow **quote**. |
| 2:20–3:30 | Question 2 (two-page multi-hop) | "The planner split this into sub-questions; each was retrieved separately." Click two citations on **different pages**; the viewer jumps between them. Open **Advanced diagnostics**: BM25 vs dense vs RRF vs rerank tables, the claim-verification table, and the retry log. |
| 3:30–4:15 | Question 3 (unanswerable) | Red **INSUFFICIENT EVIDENCE** card: "The uploaded documents do not provide sufficient evidence…", with the reason (best passage below the relevance threshold) and the documents searched. "It refuses rather than guesses." |
| 4:15–5:00 | **Evaluation & Analytics** | "25 held-out questions: 13 factual, 7 multi-hop, 5 unanswerable. Mandatory comparison: dense-only vs hybrid + rerank Recall@k. Abstention accuracy, false-abstention rate, latency. Manual correctness is scored separately." Headline: hybrid + rerank R@1 0.90 vs dense 0.60; abstention accuracy 25/25; 0 false abstentions vs 20/20 for the original generator. |

## Writing good live questions (when the PDF is unseen)

- **Prose / factual**: use the document's own words. "What does Article 12 require of …?" "What is the deadline for …?"
- **Two-page multi-hop**: name two provisions, or ask two coordinated parts. "What does Section 4 require, and what happens under Section 9 if it is breached?" Joining the parts with "and what/how/when …" or naming both sections triggers the planner.
- **Unanswerable**: ask for something clearly outside the document. "What is the governing law of the subcontractor agreement?"

## Backup material (if something fails)

- **Ollama down** → the red status in the sidebar and a clear error. Start Ollama and click *Check again* in Settings.
- **Unseen PDF is scanned** → OCR runs automatically (Tesseract installed). The structure report shows the OCR pages and their confidence.
- **Indexing slow** (large PDF) → keep talking through the structure; 100 pages take about 20 s.
- **Pre-indexed cases**: the *legal case* (GDPR, 88 pages) and *Records Act + Amendment (demo)* (synthetic: a conflict, a table, an OCR page).
  - Conflict demo: "How long must an active service record be retained?" shows the five vs seven years conflict panel.
  - OCR demo: "Who is the contact point for requests under the amendment?" is answered from the scanned annex.

## Likely examiner follow-ups

- *Why does it abstain?* There are three layers: the evidence gate (reranker logit < 0), the model reporting insufficient evidence, and claim verification removing everything. The abstention card shows which layer fired.
- *How do you know a citation is right?* The quote must appear verbatim in the cited passage, and every number in the claim must appear there. Otherwise the 3B reviewer judges the claim and the corrective retry runs. Then click the citation and show the highlighted region.
- *Why hybrid?* BM25 nails exact tokens such as "83(4)" or "Section 7.2". Dense retrieval handles paraphrases. RRF combines ranks without score calibration. The cross-encoder rescoring lifts Recall@1 from 0.60 (dense) to 0.90.
