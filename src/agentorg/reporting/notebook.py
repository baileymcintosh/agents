"""
Notebook builder — assembles a Jupyter notebook from research text and charts.

Charts are embedded as PNG outputs in hidden code cells, so the reader sees
a professional document with inline visuals and no visible code.

Structure of the output notebook:
  [Markdown] Title + metadata
  [Markdown] Section text
  [Code, hidden] → chart output (PNG embedded)
  [Markdown] Next section
  ...
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

# Regex that matches ![alt text](path/to/file.png)
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+\.png)\)", re.IGNORECASE)

from loguru import logger

try:
    import nbformat
    HAS_NBFORMAT = True
except ImportError:
    HAS_NBFORMAT = False
    logger.warning("[notebook] nbformat not installed — notebook export disabled")


# Keywords that trigger chart insertion after a section
_CHART_TRIGGERS = {
    "scenarios": ["scenario", "outlook", "probability", "probabilities"],
    "market_impacts": ["market", "financial", "asset", "oil", "equit", "energy"],
    "timeline": ["timeline", "chronol", "history", "sequence", "events"],
}


def _image_markdown_cell(png_path: Path, caption: str = "") -> Any:
    """A markdown cell with an embedded base64 PNG so no code input is shown."""
    data = base64.b64encode(png_path.read_bytes()).decode("utf-8")
    label = caption or png_path.stem.replace("_", " ").title()
    html = (
        f'<figure style="margin: 1.5rem 0;">'
        f'<img alt="{label}" src="data:image/png;base64,{data}" '
        f'style="max-width: 100%; height: auto;" />'
        f'<figcaption style="margin-top: 0.5rem; color: #555; font-style: italic;">'
        f"{label}</figcaption></figure>"
    )
    return nbformat.v4.new_markdown_cell(html)


def _emit_markdown_with_embedded_images(
    text: str,
    cells: list,
    used_chart_keys: set[str],
    chart_paths: dict[str, Path],
    base_dir: Path,
) -> None:
    """
    Scan markdown text for ![alt](path.png) references. For each:
    - Emit any preceding text as a markdown cell
    - Embed the PNG as a base64 hidden chart cell
    - Strip the image reference from the text (so it's not a broken link)

    Falls back to plain markdown cell if the PNG file doesn't exist
    (e.g., path is a URL or the file was deleted).
    """
    last_end = 0
    for match in _IMG_RE.finditer(text):
        alt = match.group(1) or "Chart"
        path_str = match.group(2)
        png_path = Path(path_str)
        if not png_path.is_absolute():
            png_path = (base_dir / png_path).resolve()

        # Emit text before this image
        before = text[last_end:match.start()].strip()
        if before:
            cells.append(nbformat.v4.new_markdown_cell(before))

        # Embed the chart if the file exists; otherwise emit a placeholder
        if png_path.exists():
            label = alt or png_path.stem.replace("_", " ").title()
            cells.append(_image_markdown_cell(png_path, label))
            resolved = png_path.resolve()
            for key, candidate in chart_paths.items():
                if candidate.resolve() == resolved:
                    used_chart_keys.add(key)
            logger.debug(f"[notebook] Embedded chart: {png_path.name}")
        else:
            # File not found (e.g. absolute path from a different machine) — skip image
            cells.append(nbformat.v4.new_markdown_cell(f"*[Chart not available: {alt}]*"))
            logger.warning(f"[notebook] Chart file not found, skipping: {path_str}")

        last_end = match.end()

    # Emit any remaining text after the last image
    remaining = text[last_end:].strip()
    if remaining:
        cells.append(nbformat.v4.new_markdown_cell(remaining))


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split markdown text on ## headings.
    Returns list of (heading, body) tuples.
    First item may have empty heading (preamble before first ##).
    """
    parts = re.split(r"^(#{1,3} .+)$", text, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []

    # parts alternates: [pre_text, heading, body, heading, body, ...]
    if parts[0].strip():
        sections.append(("", parts[0].strip()))

    i = 1
    while i < len(parts) - 1:
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append((heading, body))
        i += 2

    return sections


def _chart_for_section(heading: str, chart_paths: dict[str, Path]) -> Path | None:
    """Return the most relevant chart for a given section heading, if any."""
    heading_lower = heading.lower()
    for chart_key, keywords in _CHART_TRIGGERS.items():
        if chart_key in chart_paths and any(kw in heading_lower for kw in keywords):
            return chart_paths[chart_key]
    return None


def build_notebook(
    summary_text: str,
    chart_paths: dict[str, Path],
    metadata: dict[str, str] | None = None,
    base_dir: Path | None = None,
) -> "nbformat.NotebookNode | None":
    """
    Build a Jupyter notebook from the executive summary and generated charts.

    Args:
        summary_text: Full markdown text of the executive summary
        chart_paths: Dict of chart_key → PNG path (e.g. {"scenarios": Path(...)})
        metadata: Optional dict with keys like "date", "model", "project"

    Returns:
        nbformat NotebookNode ready to write, or None if nbformat not available
    """
    if not HAS_NBFORMAT:
        return None

    nb = nbformat.v4.new_notebook()
    nb["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb["metadata"]["language_info"] = {"name": "python", "version": "3.11.0"}

    cells = []
    used_charts: set[str] = set()
    notebook_base_dir = base_dir or Path.cwd()

    # ── Title cell ─────────────────────────────────────────────────────────────
    meta = metadata or {}
    title_md = (
        f"# {meta.get('project', 'Research Report')}\n\n"
        f"**Date:** {meta.get('date', '')}  \n"
        f"**Model:** {meta.get('model', '')}  \n"
        f"**Classification:** Internal Research — Not for Distribution\n\n"
        f"---"
    )
    cells.append(nbformat.v4.new_markdown_cell(title_md))

    # ── Timeline at top if available — anchors the narrative ──────────────────
    if "timeline" in chart_paths and "timeline" not in used_charts:
        cells.append(_image_markdown_cell(chart_paths["timeline"], "Event Timeline"))
        used_charts.add("timeline")

    # ── Body sections ──────────────────────────────────────────────────────────
    sections = _split_into_sections(summary_text)

    for heading, body in sections:
        # Combine heading + body, then strip inline image refs and embed as cells
        md_raw = f"{heading}\n\n{body}".strip() if heading else body
        if not md_raw:
            continue

        # Split markdown on embedded image references; emit text + chart cells
        _emit_markdown_with_embedded_images(
            md_raw,
            cells,
            used_charts,
            chart_paths,
            notebook_base_dir,
        )

        # Insert reporter summary chart after section if relevant and not yet used
        chart_path = _chart_for_section(heading, chart_paths)
        if chart_path:
            for key, path in chart_paths.items():
                if path == chart_path and key not in used_charts:
                    cells.append(_image_markdown_cell(chart_path, heading.lstrip("#").strip()))
                    used_charts.add(key)
                    break

    # ── Append any reporter charts not yet placed ──────────────────────────────
    for key, path in chart_paths.items():
        if key not in used_charts:
            label = key.replace("_", " ").title()
            cells.append(nbformat.v4.new_markdown_cell(f"---\n\n## {label}"))
            cells.append(_image_markdown_cell(path, label))

    nb.cells = cells
    logger.info(f"[notebook] Built notebook: {len(cells)} cells, {len(chart_paths)} charts")
    return nb


def save_notebook(nb: "nbformat.NotebookNode", output_path: Path) -> Path:
    """Write notebook to disk."""
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    logger.info(f"[notebook] Saved: {output_path.name}")
    return output_path
