"""Web search tool for agents — uses Tavily API (built for AI agents)."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"


def web_search(query: str, max_results: int = 8, search_depth: str = "advanced") -> list[dict[str, Any]]:
    """
    Search the web using Tavily and return structured results.

    Args:
        query: The search query
        max_results: Number of results to return (max 10)
        search_depth: "basic" (faster) or "advanced" (more thorough)

    Returns:
        List of result dicts with keys: title, url, content, score
    """
    if not TAVILY_API_KEY:
        logger.warning("[search] TAVILY_API_KEY not set — web search disabled.")
        return [{"title": "Web search unavailable", "url": "", "content": "TAVILY_API_KEY is not configured.", "score": 0}]

    try:
        response = httpx.post(
            TAVILY_URL,
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        logger.info(f"[search] '{query}' → {len(results)} results")
        return list(results)

    except httpx.HTTPError as e:
        logger.error(f"[search] HTTP error: {e}")
        return []
    except Exception as e:
        logger.error(f"[search] Unexpected error: {e}")
        return []


def format_search_results(results: list[dict[str, Any]]) -> str:
    """Format search results into a readable string for inclusion in agent prompts."""
    if not results:
        return "_No search results available._"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"**[{i}] {r.get('title', 'No title')}**")
        lines.append(f"Source: {r.get('url', 'Unknown')}")
        lines.append(r.get('content', '').strip())
        lines.append("")

    return "\n".join(lines)


# Claude tool definition — passed to the Anthropic API for tool use
SEARCH_TOOL_DEFINITION: dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for current information on a topic. "
        "Use this to find recent news, current data, and up-to-date developments "
        "that may have occurred after your training cutoff. "
        "Always search for multiple angles on complex geopolitical or financial topics."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific. Use quotes for exact phrases.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return. Default 8, max 10.",
                "default": 8,
            },
        },
        "required": ["query"],
    },
}
