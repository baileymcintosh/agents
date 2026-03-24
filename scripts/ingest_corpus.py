#!/usr/bin/env python3
"""
Research Corpus Ingester

Downloads and archives public research articles from major investment firm
insights pages. Stores markdown text AND embedded chart images together in
corpus/<firm>/<article_slug>/ so writers and quant devs can use both.

Usage:
    python scripts/ingest_corpus.py                        # ingest all firms
    python scripts/ingest_corpus.py --firm oaktree         # one firm only
    python scripts/ingest_corpus.py --firm kkr --max 50    # cap articles
    python scripts/ingest_corpus.py --list                 # show registered firms
    python scripts/ingest_corpus.py --refresh              # re-download everything

Output per article:
    corpus/kkr/2024-01_regime_change_private_equity_abc123/
        article.md       <- full text (cleaned, boilerplate stripped) + YAML frontmatter
        img_01.png       <- charts / figures extracted from the article
        img_02.png
        ...
    corpus/index.json    <- full metadata manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional runtime dependency
    BeautifulSoup = None  # type: ignore[assignment]

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - optional runtime dependency
    curl_requests = None  # type: ignore[assignment]

# ── Firm registry ─────────────────────────────────────────────────────────────
FIRMS: dict[str, dict] = {
    "kkr": {
        "name": "KKR",
        "insights_url": "https://www.kkr.com/insights",
        "discovery": "sitemap",
        "sitemap_url": "https://www.kkr.com/sitemap.xml",
        # Exclude press releases, awards, portfolio company announcements
        "article_pattern": r"kkr\.com/insights/[a-z0-9\-]+$",
        "skip_pattern": r"(award|press-release|portfolio|hiring|appoint|partner|ceo-letter|deal-close)",
        "type": "private_equity",
    },
    "apollo": {
        "name": "Apollo Global Management",
        "insights_url": "https://www.apollo.com/insights-news/insights",
        "discovery": "sitemap",
        "sitemap_url": "https://www.apollo.com/sitemap.xml",
        # Exclude short 'Overheard' news blurbs — target substantive dated research
        "article_pattern": r"apollo\.com/insights-news/insights/\d{4}/\d{2}/[a-z0-9\-]+$",
        "skip_pattern": r"overheard-at-apollo",
        "type": "private_equity",
        # Apollo embeds PDF download links in raw HTML
        "pdf_in_html": True,
        "pdf_html_pattern": r"/content/dam/apolloaem/[^\s\"'<>]+\.pdf",
        "pdf_base_url": "https://www.apollo.com",
    },
    "blackstone": {
        "name": "Blackstone",
        "insights_url": "https://www.blackstone.com/insights/",
        "discovery": "sitemap",
        "sitemap_url": "https://www.blackstone.com/sitemap_index.xml",
        "article_pattern": r"blackstone\.com/insights/article/.+",
        "type": "private_equity",
    },
    "citadel_securities": {
        "name": "Citadel Securities",
        "insights_url": "https://www.citadelsecurities.com/news-and-insights/category/market-insights/",
        "discovery": "citadel_paginated",
        "page_url_template": "https://www.citadelsecurities.com/news-and-insights/category/market-insights/page/{page}/",
        "max_pages": 22,
        "article_pattern": r"citadelsecurities\.com/news-and-insights/(?!category|in-the-media|policy)[a-z0-9\-]+/?$",
        "type": "market_maker",
    },
    "oaktree": {
        "name": "Oaktree Capital Management",
        "insights_url": "https://www.oaktreecapital.com/insights/memos",
        "discovery": "oaktree_memos",
        "article_pattern": r"oaktreecapital\.com/(insights/memo/.+|docs/default-source/memos/.+\.pdf)",
        "type": "private_credit",
    },
    "bridgewater": {
        "name": "Bridgewater Associates",
        "insights_url": "https://www.bridgewater.com/research-and-insights",
        "discovery": "jina_links",
        "article_pattern": r"bridgewater\.com/research-and-insights/.+",
        "type": "macro_hedge_fund",
    },
    "carlyle": {
        "name": "The Carlyle Group",
        "insights_url": "https://www.carlyle.com/global-insights",
        "discovery": "jina_links",
        "article_pattern": r"carlyle\.com/global-insights/[a-z0-9\-]+$",
        "type": "private_equity",
    },
    "ares": {
        "name": "Ares Management",
        "insights_url": "https://www.aresmgmt.com/news-views/perspectives",
        "discovery": "jina_links",
        "article_pattern": r"aresmgmt\.com/news-views/(perspectives|white-papers)/.+",
        "type": "private_credit",
    },
    "blue_owl": {
        "name": "Blue Owl Capital",
        "insights_url": "https://www.blueowl.com/insights",
        "discovery": "jina_links",
        "article_pattern": r"blueowl\.com/insights/[a-z0-9\-]+$",
        "type": "private_credit",
    },
    "aqr": {
        "name": "AQR Capital Management",
        "insights_url": "https://www.aqr.com/Insights/Research",
        "discovery": "jina_links",
        "article_pattern": r"aqr\.com/Insights/(Research|Perspectives|Blog)/.+",
        "type": "quant_hedge_fund",
    },
    "man_group": {
        "name": "Man Group",
        "insights_url": "https://www.man.com/insights",
        "discovery": "jina_links",
        "article_pattern": r"man\.com/insights/[a-z0-9\-]+$",
        "type": "quant_hedge_fund",
    },
    "neuberger": {
        "name": "Neuberger Berman",
        "insights_url": "https://www.nb.com/en/global/insights",
        "discovery": "jina_links",
        "article_pattern": r"nb\.com/en/.*/insights/.+",
        "type": "asset_manager",
    },
    "two_sigma": {
        "name": "Two Sigma",
        "insights_url": "https://www.twosigma.com/insights/",
        "discovery": "jina_links",
        "article_pattern": r"twosigma\.com/(insights|articles)/[a-z0-9\-]+$",
        "type": "quant_hedge_fund",
    },
}

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
INDEX_PATH = CORPUS_DIR / "index.json"
JINA_BASE = "https://r.jina.ai/"
REQUEST_DELAY = 1.5
TIMEOUT = 30.0
MIN_IMAGE_BYTES = 20_000
JINA_RETRIES = 5

# Keywords that mark the start of boilerplate to strip at the end of articles
_FOOTER_MARKERS = [
    "important information", "important notice", "important disclosures",
    "legal disclaimer", "disclaimer", "this material does not constitute",
    "this document is for informational purposes only",
    "educational purposes only", "for illustrative purposes only",
    "important disclosure information",
    "past performance is not", "not investment advice",
    "risk factors", "forward-looking statements",
    "footnotes\n", "endnotes\n",
    "about kkr\n", "about apollo\n", "about blackstone\n",
    "about oaktree\n", "about carlyle\n", "about ares\n",
    "about bridgewater\n",
    "related insights", "related articles", "explore more",
    "recommended for you", "you may also like", "more from",
    "subscribe to", "sign up for",
    "tags\n", "tags",
    "social",
    "explore apollo", "more information", "governance",
    "apollo in the media", "life at apollo",
    "copyright ©", "all rights reserved",
    "© oaktree capital management", "© 20",
    "legal entities disseminating",
]

# Nav/boilerplate signals — blocks containing these are likely navigation
_NAV_SIGNALS = [
    "cookie policy", "manage preferences", "privacy policy",
    "general public", "institutional investors", "wealth professionals",
    "select your experience", "login\n",
    "careers\n", "contact us\n",
]

_PROSE_EXCLUDE = [
    "cookie", "privacy policy", "terms of use", "terms of service",
    "all rights reserved", "personalize your experience",
    "analytics tools", "we use cookies",
    "by continuing", "please review our",
    "manage preferences", "consent",
]

_MIN_SUBSTANTIVE_CHARS = 500
DEFAULT_REVIEW_MODEL = os.getenv("CORPUS_REVIEW_MODEL", "gpt-4o-mini")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, retries: int = 1, retry_delay: float = 1.0, **kwargs) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, **kwargs)
            if r.status_code == 429 and attempt < retries - 1:
                delay = retry_delay * (2 ** attempt)
                print(f"  [warn] 429 for {url[:80]} - retrying in {delay:.1f}s", file=sys.stderr)
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt < retries - 1:
                delay = retry_delay * (2 ** attempt)
                print(f"  [warn] GET retry {attempt + 1}/{retries} {url[:80]}: {e}", file=sys.stderr)
                time.sleep(delay)
                continue
            print(f"  [warn] GET {url[:80]}: {e}", file=sys.stderr)
            return None
    return None


def _browser_get(url: str, retries: int = 2):
    if curl_requests is None:
        return None
    for attempt in range(retries):
        try:
            resp = curl_requests.get(url, impersonate="chrome", timeout=TIMEOUT)
            if resp.status_code == 429 and attempt < retries - 1:
                delay = 2.0 * (2 ** attempt)
                print(f"  [warn] browser 429 for {url[:80]} - retrying in {delay:.1f}s", file=sys.stderr)
                time.sleep(delay)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}")
            return resp
        except Exception as e:
            if attempt < retries - 1:
                delay = 2.0 * (2 ** attempt)
                print(f"  [warn] browser retry {attempt + 1}/{retries} {url[:80]}: {e}", file=sys.stderr)
                time.sleep(delay)
                continue
            print(f"  [warn] browser GET {url[:80]}: {e}", file=sys.stderr)
            return None
    return None


def _fetch_browser_html(url: str) -> str:
    resp = _browser_get(url)
    if not resp:
        return ""
    content_type = str(resp.headers.get("content-type", ""))
    if "html" not in content_type.lower():
        return ""
    return resp.text


def _fetch_via_jina(url: str, max_chars: int = 50000) -> str:
    jina_url = f"{JINA_BASE}{url}"
    r = _get(
        jina_url,
        retries=JINA_RETRIES,
        retry_delay=2.0,
        headers={"Accept": "text/plain", "X-Return-Format": "markdown"},
    )
    if not r:
        return ""
    content = r.text.strip()
    return content[:max_chars] if len(content) > max_chars else content


def _fetch_pdf_text(url: str) -> str:
    try:
        import io
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                return _fetch_via_jina(url)
        r = _get(url)
        if not r:
            return ""
        reader = PdfReader(io.BytesIO(r.content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())[:50000]
    except Exception as e:
        print(f"  [warn] PDF text extraction failed {url[:60]}: {e}", file=sys.stderr)
        return ""


def _find_pdf_in_html(html: str, pattern: str, base_url: str) -> str | None:
    """Find a PDF download link in raw HTML using a firm-specific pattern."""
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        path = matches[0]
        if path.startswith("http"):
            return path
        return base_url.rstrip("/") + "/" + path.lstrip("/")
    return None


def _find_pdf_link(text: str, base_url: str) -> str | None:
    match = re.search(r"(https?://[^\s\"'()<>]+\.pdf|/[^\s\"'()<>]+\.pdf)", text, re.IGNORECASE)
    if not match:
        return None
    pdf_url = match.group(1)
    if pdf_url.startswith("http"):
        return pdf_url
    return urljoin(base_url, pdf_url)


def _title_from_pdf_url(url: str) -> str:
    filename = Path(urlparse(url).path).stem
    filename = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename)
    filename = filename.replace("-", " ").replace("_", " ").strip()
    return _clean_text(filename.title()) if filename else ""


def _extract_pdf_header_title(text: str) -> str:
    head = text[:3000]
    patterns = [
        r"\bRe:\s+([^\n\r]{3,120})",
        r"\bTitle:\s+([^\n\r]{3,120})",
    ]
    for pattern in patterns:
        match = re.search(pattern, head, re.IGNORECASE)
        if match:
            candidate = _clean_text(match.group(1))
            if 3 <= len(candidate) <= 120:
                return candidate
    return ""


def _contains_boilerplate_marker(text: str) -> bool:
    lower = text.strip().lower()
    return any(marker in lower for marker in _FOOTER_MARKERS) or any(
        marker in lower for marker in _NAV_SIGNALS
    )


def _is_substantive_line(line: str) -> bool:
    s = line.strip()
    lower = s.lower()
    if not s:
        return False
    if any(kw in lower for kw in _PROSE_EXCLUDE):
        return False
    if _contains_boilerplate_marker(s):
        return False
    if s.startswith("[!["):
        return False
    if s.startswith("!"):
        return False
    if "source:" in lower or lower.startswith("exhibit "):
        return False
    month_hits = len(re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", lower))
    digit_ratio = sum(ch.isdigit() for ch in s) / max(len(s), 1)
    if len(s) < 180 and month_hits >= 2 and digit_ratio > 0.01:
        return False
    if len(s) < 200 and s.startswith(("[", "*", "-", "|")) and "](" in s:
        return False
    if len(s) < 250 and s.count("](") >= 2:
        return False
    if re.fullmatch(r"#{1,6}", s):
        return False
    return True


def _substantive_char_count(text: str) -> int:
    total = 0
    for line in text.splitlines():
        if not _is_substantive_line(line):
            continue
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line).strip(" #>*`")
        if cleaned:
            total += len(cleaned)
    return total


def _cut_footer_lines(lines: list[str]) -> list[str]:
    substantive_seen = False
    total = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") or _is_substantive_line(line):
            substantive_seen = True
        if _contains_boilerplate_marker(line):
            if not substantive_seen:
                continue
            # PDFs like Oaktree memos repeat copyright/footer lines on every page.
            # Only treat a boilerplate marker as the true document footer when it
            # appears late in the text; otherwise drop it during line cleanup.
            if i < max(20, int(total * 0.7)):
                tail = [candidate.strip() for candidate in lines[i + 1 : i + 6] if candidate.strip()]
                if tail and all(len(candidate) < 80 for candidate in tail):
                    return lines[:i]
                continue
            return lines[:i]
    return lines


def _drop_leading_boilerplate(lines: list[str]) -> list[str]:
    first_h1_idx = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("# ")),
        -1,
    )
    content_seen = False
    for i, line in enumerate(lines[: min(len(lines), 20)]):
        stripped = line.strip()
        if stripped.startswith("# ") or _is_substantive_line(line):
            content_seen = True
        if _contains_boilerplate_marker(line):
            if content_seen:
                break
            if first_h1_idx != -1 and first_h1_idx > i:
                return lines[first_h1_idx:]
            return lines[i + 1 :]
    return lines


def _finalize_content(content: str) -> str:
    lines = _drop_leading_boilerplate(content.splitlines())
    lines = _cut_footer_lines(lines)
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if _contains_boilerplate_marker(stripped):
            continue
        if lower == "share on":
            continue
        if stripped.startswith("*") and "share on " in lower:
            continue
        if lower.startswith(("memo to:", "from:", "re:", "follow us:")):
            continue
        if re.fullmatch(r"[A-Z]|\d+", stripped):
            continue
        exhibit_match = re.match(r"(.{80,}?)(?:\s+Exhibit\s+\d+:.*)$", stripped)
        if exhibit_match:
            stripped = exhibit_match.group(1).strip()
        source_match = re.match(r"(.{80,}?)(?:\s+Source:.*)$", stripped)
        if source_match:
            stripped = source_match.group(1).strip()
        cleaned_lines.append(stripped if stripped else "")
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    cleaned = "\n".join(cleaned_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _has_minimum_substance(content: str, min_chars: int = _MIN_SUBSTANTIVE_CHARS) -> bool:
    return _substantive_char_count(content) >= min_chars


def _merge_wrapped_lines(text: str) -> str:
    # Some PDFs extract decorative drop caps as standalone lines:
    #   I\nn May ...   T\nhis Time ...
    # Repair those before any other line-merging heuristics.
    while True:
        repaired = re.sub(r"(?m)^([A-Za-z])\s*\n([a-z])", r"\1\2", text)
        if repaired == text:
            break
        text = repaired

    lines = text.splitlines()
    nonblank = [line.strip() for line in lines if line.strip()]
    if not nonblank:
        return text
    heading_count = sum(1 for line in nonblank if line.startswith("#"))
    short_ratio = sum(1 for line in nonblank if len(line) < 90) / len(nonblank)
    if heading_count > 3 or short_ratio < 0.6:
        return text

    merged: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            merged.append(" ".join(buffer))
            buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush()
            merged.append("")
            continue
        if line.startswith(("#", "*", "-", "!", "[", ">")):
            flush()
            merged.append(line)
            continue
        if re.fullmatch(r"[A-Z0-9\s:,&.'()/-]{8,}", line):
            flush()
            merged.append(line)
            continue
        if len(line) <= 40 and re.fullmatch(r"[A-Za-z][A-Za-z0-9 &:/-]{0,39}", line):
            flush()
            merged.append(line)
            continue
        buffer.append(line)

    flush()
    return "\n".join(merged)


def _numbered_text(text: str) -> str:
    return "\n".join(f"{idx + 1:04d}: {line}" for idx, line in enumerate(text.splitlines()))


def _apply_keep_ranges(text: str, keep_ranges: list[list[int]]) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    kept: list[str] = []
    last_end = 0
    for start, end in sorted(keep_ranges):
        start = max(1, start)
        end = min(len(lines), end)
        if end < start:
            continue
        if kept and start > last_end + 1:
            kept.append("")
        kept.extend(lines[start - 1:end])
        last_end = end
    return "\n".join(kept).strip()


@dataclass
class LinkReview:
    include: bool
    content_type: str
    canonical_title: str
    reason: str


@dataclass
class ArticleReview:
    approve: bool
    content_type: str
    clean_title: str
    keep_ranges: list[list[int]]
    reason: str


class CorpusReviewAgent:
    def __init__(self, model: str = DEFAULT_REVIEW_MODEL) -> None:
        import openai

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for agent-reviewed corpus ingestion.")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def review_link(self, firm_key: str, firm_cfg: dict, title: str, url: str, preview: str = "") -> LinkReview:
        system_prompt = (
            "You are screening candidate links from an investment firm's research/insights page. "
            "Your job is to decide whether the link is a substantive written research item worth archiving. "
            "Approve substantive written research only: reports, white papers, memos, research articles, "
            "market commentary, long-form analysis. Reject podcasts, videos, media appearances, event pages, "
            "teasers, landing pages, nav pages, hiring pages, press releases, and thin promotional posts. "
            "Use common sense like a human curator."
        )
        payload = self._complete_json(
            system_prompt,
            (
                f"Firm: {firm_cfg['name']} ({firm_key})\n"
                f"URL: {url}\n"
                f"Candidate title: {title}\n"
                "Preview text follows. It may be empty if preview fetch was skipped to avoid rate limits.\n\n"
                f"{preview[:6000]}\n\n"
                "Return JSON with keys: decision (include/reject), content_type, canonical_title, reason."
            ),
        )
        decision = str(payload.get("decision", "reject")).lower()
        content_type = str(payload.get("content_type", "other")).lower()
        canonical_title = str(payload.get("canonical_title", title)).strip() or title
        reason = str(payload.get("reason", "")).strip()
        include = decision == "include" and content_type not in {"podcast", "video", "audio", "teaser", "landing_page", "press_release", "navigation", "other"}
        return LinkReview(include=include, content_type=content_type, canonical_title=canonical_title, reason=reason)

    def review_article(self, firm_key: str, firm_cfg: dict, title: str, url: str, content: str) -> ArticleReview:
        numbered = _numbered_text(content)
        system_prompt = (
            "You are reviewing scraped content from an investment firm's research page. "
            "Keep only the actual written report/article body. Remove social share blocks, tags, related links, "
            "recommendation cards, podcast/video embeds, repeated headers/footers, cover-page legal boilerplate, "
            "table of contents noise, and generic site chrome. "
            "Approve only substantive written research. Reject podcasts, videos, transcripts, teaser pages, "
            "landing pages, and thin items. "
            "Return line ranges from the provided numbered text that should be kept."
        )
        payload = self._complete_json(
            system_prompt,
            (
                f"Firm: {firm_cfg['name']} ({firm_key})\n"
                f"URL: {url}\n"
                f"Current title: {title}\n\n"
                "Numbered content:\n"
                f"{numbered[:90000]}\n\n"
                "Return JSON with keys: decision (approve/reject), content_type, clean_title, "
                "keep_ranges (array of [start,end]), reason."
            ),
        )
        decision = str(payload.get("decision", "reject")).lower()
        content_type = str(payload.get("content_type", "other")).lower()
        clean_title = str(payload.get("clean_title", title)).strip() or title
        keep_ranges = payload.get("keep_ranges", [])
        if not isinstance(keep_ranges, list):
            keep_ranges = []
        normalized_ranges: list[list[int]] = []
        for item in keep_ranges:
            if isinstance(item, list) and len(item) == 2:
                try:
                    normalized_ranges.append([int(item[0]), int(item[1])])
                except Exception:
                    continue
        reason = str(payload.get("reason", "")).strip()
        approve = decision == "approve" and content_type not in {"podcast", "video", "audio", "transcript", "teaser", "landing_page", "press_release", "navigation", "other"}
        return ArticleReview(
            approve=approve,
            content_type=content_type,
            clean_title=clean_title,
            keep_ranges=normalized_ranges,
            reason=reason,
        )


# ── Boilerplate stripping ─────────────────────────────────────────────────────

def _strip_boilerplate(text: str) -> str:
    """
    Remove nav headers, cookie banners, login sections, and footer boilerplate
    from Jina-rendered markdown. Keeps the article title and body only.

    Algorithm:
    1. Find first real prose paragraph: >200 chars, not a link/list/image line.
    2. Walk back from there (up to 40 lines) to find the nearest H1/H2 heading.
    3. Start content from that heading (or from the prose paragraph if no heading).
    4. Cut at first footer marker.
    5. Collapse excess blank lines.
    """
    return _extract_article_body(text)

    lines = _drop_leading_boilerplate(text.splitlines())

    def _is_prose(line: str) -> bool:
        s = line.strip()
        if not _is_substantive_line(s):
            return False
        if s.startswith("#"):
            return False
        return True

    # ── Phase 1: find the first real prose paragraph ─────────────────────────
    prose_idx = -1
    for i, line in enumerate(lines):
        if len(line.strip()) > 200 and _is_prose(line):
            prose_idx = i
            break

    # Fallback: lower threshold (>120 chars)
    if prose_idx == -1:
        for i, line in enumerate(lines):
            if len(line.strip()) > 120 and _is_prose(line):
                prose_idx = i
                break

    if prose_idx == -1:
        # Can't find prose — return whole text stripped of nav signals
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# ") and len(stripped) > 5:
                return _finalize_content("\n".join(lines[i:]))
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("## ") and len(stripped) > 5:
                return _finalize_content("\n".join(lines[i:]))
        return _finalize_content("\n".join(lines))

    # ── Phase 2: walk back to find nearest heading ────────────────────────────
    start_idx = prose_idx
    for i in range(prose_idx - 1, max(-1, prose_idx - 40), -1):
        stripped = lines[i].strip()
        if stripped.startswith("# ") and len(stripped) > 5:
            # Prefer headings not immediately followed by a nav bullet
            next_content = ""
            for j in range(i + 1, min(n, i + 4)):
                if lines[j].strip():
                    next_content = lines[j].strip()
                    break
            if not next_content.startswith("*") and not next_content.startswith("["):
                start_idx = i
                break
            # Still prefer this H1 over deeper headings
            if start_idx == prose_idx:
                start_idx = i

        elif stripped.startswith("## ") and len(stripped) > 5 and start_idx == prose_idx:
            start_idx = i

    result_lines = lines[start_idx:]

    # ── Phase 3: cut at first footer marker ──────────────────────────────────
    for i, line in enumerate(result_lines):
        lower = line.strip().lower()
        if any(marker in lower for marker in _FOOTER_MARKERS):
            result_lines = result_lines[:i]
            break

    # Remove trailing blank lines
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()

    content = "\n".join(result_lines).strip()

    # ── Phase 4: collapse excessive blank lines ───────────────────────────────
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content


def _extract_article_body(text: str) -> str:
    text = _merge_wrapped_lines(text)
    lines = _drop_leading_boilerplate(text.splitlines())

    def _is_date_line(line: str) -> bool:
        return bool(
            re.search(
                r"\b(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+\d{1,2},\s+\d{4}\b",
                line.strip(),
                re.IGNORECASE,
            )
        )

    def _is_prose(line: str) -> bool:
        s = line.strip()
        if not _is_substantive_line(s):
            return False
        if s.startswith("#"):
            return False
        return True

    heading_candidates: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not (stripped.startswith("# ") and len(stripped) > 5):
            continue
        score = 0
        for j in range(i + 1, min(len(lines), i + 8)):
            lookahead = lines[j].strip()
            if not lookahead:
                continue
            lower = lookahead.lower()
            if _is_date_line(lookahead):
                score += 3
            if "share on" in lower:
                score += 2
            if lower.startswith("### **by") or lower.startswith("### by") or lower.startswith("by "):
                score += 3
            if "series:" in lower:
                score += 1
        if score:
            heading_candidates.append((i, score))

    if heading_candidates:
        best_idx, _ = max(heading_candidates, key=lambda item: (item[1], item[0]))
        if best_idx > 20:
            return _finalize_content("\n".join(lines[best_idx:]))

    prose_idx = -1
    for i, line in enumerate(lines):
        if len(line.strip()) > 200 and _is_prose(line):
            prose_idx = i
            break

    if prose_idx == -1:
        for i, line in enumerate(lines):
            if len(line.strip()) > 120 and _is_prose(line):
                prose_idx = i
                break

    if prose_idx == -1:
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# ") and len(stripped) > 5:
                return _finalize_content("\n".join(lines[i:]))
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("## ") and len(stripped) > 5:
                return _finalize_content("\n".join(lines[i:]))
        for i, line in enumerate(lines):
            stripped = line.strip()
            if len(stripped) > 40 and _is_substantive_line(stripped):
                return _finalize_content("\n".join(lines[i:]))
        return _finalize_content("\n".join(lines))

    start_idx = prose_idx
    for i in range(prose_idx - 1, max(-1, prose_idx - 40), -1):
        stripped = lines[i].strip()
        if stripped.startswith("# ") and len(stripped) > 5:
            start_idx = i
            break
        if stripped.startswith("## ") and len(stripped) > 5 and start_idx == prose_idx:
            start_idx = i

    return _finalize_content("\n".join(lines[start_idx:]))


def _strip_boilerplate(text: str) -> str:
    return _extract_article_body(text)


# ── Link discovery ────────────────────────────────────────────────────────────

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_RAW_URL_RE = re.compile(r"https?://[^\s)>\"]+")


def _iter_discovered_links(content: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for match in _MD_LINK_RE.finditer(content):
        title = match.group(1).strip()
        url = match.group(2).strip()
        if url not in seen_urls:
            seen_urls.add(url)
            links.append((title, url))

    for match in _RAW_URL_RE.finditer(content):
        url = match.group(0).strip().rstrip(".,")
        if url in seen_urls:
            continue
        parsed = urlparse(url)
        slug = parsed.path.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").replace("_", " ").title() if slug else url
        seen_urls.add(url)
        links.append((title, url))

    return links


def _discover_via_sitemap(sitemap_url: str, article_pattern: str,
                          skip_pattern: str = "") -> list[tuple[str, str]]:
    print(f"  Loading sitemap: {sitemap_url}")
    r = _get(sitemap_url)
    if not r:
        return []

    if "<sitemapindex" in r.text or ("<sitemap>" in r.text and "<url>" not in r.text):
        sub_urls = re.findall(r"<loc>(https?://[^<]+)</loc>", r.text)
        all_articles: list[tuple[str, str]] = []
        for sub in sub_urls:
            time.sleep(0.3)
            sub_r = _get(sub)
            if sub_r:
                all_articles.extend(_urls_from_sitemap_xml(sub_r.text, article_pattern, skip_pattern))
        return all_articles

    return _urls_from_sitemap_xml(r.text, article_pattern, skip_pattern)


def _urls_from_sitemap_xml(xml: str, article_pattern: str,
                           skip_pattern: str = "") -> list[tuple[str, str]]:
    pattern = re.compile(article_pattern, re.IGNORECASE)
    skip = re.compile(skip_pattern, re.IGNORECASE) if skip_pattern else None
    urls = re.findall(r"<loc>(https?://[^<]+)</loc>", xml)
    results = []
    for url in urls:
        clean = url.strip().rstrip("/")
        if not pattern.search(clean):
            continue
        if skip and skip.search(clean):
            continue
        slug = clean.rstrip("/").split("/")[-1].replace("-", " ").title()
        results.append((slug, clean))
    return results


def _discover_via_jina_links(insights_url: str, article_pattern: str,
                             skip_pattern: str = "") -> list[tuple[str, str]]:
    print(f"  Discovering from: {insights_url}")
    content = _fetch_via_jina(insights_url, max_chars=80000)
    if not content:
        return []

    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    pattern = re.compile(article_pattern, re.IGNORECASE)
    skip = re.compile(skip_pattern, re.IGNORECASE) if skip_pattern else None

    for title, url in _iter_discovered_links(content):
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if clean_url in seen:
            continue
        if not pattern.search(clean_url):
            continue
        if skip and skip.search(clean_url):
            continue
        if any(x in clean_url for x in ("/tag/", "/category/", "/author/", "/page/", "/feed")):
            continue
        seen.add(clean_url)
        results.append((title, clean_url))

    return results


def _discover_via_jina_paginated(
    insights_url: str,
    page_url_template: str,
    max_pages: int,
    article_pattern: str,
    skip_pattern: str = "",
) -> list[tuple[str, str]]:
    all_pages = [insights_url] + [page_url_template.format(page=i) for i in range(2, max_pages + 1)]
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    pattern = re.compile(article_pattern, re.IGNORECASE)
    skip = re.compile(skip_pattern, re.IGNORECASE) if skip_pattern else None

    for page_url in all_pages:
        print(f"  Discovering from: {page_url}")
        content = _fetch_via_jina(page_url, max_chars=80000)
        if not content:
            continue

        for title, url in _iter_discovered_links(content):
            title = title.strip()
            url = url.strip()
            parsed = urlparse(url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if clean_url in seen:
                continue
            if not pattern.search(clean_url):
                continue
            if skip and skip.search(clean_url):
                continue
            if any(x in clean_url for x in ("/tag/", "/category/", "/author/", "/page/", "/feed")):
                continue
            seen.add(clean_url)
            results.append((title, clean_url))

    return results


def _discover_citadel_paginated(
    insights_url: str,
    page_url_template: str,
    max_pages: int,
    article_pattern: str,
    skip_pattern: str = "",
) -> list[tuple[str, str]]:
    if BeautifulSoup is None:
        return _discover_via_jina_paginated(insights_url, page_url_template, max_pages, article_pattern, skip_pattern)

    all_pages = [insights_url] + [page_url_template.format(page=i) for i in range(2, max_pages + 1)]
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    pattern = re.compile(article_pattern, re.IGNORECASE)
    skip = re.compile(skip_pattern, re.IGNORECASE) if skip_pattern else None

    for page_url in all_pages:
        print(f"  Discovering from: {page_url}")
        html = _fetch_browser_html(page_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a.text-block-citsec__link[href]"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            url = urljoin(page_url, href).rstrip("/")
            if url in seen:
                continue
            if not pattern.search(url):
                continue
            if skip and skip.search(url):
                continue
            title = (
                (link.get("aria-label") or "").strip()
                or (link.get("data-click-text") or "").strip()
                or url.rstrip("/").split("/")[-1].replace("-", " ").title()
            )
            title = _clean_text(title)
            seen.add(url)
            results.append((title, url))

    return results


def _extract_js_openpdf_url(href: str, base_url: str) -> str | None:
    match = re.search(r"openPDF\([^,]+,\s*'([^']+\.pdf[^']*)'\)", href, re.IGNORECASE)
    if not match:
        return None
    return urljoin(base_url, match.group(1))


def _discover_oaktree_memos(archive_url: str) -> list[tuple[str, str]]:
    if BeautifulSoup is None:
        return []

    html = _fetch_browser_html(archive_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    skip_titles = {"The Complete Collection", "The Best of . . ."}

    for link in soup.select("a.oc-title-link[href]"):
        title = _clean_text(link.get_text(" ", strip=True))
        href = (link.get("href") or "").strip()
        if not title or not href or title in skip_titles:
            continue
        if href.startswith("javascript:openPDF"):
            resolved = _extract_js_openpdf_url(href, archive_url)
        else:
            resolved = urljoin(archive_url, href)
        if not resolved:
            continue
        resolved = resolved.rstrip("/")
        if resolved in seen:
            continue
        if "/docs/default-source/memos/" not in resolved and "/insights/memo/" not in resolved:
            continue
        seen.add(resolved)
        results.append((title, resolved))

    return results


def _find_oaktree_pdf_link(html: str, base_url: str) -> str | None:
    if BeautifulSoup is None:
        return None

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a[href]"):
        href = (link.get("href") or "").strip()
        text = _clean_text(link.get_text(" ", strip=True))
        if "PDF (English)" in text and href:
            if href.startswith("javascript:openPDF"):
                return _extract_js_openpdf_url(href, base_url)
            return urljoin(base_url, href)
    return None


def _extract_citadel_article_from_html(html: str, fallback_title: str) -> tuple[str, str, list[str]]:
    if BeautifulSoup is None:
        return fallback_title, "", []

    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one(".page-section__article-header")
    body = soup.select_one(".page-section--single-news-body")
    if not body:
        return fallback_title, "", []

    title = fallback_title
    date_text = ""
    if header:
        title_tag = header.select_one("h1")
        if title_tag:
            clean_title = " ".join(title_tag.get_text(" ", strip=True).split())
            if clean_title:
                title = _clean_text(clean_title)
        date_tag = header.select_one(".page-section__article-header__date")
        if date_tag:
            date_text = " ".join(date_tag.get_text(" ", strip=True).split())

    lines: list[str] = [f"# {title}"]
    if date_text:
        lines.extend(["", date_text])

    images: list[str] = []
    legal_markers = (
        "legal entities disseminating this material",
        "for institutional use only",
        "please see additional important disclosures",
    )

    for tag in body.find_all(["h2", "h3", "h4", "p", "img"], recursive=True):
        if tag.name == "img":
            src = (tag.get("src") or "").strip()
            if src and src not in images:
                images.append(src)
                lines.extend(["", f"![Image {len(images)}]({src})"])
            continue

        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text:
            continue
        lower = text.lower()
        if any(marker in lower for marker in legal_markers):
            break
        if text in {"Share on", "/"}:
            continue
        if tag.name == "h2":
            lines.extend(["", f"## {text}"])
        elif tag.name in {"h3", "h4"}:
            lines.extend(["", f"### {text}"])
        else:
            lines.extend(["", text])

    content = _finalize_content("\n".join(lines))
    return title, content, images


# ── Image extraction ──────────────────────────────────────────────────────────

def _extract_images_from_html(html: str, base_url: str, out_dir: Path) -> list[str]:
    img_re = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    saved = []
    counter = 0
    seen: set[str] = set()

    for match in img_re.finditer(html):
        src = match.group(1).strip()
        if not src or src.startswith("data:") or "{" in src or "}" in src:
            continue
        full_url = urljoin(base_url, src)
        if full_url in seen:
            continue
        seen.add(full_url)

        skip_patterns = ["logo", "icon", "avatar", "social", "flag", "arrow",
                         "linkedin", "twitter", "facebook", "header", "nav",
                         "menu", "close", "search", "spinner", "loader",
                         "button", "badge", "thumbnail"]
        if any(p in full_url.lower() for p in skip_patterns):
            continue

        ext = Path(urlparse(full_url).path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            continue

        time.sleep(0.3)
        browser_r = _browser_get(full_url)
        content = browser_r.content if browser_r else b""
        if not content:
            r = _get(full_url)
            content = r.content if r else b""
        if len(content) < MIN_IMAGE_BYTES:
            continue

        counter += 1
        save_ext = ext if ext != ".webp" else ".png"
        fname = f"img_{counter:02d}{save_ext}"
        (out_dir / fname).write_bytes(content)
        saved.append(fname)

    return saved


def _extract_images_from_pdf(pdf_bytes: bytes, out_dir: Path) -> list[str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []  # PyMuPDF not installed — skip PDF image extraction
    saved = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        counter = 0
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                if len(img_bytes) < MIN_IMAGE_BYTES:
                    continue
                ext = base_image["ext"]
                if ext not in ("png", "jpg", "jpeg"):
                    continue
                counter += 1
                fname = f"img_{counter:02d}.{ext}"
                (out_dir / fname).write_bytes(img_bytes)
                saved.append(fname)
    except Exception as e:
        print(f"  [warn] PDF image extraction: {e}", file=sys.stderr)
    return saved


def _extract_images_from_markdown(md: str, out_dir: Path,
                                   existing_count: int = 0) -> list[str]:
    """Download images linked inline in Jina markdown: ![alt](url)"""
    img_re = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")
    saved = []
    counter = existing_count
    seen: set[str] = set()

    for match in img_re.finditer(md):
        url = match.group(1).strip()
        parsed = urlparse(url)
        if url in seen:
            continue
        if "{" in url or "}" in url:
            continue
        skip_patterns = ["logo", "icon", "avatar", "social", "flag", "arrow",
                         "linkedin", "twitter", "facebook", "header", "nav"]
        if any(p in url.lower() for p in skip_patterns):
            continue
        ext = Path(parsed.path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
            ext = ".png"  # default for extensionless image URLs
        seen.add(url)

        time.sleep(0.3)
        browser_r = _browser_get(url)
        content = browser_r.content if browser_r else b""
        if not content:
            r = _get(url)
            content = r.content if r else b""
        if len(content) < MIN_IMAGE_BYTES:
            continue

        counter += 1
        save_ext = ext if ext != ".webp" else ".png"
        fname = f"img_{counter:02d}{save_ext}"
        (out_dir / fname).write_bytes(content)
        saved.append(fname)

    return saved


# ── Storage ───────────────────────────────────────────────────────────────────

def _load_index() -> dict:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"articles": [], "last_updated": ""}


def _save_index(index: dict) -> None:
    index["last_updated"] = datetime.utcnow().isoformat()
    CORPUS_DIR.mkdir(exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _clean_text(text: str) -> str:
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", text)
    return " ".join(text.split()).strip()


def _is_pdf_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


def _slug(text: str, max_len: int = 55) -> str:
    text = _clean_text(text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


def _already_downloaded(index: dict, url: str) -> bool:
    return any(a["url"] == url for a in index.get("articles", []))


# ── Per-article fetcher ───────────────────────────────────────────────────────

def _fetch_article(
    url: str,
    firm_key: str,
    firm_cfg: dict,
    title: str,
    index: dict,
    reviewer: CorpusReviewAgent | None = None,
) -> bool:
    firm_name = firm_cfg["name"]
    is_pdf = _is_pdf_url(url)
    title = _clean_text(title)
    content = ""

    date_str = datetime.utcnow().strftime("%Y-%m")
    article_dir: Path | None = None
    images: list[str] = []
    article_review: ArticleReview | None = None

    if is_pdf:
        r = _get(url)
        if not r:
            return False
        pdf_bytes = r.content
        text = _fetch_pdf_text(url)
        if not text or len(text) < 300:
            return False
        extracted_title = _extract_pdf_header_title(text) or _title_from_pdf_url(url)
        if extracted_title:
            title = extracted_title
        content = _extract_article_body(text)
        article_dir = CORPUS_DIR / firm_key / f"{date_str}_{_slug(title)}_{_url_hash(url)}"
        article_dir.mkdir(parents=True, exist_ok=True)
        images = _extract_images_from_pdf(pdf_bytes, article_dir)

    else:
        if firm_key == "citadel_securities":
            html = _fetch_browser_html(url)
            if html:
                extracted_title, content, body_image_urls = _extract_citadel_article_from_html(html, title)
                if content:
                    title = extracted_title or title
                    article_dir = CORPUS_DIR / firm_key / f"{date_str}_{_slug(title)}_{_url_hash(url)}"
                    article_dir.mkdir(parents=True, exist_ok=True)
                    images = []
                    for idx, image_url in enumerate(body_image_urls, start=1):
                        time.sleep(0.2)
                        browser_r = _browser_get(image_url)
                        if not browser_r or len(browser_r.content) < MIN_IMAGE_BYTES:
                            continue
                        ext = Path(urlparse(image_url).path).suffix.lower() or ".png"
                        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                            ext = ".png"
                        save_ext = ext if ext != ".webp" else ".png"
                        fname = f"img_{idx:02d}{save_ext}"
                        (article_dir / fname).write_bytes(browser_r.content)
                        images.append(fname)
        elif firm_key == "oaktree" and "/insights/memo/" in url:
            html = _fetch_browser_html(url)
            pdf_url = _find_oaktree_pdf_link(html, url) if html else None
            if pdf_url:
                print(f"    [pdf] {pdf_url[-60:]}")
                time.sleep(REQUEST_DELAY)
                pdf_text = _fetch_pdf_text(pdf_url)
                if pdf_text and len(pdf_text) > 500:
                    content = _extract_article_body(pdf_text)

        pdf_url: str | None = None
        if not content:
            # Check if firm has a PDF in the raw HTML — download that instead if possible
            raw_r = _get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}) if firm_key != "citadel_securities" else None
            if firm_cfg.get("pdf_in_html") and raw_r:
                pdf_url = _find_pdf_in_html(
                    raw_r.text,
                    firm_cfg["pdf_html_pattern"],
                    firm_cfg.get("pdf_base_url", ""),
                )
            if raw_r and not pdf_url:
                pdf_url = _find_pdf_link(raw_r.text, url)
            if raw_r and "text/html" in raw_r.headers.get("content-type", ""):
                article_dir = CORPUS_DIR / firm_key / f"{date_str}_{_slug(title)}_{_url_hash(url)}"
                article_dir.mkdir(parents=True, exist_ok=True)
                images = _extract_images_from_html(raw_r.text, url, article_dir)

            if pdf_url:
                print(f"    [pdf] {pdf_url[-60:]}")
                time.sleep(REQUEST_DELAY)
                pdf_text = _fetch_pdf_text(pdf_url)
                if pdf_text and len(pdf_text) > 500:
                    content = _extract_article_body(pdf_text)
                    # Also get any additional images from the PDF
                    pdf_r = _get(pdf_url)
                    if pdf_r:
                        extra_imgs = _extract_images_from_pdf(pdf_r.content, article_dir)
                        images.extend(extra_imgs)
                else:
                    # PDF failed — fall through to HTML
                    pdf_url = None

        if not pdf_url and not content:
            jina_content = _fetch_via_jina(url)
            if not jina_content or len(jina_content) < 300:
                return False
            generic_pdf_url = _find_pdf_link(jina_content, url)
            if generic_pdf_url:
                print(f"    [pdf] {generic_pdf_url[-60:]}")
                time.sleep(REQUEST_DELAY)
                pdf_text = _fetch_pdf_text(generic_pdf_url)
                if pdf_text and len(pdf_text) > 500:
                    jina_content = pdf_text

            # Guard: skip pages that returned a "not found" result
            if re.search(r"page.{0,10}not found", jina_content[:500], re.IGNORECASE):
                print(f"    [skip] Page not found: {url[:70]}", file=sys.stderr)
                return False

            # Extract better title from H1 (prefer the LAST H1 — Jina often
            # puts a concatenated page-title H1 first and the clean article H1 later)
            h1_matches = list(re.finditer(r"^#\s+(.+)$", jina_content, re.MULTILINE))
            if h1_matches:
                # Use the last H1 that's reasonably sized
                for m in reversed(h1_matches):
                    candidate = m.group(1).strip()
                    # Strip common firm-name suffixes appended by Jina
                    for suffix in [" | Apollo", "Apollo Global Management",
                                   " | KKR", " | Blackstone", " | Oaktree",
                                   " | Bridgewater", " | Citadel"]:
                        candidate = candidate.replace(suffix, "").strip()
                    if 5 < len(candidate) < 200:
                        title = _clean_text(candidate)
                        break

            # Strip boilerplate
            content = _extract_article_body(jina_content)
            content = _finalize_content(content)
            if len(content) < 300:
                content = jina_content  # stripping too aggressive — use raw

            if not article_dir:
                article_dir = CORPUS_DIR / firm_key / f"{date_str}_{_slug(title)}_{_url_hash(url)}"
                article_dir.mkdir(parents=True, exist_ok=True)
                # Get images from HTML if accessible, otherwise extract from Jina markdown
                raw_r = _get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
                if raw_r and "text/html" in raw_r.headers.get("content-type", ""):
                    images = _extract_images_from_html(raw_r.text, url, article_dir)
                # Always supplement with images found in Jina markdown
                md_images = _extract_images_from_markdown(content, article_dir, len(images))
                images.extend(md_images)

    content = _finalize_content(content)
    if reviewer:
        article_review = reviewer.review_article(firm_key, firm_cfg, title, url, content)
        if not article_review.approve:
            print(f"    [skip] Agent rejected article as {article_review.content_type}: {article_review.reason}", file=sys.stderr)
            return False
        reviewed_content = _apply_keep_ranges(content, article_review.keep_ranges) if article_review.keep_ranges else content
        content = _finalize_content(reviewed_content)
        title = article_review.clean_title or title
    min_substantive_chars = 250 if firm_key == "oaktree" and is_pdf else _MIN_SUBSTANTIVE_CHARS
    substantive_chars = _substantive_char_count(content)
    if not _has_minimum_substance(content, min_substantive_chars):
        print(
            f"    [skip] Thin/boilerplate content ({substantive_chars} substantive chars): {url[:70]}",
            file=sys.stderr,
        )
        return False

    if not article_dir:
        article_dir = CORPUS_DIR / firm_key / f"{date_str}_{_slug(title)}_{_url_hash(url)}"
        article_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = (
        f"---\n"
        f"title: \"{title.replace(chr(34), chr(39))}\"\n"
        f"source: \"{firm_name}\"\n"
        f"firm: \"{firm_key}\"\n"
        f"url: \"{url}\"\n"
        f"downloaded: \"{datetime.utcnow().strftime('%Y-%m-%d')}\"\n"
        f"images: {json.dumps(images)}\n"
        f"---\n\n"
    )
    (article_dir / "article.md").write_text(frontmatter + content, encoding="utf-8")
    if article_review:
        (article_dir / "review.json").write_text(
            json.dumps(
                {
                    "content_type": article_review.content_type,
                    "reason": article_review.reason,
                    "keep_ranges": article_review.keep_ranges,
                    "model": reviewer.model if reviewer else "",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    index["articles"] = [entry for entry in index.get("articles", []) if entry.get("url") != url]
    index.setdefault("articles", []).append({
        "firm": firm_key,
        "firm_name": firm_name,
        "title": title,
        "url": url,
        "dir": str(article_dir.relative_to(CORPUS_DIR)),
        "downloaded": datetime.utcnow().strftime("%Y-%m-%d"),
        "chars": len(content),
        "images": images,
        "content_type": article_review.content_type if article_review else "",
    })
    return True


# ── Per-firm ingestor ─────────────────────────────────────────────────────────

def ingest_firm(
    firm_key: str,
    max_articles: int = 50,
    refresh: bool = False,
    reviewer: CorpusReviewAgent | None = None,
) -> int:
    firm = FIRMS.get(firm_key)
    if not firm:
        print(f"Unknown firm: {firm_key}")
        return 0

    print(f"\n{'='*60}")
    print(f"Ingesting: {firm['name']} ({firm_key})")
    print(f"{'='*60}")

    index = _load_index()
    skip_pattern = firm.get("skip_pattern", "")

    if firm["discovery"] == "sitemap":
        links = _discover_via_sitemap(firm["sitemap_url"], firm["article_pattern"], skip_pattern)
    elif firm["discovery"] == "seed_urls":
        links = list(firm.get("seed_urls", []))
        print(f"  Using {len(links)} seeded URLs")
    elif firm["discovery"] == "jina_paginated":
        links = _discover_via_jina_paginated(
            firm["insights_url"],
            firm["page_url_template"],
            int(firm.get("max_pages", 1)),
            firm["article_pattern"],
            skip_pattern,
        )
    elif firm["discovery"] == "citadel_paginated":
        links = _discover_citadel_paginated(
            firm["insights_url"],
            firm["page_url_template"],
            int(firm.get("max_pages", 1)),
            firm["article_pattern"],
            skip_pattern,
        )
    elif firm["discovery"] == "oaktree_memos":
        links = _discover_oaktree_memos(firm["insights_url"])
    else:
        links = _discover_via_jina_links(firm["insights_url"], firm["article_pattern"], skip_pattern)

    print(f"  Found {len(links)} candidate articles")
    if not links:
        print(f"  No articles found — site may require JS rendering or pattern needs adjustment")
        return 0

    saved = 0
    for i, (title, url) in enumerate(links[:max_articles]):
        if not refresh and _already_downloaded(index, url):
            print(f"  [skip] {title[:60]}")
            continue

        if reviewer:
            link_review = reviewer.review_link(firm_key, firm, title, url, "")
            if not link_review.include:
                print(f"  [skip] Agent rejected link as {link_review.content_type}: {title[:60]}")
                continue
            title = _clean_text(link_review.canonical_title)

        safe_title = _clean_text(title)
        print(f"  [{i+1}/{min(len(links), max_articles)}] {safe_title[:70]}")
        time.sleep(REQUEST_DELAY)

        ok = _fetch_article(url, firm_key, firm, safe_title, index, reviewer=reviewer)
        if ok:
            entry = index["articles"][-1]
            img_note = f", {len(entry['images'])} charts" if entry["images"] else ""
            print(f"    -> {entry['chars']:,} chars{img_note}")
            saved += 1
            _save_index(index)

    print(f"\n  Done: {saved} new articles for {firm['name']}")
    return saved


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest public research + charts from investment firm insights pages"
    )
    parser.add_argument("--firm", help="Firm key (e.g. kkr). Omit to ingest all.")
    parser.add_argument("--max", type=int, default=50, help="Max articles per firm (default: 50)")
    parser.add_argument("--refresh", action="store_true", help="Re-download already-archived articles")
    parser.add_argument("--list", action="store_true", help="List registered firms and exit")
    parser.add_argument("--agent-review", action="store_true", help="Use an LLM reviewer to approve candidate links and cleaned article bodies")
    parser.add_argument("--review-model", default=DEFAULT_REVIEW_MODEL, help=f"Model for corpus review agent (default: {DEFAULT_REVIEW_MODEL})")
    args = parser.parse_args()

    if args.list:
        print("\nRegistered firms:")
        for key, firm in FIRMS.items():
            disc = firm["discovery"]
            print(f"  {key:<20} {firm['name']:<35} [{firm['type']}] ({disc})")
        return

    CORPUS_DIR.mkdir(exist_ok=True)
    readme = CORPUS_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Research Corpus\n\n"
            "Public research articles and charts from major investment firm insights pages.\n\n"
            "## Structure\n\n"
            "```\n"
            "corpus/\n"
            "├── index.json                    <- full metadata manifest\n"
            "├── kkr/\n"
            "│   ├── 2024-01_regime_change_abc123/\n"
            "│   │   ├── article.md            <- cleaned article text + YAML frontmatter\n"
            "│   │   ├── img_01.png            <- charts / figures from the article\n"
            "│   │   └── img_02.png\n"
            "│   └── ...\n"
            "├── apollo/\n"
            "├── oaktree/\n"
            "└── ...\n"
            "```\n\n"
            "Run: `python scripts/ingest_corpus.py --list` to see all registered firms.\n",
            encoding="utf-8",
        )

    reviewer = CorpusReviewAgent(model=args.review_model) if args.agent_review else None

    if args.firm:
        if args.firm not in FIRMS:
            print(f"Unknown firm '{args.firm}'. Available: {', '.join(FIRMS)}")
            sys.exit(1)
        ingest_firm(args.firm, max_articles=args.max, refresh=args.refresh, reviewer=reviewer)
    else:
        total = 0
        for firm_key in FIRMS:
            total += ingest_firm(firm_key, max_articles=args.max, refresh=args.refresh, reviewer=reviewer)
        print(f"\n{'='*60}")
        print(f"Total new articles saved: {total}")

    index = _load_index()
    articles = index.get("articles", [])
    by_firm: dict[str, dict] = {}
    for a in articles:
        fk = a["firm"]
        by_firm.setdefault(fk, {"articles": 0, "images": 0})
        by_firm[fk]["articles"] += 1
        by_firm[fk]["images"] += len(a.get("images", []))

    if by_firm:
        print(f"\nCorpus summary ({len(articles)} total articles):")
        for fk, counts in sorted(by_firm.items(), key=lambda x: -x[1]["articles"]):
            fname = FIRMS.get(fk, {}).get("name", fk)
            print(f"  {fname:<35} {counts['articles']:>4} articles, {counts['images']:>4} charts")


if __name__ == "__main__":
    main()
