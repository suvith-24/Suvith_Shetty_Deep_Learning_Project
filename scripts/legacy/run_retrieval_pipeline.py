
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


def main() -> None:
    query = (
        "What conditions must be satisfied when "
        "transferring personal data to a third country?"
    )

    print("\nLEXISYNCAI — REAL RETRIEVAL TEST")
    print("=" * 70)
    print(f"\nQuestion: {query}")

    # Load the persisted FAISS index and initialize
    # BM25, hybrid retrieval, and the cross-encoder.
    pipeline = RetrievalPipeline(
        candidate_k=20,
        top_k=5,
    )

    print("\nInitializing retrieval pipeline...")
    pipeline.initialize()

    print("Pipeline initialized successfully.")
    print(f"Indexed chunks: {len(pipeline.faiss_retriever.chunks)}")

    # Execute the complete retrieval workflow.
    print("\nSearching legal documents...")
    results = pipeline.search(query)

    if not results:
        print("\nNo relevant evidence was retrieved.")
        return

    print(f"\nRetrieved {len(results)} evidence chunks.")
    print("=" * 70)

    for rank, (chunk, score) in enumerate(results, start=1):
        print(f"\nRESULT {rank}")
        print("-" * 70)
        print(f"Document ID : {chunk.document_id}")
        print(f"Chunk ID    : {chunk.chunk_id}")
        print(f"Pages       : {chunk.page_numbers}")
        print(f"Section     : {chunk.section}")
        print(f"Subsection  : {chunk.subsection}")
        print(f"Rerank score: {score:.4f}")
        print("\nEvidence:")
        print(chunk.text)
        print("-" * 70)

    print("\nRetrieval test completed successfully.")


if __name__ == "__main__":
    main()
