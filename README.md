@'
# LexiSyncAI

**Evidence-Grounded Legal Document Analyst**

LexiSyncAI is a locally running legal document analysis system designed to answer questions about public legal documents using retrieved evidence.

Its main goal is to produce understandable answers supported by precise document, page, and section citations, while abstaining when sufficient evidence is unavailable.

## Project objectives

- Ingest multiple public legal PDF documents.
- Extract text while preserving page references.
- Identify potentially scanned pages.
- Split documents into meaningful legal sections and clauses.
- Retrieve relevant evidence using hybrid BM25 and dense-vector search.
- Rerank retrieved passages using a cross-encoder.
- Generate evidence-grounded answers using a local language model.
- Display citations and confidence information.
- Abstain when the available evidence cannot support an answer.

## Technology stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| User interface | Streamlit |
| PDF extraction | PyMuPDF |
| Dense embeddings | Sentence Transformers |
| Sparse retrieval | BM25 |
| Vector search | FAISS |
| Reranking | Cross-Encoder |
| Local language model | Ollama |
| Testing | Pytest |

## Project structure

```text
LexiSyncAI/
├── data/
│   ├── raw/
│   ├── processed/
│   └── uploads/
├── docs/
├── evaluation/
├── models/
├── src/
│   └── lexisync/
│       ├── ingestion/
│       ├── retrieval/
│       ├── generation/
│       └── evaluation/
├── storage/
│   └── indexes/
├── tests/
├── app.py
├── config.py
└── pyproject.toml

## Local development setup

1. Install Python 3.11.
2. Install Ollama.
3. Download the local model:

   ollama pull qwen2.5:3b

4. Create and activate the virtual environment:

   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1

5. Install the project:

   python -m pip install -e .

## Running tests

python -m pytest -v

## Current development status

- [x] Development environment configured.
- [x] Local language model installed and tested.
- [x] Embedding model installed and tested.
- [x] Cross-encoder installed and tested.
- [x] Initial PDF extraction module implemented.
- [x] PDF extraction unit tests passing.
- [ ] Legal section-aware chunking.
- [ ] Hybrid retrieval pipeline.
- [ ] Reranking integration.
- [ ] Evidence-grounded answer generation.
- [ ] Citation and abstention verification.
- [ ] Streamlit application.
- [ ] Evaluation on held-out questions.

## Data and privacy

The application is designed for local execution. Use public legal documents for testing. Private or confidential client documents should not be uploaded.

Downloaded PDFs, local models, generated indexes, virtual environments, and environment secrets are excluded from version control.

## Academic project

Developed as part of the Deep Learning and Generative AI coursework.