"""Report generator — renders Jinja2 templates and optionally exports to PDF."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from agentorg import config


class ReportGenerator:
    """Renders Markdown reports from templates and exports them to PDF."""

    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else config.REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        templates_dir = config.REPORTS_DIR / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
        )

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context."""
        template = self.env.get_template(template_name)
        return template.render(**context)

    def generate_executive_summary(
        self,
        context: dict[str, Any] | None = None,
        export_format: str = "markdown",
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
        logger.info(f"Executive summary → {md_path.name}")

        if export_format in ("pdf", "both") and config.PDF_EXPORT_ENABLED:
            self._export_pdf(md_path)

        return md_path

    def export(self, format: str = "both") -> None:
        """Export all recent Markdown reports to the specified format."""
        md_files = list(self.output_dir.glob("*.md"))
        logger.info(f"Exporting {len(md_files)} reports as {format}")
        for md_file in md_files:
            if format in ("pdf", "both"):
                self._export_pdf(md_file)

    def _export_pdf(self, md_path: Path) -> Path:
        """Convert a Markdown file to PDF using weasyprint."""
        try:
            import markdown
            from weasyprint import HTML

            html_content = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables"])
            styled_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; line-height: 1.6; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #1a1a2e; }}
  h2 {{ color: #16213e; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background-color: #f2f2f2; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
</style>
</head><body>{html_content}</body></html>"""

            pdf_path = md_path.with_suffix(".pdf")
            HTML(string=styled_html).write_pdf(str(pdf_path))
            logger.info(f"PDF → {pdf_path.name}")
            return pdf_path
        except ImportError as e:
            logger.warning(f"PDF export skipped (missing dependency: {e})")
            return md_path
