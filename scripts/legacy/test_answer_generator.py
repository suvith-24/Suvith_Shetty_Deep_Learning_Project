
from lexisync.generation.answer_generator import AnswerGenerator
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


def main() -> None:
    query = (
        "What conditions must be satisfied when transferring "
        "personal data to a third country?"
    )

    print("\nLEXISYNCAI — EVIDENCE-GROUNDED ANSWER TEST")
    print("=" * 70)

    # Step 1: Initialize retrieval.
    print("\n[1/3] Initializing retrieval pipeline...")

    retrieval_pipeline = RetrievalPipeline(
        candidate_k=20,
        top_k=5,
    )

    retrieval_pipeline.initialize()

    print("Retrieval pipeline initialized.")

    # Step 2: Retrieve legal evidence.
    print("\n[2/3] Retrieving relevant legal evidence...")

    evidence = retrieval_pipeline.search(query)

    print(f"Retrieved {len(evidence)} evidence chunks.")

    if not evidence:
        print("No evidence found. Cannot generate an answer.")
        return

    # Step 3: Generate an answer using Ollama.
    print("\n[3/3] Generating evidence-grounded answer...")

    answer_generator = AnswerGenerator()

    result = answer_generator.generate_answer(
        query=query,
        evidence=evidence,
    )

    print("\n" + "=" * 70)
    print("LEXISYNCAI — GENERATED ANSWER")
    print("=" * 70)

    print("\nQUESTION:")
    print(query)

    print("\nANSWER:")
    print(result["answer"])

    print("\nSOURCES:")
    for source in result["sources"]:
        print(
            f"\n[{source['source_id']}] "
            f"Document: {source['document_id']}"
        )
        print(f"    Section: {source['section']}")
        print(f"    Pages: {source['pages']}")
        print(f"    Chunk ID: {source['chunk_id']}")

    print("\nABSTAINED:", result["abstained"])

    print("\n" + "=" * 70)
    print("ANSWER GENERATION TEST COMPLETED.")
    print("=" * 70)


if __name__ == "__main__":
    main()
