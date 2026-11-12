
from collections import defaultdict

from lexisync.schemas.document import Chunk


class ContextExpander:
    """
    Retrieve neighboring chunks for additional document context.

    Primary evidence remains unchanged. Neighboring chunks are returned
    separately and are never assigned new or synthetic chunk IDs.
    """

    def __init__(
        self,
        previous_chunks: int = 1,
        next_chunks: int = 1,
    ) -> None:

        if previous_chunks < 0:
            raise ValueError(
                "previous_chunks cannot be negative."
            )

        if next_chunks < 0:
            raise ValueError(
                "next_chunks cannot be negative."
            )

        self.previous_chunks = previous_chunks
        self.next_chunks = next_chunks

    @staticmethod
    def _sort_key(chunk: Chunk) -> tuple:
        """
        Sort chunks using document and page-relative positions.

        Character offsets are page-relative, so page numbers must
        be considered before character positions.
        """

        first_page = min(chunk.page_numbers) if chunk.page_numbers else 0
        last_page = max(chunk.page_numbers) if chunk.page_numbers else 0

        return (
            first_page,
            chunk.start_char,
            last_page,
            chunk.end_char,
            chunk.chunk_id,
        )

    def expand(
        self,
        primary_chunks: list[Chunk],
        all_chunks: list[Chunk],
    ) -> list[Chunk]:
        """
        Return neighboring chunks for the supplied primary evidence.

        Args:
            primary_chunks: Chunks already selected by retrieval.
            all_chunks: Complete indexed chunk collection.

        Returns:
            Additional neighboring chunks, excluding primary evidence
            and duplicate context chunks.
        """

        if not primary_chunks or not all_chunks:
            return []

        primary_ids = {
            chunk.chunk_id
            for chunk in primary_chunks
        }

        chunks_by_document = defaultdict(list)

        for chunk in all_chunks:
            chunks_by_document[chunk.document_id].append(chunk)

        ordered_chunks = {
            document_id: sorted(
                chunks,
                key=self._sort_key,
            )
            for document_id, chunks in chunks_by_document.items()
        }

        positions_by_document = {
            document_id: {
                chunk.chunk_id: position
                for position, chunk in enumerate(chunks)
            }
            for document_id, chunks in ordered_chunks.items()
        }

        context_chunks = []
        seen_context_ids = set()

        for primary in primary_chunks:

            document_chunks = ordered_chunks.get(
                primary.document_id,
                [],
            )

            positions = positions_by_document.get(
                primary.document_id,
                {},
            )

            primary_position = positions.get(
                primary.chunk_id
            )

            if primary_position is None:
                continue

            start_position = max(
                0,
                primary_position - self.previous_chunks,
            )

            end_position = min(
                len(document_chunks),
                primary_position + self.next_chunks + 1,
            )

            for position in range(
                start_position,
                end_position,
            ):

                if position == primary_position:
                    continue

                neighbor = document_chunks[position]

                if neighbor.chunk_id in primary_ids:
                    continue

                if neighbor.chunk_id in seen_context_ids:
                    continue

                seen_context_ids.add(neighbor.chunk_id)
                context_chunks.append(neighbor)

        return context_chunks
