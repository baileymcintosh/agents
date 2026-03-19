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
        article.md       ← full text with YAML frontmatter
        img_01.png       ← charts / figures extracted from the article
        img_02.png
        ...
    corpus/index.json    ← full metadata manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

# ── Firm registry ─────────────────────────────────────────────────────────────
# discovery: "sitemap" | "jina_links"  (use sitemap where possible)
# sitemap_url: direct URL to the sitemap that contains article listings
# article_pattern: regex matched against article URLs for filtering

FIRMS: dict[str, dict] = {
    "kkr": {
        "name": "KKR",
        "insights_url": "https://www.kkr.com/insights",
        "discovery": "sitemap",
        "sitemap_url": "https://www.kkr.com/sitemap.xml",
        "article_pattern": r"kkr\.com/insights/[a-z0-9\-]+$",
        "type": "private_equity",
    },
    "apollo": {
        "name": "Apollo Global Management",
        "insights_url": "https://www.apollo.com/insights-news/insights",
        "discovery": "sitemap",
        "sitemap_url": "https://www.apollo.com/sitemap.xml",
        "article_pattern": r"apollo\.com/insights-news/insights/[a-z0-9\-/]+\d{4}/\d{2}/[a-z0-9\-]+$",
        "type": "private_equity",
    },
    "blackstone": {
        "name": "Blackstone",
        "insights_url": "https://www.blackstone.com/insights/",
        "discovery": "sitemap",
        "sitemap_url": "https://www.blackstone.com/sitemap_index.xml",
        "article_pattern": r"blackstone\.com/insights/article/.+",
        "type": "private_equity",
    },
    "oaktree": {
        "name": "Oaktree Capital Management",
        "insights_url": "https://www.oaktreecapital.com/insights",
        "discovery": "jina_links",
        "article_pattern": r"oaktreecapital\.com/insights/(memo|article|insight)/.+",
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
REQUEST_DELAY = 1.5   # seconds between requests
TIMEOUT = 30.0

# Min image file size to bother saving (skip icons/spacers)
MIN_IMAGE_BYTES = 20_000


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, **kwargs) -> httpx.Response | None:
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [warn] GET failed {url}: {e}", file=sys.stderr)
        return None


def _fetch_via_jina(url: str, max_chars: int = 40000) -> str:
    jina_url = f"{JINA_BASE}{url}"
    r = _get(jina_url, headers={"Accept": "text/plain", "X-Return-Format": "markdown"})
    if not r:
        return ""
    content = r.text.strip()
    return content[:max_chars] if len(content) > max_chars else content


def _fetch_pdf_text(url: str) -> str:
    try:
        import io
        from pypdf import PdfReader
        r = _get(url)
        if not r:
            return ""
        reader = PdfReader(io.BytesIO(r.content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip())[:40000]
    except Exception as e:
        print(f"  [warn] PDF text extraction failed {url}: {e}", file=sys.stderr)
        return ""


def _extract_images_from_html(html: str, base_url: str, out_dir: Path) -> list[str]:
    """
    Extract chart-like images from raw HTML and save them to out_dir.
    Returns list of saved filenames.
    """
    img_re = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    saved = []
    counter = 0
    seen: set[str] = set()

    for match in img_re.finditer(html):
        src = match.group(1).strip()
        if not src or src.startswith("data:"):
            continue
        # Make absolute
        full_url = urljoin(base_url, src)
        if full_url in seen:
            continue
        seen.add(full_url)

        # Skip responsive image URL templates (e.g. KKR uses {.width} placeholders)
        if "{" in full_url or "}" in full_url:
            continue

        # Skip obvious non-charts: icons, logos, avatars, social, flags
        skip_patterns = ["logo", "icon", "avatar", "social", "flag", "arrow",
                         "linkedin", "twitter", "facebook", "header", "nav",
                         "menu", "close", "search", "spinner", "loader"]
        if any(p in full_url.lower() for p in skip_patterns):
            continue

        # Only save real image formats
        ext = Path(urlparse(full_url).path).suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            continue

        time.sleep(0.5)
        r = _get(full_url)
        if not r:
            continue

        # Skip tiny images (icons, spacers)
        if len(r.content) < MIN_IMAGE_BYTES:
            continue

        counter += 1
        save_ext = ext if ext != ".webp" else ".png"
        fname = f"img_{counter:02d}{save_ext}"
        (out_dir / fname).write_bytes(r.content)
        saved.append(fname)

    return saved


def _extract_images_from_pdf(pdf_bytes: bytes, out_dir: Path) -> list[str]:
    """Extract images from a PDF using pymupdf (fitz) if available."""
    try:
        import fitz  # pymupdf
    except ImportError:
        return []  # pymupdf not installed — skip silently

    saved = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        counter = 0
        for page_num, page in enumerate(doc):
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
        print(f"  [warn] PDF image extraction failed: {e}", file=sys.stderr)
    return saved


# ── Link discovery ────────────────────────────────────────────────────────────

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _discover_via_sitemap(sitemap_url: str, article_pattern: str) -> list[tuple[str, str]]:
    """Crawl a sitemap (or sitemap index) and return matching article URLs."""
    print(f"  Loading sitemap: {sitemap_url}")
    r = _get(sitemap_url)
    if not r:
        return []

    # Check if this is a sitemap index (contains nested sitemaps)
    if "<sitemapindex" in r.text or ("<sitemap>" in r.text and "<loc>" in r.text
                                      and "<url>" not in r.text):
        sub_urls = re.findall(r"<loc>(https?://[^<]+)</loc>", r.text)
        all_articles: list[tuple[str, str]] = []
        for sub in sub_urls:
            time.sleep(0.3)
            sub_r = _get(sub)
            if sub_r:
                all_articles.extend(_urls_from_sitemap_xml(sub_r.text, article_pattern))
        return all_articles

    return _urls_from_sitemap_xml(r.text, article_pattern)


def _urls_from_sitemap_xml(xml: str, article_pattern: str) -> list[tuple[str, str]]:
    pattern = re.compile(article_pattern, re.IGNORECASE)
    urls = re.findall(r"<loc>(https?://[^<]+)</loc>", xml)
    results = []
    for url in urls:
        clean = url.strip().rstrip("/")
        if pattern.search(clean):
            # Title is just the slug for now — will be overwritten when article is fetched
            slug = clean.rstrip("/").split("/")[-1].replace("-", " ").title()
            results.append((slug, clean))
    return results


def _discover_via_jina_links(insights_url: str, article_pattern: str) -> list[tuple[str, str]]:
    """Discover article links by fetching the insights index page via Jina Reader."""
    print(f"  Discovering from: {insights_url}")
    content = _fetch_via_jina(insights_url, max_chars=60000)
    if not content:
        return []

    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    pattern = re.compile(article_pattern, re.IGNORECASE)

    for match in _MD_LINK_RE.finditer(content):
        title = match.group(1).strip()
        url = match.group(2).strip()
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if clean_url in seen:
            continue
        if not pattern.search(clean_url):
            continue
        if any(x in clean_url for x in ("/tag/", "/category/", "/author/", "/page/", "/feed")):
            continue
        seen.add(clean_url)
        results.append((title, clean_url))

    return results


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


def _slug(text: str, max_len: int = 55) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:max_len]


def _already_downloaded(index: dict, url: str) -> bool:
    return any(a["url"] == url for a in index.get("articles", []))


# ── Per-article fetcher ───────────────────────────────────────────────────────

def _fetch_article(url: str, firm_key: str, firm_name: str, title: str, index: dict) -> bool:
    """
    Fetch one article (text + images) and save to corpus/<firm>/<slug>/.
    Returns True if saved successfully.
    """
    is_pdf = url.lower().endswith(".pdf")
    article_dir = None  # created once we know the title

    if is_pdf:
        r = _get(url)
        if not r:
            return False
        pdf_bytes = r.content
        text = _fetch_pdf_text(url)
        if not text or len(text) < 200:
            return False

        # Extract title from PDF first page if possible
        first_line = text.split("\n")[0].strip()
        if 10 < len(first_line) < 120:
            title = first_line

        date_str = datetime.utcnow().strftime("%Y-%m")
        slug_name = f"{date_str}_{_slug(title)}_{_url_hash(url)}"
        article_dir = CORPUS_DIR / firm_key / slug_name
        article_dir.mkdir(parents=True, exist_ok=True)

        images = _extract_images_from_pdf(pdf_bytes, article_dir)

    else:
        # Fetch via Jina for clean markdown text
        content = _fetch_via_jina(url)
        if not content or len(content) < 200:
            return False

        # Extract a better title from the first H1 in the markdown
        h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1 and len(h1.group(1)) < 150:
            title = h1.group(1).strip()

        date_str = datetime.utcnow().strftime("%Y-%m")
        slug_name = f"{date_str}_{_slug(title)}_{_url_hash(url)}"
        article_dir = CORPUS_DIR / firm_key / slug_name
        article_dir.mkdir(parents=True, exist_ok=True)

        text = content

        # Also fetch raw HTML to extract chart images
        raw_r = _get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; research-archiver/1.0)"})
        if raw_r and raw_r.headers.get("content-type", "").startswith("text/html"):
            time.sleep(0.5)
            images = _extract_images_from_html(raw_r.text, url, article_dir)
        else:
            images = []

    # Write article markdown
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
    (article_dir / "article.md").write_text(frontmatter + text, encoding="utf-8")

    # Update index
    index.setdefault("articles", []).append({
        "firm": firm_key,
        "firm_name": firm_name,
        "title": title,
        "url": url,
        "dir": str(article_dir.relative_to(CORPUS_DIR)),
        "downloaded": datetime.utcnow().strftime("%Y-%m-%d"),
        "chars": len(text),
        "images": images,
    })
    return True


# ── Per-firm ingestor ─────────────────────────────────────────────────────────

def ingest_firm(firm_key: str, max_articles: int = 50, refresh: bool = False) -> int:
    firm = FIRMS.get(firm_key)
    if not firm:
        print(f"Unknown firm: {firm_key}")
        return 0

    print(f"\n{'='*60}")
    print(f"Ingesting: {firm['name']} ({firm_key})")
    print(f"{'='*60}")

    index = _load_index()

    # Discover article links
    if firm["discovery"] == "sitemap":
        links = _discover_via_sitemap(firm["sitemap_url"], firm["article_pattern"])
    else:
        links = _discover_via_jina_links(firm["insights_url"], firm["article_pattern"])

    print(f"  Found {len(links)} candidate articles")

    if not links:
        print(f"  No articles found — site may require JS rendering or pattern may need adjustment")
        return 0

    saved = 0
    for i, (title, url) in enumerate(links[:max_articles]):
        if not refresh and _already_downloaded(index, url):
            print(f"  [skip] {title[:60]}")
            continue

        print(f"  [{i+1}/{min(len(links), max_articles)}] {title[:70]}")
        time.sleep(REQUEST_DELAY)

        ok = _fetch_article(url, firm_key, firm["name"], title, index)
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
    args = parser.parse_args()

    if args.list:
        print("\nRegistered firms:")
        for key, firm in FIRMS.items():
            disc = firm["discovery"]
            print(f"  {key:<15} {firm['name']:<35} [{firm['type']}] (discovery: {disc})")
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
            "├── index.json                    ← full metadata manifest\n"
            "├── kkr/\n"
            "│   ├── 2024-01_regime_change_abc123/\n"
            "│   │   ├── article.md            ← full article text\n"
            "│   │   ├── img_01.png            ← charts / figures from the article\n"
            "│   │   └── img_02.png\n"
            "│   └── ...\n"
            "├── apollo/\n"
            "├── oaktree/\n"
            "└── ...\n"
            "```\n\n"
            "## Adding a new firm\n\n"
            "Edit `scripts/ingest_corpus.py` — add an entry to `FIRMS` with:\n"
            "- `insights_url`: the listing page URL\n"
            "- `discovery`: `sitemap` (preferred) or `jina_links`\n"
            "- `sitemap_url`: if using sitemap discovery\n"
            "- `article_pattern`: regex to identify article URLs on that domain\n"
            "- `type`: firm category\n\n"
            "Then run: `python scripts/ingest_corpus.py --firm <key>`\n",
            encoding="utf-8",
        )

    if args.firm:
        if args.firm not in FIRMS:
            print(f"Unknown firm '{args.firm}'. Available: {', '.join(FIRMS)}")
            sys.exit(1)
        ingest_firm(args.firm, max_articles=args.max, refresh=args.refresh)
    else:
        total = 0
        for firm_key in FIRMS:
            total += ingest_firm(firm_key, max_articles=args.max, refresh=args.refresh)
        print(f"\n{'='*60}")
        print(f"Total new articles saved: {total}")

    # Summary
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
