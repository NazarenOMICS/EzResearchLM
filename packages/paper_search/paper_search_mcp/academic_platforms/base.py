"""Base class for all academic paper source searchers."""
from abc import ABC, abstractmethod
from typing import List
from ..paper import Paper


class PaperSource(ABC):
    """Abstract base class for academic paper sources."""

    @abstractmethod
    def search(self, query: str, **kwargs) -> List[Paper]:
        """Search papers matching the query.

        Args:
            query: Search query string.
            **kwargs: Source-specific parameters (e.g., max_results, year).

        Returns:
            List of Paper objects.
        """

