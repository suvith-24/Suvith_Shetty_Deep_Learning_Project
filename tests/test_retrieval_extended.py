"""Clause tokens, RRF, retrieval modes, metadata filters, multi-hop search, planner."""

import pytest

from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker
from lexisync.retrieval.faiss_retriever import FAISSRetriever
from lexisync.retrieval.hybrid_retriever import reciprocal_rank_fusion
from lexisync.retrieval.query_planner import QueryPlanner
from lexisync.retrieval.retrieval_pipeline import RetrievalFilters, RetrievalPipeline
from lexisync.retrieval.text_utils import index_text, legal_tokens
from lexisync.schemas.document import Chunk
from tests.conftest import HashEmbedder, OverlapCrossEncoder


def _chunk(cid, doc, text, section, pages, key=None):
    return Chunk(chunk_id=cid, document_id=doc, text=text, page_numbers=pages, section=section,
                 metadata={"section_key": key, "clause_ids": []})


@pytest.fixture
def corpus():
    return [
        _chunk("c1", "contract", "The total liability of the supplier is capped at EUR 2.0M per year.", "Section 7 — Liability", [14], "section 7"),
        _chunk("c2", "contract", "7.2 The cap does not apply to wilful misconduct.", "Section 7 — Liability", [14], "section 7"),
        _chunk("c3", "contract", "The supplier shall indemnify the customer for third party IP claims up to EUR 3.5M.", "Section 9 — Indemnities", [18], "section 9"),
        _chunk("c4", "gdpr", "Infringements shall be subject to administrative fines up to 20 000 000 EUR.", "Article 83 — Fines", [83], "article 83"),
        _chunk("c5", "gdpr", "Processing of personal data of a child shall be lawful where the child is at least 16 years old.", "Article 8 — Child consent", [37], "article 8"),
        _chunk("c6", "gdpr", "The controller shall notify the supervisory authority within 72 hours.", "Article 33 — Breach notification", [52], "article 33"),
    ]


class _Indexer:
    def __init__(self, retriever):
        self.retriever = retriever

    def load(self):
        return self.retriever


@pytest.fixture
def pipeline(corpus):
    # Production configuration: contextual section headers everywhere.
    dense = FAISSRetriever(chunks=corpus, model=HashEmbedder(), contextual=True)
    p = RetrievalPipeline(
        indexing_pipeline=_Indexer(dense),
        reranker=CrossEncoderReranker(model=OverlapCrossEncoder(), contextual=True),
        candidate_k=10,
        top_k=3,
        contextual=True,
    )
    p.initialize()
    return p


def test_legal_tokens_keep_clause_numbers_whole():
    tokens = legal_tokens("Section 7.2 and Article 83(4) apply")
    assert "7.2" in tokens and "83(4)" in tokens
    assert "section:7.2" in tokens and "section:7" in tokens and "article:83" in tokens
    # Original tokens are still present (backward compatible).
    assert {"section", "7", "2", "article", "83"} <= set(tokens)


def test_bm25_matches_exact_clause_number(corpus):
    results = BM25Retriever(corpus).search("What does clause 7.2 say?", top_k=1)
    assert results[0][0].chunk_id == "c2"


def test_index_text_prepends_section_only_when_contextual(corpus):
    chunk = corpus[1]
    assert index_text(chunk, contextual=False) == chunk.text
    assert index_text(chunk, contextual=True).startswith("Section 7 — Liability\n")


def test_contextual_bm25_finds_chunk_by_section_title(corpus):
    query = "indemnities"
    plain = BM25Retriever(corpus).search(query, top_k=3)
    contextual = BM25Retriever(corpus, contextual=True).search(query, top_k=3)
    assert "c3" not in [c.chunk_id for c, _ in plain]  # word only in the heading
    assert contextual[0][0].chunk_id == "c3"


def test_rrf_rewards_agreement_and_is_deterministic(corpus):
    a = [(corpus[0], 9.0), (corpus[1], 5.0), (corpus[2], 1.0)]
    b = [(corpus[2], 0.9), (corpus[0], 0.8)]
    fused = reciprocal_rank_fusion([a, b], k=60)
    assert [c.chunk_id for c, _ in fused][:2] == ["c1", "c3"]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)
    assert reciprocal_rank_fusion([a, b], k=60) == fused


def test_rrf_rejects_bad_arguments(corpus):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[(corpus[0], 1.0)]], k=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[(corpus[0], 1.0)]], weights=[1.0, 2.0])


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_search_detailed_modes_return_ranked_results(pipeline, mode):
    detailed = pipeline.search_detailed("supplier liability cap", mode=mode, top_k=3)
    assert detailed.mode == mode
    assert 0 < len(detailed.results) <= 3
    assert "total_seconds" in detailed.timings
    if mode == "hybrid_rerank":
        assert detailed.bm25 and detailed.dense and detailed.fused
        assert detailed.results[0][0].chunk_id == "c1"
    if mode == "dense":
        assert not detailed.bm25


def test_search_detailed_rejects_unknown_mode(pipeline):
    with pytest.raises(ValueError):
        pipeline.search_detailed("x", mode="magic")


def test_document_filter_restricts_every_stage(pipeline):
    detailed = pipeline.search_detailed("fines and liability caps", filters=RetrievalFilters(document_ids={"gdpr"}))
    for ranking in (detailed.bm25, detailed.dense, detailed.fused, detailed.results):
        assert all(chunk.document_id == "gdpr" for chunk, _ in ranking)


def test_section_filter_uses_word_boundaries(corpus):
    filters = RetrievalFilters(section="Article 8")
    assert filters.matches(corpus[4])
    assert not filters.matches(corpus[3])  # Article 83 must not match Article 8


def test_page_filter(corpus):
    assert RetrievalFilters(pages={14}).matches(corpus[0])
    assert not RetrievalFilters(pages={14}).matches(corpus[2])


def test_multi_hop_search_retrieves_each_part(pipeline):
    plan = QueryPlanner().plan("Does the liability cap in Section 7 exceed the indemnity obligations in Section 9?")
    assert plan.is_multi_hop and plan.strategy == "comparison"
    result = pipeline.multi_hop_search(plan, top_k=2, per_sub_query_k=2)
    sections = {item.chunk.metadata["section_key"] for item in result.evidence}
    assert {"section 7", "section 9"} <= sections
    assert len(result.coverage) == 2
    assert all(entry["covered"] for entry in result.coverage)
    # Evidence is de-duplicated and tagged with the sub-queries it serves.
    ids = [item.chunk.chunk_id for item in result.evidence]
    assert len(ids) == len(set(ids))
    assert any(item.sub_queries for item in result.evidence)


def test_multi_hop_coverage_threshold_marks_missing_part(pipeline):
    plan = QueryPlanner().plan("What fines apply under Article 83 and what does Article 99 say about penguins?")
    result = pipeline.multi_hop_search(plan, coverage_threshold=0.5)
    covered = {entry["sub_query"]: entry["covered"] for entry in result.coverage}
    assert any(covered.values()) and not all(covered.values())


# ----------------------------------------------------------------- planner


def test_planner_keeps_simple_questions_whole():
    plan = QueryPlanner().plan("What is the deadline for notifying a breach?")
    assert not plan.is_multi_hop and plan.sub_queries == ["What is the deadline for notifying a breach?"]


def test_planner_splits_coordinated_questions_and_resolves_pronouns():
    plan = QueryPlanner().plan("What conditions apply to consent, and how can a data subject withdraw it?")
    assert plan.strategy == "coordinated_clauses"
    assert len(plan.sub_queries) == 2
    assert "consent" in plan.sub_queries[1].casefold()


def test_planner_splits_multiple_questions():
    plan = QueryPlanner().plan("Who is the controller? What is the retention period?")
    assert plan.strategy == "multiple_questions" and len(plan.sub_queries) == 2


def test_planner_multi_reference_without_comparison():
    plan = QueryPlanner().plan("Summarise the obligations in Article 33 and Article 34 regarding breaches.")
    assert plan.strategy == "multi_reference"
    assert plan.sub_queries[0].startswith("Article 33") and plan.sub_queries[1].startswith("Article 34")


def test_planner_does_not_split_on_plain_and():
    plan = QueryPlanner().plan("What are the rights to rectification and erasure?")
    assert not plan.is_multi_hop


def test_planner_rejects_empty_question():
    with pytest.raises(ValueError):
        QueryPlanner().plan("  ")
