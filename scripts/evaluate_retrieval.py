
import time

from lexisync.retrieval.query_expander import StaticQueryExpander
from lexisync.retrieval.retrieval_pipeline import RetrievalPipeline


QUESTION = (
    "What conditions must be satisfied when "
    "transferring personal data to a third country?"
)

EXPANDED_QUERY = (
    QUESTION
    + " appropriate safeguards enforceable data subject rights "
    "effective legal remedies adequacy decision"
)


def is_article_46(chunk) -> bool:
    """Identify chunks belonging to GDPR Article 46."""

    section = (chunk.section or "").casefold()
    subsection = (chunk.subsection or "").casefold()

    return (
        "article 46" in section
        or "article 46" in subsection
    )


def run_benchmark(pipeline, label):
    """Execute retrieval and measure its latency."""

    print("\n" + "=" * 85)
    print(label)
    print("=" * 85)

    start = time.perf_counter()
    results = pipeline.search(QUESTION)
    elapsed = time.perf_counter() - start

    article_46_ranks = []

    print(f"Results returned: {len(results)}")
    print(f"Retrieval time: {elapsed:.3f} seconds")

    for rank, (chunk, score) in enumerate(results, start=1):

        article_46 = is_article_46(chunk)

        if article_46:
            article_46_ranks.append(rank)

        marker = " <-- ARTICLE 46" if article_46 else ""

        print(
            f"\n[{rank}] "
            f"{chunk.section or 'Unknown section'} | "
            f"{chunk.subsection or 'Unknown subsection'}"
            f"{marker}"
        )

        print(f"    Chunk ID: {chunk.chunk_id}")
        print(f"    Pages: {chunk.page_numbers}")
        print(f"    Reranker score: {score:.4f}")

    top_5 = any(rank <= 5 for rank in article_46_ranks)

    print("\nArticle 46 evaluation:")

    if article_46_ranks:
        print(f"Article 46 ranks: {article_46_ranks}")
    else:
        print("Article 46 not found in returned results.")

    print(f"Article 46 in top 5: {top_5}")

    return {
        "label": label,
        "article_46_ranks": article_46_ranks,
        "top_5": top_5,
        "latency": elapsed,
    }


def main():

    print("\nLEXSYNC AI - WEIGHTED RRF BENCHMARK")
    print("=" * 85)
    print(f"\nQuestion: {QUESTION}")

    print("\n[1/4] Initializing retrieval pipeline...")

    initialization_start = time.perf_counter()

    pipeline = RetrievalPipeline(
        candidate_k=20,
        top_k=10,
        original_query_weight=1.0,
        expanded_query_weight=1.0,
    )

    pipeline.initialize()

    initialization_time = (
        time.perf_counter() - initialization_start
    )

    print("Pipeline initialized successfully.")
    print(f"Indexed chunks: {len(pipeline.faiss_retriever.chunks)}")
    print(f"Initialization time: {initialization_time:.3f} seconds")

    results = []

    # Experiment 1: Original query only.
    print("\n[2/4] Running baseline retrieval...")

    results.append(
        run_benchmark(
            pipeline,
            "EXPERIMENT 1: BASELINE - ORIGINAL QUERY",
        )
    )

    # Configure multi-query expansion.
    pipeline.query_expander = StaticQueryExpander(
        lambda query: [EXPANDED_QUERY]
    )

    # Experiment 2: Equal-weight multi-query.
    print("\n[3/4] Running equal-weight multi-query retrieval...")

    pipeline.original_query_weight = 1.0
    pipeline.expanded_query_weight = 1.0

    results.append(
        run_benchmark(
            pipeline,
            "EXPERIMENT 2: EQUAL-WEIGHT MULTI-QUERY (1.0 / 1.0)",
        )
    )

    # Experiment 3: Weighted multi-query.
    print("\n[4/4] Running weighted multi-query retrieval...")

    pipeline.original_query_weight = 1.0
    pipeline.expanded_query_weight = 1.5

    results.append(
        run_benchmark(
            pipeline,
            "EXPERIMENT 3: WEIGHTED MULTI-QUERY (1.0 / 1.5)",
        )
    )

    # Final comparison.
    print("\n" + "=" * 85)
    print("FINAL BENCHMARK COMPARISON")
    print("=" * 85)

    print(
        f"{'Configuration':<48}"
        f"{'Article 46':<15}"
        f"{'Top 5':<10}"
        f"{'Time (s)':<10}"
    )

    print("-" * 85)

    for result in results:

        rank = (
            str(result["article_46_ranks"])
            if result["article_46_ranks"]
            else "Not found"
        )

        print(
            f"{result['label']:<48}"
            f"{rank:<15}"
            f"{str(result['top_5']):<10}"
            f"{result['latency']:<10.3f}"
        )

    print("\nBenchmark completed.")


if __name__ == "__main__":
    main()
