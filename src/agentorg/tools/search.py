"""Web search tool for agents — uses Tavily API with DuckDuckGo fallback."""

from __future__ import annotations

import os
from typing import Any
import urllib.parse

import httpx
try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"

# Module-level flag so we stop retrying Tavily after a quota error this session
_TAVILY_QUOTA_EXCEEDED = False


def _duckduckgo_search(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Fallback search via DuckDuckGo Instant Answer API (no API key required)."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

        results: list[dict[str, Any]] = []

        # AbstractText (main answer)
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "url": data.get("AbstractURL", ""),
                "content": data["AbstractText"],
                "score": 0.9,
            })

        # RelatedTopics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "url": topic.get("FirstURL", ""),
                    "content": topic.get("Text", ""),
                    "score": 0.6,
                })

        logger.info(f"[search] DuckDuckGo fallback '{query}' → {len(results)} results")
        return results[:max_results]
    except Exception as e:
        logger.warning(f"[search] DuckDuckGo fallback failed: {e}")
        return []


def web_search(query: str, max_results: int = 8, search_depth: str = "advanced") -> list[dict[str, Any]]:
    """
    Search the web using Tavily, falling back to DuckDuckGo if quota is exceeded.

    Args:
        query: The search query
        max_results: Number of results to return (max 10)
        search_depth: "basic" (faster) or "advanced" (more thorough)

    Returns:
        List of result dicts with keys: title, url, content, score
    """
    global _TAVILY_QUOTA_EXCEEDED

    if not TAVILY_API_KEY:
        logger.warning("[search] TAVILY_API_KEY not set — falling back to DuckDuckGo.")
        return _duckduckgo_search(query, max_results)

    if not _TAVILY_QUOTA_EXCEEDED:
        try:
            response = httpx.post(
                TAVILY_URL,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_answer": True,
                    "include_raw_content": True,
                },
                timeout=30.0,
            )
            if response.status_code == 432:
                logger.warning("[search] Tavily quota exceeded (HTTP 432) — switching to DuckDuckGo for this session.")
                _TAVILY_QUOTA_EXCEEDED = True
            else:
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                logger.info(f"[search] Tavily '{query}' → {len(results)} results")
                return list(results)
        except httpx.HTTPStatusError:
            pass  # fall through to DuckDuckGo
        except httpx.HTTPError as e:
            logger.error(f"[search] Tavily HTTP error: {e}")
        except Exception as e:
            logger.error(f"[search] Tavily unexpected error: {e}")

    # Tavily failed or quota exceeded — use DuckDuckGo
    ddg_results = _duckduckgo_search(query, max_results)
    if ddg_results:
        return ddg_results

    logger.warning(f"[search] All search backends failed for '{query}'")
    return []


def fetch_url(url: str, max_chars: int = 12000) -> str:
    """
    Fetch the full text content of a URL using Jina Reader (r.jina.ai).

    Jina converts any webpage to clean markdown — no API key required.
    Use this after web_search to read full articles instead of just snippets.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 12000 ≈ ~3000 tokens)

    Returns:
        Full article text as markdown, or an error message.
    """
    if not url or not url.startswith("http"):
        return f"Invalid URL: {url}"
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = httpx.get(
            jina_url,
            headers={"Accept": "text/plain", "X-Return-Format": "markdown"},
            timeout=30.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        content = resp.text.strip()
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[... content truncated at {max_chars} chars ...]"
        logger.info(f"[search] fetch_url '{url}' → {len(content)} chars")
        return content
    except Exception as e:
        logger.warning(f"[search] fetch_url failed for '{url}': {e}")
        return f"Could not fetch content from {url}: {e}"


def format_search_results(results: list[dict[str, Any]]) -> str:
    """Format search results into a readable string for inclusion in agent prompts."""
    if not results:
        return "_No search results available._"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"**[{i}] {r.get('title', 'No title')}**")
        lines.append(f"Source: {r.get('url', 'Unknown')}")
        body = (r.get("raw_content") or r.get("content") or "").strip()
        if len(body) > 3000:
            body = body[:3000] + "\n[... truncated raw content ...]"
        lines.append(body)
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

FETCH_URL_TOOL_DEFINITION: dict[str, Any] = {
    "name": "fetch_url",
    "description": (
        "Fetch the full text content of a URL as clean markdown via Jina Reader. "
        "Use this after search to read full articles, Substack posts, papers, reports, and official documents."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "A fully-qualified http(s) URL to fetch.",
            },
        },
        "required": ["url"],
    },
}
