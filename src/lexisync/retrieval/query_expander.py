
from abc import ABC, abstractmethod


class QueryExpansionStrategy(ABC):
    """Interface for generating complementary retrieval queries."""

    @abstractmethod
    def expand(self, query: str) -> list[str]:
        """Return complementary queries for the original question."""
        raise NotImplementedError


class NoOpQueryExpander(QueryExpansionStrategy):
    """Preserve single-query retrieval without expansion."""

    def expand(self, query: str) -> list[str]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        return []


class StaticQueryExpander(QueryExpansionStrategy):
    """
    Deterministic query expander using an injected expansion function.

    The function receives the original query and returns additional
    search queries. This keeps expansion independent of any LLM.
    """

    def __init__(self, expansion_function):
        if not callable(expansion_function):
            raise TypeError("expansion_function must be callable.")

        self.expansion_function = expansion_function

    def expand(self, query: str) -> list[str]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        expanded_queries = self.expansion_function(query.strip())

        if not isinstance(expanded_queries, list):
            raise TypeError("Expansion function must return a list.")

        results = []
        seen = {query.strip().casefold()}

        for item in expanded_queries:
            if not isinstance(item, str):
                continue

            normalized = item.strip()

            if not normalized:
                continue

            key = normalized.casefold()

            if key not in seen:
                seen.add(key)
                results.append(normalized)

        return results
