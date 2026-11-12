
import pytest

from lexisync.retrieval.context_expander import ContextExpander
from lexisync.schemas.document import Chunk


def make_chunk(
    chunk_id: str,
    document_id: str = "gdpr",
    page: int = 1,
    start: int = 0,
    end: int = 100,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=f"Text for {chunk_id}",
        page_numbers=[page],
        start_char=start,
        end_char=end,
    )


@pytest.fixture
def document_chunks():
    return [
        make_chunk("chunk_1", page=1, start=0, end=100),
        make_chunk("chunk_2", page=1, start=80, end=180),
        make_chunk("chunk_3", page=1, start=160, end=260),
        make_chunk("chunk_4", page=2, start=0, end=100),
        make_chunk("chunk_5", page=2, start=80, end=180),
    ]


def test_expands_previous_and_next_chunks(document_chunks):
    expander = ContextExpander(
        previous_chunks=1,
        next_chunks=1,
    )

    result = expander.expand(
        primary_chunks=[document_chunks[2]],
        all_chunks=document_chunks,
    )

    assert [chunk.chunk_id for chunk in result] == [
        "chunk_2",
        "chunk_4",
    ]


def test_does_not_include_primary_chunks(document_chunks):
    expander = ContextExpander()

    result = expander.expand(
        primary_chunks=[
            document_chunks[1],
            document_chunks[2],
        ],
        all_chunks=document_chunks,
    )

    result_ids = {
        chunk.chunk_id
        for chunk in result
    }

    assert "chunk_2" not in result_ids
    assert "chunk_3" not in result_ids


def test_does_not_cross_document_boundaries(document_chunks):
    other_document_chunk = make_chunk(
        "other_document_chunk",
        document_id="other_document",
        page=1,
    )

    all_chunks = document_chunks + [other_document_chunk]

    expander = ContextExpander()

    result = expander.expand(
        primary_chunks=[document_chunks[0]],
        all_chunks=all_chunks,
    )

    assert all(
        chunk.document_id == "gdpr"
        for chunk in result
    )


def test_deduplicates_shared_neighbors(document_chunks):
    expander = ContextExpander(
        previous_chunks=1,
        next_chunks=1,
    )

    result = expander.expand(
        primary_chunks=[
            document_chunks[1],
            document_chunks[2],
        ],
        all_chunks=document_chunks,
    )

    result_ids = [
        chunk.chunk_id
        for chunk in result
    ]

    assert len(result_ids) == len(set(result_ids))


def test_preserves_document_order_across_pages(document_chunks):
    expander = ContextExpander(
        previous_chunks=2,
        next_chunks=2,
    )

    result = expander.expand(
        primary_chunks=[document_chunks[3]],
        all_chunks=document_chunks,
    )

    assert [chunk.chunk_id for chunk in result] == [
        "chunk_2",
        "chunk_3",
        "chunk_5",
    ]


def test_respects_configured_neighbor_limits(document_chunks):
    expander = ContextExpander(
        previous_chunks=2,
        next_chunks=0,
    )

    result = expander.expand(
        primary_chunks=[document_chunks[3]],
        all_chunks=document_chunks,
    )

    assert [chunk.chunk_id for chunk in result] == [
        "chunk_2",
        "chunk_3",
    ]


def test_returns_empty_for_empty_primary_chunks(document_chunks):
    expander = ContextExpander()

    result = expander.expand(
        primary_chunks=[],
        all_chunks=document_chunks,
    )

    assert result == []


def test_returns_empty_for_empty_index():
    expander = ContextExpander()

    result = expander.expand(
        primary_chunks=[make_chunk("chunk_1")],
        all_chunks=[],
    )

    assert result == []


@pytest.mark.parametrize(
    ("previous", "next_count"),
    [
        (-1, 1),
        (1, -1),
        (-1, -1),
    ],
)
def test_rejects_negative_neighbor_limits(previous, next_count):
    with pytest.raises(ValueError):
        ContextExpander(
            previous_chunks=previous,
            next_chunks=next_count,
        )
