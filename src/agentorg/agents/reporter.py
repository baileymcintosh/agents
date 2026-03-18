"""Reporter agent — synthesizes research into a Jupyter notebook with inline charts."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg.agents.base import BaseAgent
from agentorg import config
from agentorg.evidence import ClaimRecord, EvidenceStore, SourceRecord


class ReporterAgent(BaseAgent):
    role = "reporter"

    def __init__(self) -> None:
        super().__init__()
        if not config.FAST_MODE:
            self.model = config.REPORTER_MODEL
        self.max_tokens = config.AGENT_MAX_TOKENS
        self.clock = None  # never cap reporter tokens
        self.store = EvidenceStore(config.REPORTS_DIR)

    def _gather_recent_reports(self) -> str:
        sections = []

        def _add_glob(pattern: str, label: str) -> None:
            for f in sorted(config.REPORTS_DIR.glob(pattern), key=lambda f: f.stat().st_mtime):
                content = f.read_text(encoding="utf-8")
                if "_Dry-run mode_" in content or "Dry-run mode" in content:
                    continue
                sections.append(f"## {label} — {f.stem}\n\n{content}")

        # Legacy builder reports (old workflow)
        _add_glob("*_builder_*.md", "Builder Report")

        # New collaborative session reports
        _add_glob("*_qual_builder_*.md", "Qualitative Research")
        _add_glob("*_quant_builder_*.md", "Quantitative Research")

        # Cross-agent dialogue log (key context for synthesis)
        for f in sorted(config.REPORTS_DIR.glob("*_session_dialogue.md"), key=lambda f: f.stat().st_mtime):
            sections.append(f"## Cross-Agent Research Dialogue\n\n{f.read_text(encoding='utf-8')}")

        # Latest planner and verifier
        for agent_role in ("planner", "verifier"):
            files = sorted(
                config.REPORTS_DIR.glob(f"*_{agent_role}_*.md"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                content = files[0].read_text(encoding="utf-8")
                if "_Dry-run mode_" in content or "Dry-run mode" in content:
                    continue
                sections.append(f"## {agent_role.capitalize()} Report\n\n{content}")

        return "\n\n---\n\n".join(sections) if sections else "No reports found."

    def _extract_chart_data(self, summary: str, context: str) -> dict[str, Any]:
        """
        Ask Claude directly for structured chart data based on the full research.
        Much more reliable than hoping the builder embedded correct JSON.
        """
        prompt = (
            "Based on the research below, output ONLY a JSON object (no explanation, no markdown, "
            "just raw JSON) with the following structure. Use real numbers from the research.\n\n"
            "{\n"
            '  "scenario_title": "string",\n'
            '  "scenarios": [{"name": "string", "probability": number_0_to_100, "color": "#hexcode"}, ...],\n'
            '  "market_title": "string",\n'
            '  "market_impacts": [{"name": "string", "low": number, "high": number, "direction": "up"|"down"}, ...],\n'
            '  "timeline_title": "string",\n'
            '  "timeline": [{"date": "string", "label": "string", "severity": "high"|"medium"|"low"}, ...]\n'
            "}\n\n"
            "Rules:\n"
            "- scenarios: 4-6 items, probabilities must sum to ~100\n"
            "- market_impacts: 6-10 assets with realistic % ranges (can be negative)\n"
            "- timeline: 6-10 key events in chronological order\n"
            "- colors: use #27ae60 (green/positive), #e74c3c (red/high-risk), "
            "#f39c12 (yellow/uncertain), #3498db (blue/neutral), #8e44ad (purple/severe)\n\n"
            f"Research summary:\n{summary[:4000]}\n\nFull context:\n{context[:3000]}"
        )
        try:
            raw = self.call_claude(prompt)
            # Strip any accidental markdown fences
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.warning(f"[reporter] Chart data extraction failed: {e}")
            return {}

    def _generate_charts(self, data: dict[str, Any]) -> dict[str, Path]:
        from agentorg.reporting.charts import (
            scenario_probability_chart,
            market_impact_chart,
            timeline_chart,
        )
        paths: dict[str, Path] = {}

        if "scenarios" in data:
            try:
                p = scenario_probability_chart(
                    data["scenarios"][:10],
                    config.REPORTS_DIR / "chart_scenarios.png",
                    title=data.get("scenario_title", "Scenario Probability Distribution"),
                )
                if p:
                    paths["scenarios"] = p
            except Exception as e:
                logger.warning(f"[reporter] scenario_probability_chart failed (skipping): {e}")

        if "market_impacts" in data:
            try:
                p = market_impact_chart(
                    data["market_impacts"][:12],
                    config.REPORTS_DIR / "chart_market_impact.png",
                    title=data.get("market_title", "Estimated Market Impact by Asset Class"),
                )
                if p:
                    paths["market_impacts"] = p
            except Exception as e:
                logger.warning(f"[reporter] market_impact_chart failed (skipping): {e}")

        if "timeline" in data:
            try:
                p = timeline_chart(
                    data["timeline"][:14],
                    config.REPORTS_DIR / "chart_timeline.png",
                    title=data.get("timeline_title", "Event Timeline"),
                )
                if p:
                    paths["timeline"] = p
            except Exception as e:
                logger.warning(f"[reporter] timeline_chart failed (skipping): {e}")

        logger.info(f"[reporter] Generated {len(paths)} chart(s): {list(paths.keys())}")
        return paths

    def _build_notebook(
        self, summary: str, chart_paths: dict[str, Path], report_path: Path
    ) -> Path | None:
        try:
            from agentorg.reporting.notebook import build_notebook, save_notebook
            meta = {
                "project": self._project_title(),
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "model": self.model,
            }
            nb = build_notebook(summary, chart_paths, metadata=meta)
            if nb is None:
                return None
            nb_path = report_path.with_suffix(".ipynb")
            save_notebook(nb, nb_path)
            logger.info(f"[reporter] Notebook → {nb_path.name}")
            return nb_path
        except Exception as e:
            logger.warning(f"[reporter] Notebook build failed: {e}")
            return None

    def _project_title(self) -> str:
        brief_path = config.REPORTS_DIR.parent / "BRIEF.md"
        if brief_path.exists():
            lines = [line.strip() for line in brief_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for line in lines:
                if not line.startswith("#"):
                    return line[:120]
        return config.REPORTS_DIR.parent.name.replace("-", " ").title()

    def _evidence_digest(self) -> str:
        verification = self.store.latest_verification()
        sources = self.store.sources()
        claims = self.store.claims()
        lines = [
            "## Structured Evidence Digest",
            f"- Claims recorded: {len(claims)}",
            f"- Sources recorded: {len(sources)}",
        ]
        if verification:
            lines.append(f"- Verification verdict: {verification.get('verdict', 'UNKNOWN')}")
        top_sources = sources[:8]
        if top_sources:
            lines.append("\n### Source Register")
            for source in top_sources:
                lines.append(f"- [{source.tier}] {source.title} — {source.url or source.publisher}")
        top_claims = claims[:10]
        if top_claims:
            lines.append("\n### Verified Claim Inventory")
            for claim in top_claims:
                lines.append(f"- ({claim.status}) {claim.statement}")
        return "\n".join(lines)

    def _citation_mappings(self) -> tuple[list[ClaimRecord], dict[str, SourceRecord]]:
        claims = sorted(
            self.store.claims(),
            key=lambda claim: (
                0 if claim.status == "verified" else 1,
                0 if claim.materiality == "core" else 1,
                -claim.confidence,
            ),
        )
        sources = {source.id: source for source in self.store.sources()}
        return claims, sources

    def _apply_inline_citations(self, summary: str) -> str:
        claims, _ = self._citation_mappings()
        cited = summary
        for claim in claims[:12]:
            if claim.statement in cited:
                refs = ", ".join(claim.source_ids[:2]) if claim.source_ids else claim.id
                cited = cited.replace(claim.statement, f"{claim.statement} [{refs}]", 1)
        return cited

    def _references_section(self) -> str:
        _, sources = self._citation_mappings()
        if not sources:
            return ""
        lines = [
            "## Sources",
            "",
            "| ID | Title | Tier | Publisher |",
            "|---|---|---|---|",
        ]
        for source in sorted(sources.values(), key=lambda item: (item.tier, item.title))[:40]:
            publisher = source.publisher or source.url or ""
            lines.append(f"| {source.id} | {source.title} | {source.tier} | {publisher} |")
        return "\n".join(lines)

    def _confidence_banner(self) -> str:
        low_confidence_core = [
            claim for claim in self.store.claims()
            if claim.materiality == "core" and claim.confidence < 0.6
        ]
        if not low_confidence_core:
            return ""
        return (
            "> This report contains claims with limited source corroboration. "
            "See verification artifacts for details.\n"
        )

    def _export_pdf(self, report_path: Path) -> Path | None:
        import subprocess
        pdf_path = report_path.with_suffix(".pdf")
        cmd = [
            "pandoc", str(report_path),
            "--output", str(pdf_path),
            "--pdf-engine=xelatex",
            "--toc",
            f"--resource-path={config.REPORTS_DIR}",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
            "-V", "colorlinks=true",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logger.info(f"[reporter] PDF → {pdf_path.name}")
                return pdf_path
            logger.warning(f"[reporter] pandoc failed: {result.stderr[:300]}")
        except Exception as e:
            logger.warning(f"[reporter] PDF export failed: {e}")
        return None

    def _post_slack(self, brief: str, nb_path: Path | None, pdf_path: Path | None, report_path: Path) -> None:
        if not config.SLACK_BOT_TOKEN or not config.SLACK_EXECUTIVE_CHANNEL_ID:
            return
        try:
            from agentorg.slack_bot.client import SlackClient
            slack = SlackClient()
            cycle_date = report_path.stem.split("_")[0]
            slack.post_message(
                channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                text=f"*Research Report — {cycle_date}*\n\n{brief}",
            )
            for path, title, comment in [
                (nb_path, f"Report — {cycle_date} (Notebook)", "Open in VS Code or Jupyter — charts inline."),
                (pdf_path, f"Report — {cycle_date} (PDF)", "PDF version."),
            ]:
                if path:
                    try:
                        slack.upload_file(
                            channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                            file_path=str(path), title=title, initial_comment=comment,
                        )
                    except Exception as e:
                        logger.warning(f"[reporter] Slack upload failed: {e}")
        except Exception as e:
            logger.warning(f"[reporter] Slack post failed (non-fatal): {e}")

    def run(self, dry_run: bool = False, revision_instructions: str = "") -> dict[str, Any]:
        logger.info("[reporter] Starting.")
        self.post_slack_progress("📝", "starting", "Synthesizing all research into final report...")

        context = self._gather_recent_reports()
        evidence_digest = self._evidence_digest()

        summary_prompt = (
            "You are the reporter — the senior editor who synthesises work from a two-person research team:\n"
            "- **Qualitative researcher (OpenAI GPT-4o):** news, speeches, policy analysis, geopolitical context\n"
            "- **Quantitative researcher (Claude):** live market data, annotated charts, statistical analysis\n\n"
            "Your job: weave both threads into a single coherent, publication-quality executive summary "
            "that is strong both quantitatively AND qualitatively. Where the quant identified data anomalies "
            "and the qual explained them, make that cross-verification explicit — it's the most valuable part.\n\n"
            "Use these exact section headings:\n"
            "# [Project Title]\n"
            "## One-Line Status\n"
            "## Situation Overview\n"
            "## Key Findings\n"
            "## Scenario Outlook\n"
            "## Financial Markets Implications\n"
            "## Historical Precedents & Lessons\n"
            "## Quality Assessment\n"
            "## Recommended Next Steps\n\n"
            "Rules:\n"
            "- Cite specific data points from the quant research (exact prices, % changes, dates)\n"
            "- Cite named sources from the qual research (publications, officials, think tanks)\n"
            "- Where a chart was generated, reference it: 'As shown in the oil price chart above...'\n"
            "- Include the cross-agent dialogue insights: moments where quant spotted something and qual explained it\n"
            "- Prefer claims marked `verified` when the evidence digest distinguishes them\n"
            "- This is the final deliverable for senior leadership making real financial decisions\n\n"
            f"{context}\n\n{evidence_digest}"
        )
        if revision_instructions:
            summary_prompt = (
                "REVISION REQUIRED. Fix the following before writing:\n"
                f"{revision_instructions}\n\n"
                + summary_prompt
            )

        if dry_run:
            summary = "_Dry-run mode._"
            brief = "_Dry-run mode._"
        else:
            summary = self.call_claude(summary_prompt)
            brief_prompt = (
                "Write a 3-sentence Slack update for a senior executive. "
                "What was researched, the single most important finding, one key risk. "
                "Specific, no filler.\n\n" + summary[:3000]
            )
            brief = self.call_claude(brief_prompt)

        # Generate reporter summary charts (scenarios, timeline, market impact)
        chart_paths: dict[str, Path] = {}
        if not dry_run:
            chart_data = self._extract_chart_data(summary, context)
            if chart_data:
                chart_paths = self._generate_charts(chart_data)

        # Load quant charts manifest
        quant_charts: list[dict] = []
        manifest_path = config.REPORTS_DIR / "charts_manifest.json"
        if manifest_path.exists():
            try:
                import json as _json
                quant_charts = _json.loads(manifest_path.read_text(encoding="utf-8"))
                logger.info(f"[reporter] Loaded {len(quant_charts)} quant charts from manifest")
            except Exception as e:
                logger.warning(f"[reporter] Could not load charts manifest: {e}")

        # Build markdown with ALL charts embedded + explained
        cited_summary = self._apply_inline_citations(summary)
        banner = self._confidence_banner()
        md_with_charts = f"{banner}\n{cited_summary}" if banner else cited_summary

        # Insert reporter summary charts next to relevant sections
        if chart_paths:
            triggers = {
                "timeline": ["## situation", "## one-line", "## overview"],
                "scenarios": ["## scenario"],
                "market_impacts": ["## financial", "## market"],
            }
            remaining = dict(chart_paths)
            lines = cited_summary.split("\n")
            out = []
            for line in lines:
                out.append(line)
                ll = line.lower()
                for key, keywords in list(remaining.items()):
                    if any(ll.startswith(kw) for kw in keywords):
                        p = chart_paths[key]
                        out.append(f"\n![{p.stem.replace('_', ' ').title()}]({p})\n")
                        remaining.pop(key)
                        break
            for key, p in remaining.items():
                out.append(f"\n---\n\n## {key.replace('_', ' ').title()}\n\n![{p.stem}]({p})\n")
            md_with_charts = "\n".join(out)

        # Append a dedicated Data section with every quant chart explained
        if quant_charts:
            data_section = "\n\n---\n\n## Data & Charts\n\n"
            data_section += (
                "_All charts below were generated by the quantitative agent using live market data. "
                "Each is annotated with key conflict events._\n\n"
            )
            for entry in quant_charts:
                fname = entry.get("filename", "")
                title = entry.get("title", fname)
                desc = entry.get("description", "")
                chart_file = config.REPORTS_DIR / fname
                if chart_file.exists():
                    data_section += f"### {title}\n\n"
                    data_section += f"![{title}]({chart_file})\n\n"
                    if desc:
                        data_section += f"{desc}\n\n"
            md_with_charts = md_with_charts + data_section

        references_section = self._references_section()
        if evidence_digest:
            md_with_charts = md_with_charts + "\n\n---\n\n" + evidence_digest
        if references_section:
            md_with_charts = md_with_charts + "\n\n---\n\n" + references_section

        # Collect ALL chart paths for notebook embedding
        all_pngs = sorted(config.REPORTS_DIR.glob("chart_*.png"), key=lambda p: p.stat().st_mtime)
        chart_paths = {p.stem.removeprefix("chart_"): p for p in all_pngs}

        report_path = self.write_report("Executive Summary", md_with_charts)

        # Build Jupyter notebook — primary output, open in VS Code
        nb_path = self._build_notebook(cited_summary, chart_paths, report_path) if not dry_run else None

        # PDF
        pdf_path: Path | None = None
        if not dry_run and config.PDF_EXPORT_ENABLED and not config.FAST_MODE:
            pdf_path = self._export_pdf(report_path)

        # Log where outputs are
        logger.info(f"[reporter] Outputs in {config.REPORTS_DIR}:")
        logger.info(f"  Markdown: {report_path.name}")
        if nb_path:
            logger.info(f"  Notebook: {nb_path.name}  ← open this in VS Code")
        if pdf_path:
            logger.info(f"  PDF:      {pdf_path.name}")

        # Slack — secondary, best-effort
        if not dry_run:
            self._post_slack(brief, nb_path, pdf_path, report_path)

        self.post_slack_progress("✅", "done", brief[:200] if not dry_run else "Dry-run complete.")
        return {
            "status": "ok",
            "report": str(report_path),
            "notebook": str(nb_path) if nb_path else None,
            "pdf": str(pdf_path) if pdf_path else None,
        }


def main(dry_run: bool = False) -> None:
    ReporterAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
