"""
Python execution tool for the quantitative builder agent.

Runs code in a subprocess, captures output, and automatically intercepts
plt.show() calls to save charts to the reports directory.

The quant builder passes code strings; this module executes them and returns
stdout, stderr, and paths to any charts generated.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

from loguru import logger

from agentorg import config


# Preamble injected before every code snippet — sets up data libraries and
# patches plt.show() to auto-save figures to the reports directory.
_PREAMBLE = textwrap.dedent("""\
    import os, sys, warnings
    warnings.filterwarnings('ignore')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    import pandas as pd

    try:
        import seaborn as sns
        sns.set_theme(style='whitegrid', palette='muted', font_scale=1.1)
    except ImportError:
        pass

    # Chart style defaults — clean, publication-ready
    plt.rcParams.update({
        'figure.figsize': (14, 6),
        'figure.dpi': 150,
        'axes.titlesize': 13,
        'axes.titleweight': 'bold',
        'axes.labelsize': 11,
        'axes.labelweight': 'bold',
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'xtick.major.pad': 4,
        'legend.fontsize': 9,
        'legend.framealpha': 0.85,
        'lines.linewidth': 1.8,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'figure.constrained_layout.use': True,
    })

    try:
        import yfinance as yf
    except ImportError:
        pass

    try:
        from fredapi import Fred
        _FRED_KEY = os.getenv('FRED_API_KEY', '')
        fred = Fred(api_key=_FRED_KEY) if _FRED_KEY else None
    except ImportError:
        fred = None

    REPORTS_DIR = os.getenv('REPORTS_DIR', 'reports')
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # fetch_url(url) — read the full content of any URL as clean markdown (via Jina Reader)
    # Use this to pull full reports, filings, articles that yfinance/FRED don't cover.
    def fetch_url(url, max_chars=12000):
        try:
            import httpx as _httpx
            resp = _httpx.get(f'https://r.jina.ai/{url}',
                headers={'Accept': 'text/plain', 'X-Return-Format': 'markdown'},
                timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            content = resp.text.strip()
            return content[:max_chars] if len(content) > max_chars else content
        except Exception as e:
            return f'fetch_url failed: {e}'

    _chart_counter = [0]
    _saved_charts = []
    _chart_source = ['']  # set via set_source() before plt.show()

    def set_source(text):
        # Call before plt.show() to annotate the chart with its data source.
        _chart_source[0] = text

    _orig_show = plt.show
    def _auto_save_and_show(*args, **kwargs):
        import re as _re
        _chart_counter[0] += 1
        # Use the current axes title as the filename if available
        ax = plt.gcf().axes[0] if plt.gcf().axes else None
        raw_title = (ax.get_title() if ax else '') or ''
        if raw_title:
            slug = _re.sub(r'[^a-z0-9]+', '_', raw_title.lower()).strip('_')[:40]
        else:
            slug = f'chart_{_chart_counter[0]:02d}'
        # Add source annotation at bottom-right of figure
        source_text = _chart_source[0]
        if source_text:
            plt.gcf().text(0.99, 0.01, source_text, ha='right', va='bottom',
                           fontsize=7, style='italic', color='#666666',
                           transform=plt.gcf().transFigure)
        _chart_source[0] = ''  # reset for next chart
        fname = os.path.join(REPORTS_DIR, f'{_chart_counter[0]:02d}_{slug}.png')
        plt.savefig(fname, dpi=150, bbox_inches='tight', facecolor='white')
        _saved_charts.append(fname)
        print(f'CHART_SAVED:{fname}', flush=True)
        plt.close()

    plt.show = _auto_save_and_show
    import time  # needed for timestamp in _auto_save_and_show

""")


# Anthropic tool definition for the quant builder's agentic loop
PYTHON_EXEC_TOOL_DEFINITION: dict[str, Any] = {
    "name": "execute_python",
    "description": (
        "Execute Python code for data analysis and visualization. "
        "Use this to fetch live market data (yfinance), macro data (fredapi), "
        "run calculations, and generate charts. "
        "plt.show() automatically saves charts to the reports directory — call it after each figure. "
        "Available: numpy, pandas, matplotlib, seaborn, yfinance, fredapi. "
        "Print key findings to stdout so they appear in the output. "
        "Always label axes, add a title, and annotate key events on charts."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Can be multi-line.",
            },
            "description": {
                "type": "string",
                "description": "One-line description of what this code does (for logging).",
            },
        },
        "required": ["code"],
    },
}


class ExecutionResult:
    def __init__(self, stdout: str, stderr: str, charts: list[str], success: bool, duration: float):
        self.stdout = stdout
        self.stderr = stderr
        self.charts = charts          # list of saved chart paths
        self.success = success
        self.duration = duration

    def to_tool_result(self) -> str:
        """Format as a string to return to Claude as the tool result."""
        parts = []
        if self.stdout.strip():
            parts.append(f"Output:\n{self.stdout.strip()}")
        if self.charts:
            parts.append(f"Charts saved: {', '.join(self.charts)}")
        if not self.success and self.stderr.strip():
            parts.append(f"Error:\n{self.stderr.strip()[:1000]}")
        if not parts:
            parts.append("Code executed successfully (no output).")
        parts.append(f"[Execution time: {self.duration:.1f}s]")
        return "\n\n".join(parts)


class PythonExecutor:
    """Executes Python code snippets in a subprocess with a configurable timeout."""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def run(self, code: str, description: str = "") -> ExecutionResult:
        if description:
            logger.info(f"[quant] Executing: {description}")

        full_code = _PREAMBLE + "\n" + code

        start = time.time()
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(full_code)
                tmp_path = f.name

            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={
                    **__import__("os").environ,
                    "REPORTS_DIR": str(config.REPORTS_DIR),
                    "MPLBACKEND": "Agg",
                },
            )
            duration = time.time() - start

            # Parse chart paths from stdout
            charts = []
            clean_stdout_lines = []
            for line in result.stdout.split("\n"):
                if line.startswith("CHART_SAVED:"):
                    path = line.removeprefix("CHART_SAVED:").strip()
                    charts.append(path)
                    logger.info(f"[quant] Chart saved: {Path(path).name}")
                else:
                    clean_stdout_lines.append(line)

            return ExecutionResult(
                stdout="\n".join(clean_stdout_lines),
                stderr=result.stderr,
                charts=charts,
                success=result.returncode == 0,
                duration=duration,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            logger.warning(f"[quant] Code execution timed out after {self.timeout}s")
            return ExecutionResult(
                stdout="",
                stderr=f"Execution timed out after {self.timeout}s.",
                charts=[],
                success=False,
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start
            logger.warning(f"[quant] Execution error: {e}")
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                charts=[],
                success=False,
                duration=duration,
            )
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
