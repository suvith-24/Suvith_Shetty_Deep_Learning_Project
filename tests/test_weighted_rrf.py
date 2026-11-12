
import pytest

from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline
from lexisync.schemas.document import Chunk


@pytest.fixture
def pipeline():
    return RetrievalPipeline(
        original_query_weight=1.0,
        expanded_query_weight=1.5,
    )


@pytest.fixture
def article_44():
    return Chunk(
        chunk_id="article_44",
        document_id="gdpr",
        text="International data transfer provisions.",
        page_numbers=[60],
        section="CHAPTER V",
        subsection="Article 44",
    )


@pytest.fixture
def article_46():
    return Chunk(
        chunk_id="article_46",
        document_id="gdpr",
        text="Appropriate safeguards for international transfers.",
        page_numbers=[62],
        section="CHAPTER V",
        subsection="Article 46",
    )


def test_expanded_query_weight_changes_fusion_ranking(
    pipeline,
    article_44,
    article_46,
):
    original_results = [
        (article_44, 0.9),
        (article_46, 0.8),
    ]

    expanded_results = [
        (article_46, 0.95),
        (article_44, 0.7),
    ]

    results = pipeline._fuse_query_results(
        [original_results, expanded_results],
        query_weights=[1.0, 1.5],
    )

    assert results[0][0].chunk_id == "article_46"
    assert results[1][0].chunk_id == "article_44"


def test_weighted_rrf_calculates_expected_scores(
    pipeline,
    article_44,
    article_46,
):
    results = pipeline._fuse_query_results(
        [
            [(article_44, 0.9), (article_46, 0.8)],
            [(article_46, 0.95), (article_44, 0.7)],
        ],
        query_weights=[1.0, 1.5],
    )

    scores = {
        chunk.chunk_id: score
        for chunk, score in results
    }

    expected_article_44 = (1.0 / 61) + (1.5 / 62)
    expected_article_46 = (1.0 / 62) + (1.5 / 61)

    assert scores["article_44"] == pytest.approx(
        expected_article_44
    )

    assert scores["article_46"] == pytest.approx(
        expected_article_46
    )


def test_default_query_weights_are_equal():
    pipeline = RetrievalPipeline()

    assert pipeline.original_query_weight == 1.0
    assert pipeline.expanded_query_weight == 1.0


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("original_query_weight", 0),
        ("original_query_weight", -1),
        ("original_query_weight", float("inf")),
        ("original_query_weight", float("nan")),
        ("expanded_query_weight", 0),
        ("expanded_query_weight", -1),
        ("expanded_query_weight", float("inf")),
        ("expanded_query_weight", float("nan")),
    ],
)
def test_invalid_query_weights_are_rejected(parameter, value):
    with pytest.raises(ValueError, match="weight"):
        RetrievalPipeline(**{parameter: value})


def test_fusion_rejects_mismatched_weight_count(
    pipeline,
    article_44,
    article_46,
):
    query_results = [
        [(article_44, 0.9)],
        [(article_46, 0.8)],
    ]

    with pytest.raises(ValueError, match="one weight per result list"):
        pipeline._fuse_query_results(
            query_results,
            query_weights=[1.0],
        )


def test_fusion_rejects_invalid_weights(
    pipeline,
    article_44,
    article_46,
):
    query_results = [
        [(article_44, 0.9)],
        [(article_46, 0.8)],
    ]

    with pytest.raises(ValueError, match="finite positive"):
        pipeline._fuse_query_results(
            query_results,
            query_weights=[1.0, 0],
        )


def test_single_query_fusion_preserves_original_results(
    pipeline,
    article_44,
):
    original_results = [(article_44, 0.9)]

    results = pipeline._fuse_query_results(
        [original_results],
        query_weights=[1.5],
    )

    assert results is original_results
