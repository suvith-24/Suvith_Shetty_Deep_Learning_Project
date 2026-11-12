"""Rule-based confidence levels from measurable signals.

The level is **not a calibrated probability**. It is a transparent rule over
signals the system actually measured:

* ``top_score``: best cross-encoder relevance logit of the evidence
* claim verification: supported vs removed claims
* coverage: whether every part of a multi-hop question has a verified claim
* conflicts: detected cross-document value conflicts
* retries: whether a corrective retry was needed

Levels:

* ``INSUFFICIENT``: the system abstained.
* ``HIGH``: every drafted claim verified, all parts covered, no conflicts,
  and strong retrieval (``top_score >= high_score``).
* ``LOW``: a question part is unanswered, most claims were removed, or
  retrieval is weak (within 2 logits of the abstention gate).
* ``MEDIUM``: anything in between.
"""

from __future__ import annotations


def compute_confidence(
    *,
    abstained: bool,
    top_score: float | None,
    high_score: float,
    gate_score: float,
    supported: int,
    removed: int,
    coverage: list[dict],
    conflicts: int,
    retries: int,
) -> dict:
    signals = {
        "top_rerank_score": None if top_score is None else round(float(top_score), 3),
        "supported_claims": supported,
        "removed_claims": removed,
        "parts_total": len(coverage),
        "parts_covered": sum(1 for c in coverage if c.get("covered")),
        "conflicts": conflicts,
        "corrective_retries": retries,
    }

    if abstained:
        return {
            "level": "INSUFFICIENT",
            "reasons": ["The system abstained: the evidence did not support an answer."],
            "signals": signals,
        }

    reasons: list[str] = []
    total = supported + removed
    supported_ratio = supported / total if total else 0.0
    partial = signals["parts_covered"] < signals["parts_total"]
    weak = top_score is None or top_score < gate_score + 2.0

    if partial:
        reasons.append("At least one part of the question is not answered by verified evidence.")
    if supported_ratio < 0.5:
        reasons.append(f"Only {supported} of {total} drafted claims passed verification.")
    if weak:
        reasons.append("The best retrieved passage is only weakly relevant.")

    if partial or supported_ratio < 0.5 or weak:
        level = "LOW"
    elif removed == 0 and conflicts == 0 and top_score >= high_score:
        level = "HIGH"
        reasons.append(
            f"All {supported} claims verified against their cited passages; strong retrieval "
            f"(score {top_score:.2f})."
        )
    else:
        level = "MEDIUM"
        if removed:
            reasons.append(f"{removed} unverified claim(s) were removed.")
        if conflicts:
            reasons.append("The documents contain potentially conflicting provisions.")
        if top_score < high_score:
            reasons.append(f"Retrieval relevance is moderate (score {top_score:.2f}).")

    return {"level": level, "reasons": reasons, "signals": signals}
