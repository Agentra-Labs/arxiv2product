"""
Agno-compatible tools for the arxiv2product pipeline.

These tools wrap the existing search functionality in Agno's tool format,
allowing agents to perform web searches during pipeline execution.
"""

from typing import Optional

from agno.tools import tool

from .research import (
    SearchTrace,
    SearchIntent,
    routed_search,
    render_search_markdown,
)


# Track calls per tool instance
_call_counts: dict[int, int] = {}


def _get_max_calls_per_tool() -> int:
    """Get the maximum number of search calls allowed per tool."""
    import os
    default = 2
    raw_value = os.getenv("SEARCH_MAX_CALLS_PER_AGENT", str(default))
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(1, value)


def create_search_tool(
    default_intent: SearchIntent = "fast",
    trace: Optional[SearchTrace] = None,
):
    """
    Create an Agno-compatible web search tool.

    Args:
        default_intent: The default search intent ("fast" or "fresh")
        trace: Optional SearchTrace to record search results

    Returns:
        A tool function that can be used with Agno agents
    """
    tool_id = id(trace) if trace else id(default_intent)
    _call_counts[tool_id] = 0

    @tool
    async def web_search(query: str) -> str:
        """
        Search the web for information relevant to the query.

        Use this tool to find current market data, recent papers, industry trends,
        company information, pricing data, and other real-world evidence.

        Args:
            query: The search query string

        Returns:
            Search results formatted as markdown with titles, snippets, and URLs
        """
        if _call_counts[tool_id] >= _get_max_calls_per_tool():
            if trace is not None:
                trace.budget_exhausted = True
            return (
                "[web_search budget exhausted] Use the sources already gathered and "
                "only make stronger inferences from existing evidence."
            )

        _call_counts[tool_id] += 1
        if trace is not None:
            trace.calls_used += 1

        response = await routed_search(query, default_intent=default_intent)
        if trace is not None:
            trace.record(response)

        return render_search_markdown(response)

    return web_search


class WebSearchTool:
    """
    Class-based web search tool for Agno agents.

    This provides an alternative interface for tools that need to maintain
    state across multiple calls.
    """

    def __init__(
        self,
        default_intent: SearchIntent = "fast",
        trace: Optional[SearchTrace] = None,
    ):
        self.default_intent = default_intent
        self.trace = trace
        self._calls_used = 0
        self._max_calls = _get_max_calls_per_tool()

    @tool
    async def web_search(self, query: str) -> str:
        """
        Search the web for information relevant to the query.

        Use this tool to find current market data, recent papers, industry trends,
        company information, pricing data, and other real-world evidence.

        Args:
            query: The search query string

        Returns:
            Search results formatted as markdown with titles, snippets, and URLs
        """
        if self._calls_used >= self._max_calls:
            if self.trace is not None:
                self.trace.budget_exhausted = True
            return (
                "[web_search budget exhausted] Use the sources already gathered and "
                "only make stronger inferences from existing evidence."
            )

        self._calls_used += 1
        if self.trace is not None:
            self.trace.calls_used += 1

        response = await routed_search(query, default_intent=self.default_intent)
        if self.trace is not None:
            self.trace.record(response)

        return render_search_markdown(response)

    @property
    def calls_used(self) -> int:
        return self._calls_used


class DisabledWebSearchTool:
    """
    A disabled web search tool that returns a fixed message.

    Used when search is disabled but the agent still expects a web_search tool.
    """

    def __init__(self, message: Optional[str] = None):
        self.message = message or (
            "[web_search disabled] Use the existing pipeline evidence instead of live search."
        )

    @tool
    async def web_search(self, query: str) -> str:
        """
        Web search is currently disabled.

        Args:
            query: The search query (ignored)

        Returns:
            A message indicating search is disabled
        """
        return self.message
