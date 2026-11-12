
from lexisync.ingestion.pdf_loader import load_pdf
from lexisync.chunking.legal_chunker import chunk_document

from lexisync.retrieval.bm25_retriever import BM25Retriever
from lexisync.retrieval.faiss_retriever import FAISSRetriever
from lexisync.retrieval.hybrid_retriever import HybridRetriever
from lexisync.retrieval.cross_encoder_reranker import CrossEncoderReranker


PDF_PATH = "data/raw/gdpr.pdf"

QUERY = (
    "What conditions must be satisfied when transferring "
    "personal data to a third country?"
)


def main():

    print("\nSTEP 1: Loading GDPR document...")

    document = load_pdf(PDF_PATH)
    chunks = chunk_document(document)

    print(f"Document: {document.file_name}")
    print(f"Pages: {document.total_pages}")
    print(f"Chunks: {len(chunks)}")

    print("\nSTEP 2: Initializing BM25...")
    bm25 = BM25Retriever(chunks)

    print("\nSTEP 3: Initializing FAISS...")
    faiss_retriever = FAISSRetriever(chunks)

    print("\nSTEP 4: Initializing hybrid retrieval...")
    hybrid = HybridRetriever(
        bm25_retriever=bm25,
        faiss_retriever=faiss_retriever,
    )

    print("\nSTEP 5: Retrieving candidate passages...")

    candidates = hybrid.search(
        query=QUERY,
        top_k=20,
        candidate_k=20,
    )

    print(f"Hybrid candidates: {len(candidates)}")

    print("\nSTEP 6: Initializing cross-encoder...")
    reranker = CrossEncoderReranker()

    print("\nSTEP 7: Reranking candidates...")

    results = reranker.rerank(
        query=QUERY,
        candidates=candidates,
        top_k=5,
    )

    print("\n" + "=" * 80)
    print("FINAL TOP 5 RESULTS")
    print("=" * 80)

    for rank, (chunk, score) in enumerate(results, start=1):

        print(f"\nRank: {rank}")
        print(f"Cross-encoder score: {score:.4f}")
        print(f"Chunk ID: {chunk.chunk_id}")
        print(f"Page: {chunk.page_numbers}")
        print(f"Section: {chunk.section}")
        print("-" * 60)
        print(chunk.text[:700])
        print("-" * 60)


if __name__ == "__main__":
    main()
