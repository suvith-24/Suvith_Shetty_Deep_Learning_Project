"""Case management, case isolation, QA orchestration and the HTTP API (all offline)."""

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from lexisync.api.highlight import locate, page_highlights
from lexisync.api.server import create_app
from lexisync.evaluation import metrics as M
from lexisync.generation.grounded_answerer import GroundedAnswerer
from lexisync.generation.llm_claim_reviewer import LLMClaimReviewer
from lexisync.schemas.document import Chunk
from lexisync.services.case_manager import CaseError, CaseManager, SharedModels
from lexisync.services.qa_service import QAService
from tests.conftest import FakeOllama, HashEmbedder, OverlapCrossEncoder, answer_json, legal_lines, make_pdf


def _pdf_bytes(tmp_path: Path, name: str, lines: list[str]) -> bytes:
    path = make_pdf(tmp_path / name, [legal_lines(100, lines)])
    return path.read_bytes()


@pytest.fixture
def manager(tmp_path):
    return CaseManager(
        uploads_dir=tmp_path / "uploads",
        index_dir=tmp_path / "indexes",
        cases_dir=tmp_path / "cases",
        models_factory=lambda: SharedModels(embedder=HashEmbedder(), reranker=OverlapCrossEncoder()),
    )


CONTRACT = ["ARTICLE 7 - LIABILITY", "7.1 The supplier's liability is capped at EUR 2,000,000 per contract year."]
LEASE = ["ARTICLE 3 - RENT", "3.1 The tenant shall pay monthly rent of EUR 4,500 to the landlord."]


# ------------------------------------------------------------------ case manager


def test_case_lifecycle(manager, tmp_path):
    case = manager.create_case("Vendor review", "Supplier contract")
    assert case["status"] == "empty" and case["id"] == "Vendor-review"
    assert manager.create_case("Vendor review")["id"] == "Vendor-review-2"

    manager.add_document(case["id"], "contract.pdf", _pdf_bytes(tmp_path, "c.pdf", CONTRACT))
    assert manager.get_case(case["id"])["status"] == "pending"

    indexed = manager.index_case(case["id"])
    assert indexed["status"] == "indexed"
    document = indexed["documents"][0]
    assert document["pages"] == 1 and document["chunks"] >= 1
    assert "ARTICLE 7 - LIABILITY" in document["section_titles"]

    reset = manager.reset_case(case["id"])
    assert reset["status"] == "empty" and reset["documents"] == []
    manager.delete_case(case["id"])
    with pytest.raises(CaseError):
        manager.get_case(case["id"])


def test_upload_validation(manager, tmp_path):
    case = manager.create_case("Validation")
    pdf = _pdf_bytes(tmp_path, "a.pdf", CONTRACT)
    with pytest.raises(CaseError, match="not a PDF"):
        manager.add_document(case["id"], "notes.txt", b"hello")
    with pytest.raises(CaseError, match="signature"):
        manager.add_document(case["id"], "fake.pdf", b"hello world")
    with pytest.raises(CaseError, match="empty"):
        manager.add_document(case["id"], "empty.pdf", b"")
    manager.add_document(case["id"], "a.pdf", pdf)
    with pytest.raises(CaseError, match="identical"):
        manager.add_document(case["id"], "copy.pdf", pdf)
    # Same filename, different content -> renamed, not overwritten.
    second = manager.add_document(case["id"], "a.pdf", _pdf_bytes(tmp_path, "b.pdf", LEASE))
    assert second["file_name"] == "a (2).pdf"


def test_document_limit(manager, tmp_path):
    case = manager.create_case("Limit")
    for i in range(5):
        manager.add_document(case["id"], f"d{i}.pdf", _pdf_bytes(tmp_path, f"d{i}.pdf", [f"Article {i} - Item", f"Text number {i}."]))
    with pytest.raises(CaseError, match="at most 5"):
        manager.add_document(case["id"], "d5.pdf", _pdf_bytes(tmp_path, "d5.pdf", ["Article 9 - X", "Other."]))


def test_invalid_case_id_is_rejected(manager):
    with pytest.raises(CaseError):
        manager.get_case("../etc")


def test_case_isolation(manager, tmp_path):
    a = manager.create_case("Contract case")
    b = manager.create_case("Lease case")
    manager.add_document(a["id"], "contract.pdf", _pdf_bytes(tmp_path, "c.pdf", CONTRACT))
    manager.add_document(b["id"], "lease.pdf", _pdf_bytes(tmp_path, "l.pdf", LEASE))
    manager.index_case(a["id"])
    manager.index_case(b["id"])

    texts_a = " ".join(c.text for c in manager.get_pipeline(a["id"]).chunks)
    texts_b = " ".join(c.text for c in manager.get_pipeline(b["id"]).chunks)
    assert "liability" in texts_a and "rent" not in texts_a
    assert "rent" in texts_b and "liability" not in texts_b

    results = manager.get_pipeline(a["id"]).search_detailed("monthly rent tenant landlord", top_k=5).results
    assert all(chunk.document_id == "contract" for chunk, _ in results)

    # Re-indexing one case leaves the other untouched.
    manager.index_case(a["id"])
    assert "rent" in " ".join(c.text for c in manager.get_pipeline(b["id"]).chunks)


def test_legacy_upload_folders_are_imported(tmp_path):
    legacy = tmp_path / "uploads" / "old-case"
    legacy.mkdir(parents=True)
    make_pdf(legacy / "doc.pdf", [legal_lines(100, CONTRACT)])
    manager = CaseManager(uploads_dir=tmp_path / "uploads", index_dir=tmp_path / "idx", cases_dir=tmp_path / "cases")
    case = manager.get_case("old-case")
    assert case["status"] == "pending" and case["documents"][0]["file_name"] == "doc.pdf"


def test_qa_service_answers_and_records_history(manager, tmp_path):
    case = manager.create_case("QA")
    manager.add_document(case["id"], "contract.pdf", _pdf_bytes(tmp_path, "c.pdf", CONTRACT))
    manager.index_case(case["id"])
    claims = [{"text": "The supplier's liability is capped at EUR 2,000,000 per contract year.", "sources": ["S1"],
               "quote": "liability is capped at EUR 2,000,000 per contract year"}]
    llm = FakeOllama([answer_json(claims)])
    answerer = GroundedAnswerer(ollama_client=llm, claim_reviewer=LLMClaimReviewer(ollama_client=llm), evidence_gate=-5.0)
    result = QAService(manager, answerer=answerer).ask(case["id"], "What is the supplier liability cap per contract year?")

    assert result["status"] == "answered"
    assert result["direct_answer"]["sources"] == ["S1"]
    assert result["sources"][0]["file_name"] == "contract.pdf"
    assert result["retrieval"]["per_query"][0]["reranked"]
    assert set(result["timings"]) == {"retrieval_seconds", "generation_seconds", "total_seconds"}
    assert manager.history(case["id"])[0]["id"] == result["id"]


def test_qa_service_requires_indexed_case(manager):
    case = manager.create_case("Not indexed")
    with pytest.raises(CaseError, match="not been indexed"):
        QAService(manager, answerer=GroundedAnswerer(ollama_client=FakeOllama())).ask(case["id"], "Anything?")


# ------------------------------------------------------------------ API


@pytest.fixture
def client(manager):
    llm = FakeOllama([answer_json([{"text": "The supplier's liability is capped at EUR 2,000,000 per contract year.",
                                    "sources": ["S1"], "quote": "liability is capped at EUR 2,000,000 per contract year"}])])
    qa = QAService(manager, answerer=GroundedAnswerer(ollama_client=llm, evidence_gate=-5.0))
    with TestClient(create_app(case_manager=manager, qa_service=qa)) as test_client:
        yield test_client


def test_api_end_to_end(client, manager, tmp_path):
    assert client.get("/api/health").json()["status"] == "ok"
    created = client.post("/api/cases", json={"name": "API case"}).json()
    cid = created["id"]

    upload = client.post(f"/api/cases/{cid}/documents", files=[
        ("files", ("contract.pdf", _pdf_bytes(tmp_path, "c.pdf", CONTRACT), "application/pdf")),
        ("files", ("bad.pdf", b"not a pdf", "application/pdf")),
    ]).json()
    assert [r["ok"] for r in upload["results"]] == [True, False]

    manager.index_case(cid)  # synchronous in tests
    case = client.get(f"/api/cases/{cid}").json()
    assert case["status"] == "indexed" and case["document_count"] == 1

    answer = client.post(f"/api/cases/{cid}/ask", json={"question": "What is the supplier liability cap per contract year?"}).json()
    assert answer["status"] == "answered"
    source = answer["sources"][0]

    image = client.get(f"/api/cases/{cid}/documents/{source['document_id']}/pages/1/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    highlights = client.get(
        f"/api/cases/{cid}/documents/{source['document_id']}/pages/1/highlights",
        params={"chunk_id": source["chunk_id"], "quote": "capped at EUR 2,000,000"},
    ).json()
    assert highlights["passage"]["rects"] and highlights["quote"]["rects"]

    assert client.get(f"/api/cases/{cid}/history").json()[0]["id"] == answer["id"]
    assert client.get("/api/dashboard").json()["totals"]["documents"] >= 1
    assert client.get(f"/api/cases/{cid}/documents/{source['document_id']}/pages/99/image").status_code == 404
    assert client.get("/api/cases/missing-case").status_code == 400
    assert client.delete(f"/api/cases/{cid}").status_code == 204


def test_api_rejects_empty_question(client, manager):
    cid = client.post("/api/cases", json={"name": "Empty question"}).json()["id"]
    assert client.post(f"/api/cases/{cid}/ask", json={"question": ""}).status_code == 422


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200 and "LexiSync" in response.text
    assert client.get("/static/app.js").status_code == 200


# ------------------------------------------------------------------ highlight


def test_locate_returns_line_boxes_and_coverage(tmp_path):
    path = make_pdf(tmp_path / "h.pdf", [legal_lines(100, ["The supplier must deliver goods within ten days.", "Payment is due monthly."])])
    with pymupdf.open(path) as pdf:
        found = locate(pdf[0], "supplier must deliver goods within ten days")
        missing = locate(pdf[0], "penguins dance quietly at night")
    assert found["coverage"] == 1.0 and len(found["rects"]) == 1
    assert missing["rects"] == []
    with pytest.raises(ValueError):
        page_highlights(str(path), 5, "x", None)


# ------------------------------------------------------------------ metrics


def _c(section):
    return Chunk(chunk_id=section, document_id="d", text="", page_numbers=[1], section=section,
                 metadata={"section_key": section.split(" —")[0].casefold()})


def test_section_match_uses_word_boundaries():
    assert M.section_matches(_c("Article 8 — Child"), "Article 8")
    assert not M.section_matches(_c("Article 83 — Fines"), "Article 8")


def test_retrieval_metrics():
    ranked = [_c("Article 83 — Fines"), _c("Article 8 — Child"), _c("Article 6 — Lawful")]
    assert M.hit_at_k(ranked, ["Article 8"], 1) == 0.0
    assert M.hit_at_k(ranked, ["Article 8"], 2) == 1.0
    assert M.reciprocal_rank(ranked, ["Article 8"]) == 0.5
    assert M.full_recall_at_k(ranked, ["Article 8", "Article 6"], 2) == 0.5
    assert M.hit_at_k(ranked, [], 3) is None


def test_abstention_metrics():
    records = [
        {"answerable": True, "abstained": False},
        {"answerable": True, "abstained": True},
        {"answerable": False, "abstained": True},
        {"answerable": False, "abstained": False},
        {"answerable": False, "abstained": None},
    ]
    result = M.abstention_metrics(records)
    assert result["evaluated"] == 4 and result["failed_runs"] == 1
    assert result["abstention_accuracy"] == 0.5
    assert result["false_abstention_rate"] == 0.5
    assert result["unsupported_answer_rate"] == 0.5


def test_best_threshold_separates_scores():
    result = M.best_threshold([3.0, 5.0, 2.5], [-1.0, -4.0])
    assert result["accuracy"] == 1.0 and -1.0 < result["threshold"] < 2.5


def test_latency_summary():
    summary = M.latency_summary([1.0, 2.0, 3.0, None])
    assert summary["n"] == 3 and summary["median"] == 2.0 and summary["max"] == 3.0


def test_manual_score_summary_uses_sheet_schema(tmp_path):
    from lexisync.api.server import summarize_manual_scores

    sheet = tmp_path / "scores.csv"
    sheet.write_text(
        "question_id,answerable,manual_answer_correct_0_or_1,claims_total,supported_cited_claims,"
        "citation_precision_0_to_1,abstention_correct_0_or_1,end_to_end_latency_seconds,reviewer_notes\n"
        "q01,true,1,4,3,0.75,1,10.0,\n"
        "q02,true,0,2,2,1.0,1,8.0,\n"
        "q15,false,,,,,1,0.4,\n"
        "q16,false,,,,,,0.4,not scored yet\n",
        encoding="utf-8",
    )
    summary = summarize_manual_scores(sheet)
    assert summary["rows"] == 4
    assert summary["answer_correctness"] == 0.5
    assert summary["citation_precision"] == pytest.approx(5 / 6)
    assert summary["abstention_accuracy"] == 1.0
    assert summary["scored_abstention"] == 3
    assert summarize_manual_scores(tmp_path / "missing.csv")["answer_correctness"] is None
