# LexiSyncAI – Evidence-Grounded Legal Document Analyst

A modular starter repository for a legal-document question-answering system.

## Planned capabilities
- PDF ingestion and structure-aware extraction
- OCR fallback for scanned pages
- Clause-aware chunking
- Hybrid retrieval (BM25 + dense embeddings)
- Cross-encoder reranking
- Evidence-grounded answer generation
- Page/section citations and abstention
- Retrieval, citation, and answer evaluation

## Project structure
- `app/ingestion/`: document loading, parsing, OCR, tables, chunking
- `app/retrieval/`: BM25, embeddings, vector storage, hybrid search, reranking
- `app/generation/`: LLM integration, prompts, answers, citations
- `app/verification/`: evidence checks, confidence, abstention
- `app/evaluation/`: evaluation metrics and runner
- `app/api/`: API routes and schemas
- `frontend/`: UI
- `data/`: local input, processed data, and evaluation datasets
- `storage/`: local indexes and metadata
- `tests/`: automated tests
- `docs/`: architecture and reports

## Getting started
Create a virtual environment, install dependencies, configure `.env`, and implement the modules incrementally.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Notes
- This is an initial folder scaffold; most modules are intentionally empty.
- Do not commit confidential documents, API keys, generated indexes, or large model files.
- Copy `.env.example` to `.env` and add credentials locally.
