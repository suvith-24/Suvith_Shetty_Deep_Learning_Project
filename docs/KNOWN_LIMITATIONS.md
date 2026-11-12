# LexiSyncAI — Known Limitations

Stated plainly so that results are not over-claimed.

## Evaluation

- **One benchmark document.** The 25 held-out questions are all on the GDPR. Recall and abstention numbers may not transfer to contracts, judgments or filings with different structure.
- **Small sample.** With 20 answerable and 5 unanswerable questions, one question is 5 or 20 percentage points. Treat differences between configurations as indicative, not significant.
- **Easy unanswerables.** The unanswerable questions are clearly out of scope. Harder "near-miss" questions (the topic is present but the specific fact is not) are better tests, and the system has known risk there (see *Generation* below).
- **Claim-level scores are an assistant draft.** Answer correctness (35% strict) and claim-level citation precision (89%) in `evaluation/manual_scoring_template.csv` were scored by the AI assistant and must be confirmed by the author. The automated "citation precision (auto proxy)" only checks whether a cited passage belongs to an expected article.
- **Incomplete answers.** The 3B model usually states 1–3 facts, so list-type questions (all principles, all exceptions) are often only partly answered. Of 20 answers, 8 are correct but incomplete and 5 are wrong or off-target.
- **Threshold calibration.** The evidence gate (logit 0.0) was chosen from a 14-question dev set. Its unanswerables (VAT, minimum wage …) are easier than real out-of-scope questions.

## Ingestion

- **Reading order is heuristic.** Two-column detection uses an aligned gutter or narrow side-by-side blocks. Three or more columns, rotated text, side notes and complex magazine layouts are not handled.
- **Running heads** are removed only when they recur on at least 40 % of pages (minimum 2), so a header that appears on a single page stays in the text.
- **Footnotes** are detected (small numbered lines at the page bottom) but not linked to their reference marks.
- **Tables** need ruling lines; PyMuPDF's "lines" strategy is used for speed. Borderless, whitespace-aligned tables are extracted as ordinary text, and nested or rotated tables are not supported.
- **OCR**: Tesseract with the English model only (`LEXISYNC_OCR_LANG`). Handwriting, stamps and low-resolution scans give low confidence (a warning is shown). OCR text has no bounding boxes in the highlight view; the page image is still shown.
- **Encrypted PDFs** with a user password are rejected rather than unlocked.

## Retrieval

- **No fine-tuning.** The embedding model and reranker are off-the-shelf MS MARCO / general-purpose models, not legal-domain models.
- **Planner is rule-based.** It splits on explicit cues ("and how…", two provision references, several "?"). An implicit multi-hop question without such cues is retrieved as a single query and relies on the reranker and context expansion. Example from the benchmark: q21 ("…, and *within what* time limit must the controller respond?") was not split, because the second part starts with a preposition rather than an interrogative word.
- **Context expansion** adds only the chunk *after* each of the top three passages, to keep the prompt small. A provision that starts several chunks earlier can be missed.

## Generation and verification

- **Small local model.** `qwen2.5:3b` sometimes paraphrases too freely, blends wording from neighbouring sources (claims that fail verification are removed), or lists answered parts as "missing" (filtered when a verified claim covers them).
- **Verification proves textual support, not legal correctness.** A claim can quote the right sentence and still miss context, for example an exception in another paragraph. Lexical coverage cannot detect every subtle meaning change. Negation and numbers are checked; modal verbs (*may* vs *must*) are only checked by the LLM reviewer.
- **The LLM reviewer is the same 3B model.** It is not an independent judge, and it occasionally rejects supported claims.
- **Near-miss questions.** If the documents discuss the topic but not the asked fact (for example "which encryption algorithm?" when only "encryption" is mentioned), a fluent but off-target answer can pass if every claim is literally supported. The evidence gate catches the clear cases.
- **Conflicts** are detected only for dates, money, percentages and durations, across *different* documents. Conflicting obligations expressed in words ("must" vs "need not") are not detected automatically. The detector reports, never resolves; amendment wording and document dates are only hints.
- **Confidence levels** are rules over measured signals, not calibrated probabilities.

## Performance

- Local inference on a laptop: one answer takes about 5–40 s (median 9.3 s, mean 15.0 s in the evaluation run, with Ollama using a 4 GB laptop GPU), dominated by LLM calls. CPU-only machines are slower. On a 4 GB GPU, Ollama occasionally returns CUDA out-of-memory errors under load; the request fails cleanly and can be retried. Paraphrased claims add LLM-reviewer calls.
- Indexing is about 8–20 s for an 88-page document, including embeddings.

## Scope

- Not legal advice. The system answers only from the uploaded public documents.
- No user accounts or authentication. It is a local, single-user application bound to 127.0.0.1.
- Not implemented: chart/figure reading with a VLM, fine-tuned models, an autoencoder anomaly detector, public deployment. `docs/IMPLEMENTATION_ROADMAP.md` gives the reasons.
