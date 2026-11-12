"""LexiSyncAI evaluation: retrieval ablation, abstention calibration and generation.

Usage (repository root, virtual environment active):

    python scripts/evaluate.py                     # retrieval metrics only (~1-2 min)
    python scripts/evaluate.py --generate          # + full system answers (~15-25 min)
    python scripts/evaluate.py --generate --ids q01,q12,q25

Outputs (evaluation/results/):
    retrieval_metrics.json   Recall@1/3/5/10, MRR, multi-hop recall, latency per configuration
    calibration.json         evidence-gate threshold chosen on the separate dev set
    generation_results.json  per-question answers, citations, verification, latency, tokens
    summary.json             headline metrics used in docs/EVALUATION_REPORT.md
    ../manual_scoring_template.csv  pre-filled sheet for manual correctness/citation scoring

Evaluation indexes live in storage/eval/ and never touch user cases.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexisync import config  # noqa: E402
from lexisync.evaluation import metrics as M  # noqa: E402
from lexisync.retrieval.query_planner import QueryPlanner  # noqa: E402
from lexisync.services.case_manager import CaseManager  # noqa: E402

QUESTIONS = ROOT / "evaluation" / "held_out_questions.json"
DEV_QUESTIONS = ROOT / "evaluation" / "dev_calibration_questions.json"
RESULTS = ROOT / "evaluation" / "results"
EVAL_STORE = ROOT / "storage" / "eval"
KS = (1, 3, 5, 10)
MODES = ("dense", "bm25", "hybrid", "hybrid_rerank")


def build_case(manager: CaseManager, name: str, pdf: Path, contextual: bool, rebuild: bool) -> str:
    existing = next((c for c in manager.list_cases() if c["name"] == name), None)
    if existing and existing["status"] == "indexed" and not rebuild:
        return existing["id"]
    if existing:
        manager.delete_case(existing["id"])
    case = manager.create_case(name)
    manager.update_settings(case["id"], contextual_headers=contextual)
    manager.add_document(case["id"], pdf.name, pdf.read_bytes())
    started = time.perf_counter()
    manager.index_case(case["id"])
    print(f"  indexed {name} in {time.perf_counter() - started:.1f}s")
    return case["id"]


def retrieval_eval(manager: CaseManager, case_id: str, questions: list[dict], planner: QueryPlanner) -> dict:
    pipeline = manager.get_pipeline(case_id)
    per_mode: dict[str, dict] = {}

    for mode in MODES:
        rows = []
        for q in questions:
            started = time.perf_counter()
            detailed = pipeline.search_detailed(q["question"], mode=mode, top_k=max(KS), candidate_k=config.CANDIDATE_K)
            elapsed = time.perf_counter() - started
            ranked = [chunk for chunk, _ in detailed.results]
            expected = q.get("expected_sections", [])
            rows.append({
                "id": q["id"],
                "type": q.get("type"),
                "answerable": q["answerable"],
                **{f"hit@{k}": M.hit_at_k(ranked, expected, k) for k in KS},
                **{f"full@{k}": M.full_recall_at_k(ranked, expected, k) for k in KS},
                "rr": M.reciprocal_rank(ranked, expected),
                "page_hit@5": M.page_hit_at_k(ranked, q.get("expected_pages", []), 5),
                "top_score": float(detailed.results[0][1]) if detailed.results else None,
                "latency_seconds": elapsed,
                "top5": [{"section": c.section, "pages": c.page_numbers} for c in ranked[:5]],
            })
        answerable = [r for r in rows if r["answerable"]]
        multi = [r for r in answerable if r["type"] == "multi_hop"]
        per_mode[mode] = {
            "recall_at_k": {k: M.mean(r[f"hit@{k}"] for r in answerable) for k in KS},
            "multi_hop_full_recall_at_k": {k: M.mean(r[f"full@{k}"] for r in multi) for k in KS},
            "mrr": M.mean(r["rr"] for r in answerable),
            "page_hit_at_5": M.mean(r["page_hit@5"] for r in answerable),
            "latency": M.latency_summary(r["latency_seconds"] for r in rows),
            "rows": rows,
        }
        summary = per_mode[mode]
        print(f"  {mode:14} R@1={summary['recall_at_k'][1]:.2f} R@3={summary['recall_at_k'][3]:.2f} "
              f"R@5={summary['recall_at_k'][5]:.2f} R@10={summary['recall_at_k'][10]:.2f} "
              f"MRR={summary['mrr']:.2f} MH-full@5={summary['multi_hop_full_recall_at_k'][5] or 0:.2f} "
              f"lat={summary['latency']['mean']:.3f}s")

    # Planner-driven multi-hop retrieval (the system configuration).
    multi_rows = []
    for q in questions:
        if q.get("type") != "multi_hop":
            continue
        plan = planner.plan(q["question"])
        started = time.perf_counter()
        result = pipeline.multi_hop_search(plan, top_k=config.FINAL_TOP_K, per_sub_query_k=config.PER_SUB_QUERY_K)
        elapsed = time.perf_counter() - started
        ranked = [item.chunk for item in result.evidence]
        multi_rows.append({
            "id": q["id"],
            "sub_queries": plan.sub_queries,
            "evidence_size": len(ranked),
            "full_recall": M.full_recall_at_k(ranked, q["expected_sections"], len(ranked)),
            "latency_seconds": elapsed,
        })
    per_mode["planner_multi_hop"] = {
        "multi_hop_full_recall": M.mean(r["full_recall"] for r in multi_rows),
        "mean_evidence_size": M.mean(r["evidence_size"] for r in multi_rows),
        "latency": M.latency_summary(r["latency_seconds"] for r in multi_rows),
        "rows": multi_rows,
    }
    print(f"  planner multi-hop full recall = {per_mode['planner_multi_hop']['multi_hop_full_recall']:.2f}")
    return per_mode


def calibrate(manager: CaseManager, case_id: str) -> dict:
    pipeline = manager.get_pipeline(case_id)
    dev = json.loads(DEV_QUESTIONS.read_text(encoding="utf-8"))
    rows = []
    for q in dev:
        result = pipeline.search_detailed(q["question"], mode="hybrid_rerank", top_k=1)
        rows.append({"id": q["id"], "answerable": q["answerable"],
                     "top_score": float(result.results[0][1]) if result.results else -99.0})
    positive = [r["top_score"] for r in rows if r["answerable"]]
    negative = [r["top_score"] for r in rows if not r["answerable"]]
    chosen = M.best_threshold(positive, negative)
    return {"dev_set": DEV_QUESTIONS.name, "rows": rows, **chosen,
            "min_answerable": min(positive), "max_unanswerable": max(negative)}


def generation_eval(manager: CaseManager, case_id: str, questions: list[dict], output: Path) -> list[dict]:
    from lexisync.services.qa_service import QAService

    qa = QAService(manager)
    records = []
    for q in questions:
        print(f"  {q['id']} ...", end="", flush=True)
        try:
            result = qa.ask(case_id, q["question"], save=False)
        except Exception as error:  # record and continue
            print(f" ERROR {error}")
            records.append({"id": q["id"], "answerable": q["answerable"], "type": q["type"],
                            "abstained": None, "error": f"{type(error).__name__}: {error}"})
            continue

        shown = ([result["direct_answer"]] if result["direct_answer"] else []) + result["findings"]
        source_by_id = {s["source_id"]: s for s in result["sources"]}
        cited = [source_by_id[sid] for claim in shown for sid in claim["sources"] if sid in source_by_id]
        cited_sections = [s["section"] for s in cited]
        expected = q.get("expected_sections", [])
        found = {s for sec in cited_sections for s in expected
                 if M.relevant_sections(M.Chunk("_", "_", "", [], section=sec), [s])}

        record = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "answerable": q["answerable"],
            "expected_answer": q.get("expected_answer"),
            "expected_sections": expected,
            "expected_pages": q.get("expected_pages", []),
            "status": result["status"],
            "abstained": result["abstained"],
            "confidence": result["confidence"]["level"],
            "answer": result["answer"],
            "abstention_reason": (result["abstention"] or {}).get("reason"),
            "claims_shown": len(shown),
            "claims_removed": len(result["removed_claims"]),
            "verification": {k: v for k, v in result["verification"].items() if k != "retry_log"},
            "retry_log": result["verification"]["retry_log"],
            "cited_sources": [{"source_id": s["source_id"], "section": s["section"], "pages": s["pages"]} for s in cited],
            "citation_section_precision": M.citation_section_precision(cited_sections, expected),
            "expected_provisions_cited": (len(found) / len(set(expected))) if expected and shown else None,
            "citation_coverage": (sum(1 for c in shown if c["sources"]) / len(shown)) if shown else None,
            "retrieval_seconds": result["timings"]["retrieval_seconds"],
            "generation_seconds": result["timings"]["generation_seconds"],
            "total_seconds": result["timings"]["total_seconds"],
            "llm_calls": result["usage"]["llm_calls"],
            "prompt_tokens": result["usage"]["prompt_tokens"],
            "completion_tokens": result["usage"]["completion_tokens"],
            "plan": result["plan"],
        }
        records.append(record)
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f" {record['status']:9} {record['confidence']:12} {record['total_seconds']:6.1f}s")
    return records


def legacy_baseline(manager: CaseManager, case_id: str, questions: list[dict]) -> dict:
    """Run the original free-text ``AnswerGenerator`` on the same retrieved evidence.

    This measures the false-abstention problem *before* the structured
    answerer, on identical retrieval, so the comparison isolates generation
    and verification.
    """

    from lexisync.generation.answer_generator import AnswerGenerator
    from lexisync.retrieval.context_expander import ContextExpander

    pipeline = manager.get_pipeline(case_id)
    generator = AnswerGenerator()
    records = []
    for q in questions:
        print(f"  legacy {q['id']} ...", end="", flush=True)
        started = time.perf_counter()
        evidence = pipeline.search_detailed(q["question"], top_k=config.FINAL_TOP_K).results
        context = ContextExpander(previous_chunks=1, next_chunks=1).expand([c for c, _ in evidence], pipeline.chunks)
        try:
            result = generator.generate_answer(q["question"], evidence, context_evidence=context)
            abstained = result["abstained"]
        except Exception as error:
            abstained = None
            print(f" ERROR {error}", end="")
        elapsed = time.perf_counter() - started
        records.append({"id": q["id"], "answerable": q["answerable"], "abstained": abstained, "seconds": elapsed})
        print(f" {'abstained' if abstained else 'answered'} {elapsed:.1f}s")
    return {
        "description": "Original AnswerGenerator (free-text answer, sentence-level citation gate) on identical hybrid evidence",
        **M.abstention_metrics(records),
        "latency": M.latency_summary(r["seconds"] for r in records),
        "rows": records,
    }


def generation_summary(records: list[dict]) -> dict:
    ok = [r for r in records if r.get("abstained") is not None]
    answered = [r for r in ok if not r["abstained"]]
    answered_answerable = [r for r in answered if r["answerable"]]
    multi = [r for r in answered_answerable if r["type"] == "multi_hop"]
    return {
        **M.abstention_metrics(records),
        "citation_section_precision": M.mean(r["citation_section_precision"] for r in answered_answerable),
        "expected_provisions_cited": M.mean(r["expected_provisions_cited"] for r in answered_answerable),
        "multi_hop_expected_provisions_cited": M.mean(r["expected_provisions_cited"] for r in multi),
        "citation_coverage": M.mean(r["citation_coverage"] for r in answered),
        "claim_verification_pass_rate": (
            sum(r["verification"]["supported"] for r in ok) / max(1, sum(r["verification"]["total_claims"] for r in ok))
        ),
        "questions_needing_retry": sum(1 for r in ok if r["verification"]["retry_count"] > 0),
        "confidence_distribution": {
            level: sum(1 for r in ok if r["confidence"] == level)
            for level in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")
        },
        "latency_total": M.latency_summary(r["total_seconds"] for r in ok),
        "latency_retrieval": M.latency_summary(r["retrieval_seconds"] for r in ok),
        "latency_generation": M.latency_summary(r["generation_seconds"] for r in ok),
        "mean_llm_calls": M.mean(r["llm_calls"] for r in ok),
        "mean_prompt_tokens": M.mean(r["prompt_tokens"] for r in ok),
        "mean_completion_tokens": M.mean(r["completion_tokens"] for r in ok),
    }


# Manual scoring columns (scoring rules in README "Manual evaluation procedure").
MANUAL_COLUMNS = [
    "question_id", "answerable", "manual_answer_correct_0_or_1", "claims_total",
    "supported_cited_claims", "citation_precision_0_to_1", "abstention_correct_0_or_1",
    "end_to_end_latency_seconds", "reviewer_notes",
]
# Read-only context for the reviewer, appended after the scoring columns.
CONTEXT_COLUMNS = [
    "type", "question", "expected_answer", "expected_sections", "expected_pages",
    "system_status", "system_confidence", "system_answer", "cited_sources",
]


def write_manual_template(records: list[dict], path: Path) -> None:
    """Write the manual scoring sheet.

    Pre-filled: answerability, the number of cited claims shown
    (``claims_total``) and the measured server-side end-to-end latency.
    The reviewer fills correctness, supported claims, citation precision and
    abstention correctness after checking each cited page.
    """

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(MANUAL_COLUMNS + CONTEXT_COLUMNS)
        for r in records:
            answered = r.get("abstained") is False
            writer.writerow([
                r["id"], str(r["answerable"]).lower(), "",
                r.get("claims_shown", "") if answered else "",
                "", "", "",
                f"{r['total_seconds']:.2f}" if r.get("total_seconds") is not None else "",
                "",
                r.get("type"), r.get("question", ""), r.get("expected_answer") or "",
                "; ".join(r.get("expected_sections", [])), ", ".join(map(str, r.get("expected_pages", []))),
                r.get("status", "error"), r.get("confidence", ""), r.get("answer", r.get("error", "")),
                "; ".join(
                    f"{s['source_id']} {s['section'] or 'Preamble'} p.{','.join(map(str, s['pages']))}"
                    for s in r.get("cited_sources", [])
                ),
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, default=ROOT / "data" / "raw" / "gdpr.pdf")
    parser.add_argument("--generate", action="store_true", help="Also run the full answer pipeline (slow).")
    parser.add_argument("--ids", help="Comma-separated question IDs for --generate.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the evaluation indexes.")
    parser.add_argument("--legacy-baseline", action="store_true",
                        help="Also run the original AnswerGenerator for a before/after comparison (slow).")
    args = parser.parse_args()

    if not args.pdf.exists():
        parser.error(f"Benchmark PDF not found: {args.pdf}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    print(f"Benchmark: {len(questions)} questions "
          f"({sum(q['type'] == 'factual' for q in questions)} factual, "
          f"{sum(q['type'] == 'multi_hop' for q in questions)} multi-hop, "
          f"{sum(q['type'] == 'unanswerable' for q in questions)} unanswerable)")

    manager = CaseManager(uploads_dir=EVAL_STORE / "uploads", index_dir=EVAL_STORE / "indexes", cases_dir=EVAL_STORE / "cases")
    planner = QueryPlanner()

    print("Building evaluation indexes ...")
    contextual_id = build_case(manager, "eval-contextual", args.pdf, True, args.rebuild)
    plain_id = build_case(manager, "eval-plain", args.pdf, False, args.rebuild)

    print("Retrieval — contextual section headers (system default):")
    contextual = retrieval_eval(manager, contextual_id, questions, planner)
    print("Retrieval — plain chunk text (ablation):")
    plain = retrieval_eval(manager, plain_id, questions, planner)

    calibration = calibrate(manager, contextual_id)
    print(f"Evidence gate calibrated on dev set: threshold={calibration['threshold']} "
          f"(dev accuracy {calibration['accuracy']:.2f}; min answerable {calibration['min_answerable']:.2f}, "
          f"max unanswerable {calibration['max_unanswerable']:.2f}); configured={config.EVIDENCE_GATE_SCORE}")

    # Held-out retrieval-only abstention at the configured gate.
    rows = contextual["hybrid_rerank"]["rows"]
    gate_records = [{"answerable": r["answerable"], "abstained": (r["top_score"] or -99) < config.EVIDENCE_GATE_SCORE} for r in rows]

    retrieval_out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "document": args.pdf.name,
        "questions": len(questions),
        "contextual_headers": contextual,
        "plain_text": plain,
    }
    (RESULTS / "retrieval_metrics.json").write_text(json.dumps(retrieval_out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTS / "calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")

    summary = {
        "generated_at": retrieval_out["generated_at"],
        "retrieval": {
            variant: {
                mode: {k: v for k, v in data[mode].items() if k != "rows"} for mode in MODES
            } | {"planner_multi_hop": {k: v for k, v in data["planner_multi_hop"].items() if k != "rows"}}
            for variant, data in (("contextual_headers", contextual), ("plain_text", plain))
        },
        "evidence_gate": {
            "configured_threshold": config.EVIDENCE_GATE_SCORE,
            "dev_calibration": {k: v for k, v in calibration.items() if k != "rows"},
            "held_out_gate_only": M.abstention_metrics(gate_records),
        },
    }

    if args.generate:
        selected = questions
        if args.ids:
            wanted = {i.strip() for i in args.ids.split(",")}
            selected = [q for q in questions if q["id"] in wanted]
        print(f"Generation ({len(selected)} questions, model {config.OLLAMA_MODEL}) ...")
        output = RESULTS / ("generation_results.json" if not args.ids else "generation_results_selected.json")
        records = generation_eval(manager, contextual_id, selected, output)
        summary["generation"] = generation_summary(records)
        summary["generation"]["model"] = config.OLLAMA_MODEL
        if not args.ids:
            write_manual_template(records, ROOT / "evaluation" / "manual_scoring_template.csv")
        print(json.dumps(summary["generation"], indent=2))

    if args.legacy_baseline:
        print("Legacy baseline (original AnswerGenerator) ...")
        baseline = legacy_baseline(manager, contextual_id, questions)
        (RESULTS / "legacy_baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        summary["legacy_baseline"] = {k: v for k, v in baseline.items() if k != "rows"}

    summary_path = RESULTS / ("summary.json" if not args.ids else "summary_selected.json")
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        for key in ("generation", "legacy_baseline"):
            if key in previous and key not in summary:
                summary[key] = previous[key]
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {RESULTS}")


if __name__ == "__main__":
    main()
