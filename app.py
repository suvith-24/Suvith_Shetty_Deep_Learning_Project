from __future__ import annotations

import re
from pathlib import Path

import pymupdf
import streamlit as st

from lexisync.chunking.legal_chunker import chunk_document
from lexisync.config import INDEX_DIR, UPLOADS_DIR
from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.ingestion.pdf_loader import load_pdf
from lexisync.retrieval.context_expander import ContextExpander
from lexisync.retrieval.index_store import IndexStore
from lexisync.retrieval.indexing_pipeline import DocumentIndexingPipeline
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


st.set_page_config(
    page_title="LexiSyncAI | Legal Evidence Analyst",
    page_icon="⚖️",
    layout="wide",
)


def _safe_case_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return normalized[:48] or "case"


@st.cache_resource(show_spinner="Loading the local answer model…")
def answer_generator() -> AnswerGenerator:
    return AnswerGenerator()


def build_case(files, case_name: str):
    if not 1 <= len(files) <= 5:
        raise ValueError("Upload between 1 and 5 public legal PDFs for a case.")

    case_id = _safe_case_name(case_name)
    case_dir = UPLOADS_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    used_names = set()

    for uploaded in files:
        name = Path(uploaded.name).name
        if Path(name).suffix.lower() != ".pdf":
            raise ValueError(f"{name} is not a PDF file.")
        if name.casefold() in used_names:
            raise ValueError(f"The upload contains duplicate filename: {name}")
        used_names.add(name.casefold())
        destination = case_dir / name
        destination.write_bytes(uploaded.getvalue())
        paths.append(destination)

    # Isolate persisted FAISS files by case so a new case cannot overwrite another case.
    case_index_store = IndexStore(index_dir=INDEX_DIR / case_id, index_name="legal_documents")
    indexer = DocumentIndexingPipeline(index_store=case_index_store)
    indexed = indexer.build(paths)
    pipeline = RetrievalPipeline(indexing_pipeline=indexer)
    pipeline.initialize()
    return case_id, paths, indexed.chunks, pipeline


st.title("⚖️ LexiSyncAI")
st.caption("Evidence grounded analysis of public legal documents")
st.markdown(
    "Upload a small bundle of public legal PDFs, index their sections, and ask a question. "
    "Answers are generated from retrieved passages and include page and section citations."
)

with st.sidebar:
    st.header("Create a case")
    case_name = st.text_input("Case name", value="legal-case")
    uploads = st.file_uploader(
        "Public legal PDF documents (1–5; 2–5 recommended)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Use public documents only. Uploaded PDFs are stored locally under data/uploads.",
    )
    index_clicked = st.button("Index documents", type="primary", use_container_width=True)
    st.divider()
    st.caption("Retrieval: BM25 + dense vectors → reciprocal rank fusion → cross encoder")
    st.caption("Generation: local Ollama model with citation validation and abstention")

if index_clicked:
    if not uploads:
        st.error("Choose 1–5 PDF documents first.")
    else:
        try:
            with st.spinner("Extracting, chunking, embedding, and indexing documents…"):
                case_id, paths, chunks, pipeline = build_case(uploads, case_name)
            documents = [load_pdf(path) for path in paths]
            st.session_state.case = {
                "id": case_id,
                "paths": paths,
                "documents": documents,
                "chunks": chunks,
                "pipeline": pipeline,
            }
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_retrieval", None)
            st.session_state.pop("last_context", None)
            st.success(f"Indexed {len(documents)} documents into {len(chunks)} searchable passages.")
        except Exception as exc:
            st.exception(exc)

case = st.session_state.get("case")
if case:
    st.subheader(f"Case: {case['id']}")
    with st.expander("Indexed document structure", expanded=True):
        for document in case["documents"]:
            page_cols = st.columns([3, 1, 2])
            page_cols[0].markdown(f"**{document.file_name}**")
            page_cols[1].write(f"{document.total_pages} pages")
            page_cols[2].write(
                f"{sum(page.is_scanned for page in document.pages)} potentially scanned"
            )
            scanned = [str(page.page_number) for page in document.pages if page.is_scanned]
            if scanned:
                st.warning(f"Pages needing OCR (not currently OCR processed): {', '.join(scanned)}")
            sections = sorted({chunk.section for chunk in case["chunks"] if chunk.document_id == document.document_id})
            st.caption("Detected sections: " + ("; ".join(sections[:20]) or "No headings detected"))

    question = st.text_area(
        "Ask a question about this case",
        placeholder="For example: What safeguards apply to transfers of personal data to a third country?",
        height=90,
    )
    if st.button("Find evidence and answer", type="primary", disabled=not question.strip()):
        try:
            with st.spinner("Retrieving evidence and generating a grounded answer…"):
                retrieval = case["pipeline"].search(question)
                primary = [chunk for chunk, _ in retrieval]
                context = ContextExpander(previous_chunks=1, next_chunks=1).expand(
                    primary_chunks=primary,
                    all_chunks=case["chunks"],
                )
                result = answer_generator().generate_answer(
                    query=question,
                    evidence=retrieval,
                    context_evidence=context,
                )
            st.session_state.last_result = result
            st.session_state.last_retrieval = retrieval
            st.session_state.last_context = context
        except Exception as exc:
            st.exception(exc)

    result = st.session_state.get("last_result")
    if result:
        validation = result["validation"]
        citation_labels = {
            source["source_id"]: (
                f"{source['document_id']}, p. {', '.join(map(str, source['pages'])) or '?'}"
                f", {source['section'] or 'section not detected'}"
            )
            for source in result["sources"]
        }
        display_answer = re.sub(
            r"\[(S\d+)\]",
            lambda match: f"[{citation_labels.get(match.group(1), match.group(1))}]",
            result["answer"],
        )

        # Keep the answer and its source pages visible together, as required
        # by the assignment's cited-answer UI.
        answer_col, evidence_col = st.columns([5, 7], gap="large")

        with answer_col:
            st.markdown("### Answer")
            if result["abstained"]:
                st.error("INSUFFICIENT EVIDENCE — the system abstained")
                confidence = "INSUFFICIENT EVIDENCE"
            elif validation.get("all_claims_supported"):
                st.success("HIGH CONFIDENCE — all extracted claims passed review")
                confidence = "HIGH"
            elif validation.get("citations_valid"):
                st.warning("MEDIUM CONFIDENCE — citations are valid; review claim checks")
                confidence = "MEDIUM"
            else:
                st.warning("LOW CONFIDENCE — citation or claim verification needs review")
                confidence = "LOW"

            st.caption(f"Confidence: {confidence}")
            st.markdown(display_answer)

            if result.get("claim_verification", {}).get("reviews"):
                with st.expander("Claim verification details"):
                    for review in result["claim_verification"]["reviews"]:
                        st.write(f"**{review['status'].upper()}** — {review['claim']}")
                        if review.get("reason"):
                            st.caption(review["reason"])

        with evidence_col:
            st.markdown("### Supporting evidence")
            st.caption("Select a source to inspect its extracted passage and original PDF page.")
            chunks_by_id = {
                chunk.chunk_id: chunk
                for chunk, _ in st.session_state.last_retrieval
            }
            chunks_by_id.update({
                chunk.chunk_id: chunk
                for chunk in st.session_state.last_context
            })

            if not result["sources"]:
                st.info("No supporting passages were retrieved for this question.")

            for source in result["sources"]:
                chunk = chunks_by_id.get(source["chunk_id"])
                if chunk is None:
                    continue

                pages = ", ".join(map(str, source["pages"])) or "unknown"
                label = (
                    f"[{source['source_id']}] {source['document_id']} · "
                    f"p. {pages} · {source['section'] or 'Section not detected'}"
                )
                with st.expander(label, expanded=False):
                    st.write(chunk.text)
                    document_path = next(
                        (
                            path for path in case["paths"]
                            if path.stem == source["document_id"]
                        ),
                        None,
                    )
                    if document_path and source["pages"]:
                        with pymupdf.open(document_path) as pdf:
                            for page_number in source["pages"]:
                                if 1 <= page_number <= len(pdf):
                                    page_image = pdf[page_number - 1].get_pixmap(
                                        matrix=pymupdf.Matrix(1.25, 1.25),
                                        alpha=False,
                                    ).tobytes("png")
                                    st.image(
                                        page_image,
                                        caption=f"{document_path.name} · page {page_number}",
                                        use_container_width=True,
                                    )
