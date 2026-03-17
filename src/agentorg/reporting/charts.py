"""
Chart generator — creates matplotlib visualizations from structured research data.
Charts are saved as PNGs and uploaded to Slack alongside reports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend for server use
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("[charts] matplotlib not installed — chart generation disabled")


def _save(fig: Any, path: Path) -> Path:
    fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"[charts] Saved: {path.name}")
    return path


def scenario_probability_chart(
    scenarios: list[dict[str, Any]],
    output_path: Path,
    title: str = "Scenario Probability Distribution",
) -> Path | None:
    """
    Bar chart of scenario names vs. probability estimates.

    scenarios: [{"name": "Contained conflict", "probability": 35, "color": "#2ecc71"}, ...]
    """
    if not HAS_MATPLOTLIB:
        return None

    names = [s["name"] for s in scenarios]
    probs = [float(s["probability"]) for s in scenarios]
    colors = [s.get("color", "#3498db") for s in scenarios]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(names, probs, color=colors, edgecolor="white", height=0.6)

    for bar, prob in zip(bars, probs):
        ax.text(
            bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{prob:.0f}%", va="center", fontsize=11, fontweight="bold"
        )

    ax.set_xlabel("Probability (%)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_xlim(0, max(probs) * 1.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.axvline(x=0, color="black", linewidth=0.5)
    fig.tight_layout()

    return _save(fig, output_path)


def market_impact_chart(
    assets: list[dict[str, Any]],
    output_path: Path,
    title: str = "Estimated Market Impact by Asset Class",
) -> Path | None:
    """
    Horizontal bar chart showing estimated % impact on different assets.

    assets: [
        {"name": "Oil (Brent)", "low": 20, "high": 60, "direction": "up"},
        {"name": "S&P 500", "low": -15, "high": -5, "direction": "down"},
        ...
    ]
    """
    if not HAS_MATPLOTLIB:
        return None

    fig, ax = plt.subplots(figsize=(11, 6))

    y_positions = range(len(assets))
    for i, asset in enumerate(assets):
        low = asset["low"]
        high = asset["high"]
        mid = (low + high) / 2
        color = "#e74c3c" if asset.get("direction") == "down" else "#27ae60"

        ax.barh(i, high - low, left=low, color=color, alpha=0.7, height=0.5)
        ax.plot(mid, i, "o", color=color, markersize=8, zorder=5)
        ax.text(
            max(high, 0) + 1, i,
            f"{'+' if high > 0 else ''}{low:.0f}% to {'+' if high > 0 else ''}{high:.0f}%",
            va="center", fontsize=9, color="#333333"
        )

    ax.set_yticks(list(y_positions))
    ax.set_yticklabels([a["name"] for a in assets], fontsize=11)
    ax.axvline(x=0, color="black", linewidth=1)
    ax.set_xlabel("Estimated Price Impact (%)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    return _save(fig, output_path)


def timeline_chart(
    events: list[dict[str, Any]],
    output_path: Path,
    title: str = "Conflict Timeline",
) -> Path | None:
    """
    Horizontal timeline of key events.

    events: [{"date": "Jan 2026", "label": "US strikes Fordow", "severity": "high"}, ...]
    """
    if not HAS_MATPLOTLIB:
        return None

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_ylim(-1, 2)
    ax.set_xlim(-0.5, len(events) - 0.5)
    ax.axhline(y=0, color="#cccccc", linewidth=2, zorder=1)

    severity_colors = {"high": "#e74c3c", "medium": "#f39c12", "low": "#3498db"}

    for i, event in enumerate(events):
        color = severity_colors.get(event.get("severity", "medium"), "#3498db")
        ax.plot(i, 0, "o", color=color, markersize=14, zorder=3)
        offset = 0.3 if i % 2 == 0 else -0.7
        ax.annotate(
            f"{event['date']}\n{event['label']}",
            xy=(i, 0), xytext=(i, offset),
            fontsize=8, ha="center", va="center" if i % 2 == 0 else "top",
            arrowprops=dict(arrowstyle="-", color="#999999", lw=1),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, linewidth=1.5)
        )

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines[:].set_visible(False)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    legend_patches = [
        mpatches.Patch(color="#e74c3c", label="High severity"),
        mpatches.Patch(color="#f39c12", label="Medium severity"),
        mpatches.Patch(color="#3498db", label="Low severity"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=9)
    fig.tight_layout()

    return _save(fig, output_path)


def extract_chart_data(report_text: str) -> dict[str, Any]:
    """
    Parse structured chart data from a report.
    Agents embed JSON blocks tagged with ```chart_data ... ``` in their reports.
    """
    pattern = r"```chart_data\s*\n(.*?)\n```"
    matches = re.findall(pattern, report_text, re.DOTALL)

    data: dict[str, Any] = {}
    for match in matches:
        try:
            parsed = json.loads(match.strip())
            data.update(parsed)
        except json.JSONDecodeError:
            logger.warning("[charts] Could not parse chart_data block")

    return data


def generate_all_charts(report_text: str, output_dir: Path) -> list[Path]:
    """
    Extract all chart data from a report and generate chart PNGs.
    Returns list of generated chart file paths.
    """
    if not HAS_MATPLOTLIB:
        return []

    data = extract_chart_data(report_text)
    charts: list[Path] = []

    if "scenarios" in data:
        path = scenario_probability_chart(
            data["scenarios"],
            output_dir / "chart_scenarios.png",
            title=data.get("scenario_title", "Scenario Probability Distribution"),
        )
        if path:
            charts.append(path)

    if "market_impacts" in data:
        path = market_impact_chart(
            data["market_impacts"],
            output_dir / "chart_market_impact.png",
            title=data.get("market_title", "Estimated Market Impact by Asset Class"),
        )
        if path:
            charts.append(path)

    if "timeline" in data:
        path = timeline_chart(
            data["timeline"],
            output_dir / "chart_timeline.png",
            title=data.get("timeline_title", "Event Timeline"),
        )
        if path:
            charts.append(path)

    logger.info(f"[charts] Generated {len(charts)} chart(s)")
    return charts
