# LexiSyncAI — Evaluation Report

All numbers below were produced by `scripts/evaluate.py` on 12 November 2026 and are stored in `evaluation/results/`:

| File | Contents |
|---|---|
| `summary.json` | Headline metrics |
| `retrieval_metrics.json` | Per-question retrieval rankings |
| `generation_results.json` | Per-question answers, citations, verification and retry logs |
| `calibration.json` | Evidence-gate calibration on the dev set |
| `legacy_baseline.json` | The original generator on identical evidence |

Nothing here is estimated or copied from elsewhere.

**Hardware / models.** Windows laptop with an NVIDIA RTX 3050 Laptop GPU (4 GB), which Ollama used for the LLM. Embeddings and reranking ran on the CPU. A CPU-only machine works but generation is slower.

| Role | Model |
|---|---|
| Embeddings | `all-MiniLM-L6-v2` |
| Reranker | `ms-marco-MiniLM-L-6-v2` |
| Generator and LLM reviewer | `qwen2.5:3b` (Ollama, Q4_K_M), temperature 0, seed 42, `num_ctx` 8192 |

## 1. Dataset

| Set | File | Questions | Purpose |
|---|---|---|---|
| Held-out benchmark | `evaluation/held_out_questions.json` | 25: **13 factual, 7 multi-hop, 5 unanswerable** | All reported metrics |
| Dev calibration | `evaluation/dev_calibration_questions.json` | 14: 8 answerable, 6 unanswerable | Choosing the abstention threshold only |

- **Document**: Regulation (EU) 2016/679 (GDPR), the official 88-page Official Journal PDF from EUR-Lex.
- **Labels**: each question records its type, answerability, expected answer, expected article(s) and expected page(s). The pages were read off the PDF by locating each article's span in the extracted structure.
- **Multi-hop questions** need two provisions, for example Article 33 (p. 52) with Article 34 (pp. 52–53), or Article 15 (p. 43) with Article 12(3) (pp. 39–40). q12 is the assignment's own example: the fine tiers in Article 83(4) on p. 82 and 83(5) on p. 83.
- **Unanswerable questions** are out of scope for the GDPR: an employee leave-retention period, court jurisdiction over a supply contract, a share price, a mandatory encryption algorithm, and the governing law of a subcontractor agreement.

**Relevance judgement.** A retrieved passage is relevant if its section is one of the expected articles, using a word-boundary match on the normalised section key. The original script used substring matching, which wrongly counted Article 83 as a hit for Article 8; that bug is fixed and covered by a test.

## 2. Retrieval (mandatory comparison)

Recall@k over the 20 answerable questions, for four configurations and two index variants.

- **Multi-hop full recall@5** is the share of *all* required provisions in the top 5, averaged over the 7 multi-hop questions.
- **Latency** is the mean per query for the retrieval stage only.

### Contextual section headers (system default)

| Configuration | R@1 | R@3 | R@5 | R@10 | MRR | Page hit@5 | Multi-hop full R@5 | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense only (FAISS) | 0.60 | 0.80 | 0.90 | 0.95 | 0.71 | 0.90 | 0.64 | 12 ms |
| BM25 only | 0.50 | 0.85 | 0.85 | 0.95 | 0.67 | 0.85 | 0.71 | 2 ms |
| Hybrid (RRF, k = 60) | 0.65 | 0.80 | 0.90 | 1.00 | 0.76 | 0.90 | 0.79 | 10 ms |
| **Hybrid + cross-encoder** | **0.90** | **1.00** | **1.00** | **1.00** | **0.94** | **1.00** | 0.86 | 356 ms |
| Hybrid + rerank + **query planner** (system) | | | | | | | **0.93** | 794 ms |

### Plain chunk text (ablation)

| Configuration | R@1 | R@3 | R@5 | R@10 | MRR | Multi-hop full R@5 |
|---|---:|---:|---:|---:|---:|---:|
| Dense only | 0.50 | 0.80 | 0.85 | 1.00 | 0.66 | 0.64 |
| BM25 only | 0.50 | 0.85 | 0.90 | 0.95 | 0.67 | 0.71 |
| Hybrid (RRF) | 0.75 | 0.90 | 0.95 | 1.00 | 0.84 | 0.71 |
| Hybrid + cross-encoder | 0.90 | 0.95 | 1.00 | 1.00 | 0.94 | 0.86 |

**Findings.**

- **Hybrid + cross-encoder beats dense-only** on every cut-off: R@1 0.90 vs 0.60, MRR 0.94 vs 0.71. The cross-encoder accounts for most of the gain: RRF alone improves R@10 and multi-hop recall, but the reranker puts the right article first. The cost is about 0.35 s per query on CPU.
- **BM25 and dense retrieval are complementary.** Neither alone reaches R@10 = 1.00 with contextual headers; fused, they do.
- **The planner** raises multi-hop full recall from 0.86 to 0.93 (6.5 passages per question instead of 5). The remaining miss is q20, where Article 6 is not retrieved alongside Article 9.
- **Contextual headers** help dense retrieval (MRR 0.66 → 0.71) and the final system's R@3 (0.95 → 1.00), but slightly hurt RRF without reranking (MRR 0.84 → 0.76). On 20 questions these differences amount to one or two questions, so we treat the variants as roughly equivalent. Headers stay on because they help the deployed configuration.

**Retrieval failure analysis** (system configuration):

- **q03** (lawfulness, Article 6) and **q11** (transfer safeguards, Article 46) are found at rank 2–3, not rank 1. The top passage was Article 8 (child consent, which also says "lawful") and Article 49 (derogations for transfers), respectively. Both are topically adjacent provisions.
- **q19 / q20** (multi-hop): the single-query top 5 contains only one of the two provisions. The planner retrieves q19's second provision; q20's Article 6 remains missing.
- **Planner coverage**: 5 of the 7 multi-hop questions were split into sub-questions. q12 has no coordination cue, and q21 ("…, and within what time limit …") starts its second part with a preposition. Both still reached full recall through the single query.

## 3. Abstention gate calibration

The reranker's best logit is the retrieval-level abstention signal. On the **dev set**:

- lowest answerable score: **2.48**
- highest unanswerable score: **−0.49**
- any threshold in (−0.49, 2.48) separates the dev set perfectly

The configured threshold is **0.0** (sigmoid 0.5). It sits inside that interval but leans towards answering, because the LLM and the claim verifier form a second abstention layer.

On the held-out set, the gate alone classifies all 25 questions correctly (unanswerables ≤ −4.11, answerables ≥ 2.72). These unanswerables are easy cases (clearly out of scope), so the gate result is an upper bound for this kind of question.

## 4. Generation and abstention

Full system, 25 questions, `qwen2.5:3b`:

| Metric | Value | Type |
|---|---:|---|
| Abstention accuracy (25 questions) | **100%** | automated |
| Correct abstentions on unanswerable | 5/5 (100%) | automated |
| Unsupported answer rate (answered an unanswerable) | 0% | automated |
| Answerable questions answered | 20/20 | automated |
| False abstention rate | **0%** (0 question(s)) | automated |
| Multi-hop questions answered | 7/7 | automated |
| Claim verification pass rate (drafted claims kept) | 84% | automated |
| Questions needing a corrective retry | 6 | automated |
| Confidence distribution | HIGH 14, MEDIUM 4, LOW 2, INSUFFICIENT 5 | automated |
| Answer correctness | **Pending** | manual |

Per question:

| ID | Type | Outcome | Confidence | Claims shown (removed) | Cited provisions | Time |
|---|---|---|---|---:|---|---:|
| q01 | factual | answered | HIGH | 5 (0) | Article 5 p.35; Recitals p.2; Recitals p.12; Article 5 p.36 | 16.3 s |
| q02 | factual | answered | MEDIUM | 2 (1) | Article 24 p.47; Recitals p.15 | 14.0 s |
| q03 | factual | answered | HIGH | 1 (0) | Article 8 p.37; Recitals p.8; Article 8 p.38; Article 6 p.36; Recitals p.9 | 7.4 s |
| q04 | factual | answered | HIGH | 6 (0) | Article 7 p.37 | 22.5 s |
| q05 | factual | answered | MEDIUM | 3 (2) | Article 13 p.40 | 81.2 s |
| q06 | factual | answered | HIGH | 2 (0) | Article 12 p.40; Recitals p.11 | 12.8 s |
| q07 | factual | answered | HIGH | 1 (0) | Article 17 p.43 | 22.9 s |
| q08 | factual | answered | HIGH | 1 (0) | Article 20 p.45 | 6.6 s |
| q09 | factual | answered | HIGH | 1 (0) | Article 33 p.52 | 9.0 s |
| q10 | factual | answered | HIGH | 1 (0) | Article 34 p.52 | 5.5 s |
| q11 | factual | answered | HIGH | 9 (0) | Article 49 p.64 | 13.2 s |
| q12 | multi_hop | answered | MEDIUM | 2 (0) | Article 83 p.82; Article 83 p.83 | 8.5 s |
| q13 | factual | answered | HIGH | 2 (0) | Article 8 p.37 | 11.2 s |
| q14 | factual | answered | HIGH | 1 (0) | Article 22 p.46 | 5.7 s |
| q15 | unanswerable | correct abstention | INSUFFICIENT | 0 (0) | — | 0.4 s |
| q16 | unanswerable | correct abstention | INSUFFICIENT | 0 (0) | — | 0.4 s |
| q17 | unanswerable | correct abstention | INSUFFICIENT | 0 (0) | — | 0.4 s |
| q18 | unanswerable | correct abstention | INSUFFICIENT | 0 (0) | — | 0.4 s |
| q19 | multi_hop | answered | HIGH | 2 (0) | Recitals p.17; Article 33 p.52; Article 34 p.53; Article 34 p.52 | 14.7 s |
| q20 | multi_hop | answered | HIGH | 2 (0) | Article 9 p.38; Recitals p.9 | 9.3 s |
| q21 | multi_hop | answered | LOW | 2 (4) | Article 12 p.40 | 25.1 s |
| q22 | multi_hop | answered | HIGH | 2 (0) | Article 17 p.43; Article 17 p.44; Article 19 p.45 | 8.4 s |
| q23 | multi_hop | **partial** (one sub-question unanswered) | LOW | 1 (1) | Article 44 p.60 | 47.5 s |
| q24 | multi_hop | answered | MEDIUM | 1 (1) | Article 39 p.56 | 31.4 s |
| q25 | unanswerable | correct abstention | INSUFFICIENT | 0 (0) | — | 0.4 s |


### Before vs after: the false-abstention problem

The original `AnswerGenerator` asked for a free-text answer with a citation after every sentence and abstained if any sentence was uncited or unverified. It was run on **identical hybrid evidence** (`--legacy-baseline`):

| Generator (same evidence) | False abstention rate | Answerable answered | Correct abstentions | Mean latency |
|---|---:|---:|---:|---:|
| Original free-text `AnswerGenerator` | 100% | 0/20 | 100% | 40.1 s |
| **Structured grounded answerer (this system)** | **0%** | 20/20 | 100% | 15.0 s |

**Disclosure.** During the legacy run, one Ollama call for q22 failed with a CUDA out-of-memory error on the 4 GB laptop GPU. The legacy generator caught it and abstained. Excluding q22, the legacy baseline still falsely abstains on 19/19 answerable questions, so the conclusion does not depend on that error. The new system's run had no Ollama errors.

The root cause was format, not grounding: the 3B model writes paragraph answers with one citation per paragraph. The structured per-claim JSON output removes that failure mode while keeping, and adding, hard checks:

- verbatim quote in a *cited* passage
- every number present in the cited evidence
- content-word coverage
- negation agreement
- an LLM review for paraphrases

## 5. Citations

| Metric | Value | Type |
|---|---:|---|
| Citation coverage (shown claims with ≥ 1 citation) | 100% | automated (by construction) |
| Citation precision, automated proxy (cited passage in an expected article) | 79% | automated proxy |
| Expected provisions cited (answered questions) | 80% | automated |
| Expected provisions cited, multi-hop only | 71% | automated |
| Citation precision (claim supported by cited passage) | **Pending** | manual |

The proxy under-counts. Recitals (e.g. recital 85 for breach notification) and neighbouring articles (e.g. Article 24 for accountability) legitimately support claims but are not "expected articles". Every shown claim has already passed the per-claim verification (verbatim quote, numbers, coverage, or LLM review).

**Manual scoring status: pending.** `evaluation/manual_scoring_template.csv` lists every question with the system answer and its cited sections and pages. Columns `manual_answer_correct (1/0.5/0)`, `manual_supported_citations` and `manual_total_citations` must be completed by the author. The Evaluation dashboard computes answer correctness and manual citation precision from this file as soon as it is filled in. Until then these metrics are reported as *Pending*, never estimated.

## 6. Latency and cost

| Stage | Mean | Median | p95 | Max |
|---|---:|---:|---:|---:|
| Retrieval (planner + hybrid + rerank) | 0.8 s | 0.4 s | 1.5 s | 2.4 s |
| Generation + verification | 14.2 s | 8.6 s | 46.1 s | 80.7 s |
| **End-to-end** | **15.0 s** | **9.3 s** | 47.5 s | 81.2 s |

Tokens per question (mean): 2939 prompt + 558 completion, over 2.6 LLM calls.

- Local inference has no per-token cost.
- Prompt processing and the number of LLM calls dominate generation time.
- Questions whose claims are paraphrased need LLM-reviewer calls. A budget of 6 reviews per draft caps the worst case; unreviewed claims are never shown.

**Measured optimisations:**

1. The evidence gate answers out-of-scope questions in about 0.5 s with zero LLM calls (all 5 unanswerables).
2. A ruling-line prefilter for table detection cut GDPR ingestion from 28.7 s to 7.3 s with identical output; 27 s of that was `find_tables`.
3. Deterministic verification resolves most claims without an LLM call (35/47 = 74% of supported claims).

## 7. Generation failure analysis

- **q02** (factual): 1 drafted claim(s) removed by verification; confidence MEDIUM.
- **q02**: answered, but cited none of the expected provisions (Article 5); manual review needed.
- **q05** (factual): 2 drafted claim(s) removed by verification; confidence MEDIUM.
- **q11**: answered, but cited none of the expected provisions (Article 46); manual review needed.
- **q21** (multi_hop): 4 drafted claim(s) removed by verification; confidence LOW.
- **q23** (multi_hop): 1 drafted claim(s) removed by verification; confidence LOW.
- **q24** (multi_hop): 1 drafted claim(s) removed by verification; confidence MEDIUM.

## 8. Limitations of this evaluation

- One document, 25 questions. A difference of one question is 5 percentage points on answerable metrics and 20 points on unanswerable ones.
- The unanswerable questions are clearly out of scope. Near-miss questions (topic present, fact absent) are harder and are not represented.
- The automated citation metric is a proxy (expected-article match). Manual citation precision is pending.
- The LLM reviewer is the same 3B model as the generator.

See `docs/KNOWN_LIMITATIONS.md` for system limitations.

## 9. Reproduction

```powershell
python scripts/evaluate.py --rebuild                         # retrieval ablation + calibration
python scripts/evaluate.py --generate --legacy-baseline      # full answers + before/after baseline
python -m pytest -q                                          # 350 tests
```
