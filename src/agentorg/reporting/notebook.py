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


def _png_output(png_path: Path) -> dict[str, Any]:
    """Build an nbformat display_data output with embedded PNG."""
    data = base64.b64encode(png_path.read_bytes()).decode("utf-8")
    return {
        "output_type": "display_data",
        "data": {"image/png": data, "text/plain": ["<Figure>"]},
        "metadata": {"image/png": {"width": 900}},
    }


def _hidden_chart_cell(png_path: Path, caption: str = "") -> dict[str, Any]:
    """A code cell with hidden source that displays a chart."""
    cell = nbformat.v4.new_code_cell(source=f"# {caption}")
    cell["metadata"]["jupyter"] = {"source_hidden": True}
    cell["metadata"]["collapsed"] = True
    cell["outputs"] = [_png_output(png_path)]
    cell["execution_count"] = None
    return cell


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
        cells.append(_hidden_chart_cell(chart_paths["timeline"], "Event Timeline"))
        used_charts.add("timeline")

    # ── Body sections ──────────────────────────────────────────────────────────
    sections = _split_into_sections(summary_text)

    for heading, body in sections:
        # Combine heading + body into one markdown cell
        md = f"{heading}\n\n{body}".strip() if heading else body
        if md:
            cells.append(nbformat.v4.new_markdown_cell(md))

        # Insert chart after section if relevant and not yet used
        chart_path = _chart_for_section(heading, chart_paths)
        if chart_path:
            # Find which key this is
            for key, path in chart_paths.items():
                if path == chart_path and key not in used_charts:
                    cells.append(_hidden_chart_cell(chart_path, heading.lstrip("#").strip()))
                    used_charts.add(key)
                    break

    # ── Append any charts not yet placed ──────────────────────────────────────
    for key, path in chart_paths.items():
        if key not in used_charts:
            label = key.replace("_", " ").title()
            cells.append(nbformat.v4.new_markdown_cell(f"---\n\n## {label}"))
            cells.append(_hidden_chart_cell(path, label))

    nb.cells = cells
    logger.info(f"[notebook] Built notebook: {len(cells)} cells, {len(chart_paths)} charts")
    return nb


def save_notebook(nb: "nbformat.NotebookNode", output_path: Path) -> Path:
    """Write notebook to disk."""
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    logger.info(f"[notebook] Saved: {output_path.name}")
    return output_path
