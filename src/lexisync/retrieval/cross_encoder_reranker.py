
import numpy as np

from sentence_transformers import CrossEncoder

from lexisync.config import RERANKER_MODEL
from lexisync.retrieval.text_utils import index_text
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class CrossEncoderReranker:
    """
    Rerank retrieved chunks using a cross-encoder model.

    Unlike bi-encoder retrieval, the cross-encoder evaluates
    the query and each candidate passage together.

    Higher scores indicate greater query-passage relevance.
    """

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        batch_size: int = 16,
        model: CrossEncoder | None = None,
        contextual: bool = False,
    ) -> None:

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero."
            )

        self.batch_size = batch_size
        self.contextual = contextual

        self.model = model or CrossEncoder(
            model_name,
            device="cpu",
        )

        logger.info(
            "Cross-encoder reranker initialized using %s.",
            model_name,
        )

    def rerank(
        self,
        query: str,
        candidates: list[tuple[Chunk, float]],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        """
        Rerank candidate chunks for a given query.

        Args:
            query: User's search query.
            candidates: Retrieved (Chunk, retrieval_score) pairs.
            top_k: Maximum number of reranked results.

        Returns:
            List of (Chunk, cross_encoder_score) pairs,
            sorted by descending relevance score.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "Reranking query cannot be empty."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        if not candidates:
            return []

        query = query.strip()

        # Build query-passage pairs.
        pairs = [
            (query, index_text(chunk, self.contextual))
            for chunk, _ in candidates
        ]

        # Evaluate each query-passage pair.
        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        scores = np.asarray(
            scores,
            dtype=np.float32,
        ).reshape(-1)

        if len(scores) != len(candidates):
            raise ValueError(
                "Cross-encoder score count does not match "
                "the number of candidate chunks."
            )

        if not np.isfinite(scores).all():
            raise ValueError(
                "Cross-encoder generated invalid scores."
            )

        # Preserve original retrieval order when scores tie.
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: (
                -float(scores[index]),
                index,
            ),
        )

        results = [
            (
                candidates[index][0],
                float(scores[index]),
            )
            for index in ranked_indices[:top_k]
        ]

        logger.info(
            "Cross-encoder reranked %d candidates and returned %d results.",
            len(candidates),
            len(results),
        )

        return results
