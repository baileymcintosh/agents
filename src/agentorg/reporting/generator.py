"""Report generator — exports Markdown reports to professional LaTeX PDFs via pandoc."""

from __future__ import annotations

import datetime
import subprocess
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from agentorg import config

# LaTeX header for professional research report styling
LATEX_HEADER = r"""
\usepackage{geometry}
\geometry{margin=1.2in}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\textit{AgentOrg Research}}
\fancyhead[R]{\small\textit{\today}}
\fancyfoot[C]{\small\thepage}
\usepackage{titling}
\usepackage{booktabs}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=blue, urlcolor=blue}
\usepackage{parskip}
\setlength{\parindent}{0pt}
\usepackage{mdframed}
\usepackage{xcolor}
\definecolor{execgray}{RGB}{245,245,245}
"""


class ReportGenerator:
    """Renders Markdown reports from templates and exports to LaTeX PDF via pandoc."""

    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else config.REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        templates_dir = config.REPORTS_DIR / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
        )

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def export_to_pdf(self, md_path: Path) -> Path | None:
        """
        Convert a Markdown file to a professionally typeset PDF using pandoc + LaTeX.
        Returns the PDF path on success, None if pandoc is not available.
        """
        if not shutil.which("pandoc"):
            logger.warning("[pdf] pandoc not found — skipping PDF export. Install pandoc to enable.")
            return None

        pdf_path = md_path.with_suffix(".pdf")

        # Write a temporary LaTeX header file
        header_path = self.output_dir / "_header.tex"
        header_path.write_text(LATEX_HEADER, encoding="utf-8")

        cmd = [
            "pandoc",
            str(md_path),
            "--output", str(pdf_path),
            "--pdf-engine=xelatex",
            "--include-in-header", str(header_path),
            "--variable", "fontsize=11pt",
            "--variable", "linestretch=1.4",
            "--variable", "mainfont=DejaVu Serif",
            "--variable", "sansfont=DejaVu Sans",
            "--variable", "monofont=DejaVu Sans Mono",
            "--toc",                          # table of contents
            "--toc-depth=2",
            "--highlight-style=tango",
            "--table-of-contents",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info(f"[pdf] LaTeX PDF → {pdf_path.name}")
                return pdf_path
            else:
                logger.error(f"[pdf] pandoc failed:\n{result.stderr[:500]}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("[pdf] pandoc timed out after 120s")
            return None
        except Exception as e:
            logger.error(f"[pdf] Unexpected error: {e}")
            return None

    def export(self, format: str = "both") -> None:
        """Export all Markdown reports in the output directory to PDF."""
        md_files = list(self.output_dir.glob("*.md"))
        logger.info(f"Exporting {len(md_files)} reports")
        for md_file in md_files:
            if format in ("pdf", "both"):
                self.export_to_pdf(md_file)

    def generate_executive_summary(
        self,
        context: dict[str, Any] | None = None,
        export_format: str = "both",
    ) -> Path:
        ctx = context or {
            "date": datetime.date.today().isoformat(),
            "period": "Weekly",
            "accomplishments": [],
            "findings": [],
            "risks": [],
            "next_steps": [],
        }
        content = self.render_template("executive_summary.md.j2", ctx)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = self.output_dir / f"{timestamp}_executive_summary.md"
        md_path.write_text(content, encoding="utf-8")

        if export_format in ("pdf", "both") and config.PDF_EXPORT_ENABLED:
            self.export_to_pdf(md_path)

        return md_path
