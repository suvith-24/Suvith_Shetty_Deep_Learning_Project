
import pytest

from types import SimpleNamespace

from lexisync.generation.claim_verifier import ClaimVerifier


class MockNLIModel:
    """Mock CrossEncoder for deterministic unit testing."""

    def __init__(self, logits):
        self.logits = logits
        self.model = SimpleNamespace(
            config=SimpleNamespace(
                id2label={
                    0: "contradiction",
                    1: "entailment",
                    2: "neutral",
                }
            )
        )

    def predict(self, pairs, show_progress_bar=False):
        self.received_pairs = pairs
        return [self.logits]


def create_verifier(logits):
    return ClaimVerifier(model=MockNLIModel(logits))


def test_supported_claim():
    verifier = create_verifier([-4.2, 4.7, -0.6])

    result = verifier.verify(
        claim="A transfer must comply with Chapter V.",
        evidence="The controller must ensure compliance with Chapter V.",
    )

    assert result["status"] == "supported"
    assert result["predicted_label"] == "entailment"


def test_contradicted_claim():
    verifier = create_verifier([4.3, -5.0, 0.6])

    result = verifier.verify(
        claim="Personal data may be transferred without safeguards.",
        evidence="Transfers must be subject to appropriate safeguards.",
    )

    assert result["status"] == "contradicted"
    assert result["predicted_label"] == "contradiction"


def test_neutral_claim_is_inconclusive():
    verifier = create_verifier([-2.0, -1.0, 3.0])

    result = verifier.verify(
        claim="The controller must notify the authority.",
        evidence="The controller must maintain records of processing.",
    )

    assert result["status"] == "inconclusive"
    assert result["predicted_label"] == "neutral"


def test_low_entailment_score_is_inconclusive():
    verifier = create_verifier([0.0, 0.2, 0.1])

    result = verifier.verify(
        claim="The transfer must comply with Chapter V.",
        evidence="The transfer must comply with Chapter V.",
    )

    assert result["status"] == "inconclusive"


def test_score_margin_is_returned():
    verifier = create_verifier([-4.2, 4.7, -0.6])

    result = verifier.verify(
        claim="A transfer must comply with Chapter V.",
        evidence="The controller must ensure compliance with Chapter V.",
    )

    assert result["score_margin"] > 0
    assert "scores" in result
    assert set(result["scores"]) == {
        "contradiction",
        "entailment",
        "neutral",
    }


def test_evidence_is_passed_as_premise():
    mock_model = MockNLIModel([-4.2, 4.7, -0.6])
    verifier = ClaimVerifier(model=mock_model)

    claim = "A transfer must comply with Chapter V."
    evidence = "The controller must ensure compliance with Chapter V."

    verifier.verify(claim, evidence)

    assert mock_model.received_pairs == [
        (evidence, claim)
    ]


@pytest.mark.parametrize(
    "claim,evidence",
    [
        ("", "Some evidence."),
        ("   ", "Some evidence."),
        ("A valid claim.", ""),
        ("A valid claim.", "   "),
        (None, "Some evidence."),
        ("A valid claim.", None),
    ],
)
def test_invalid_inputs_raise_error(claim, evidence):
    verifier = create_verifier([-4.2, 4.7, -0.6])

    with pytest.raises(ValueError):
        verifier.verify(claim, evidence)


@pytest.mark.parametrize(
    "thresholds",
    [
        {"entailment_threshold": -0.1},
        {"entailment_threshold": 1.1},
        {"contradiction_threshold": -0.1},
        {"contradiction_threshold": 1.1},
        {"margin_threshold": -0.1},
        {"margin_threshold": 1.1},
    ],
)
def test_invalid_thresholds_raise_error(thresholds):
    with pytest.raises(ValueError):
        ClaimVerifier(
            model=MockNLIModel([-4.2, 4.7, -0.6]),
            **thresholds,
        )


def test_unexpected_model_label_mapping_raises_error():
    mock_model = MockNLIModel([-4.2, 4.7, -0.6])

    mock_model.model.config.id2label = {
        0: "neutral",
        1: "entailment",
        2: "contradiction",
    }

    with pytest.raises(ValueError, match="Unexpected NLI label mapping"):
        ClaimVerifier(model=mock_model)


def test_non_finite_scores_raise_error():
    verifier = create_verifier([float("nan"), 1.0, 0.0])

    with pytest.raises(ValueError, match="non-finite"):
        verifier.verify(
            "A factual claim.",
            "Supporting evidence.",
        )


def test_invalid_model_output_shape_raises_error():
    mock_model = MockNLIModel([1.0, 2.0])
    verifier = ClaimVerifier(model=mock_model)

    with pytest.raises(ValueError, match="exactly three scores"):
        verifier.verify(
            "A factual claim.",
            "Supporting evidence.",
        )
