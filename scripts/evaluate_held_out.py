"""Run the GDPR held-out retrieval benchmark and optionally generate answers.

Usage from the repository root:
    python scripts/evaluate_held_out.py
    python scripts/evaluate_held_out.py --generate

Generation is opt-in because the local LLM review loop can take several minutes.
The resulting JSON is a measurement artifact; answer correctness and citation
precision still require the manual scoring specified in the assignment.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.generation.ollama_client import OllamaClient
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "evaluation" / "held_out_questions.json"
OUTPUT_PATH = ROOT / "evaluation" / "held_out_results.json"


def section_hit(chunk, expected_sections: list[str]) -> bool:
    section = (chunk.section or "").casefold()
    subsection = (chunk.subsection or "").casefold()
    return any(
        expected.casefold() in section or expected.casefold() in subsection
        for expected in expected_sections
    )


def recall_at_k(results, expected_sections: list[str], k: int) -> float | None:
    if not expected_sections:
        return None
    return float(any(section_hit(chunk, expected_sections) for chunk, _ in results[:k]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true", help="Run the local LLM for no-retrieval and retrieval conditions.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--ids", help="Optional comma-separated question IDs, e.g. q01,q15,q16.")
    parser.add_argument("--generation-timeout", type=int, default=90, help="Per-request Ollama timeout in seconds when --generate is set.")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    if args.generation_timeout < 1:
        parser.error("--generation-timeout must be positive")

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if len(questions) < 15 or sum(not q["answerable"] for q in questions) < 3:
        raise ValueError("The benchmark must contain at least 15 questions, including 3 unanswerables.")
    if args.ids:
        selected_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
        questions = [item for item in questions if item["id"] in selected_ids]
        missing_ids = selected_ids - {item["id"] for item in questions}
        if missing_ids:
            parser.error(f"Unknown question IDs: {', '.join(sorted(missing_ids))}")
    if not questions:
        parser.error("No questions selected")
    output_path = (
        ROOT / "evaluation" / "held_out_results_selected.json"
        if args.ids
        else OUTPUT_PATH
    )

    pipeline = RetrievalPipeline(candidate_k=20, top_k=args.top_k)
    pipeline.initialize()
    generator = (
        AnswerGenerator(ollama_client=OllamaClient(timeout=args.generation_timeout))
        if args.generate
        else None
    )
    output = {
        "benchmark": QUESTIONS_PATH.name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "top_k": args.top_k,
        "conditions": {"baseline": "Dense-only FAISS retrieval", "retrieval": "Hybrid BM25 + dense RRF + cross-encoder reranking"},
        "metrics": {},
        "items": [],
        "manual_scoring": {
            "answer_correctness": "Fill in after manually reviewing each generated answer.",
            "citation_precision": "Count cited claims supported by the cited page/section; fill in after manual review.",
            "abstention_accuracy": "Computed from the retrieval condition when --generate is used.",
        },
    }
    answerable_hits = 0
    answerable_total = 0
    unanswerable_total = 0
    latencies = []

    for question in questions:
        started = time.perf_counter()
        dense = pipeline.faiss_retriever.search(question["question"], top_k=args.top_k)
        dense_elapsed = time.perf_counter() - started
        started = time.perf_counter()
        hybrid = pipeline.search(question["question"], top_k=args.top_k)
        hybrid_elapsed = time.perf_counter() - started
        latencies.append(hybrid_elapsed)

        dense_recall = recall_at_k(dense, question["expected_sections"], args.top_k)
        hybrid_recall = recall_at_k(hybrid, question["expected_sections"], args.top_k)
        if question["answerable"]:
            answerable_total += 1
            answerable_hits += int(bool(hybrid_recall))
        else:
            unanswerable_total += 1

        item = {
            **question,
            "dense_only": {
                "recall_at_k": dense_recall,
                "latency_seconds": round(dense_elapsed, 4),
                "results": [
                    {"document_id": chunk.document_id, "section": chunk.section, "pages": chunk.page_numbers, "score": float(score)}
                    for chunk, score in dense
                ],
            },
            "hybrid_reranked": {
                "recall_at_k": hybrid_recall,
                "latency_seconds": round(hybrid_elapsed, 4),
                "results": [
                    {"document_id": chunk.document_id, "section": chunk.section, "pages": chunk.page_numbers, "score": float(score)}
                    for chunk, score in hybrid
                ],
            },
            "manual_correctness": None,
            "manual_citation_precision": None,
        }

        if generator is not None:
            generation_started = time.perf_counter()
            try:
                retrieved = generator.generate_answer(question["question"], evidence=hybrid)
            except Exception as exc:
                generation_elapsed = time.perf_counter() - generation_started
                item["retrieval_generation_error"] = f"{type(exc).__name__}: {exc}"
                item["generation_seconds"] = round(generation_elapsed, 4)
                item["retrieval_abstained"] = None
                item["retrieval_answer"] = None
                item["retrieval_sources"] = []
                item["claim_verification"] = None
                item["retrieval_correctness"] = None
            else:
                generation_elapsed = time.perf_counter() - generation_started
                item["retrieval_answer"] = retrieved["answer"]
                item["retrieval_abstained"] = retrieved["abstained"]
                item["retrieval_sources"] = retrieved["sources"]
                item["claim_verification"] = retrieved["claim_verification"]
                item["generation_seconds"] = round(generation_elapsed, 4)
                item["retrieval_correctness"] = None

        output["items"].append(item)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"{question['id']} | {'answerable' if question['answerable'] else 'unanswerable':12} "
            f"dense R@{args.top_k}={dense_recall} hybrid R@{args.top_k}={hybrid_recall} "
            f"hybrid={hybrid_elapsed:.2f}s"
        )

    output["metrics"] = {
        f"dense_only_recall_at_{args.top_k}": (
            sum(item["dense_only"]["recall_at_k"] or 0 for item in output["items"] if item["answerable"])
            / answerable_total
        ),
        f"hybrid_reranked_recall_at_{args.top_k}": answerable_hits / answerable_total if answerable_total else None,
        "answerable_questions": answerable_total,
        "unanswerable_questions": unanswerable_total,
        "mean_hybrid_retrieval_latency_seconds": sum(latencies) / len(latencies) if latencies else None,
    }
    if args.generate:
        output["metrics"]["retrieval_abstention_accuracy"] = sum(
            item["retrieval_abstained"] == (not item["answerable"])
            for item in output["items"]
            if item["retrieval_abstained"] is not None
        ) / max(1, sum(item["retrieval_abstained"] is not None for item in output["items"]))
        output["metrics"]["retrieval_generation_failures"] = sum(
            item.get("retrieval_abstained") is None for item in output["items"]
        )
        output["metrics"]["mean_generation_latency_seconds"] = sum(
            item["generation_seconds"] for item in output["items"]
        ) / len(questions)

    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {output_path}")
    print(json.dumps(output["metrics"], indent=2))
    print("Manual answer and citation scoring is required before reporting those assignment metrics.")


if __name__ == "__main__":
    main()
