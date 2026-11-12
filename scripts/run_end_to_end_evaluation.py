import time

from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.retrieval.context_expander import ContextExpander
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


def main() -> None:
    question = (
        "What conditions must be satisfied when "
        "transferring personal data to a third country?"
    )

    print("\nLEXSYNC AI - END-TO-END EVALUATION")
    print("=" * 75)
    print(f"\nQuestion: {question}")

    # --------------------------------------------------
    # STEP 1: Initialize retrieval pipeline
    # --------------------------------------------------
    print("\n[1/4] Initializing retrieval pipeline...")

    initialization_start = time.perf_counter()

    retrieval_pipeline = RetrievalPipeline(
        candidate_k=20,
        top_k=5,
    )

    retrieval_pipeline.initialize()

    initialization_time = time.perf_counter() - initialization_start
    all_chunks = retrieval_pipeline.faiss_retriever.chunks

    print("Retrieval pipeline initialized.")
    print(f"Indexed chunks: {len(all_chunks)}")
    print(f"Initialization time: {initialization_time:.2f} seconds")

    # --------------------------------------------------
    # STEP 2: Retrieve and rerank primary evidence
    # --------------------------------------------------
    print("\n[2/4] Retrieving and reranking primary evidence...")

    retrieval_start = time.perf_counter()
    evidence = retrieval_pipeline.search(question)
    retrieval_time = time.perf_counter() - retrieval_start

    if not evidence:
        print("No relevant evidence was retrieved.")
        return

    print(f"Retrieved {len(evidence)} primary evidence chunks.")
    print(f"Retrieval time: {retrieval_time:.2f} seconds")

    for rank, (chunk, score) in enumerate(evidence, start=1):
        print(f"\n  [{rank}] {chunk.section or 'Unknown section'}")
        print(f"      Chunk ID: {chunk.chunk_id}")
        print(f"      Pages: {chunk.page_numbers}")
        print(f"      Rerank score: {score:.4f}")

    # --------------------------------------------------
    # STEP 3: Expand neighboring context
    # --------------------------------------------------
    print("\n[3/4] Expanding neighboring document context...")

    context_expander = ContextExpander(
        previous_chunks=1,
        next_chunks=1,
    )

    context_start = time.perf_counter()

    context_evidence = context_expander.expand(
        primary_chunks=[chunk for chunk, _ in evidence],
        all_chunks=all_chunks,
    )

    context_expansion_time = time.perf_counter() - context_start

    print(f"Additional context chunks: {len(context_evidence)}")
    print(f"Context expansion time: {context_expansion_time:.4f} seconds")

    for index, chunk in enumerate(context_evidence, start=1):
        print(f"\n  [Context {index}] {chunk.section or 'Unknown section'}")
        print(f"      Chunk ID: {chunk.chunk_id}")
        print(f"      Pages: {chunk.page_numbers}")

    # --------------------------------------------------
    # STEP 4: Generate answer and verify claims
    # --------------------------------------------------
    print("\n[4/4] Generating answer and verifying claims...")
    print("This may take some time because each claim is reviewed.")

    answer_generator = AnswerGenerator()

    generation_start = time.perf_counter()

    result = answer_generator.generate_answer(
        query=question,
        evidence=evidence,
        context_evidence=context_evidence,
    )

    generation_time = time.perf_counter() - generation_start

    # --------------------------------------------------
    # DISPLAY GENERATED ANSWER
    # --------------------------------------------------
    print("\n" + "=" * 75)
    print("GENERATED ANSWER")
    print("=" * 75)

    print(result["answer"])

    # --------------------------------------------------
    # CITATION VALIDATION
    # --------------------------------------------------
    validation = result["validation"]

    print("\n" + "=" * 75)
    print("CITATION VALIDATION")
    print("=" * 75)

    print(f"Answer valid: {validation['is_valid']}")
    print(f"Has citations: {validation['has_citations']}")
    print(f"Citations valid: {validation['citations_valid']}")
    print(f"Cited source IDs: {validation['cited_source_ids']}")
    print(f"Unknown source IDs: {validation['unknown_source_ids']}")
    print(f"Abstained: {result['abstained']}")

    # --------------------------------------------------
    # CLAIM VERIFICATION
    # --------------------------------------------------
    verification = result["claim_verification"]

    print("\n" + "=" * 75)
    print("CLAIM-LEVEL VERIFICATION")
    print("=" * 75)

    print(f"Total claims: {verification['total_claims']}")
    print(f"Supported: {verification['supported']}")
    print(f"Contradicted: {verification['contradicted']}")
    print(f"Insufficient: {verification['insufficient']}")
    print(f"Inconclusive: {verification['inconclusive']}")

    print(
        f"All claims supported: "
        f"{verification['all_claims_supported']}"
    )

    print(f"Verification message: {verification['message']}")

    for index, review in enumerate(verification["reviews"], start=1):
        print(f"\nClaim {index}")
        print("-" * 75)
        print(f"Claim: {review['claim']}")
        print(f"Sources: {review.get('source_ids', [])}")
        print(f"Status: {review['status']}")
        print(f"Quotation valid: {review.get('quotation_valid', False)}")
        print(f"Reason: {review.get('reason', 'Not provided')}")

        if review.get("raw_response"):
            print("Raw reviewer response:")
            print(review["raw_response"])

        if review.get("quotation"):
            print(f"Evidence quotation: {review['quotation']}")

    # --------------------------------------------------
    # SOURCE METADATA
    # --------------------------------------------------
    print("\n" + "=" * 75)
    print("SOURCE METADATA")
    print("=" * 75)

    for source in result["sources"]:
        print(
            f"{source['source_id']} | "
            f"Type: {source.get('evidence_type', 'primary')} | "
            f"Document: {source['document_id']} | "
            f"Pages: {source['pages']} | "
            f"Section: {source['section']}"
        )

    # --------------------------------------------------
    # PERFORMANCE SUMMARY
    # --------------------------------------------------
    print("\n" + "=" * 75)
    print("PERFORMANCE SUMMARY")
    print("=" * 75)

    print(f"Pipeline initialization: {initialization_time:.2f} seconds")
    print(f"Retrieval and reranking: {retrieval_time:.2f} seconds")
    print(f"Context expansion: {context_expansion_time:.4f} seconds")
    print(f"Generation and verification: {generation_time:.2f} seconds")

    total_time = (
        initialization_time
        + retrieval_time
        + context_expansion_time
        + generation_time
    )

    print(f"Total execution time: {total_time:.2f} seconds")
    print("\nEnd-to-end evaluation completed.")


if __name__ == "__main__":
    main()
