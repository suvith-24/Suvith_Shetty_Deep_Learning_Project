
import math

from sentence_transformers import CrossEncoder

from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class ClaimVerifier:
    """
    Verify whether an evidence passage supports an individual claim.

    Uses a local Natural Language Inference (NLI) model.

    Possible outcomes:
    - supported: Evidence entails the claim.
    - contradicted: Evidence contradicts the claim.
    - inconclusive: Evidence neither clearly supports nor contradicts it.

    Important:
    The normalized scores are model scores, not calibrated probabilities.
    """

    MODEL_NAME = "cross-encoder/nli-deberta-v3-small"

    LABELS = {
        0: "contradiction",
        1: "entailment",
        2: "neutral",
    }

    def __init__(
        self,
        model=None,
        model_name: str = MODEL_NAME,
        device: str = "cpu",
        entailment_threshold: float = 0.70,
        contradiction_threshold: float = 0.70,
        margin_threshold: float = 0.15,
    ):
        if not 0.0 <= entailment_threshold <= 1.0:
            raise ValueError("Entailment threshold must be between 0 and 1.")

        if not 0.0 <= contradiction_threshold <= 1.0:
            raise ValueError(
                "Contradiction threshold must be between 0 and 1."
            )

        if not 0.0 <= margin_threshold <= 1.0:
            raise ValueError("Margin threshold must be between 0 and 1.")

        self.model_name = model_name
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold
        self.margin_threshold = margin_threshold

        self.model = model or CrossEncoder(
            model_name,
            device=device,
        )

        self._validate_model_labels()

        logger.info(
            "Claim verifier initialized using model: %s",
            model_name,
        )

    def _validate_model_labels(self):
        """Verify that the loaded model uses the expected NLI labels."""

        config = getattr(self.model.model, "config", None)

        if config is None:
            raise ValueError("NLI model configuration is unavailable.")

        id2label = getattr(config, "id2label", None)

        if not isinstance(id2label, dict):
            raise ValueError("NLI model does not expose a valid label mapping.")

        actual_labels = {
            int(index): str(label).casefold()
            for index, label in id2label.items()
        }

        if actual_labels != self.LABELS:
            raise ValueError(
                "Unexpected NLI label mapping. "
                f"Expected {self.LABELS}, received {actual_labels}."
            )

    @staticmethod
    def _softmax(logits):
        """Convert raw model logits into normalized scores."""

        values = [float(value) for value in logits]

        if not all(math.isfinite(value) for value in values):
            raise ValueError("NLI model returned non-finite scores.")

        maximum = max(values)
        exponentials = [
            math.exp(value - maximum)
            for value in values
        ]

        total = sum(exponentials)

        if total == 0:
            raise ValueError("Unable to normalize NLI model scores.")

        return [
            value / total
            for value in exponentials
        ]

    def verify(
        self,
        claim: str,
        evidence: str,
    ) -> dict:
        """
        Compare one factual claim against one evidence passage.

        Premise: Evidence passage.
        Hypothesis: Claim being evaluated.
        """

        if not isinstance(claim, str) or not claim.strip():
            raise ValueError("Claim must be a non-empty string.")

        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("Evidence must be a non-empty string.")

        # NLI convention:
        # Premise = supplied evidence
        # Hypothesis = factual claim
        scores = self.model.predict(
            [(evidence.strip(), claim.strip())],
            show_progress_bar=False,
        )

        if len(scores) != 1 or len(scores[0]) != 3:
            raise ValueError(
                "NLI model must return exactly three scores "
                "for one claim-evidence pair."
            )

        normalized_scores = self._softmax(scores[0])

        score_by_label = {
            self.LABELS[index]: normalized_scores[index]
            for index in range(3)
        }

        ranked_scores = sorted(
            score_by_label.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        predicted_label, highest_score = ranked_scores[0]
        second_highest_score = ranked_scores[1][1]
        score_margin = highest_score - second_highest_score

        if (
            predicted_label == "entailment"
            and highest_score >= self.entailment_threshold
            and score_margin >= self.margin_threshold
        ):
            status = "supported"

        elif (
            predicted_label == "contradiction"
            and highest_score >= self.contradiction_threshold
            and score_margin >= self.margin_threshold
        ):
            status = "contradicted"

        else:
            status = "inconclusive"

        result = {
            "claim": claim.strip(),
            "status": status,
            "predicted_label": predicted_label,
            "scores": score_by_label,
            "score_margin": score_margin,
            "thresholds": {
                "entailment": self.entailment_threshold,
                "contradiction": self.contradiction_threshold,
                "margin": self.margin_threshold,
            },
        }

        logger.info(
            "Claim verification completed: %s (label=%s)",
            status,
            predicted_label,
        )

        return result
