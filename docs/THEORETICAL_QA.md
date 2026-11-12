# LexiSyncAI — Theory Q&A Preparation

Short, exam-ready answers. Each entry says what the concept is, why it matters, and where it lives in LexiSyncAI.

### RAG (retrieval-augmented generation)
An LLM answers from passages retrieved at query time instead of relying only on its parametric memory. This reduces hallucination and makes answers traceable and updatable without retraining. In LexiSyncAI: retrieve (BM25 + FAISS + RRF + cross-encoder) → generate (qwen2.5:3b) → verify each claim.

### Embeddings
Dense vectors where semantic similarity becomes geometric closeness. A text is mapped to ℝ^d (here d = 384) so that paraphrases end up close together. They are learned with contrastive objectives that pull related pairs together and push others apart.

### Sentence Transformers
A siamese/bi-encoder BERT-style network with pooling (mean pooling for MiniLM), fine-tuned on sentence pairs (NLI, MS MARCO, …) with contrastive or multiple-negatives ranking loss. `all-MiniLM-L6-v2` has 6 layers and 384 dimensions, and is fast on CPU. Queries and passages are encoded **independently**, so passage vectors can be precomputed.

### FAISS
Facebook AI Similarity Search: a library for nearest-neighbour search over vectors. We use `IndexFlatIP` (exact inner product) on L2-normalised vectors, so the inner product equals cosine similarity. Exact search is fine for a few thousand chunks. Approximate indexes (IVF, HNSW, PQ) trade recall for speed on millions of vectors.

### BM25
A probabilistic lexical ranking function:

score(q, d) = Σ_t IDF(t) · f(t,d)·(k₁+1) / (f(t,d) + k₁·(1 − b + b·|d|/avgdl))

- `IDF(t)` rewards rare terms.
- `k₁` controls term-frequency saturation.
- `b` controls length normalisation.

It is crucial for legal text: exact tokens such as "Article 83(4)", "7.2", names and defined terms. We keep clause numbers as whole tokens (`7.2`, `83(4)`, `article:83`).

### Hybrid retrieval
Combining sparse (BM25: exact matches, rare terms) and dense (semantic, paraphrase) retrieval, because their failure modes are complementary. Measured here: dense-only Recall@1 = 0.60, hybrid + rerank = 0.90.

### Reciprocal Rank Fusion (RRF)
score(d) = Σ_r 1 / (k + rank_r(d)), with k = 60. It uses **ranks, not raw scores**, so BM25 scores (unbounded) and cosine similarities (−1…1) can be combined without calibration. A larger k flattens the advantage of top ranks. Documents ranked well by several systems rise.

### Cross-encoder
Query and passage are fed **jointly** through one transformer (`[CLS] q [SEP] p`), so full self-attention runs across both. That is more accurate than a bi-encoder but needs one forward pass per pair, so it cannot be precomputed. We therefore use it to rerank only the top ~20 fused candidates (retrieve-then-rerank). Its output is a relevance logit (ms-marco); we also use it as the abstention gate (logit < 0 means sigmoid < 0.5).

### Legal-aware chunking
Chunks follow legal structure (Article / Section / clause) instead of fixed windows. This keeps a provision's meaning intact, gives precise citation metadata (section, clause ID, page) and avoids mixing unrelated clauses. Long sections are still split at paragraph boundaries with overlap, and tables are kept whole.

### Multi-hop retrieval
An answer needs several pieces of evidence, for example Article 83(4) on p. 82 and 83(5) on p. 83, or a cap in Section 7 versus indemnities in Section 9. A single query embedding tends to favour one part. We decompose the question into sub-queries, retrieve and rerank each separately, merge the evidence, and check that each part is covered by a verified claim.

### Hallucination
The model generates fluent content not supported by its input. Types: *intrinsic* (contradicts the source) and *extrinsic* (adds unsupported facts). Mitigations here:
- answer only from retrieved evidence
- structured per-claim citations
- verbatim quote checks and numeric checks
- an LLM reviewer and a corrective retry
- abstention

### Citation validation
Checking that each cited source ID exists and actually belongs to the evidence. It is necessary but **not sufficient**: a valid citation can still point to a passage that does not support the claim.

### Claim verification
Checking that the cited passage **entails** the claim. We use deterministic checks first:
- verbatim quote in the cited source
- every number present
- content-word coverage ≥ 70 %
- negation agreement

If those are inconclusive, an LLM reviewer labels the claim SUPPORTED / CONTRADICTED / INSUFFICIENT, with its own exact-quote requirement. This is a form of natural-language inference (premise = evidence, hypothesis = claim).

### Abstention
Refusing to answer when the evidence is insufficient: selective prediction, which trades coverage for precision. There are three triggers:
1. the retrieval relevance gate
2. the model declaring the evidence insufficient
3. no claim surviving verification

It is measured by abstention accuracy, the false-abstention rate on answerable questions, and the unsupported-answer rate on unanswerable ones.

### Confidence scoring
A level derived from measured signals: rerank score, share of claims verified, multi-hop coverage, conflicts and retries. It is **not** a calibrated probability. Calibration would need a labelled set and a method such as temperature or Platt scaling, with reliability diagrams and ECE.

### OCR
Optical character recognition converts page images to text. Tesseract 5 uses an LSTM line recogniser after layout analysis. We OCR only pages with almost no text layer that contain an image, at 300 DPI, and report the mean word confidence. In the demo amendment, the scanned page was recognised at 96/100.

### Recall@K
The fraction of answerable questions for which at least one relevant passage (the expected article) appears in the top K. "Did retrieval find the evidence?" It is the main retrieval metric, because the generator can only cite what was retrieved. Multi-hop "full recall" requires *all* expected provisions in the top K.

### Precision and recall
- Precision = TP / (TP + FP): of what was returned, how much was relevant.
- Recall = TP / (TP + FN): of what was relevant, how much was returned.

They trade off against each other. F1 is their harmonic mean.

### MRR (mean reciprocal rank)
The mean of 1/rank of the first relevant result (0 if none). It rewards putting the evidence *first*. Here: dense 0.71 vs hybrid + rerank 0.94.

### Citation precision
The share of citations whose cited passage actually supports the claim it is attached to. Manual scoring is the reference. Our automated proxy checks whether the cited passage belongs to an expected provision, which under-counts legitimate support from recitals or neighbouring articles.

### Latency
Wall-clock time per question, split into retrieval (≈ 0.3–1.5 s: BM25 + FAISS + reranker), generation (LLM prompt processing dominates) and verification (extra LLM-reviewer calls for paraphrased claims). We report mean, median and p95. The main optimisations:
- the evidence gate skips the LLM entirely for out-of-scope questions (≈ 0.5 s instead of 10–40 s)
- deterministic verification avoids most reviewer calls
- a ruling-line prefilter cut table detection on the 88-page GDPR from 27 s to under 1 s

### Local LLM inference
The model runs on the user's machine (Ollama, llama.cpp backend, 4-bit Q4_K_M quantisation, about 2 GB) with no API cost and no data leaving the device, which suits confidential legal work. The trade-offs are a smaller model (more instruction-following errors, hence strict verification), slower inference on laptop hardware, and a limited context window (we set `num_ctx` = 8192 so evidence is not silently truncated). Determinism comes from temperature 0 and a fixed seed.

### Limitations (one-minute version)
- One benchmark document (GDPR), and a small question set.
- Answers are precise (89% claim-level citation precision) but often incomplete (35% strict correctness).
- Rule-based planner and heuristic layout analysis.
- A 3B model as both generator and reviewer.
- Verification proves textual support, not legal correctness.
- Confidence is not calibrated.
- See `docs/KNOWN_LIMITATIONS.md`.
