
import re

from rank_bm25 import BM25Okapi

from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class BM25Retriever:
    """
    Keyword-based retrieval using the BM25 ranking algorithm.

    Returns matching chunks with their BM25 relevance scores.
    """

    def __init__(self, chunks: list[Chunk]) -> None:

        if not chunks:
            raise ValueError(
                "Cannot initialize BM25Retriever with an empty chunk list."
            )

        self.chunks = chunks

        self.tokenized_corpus = [
            self._tokenize(chunk.text)
            for chunk in chunks
        ]

        self.bm25 = BM25Okapi(self.tokenized_corpus)

        logger.info(
            "BM25 index initialized with %d chunks.",
            len(self.chunks),
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        Normalize text and tokenize it.

        Keeps alphanumeric terms, including legal identifiers
        such as Article-6 and GDPR-related references.
        """

        if not isinstance(text, str):
            raise TypeError("Input text must be a string.")

        return re.findall(
            r"\b[\w-]+\b",
            text.casefold(),
        )

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[Chunk, float]]:
        """
        Retrieve the most relevant chunks for a query.

        Args:
            query: User's search query.
            top_k: Maximum number of results.

        Returns:
            List of (Chunk, BM25 score), sorted by descending score.

            Chunks with zero relevance scores are excluded.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: (-scores[index], index),
        )

        results = []

        for index in ranked_indices:

            score = float(scores[index])

            if score <= 0:
                break

            results.append(
                (self.chunks[index], score)
            )

            if len(results) >= top_k:
                break

        logger.info(
            "BM25 retrieved %d chunks for query: '%s'.",
            len(results),
            query[:100],
        )

        return results
