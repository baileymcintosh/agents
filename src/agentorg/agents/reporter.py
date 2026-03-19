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

    def _extract_timeline_events(self, summary: str, context: str) -> list[dict[str, str]]:
        """Extract key events chronologically from the research for a markdown table."""
        prompt = (
            "Based on the research below, output ONLY a JSON array (no explanation, no markdown fences) "
            "of key events in chronological order. Include as many specific, distinct events as the research supports — "
            "aim for 15-25 entries for a thorough timeline. Each entry:\n"
            '{"date": "Mon YYYY or Q1 YYYY", "event": "Concise specific description (max 15 words)", '
            '"significance": "One sentence on why this matters"}\n\n'
            "Rules:\n"
            "- Only include events that are explicitly mentioned in the research — no invented entries\n"
            "- dates must be specific (avoid 'Recent' or 'Ongoing')\n"
            "- events must be factual, named, and specific — not generic ('markets reacted')\n"
            "- significance must explain the direct relevance to the research topic\n\n"
            f"Research summary:\n{summary[:4000]}\n\nFull context:\n{context[:3000]}"
        )
        try:
            raw = self.call_claude(prompt).strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].removeprefix("json").strip()
            events = json.loads(raw)
            return events if isinstance(events, list) else []
        except Exception as e:
            logger.warning(f"[reporter] Timeline extraction failed: {e}")
            return []

    def _build_events_table(self, events: list[dict[str, str]], title: str = "Key Events") -> str:
        """Render extracted events as a markdown table."""
        if not events:
            return ""
        lines = [
            f"## {title}",
            "",
            "| Date | Event | Significance |",
            "|---|---|---|",
        ]
        for e in events:
            date = e.get("date", "").replace("|", "/")
            event = e.get("event", "").replace("|", "-")
            sig = e.get("significance", "").replace("|", "-")
            lines.append(f"| {date} | {event} | {sig} |")
        lines.append("")
        return "\n".join(lines)

    def _generate_charts(self, data: dict[str, Any]) -> dict[str, Path]:
        # Scenario probability and market impact charts removed — they rely on
        # fabricated numbers and add no analytical value. Only quant-generated
        # charts (from real data via yfinance/FRED) are now used.
        return {}

    def _build_all_plots_md(self, all_png_paths: list[Path]) -> Path | None:
        """Build a markdown file with every chart embedded as a relative image link."""
        try:
            title = self._project_title()
            lines = [
                f"# {title} — All Charts",
                "",
                f"*{len(all_png_paths)} charts generated by the quantitative agent.*",
                "",
            ]
            for png in sorted(all_png_paths, key=lambda p: p.name):
                if not png.exists():
                    continue
                label = png.stem.replace("_", " ").title()
                # Use relative path from project root: charts/<filename>
                lines.append(f"## {label}")
                lines.append("")
                lines.append(f"![{label}](charts/{png.name})")
                lines.append("")
            out_path = config.REPORTS_DIR / "all_plots.md"
            out_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"[reporter] All-plots markdown → {out_path.name} ({len(all_png_paths)} charts)")
            return out_path
        except Exception as e:
            logger.warning(f"[reporter] all_plots.md build failed: {e}")
            return None

    def _build_all_plots_notebook(self, all_png_paths: list[Path]) -> Path | None:
        """Build a simple notebook containing every generated chart as base64-embedded cells."""
        try:
            import base64
            import nbformat

            nb = nbformat.v4.new_notebook()
            nb["metadata"]["kernelspec"] = {
                "display_name": "Python 3", "language": "python", "name": "python3"
            }
            nb["metadata"]["language_info"] = {"name": "python", "version": "3.11.0"}

            cells = []
            title = self._project_title()
            cells.append(nbformat.v4.new_markdown_cell(
                f"# {title} — All Charts\n\n"
                f"*{len(all_png_paths)} charts generated by the quantitative agent.*"
            ))

            for png in sorted(all_png_paths, key=lambda p: p.name):
                if not png.exists():
                    continue
                label = png.stem.replace("_", " ").title()
                # Caption markdown
                cells.append(nbformat.v4.new_markdown_cell(f"### {label}"))
                # Hidden code cell with embedded PNG output
                data = base64.b64encode(png.read_bytes()).decode("utf-8")
                output = nbformat.v4.new_output(
                    output_type="display_data",
                    data={"image/png": data, "text/plain": ["<Figure>"]},
                    metadata={"image/png": {"width": 900}},
                )
                cell = nbformat.v4.new_code_cell(source=f"# {label}")
                cell["metadata"]["jupyter"] = {"source_hidden": True}
                cell["metadata"]["collapsed"] = True
                cell["outputs"] = [output]
                cell["execution_count"] = None
                cells.append(cell)

            nb.cells = cells
            out_path = config.REPORTS_DIR / "all_plots.ipynb"
            with open(out_path, "w", encoding="utf-8") as f:
                nbformat.write(nb, f)
            logger.info(f"[reporter] All-plots notebook → {out_path.name} ({len(all_png_paths)} charts)")
            return out_path
        except Exception as e:
            logger.warning(f"[reporter] all_plots notebook build failed: {e}")
            return None

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
            nb = build_notebook(
                summary,
                chart_paths,
                metadata=meta,
                base_dir=report_path.parent,
            )
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

        # Load quant charts manifest early so the reporter can write per-chart analysis
        quant_charts: list[dict] = []
        manifest_path = config.REPORTS_DIR / "charts_manifest.json"
        if manifest_path.exists():
            try:
                import json as _json
                quant_charts = _json.loads(manifest_path.read_text(encoding="utf-8"))
                logger.info(f"[reporter] Loaded {len(quant_charts)} quant charts from manifest")
            except Exception as e:
                logger.warning(f"[reporter] Could not load charts manifest: {e}")

        # In fast/prelim mode, truncate context to stay within Groq's ~32k token limit.
        # The prompt template itself is ~600 chars; leave ~20k chars for context + digest.
        if config.FAST_MODE:
            context_for_prompt = context[:12000]
            digest_for_prompt = evidence_digest[:6000]
            if len(context) > 12000:
                context_for_prompt += "\n\n[... context truncated for fast-mode reporter ...]"
        else:
            context_for_prompt = context
            digest_for_prompt = evidence_digest

        # Build the chart catalogue for the prompt so the reporter knows exactly what exists
        chart_catalogue = ""
        if quant_charts:
            chart_catalogue = "\n\nAVAILABLE CHARTS (generated by the quantitative agent):\n"
            for i, entry in enumerate(quant_charts, 1):
                fname = entry.get("filename", "")
                title = entry.get("title", fname)
                desc = entry.get("description", "")
                chart_catalogue += f"  {i}. [{fname}] {title}"
                if desc:
                    chart_catalogue += f"\n     Quant note: {desc}"
                chart_catalogue += "\n"
            chart_catalogue += (
                "\nYou MUST include a `## Data & Charts` section at the end of the report. "
                "For EACH chart above, write:\n"
                "  1. A `### [Chart Title]` subheading\n"
                "  2. A `[CHART: filename]` placeholder on its own line — use the EXACT filename shown in brackets above\n"
                "  3. A substantive 2-4 paragraph analysis. CRITICAL RULES for chart analysis:\n"
                "     a) UNIQUE analysis for EACH chart — do NOT reuse the same sentences, structure, or themes across charts\n"
                "     b) Reference SPECIFIC numbers from THAT chart only (e.g. 'Brent crude peaked at $127/bbl on March 8')\n"
                "     c) Connect to qualitative findings that are DIRECTLY relevant to this specific chart — not generic geopolitical boilerplate\n"
                "     d) Flag the single most surprising or decision-relevant insight from this chart\n"
                "     e) If two charts show contradictory signals, say so explicitly\n"
                "\nFORBIDDEN patterns (will cause a revision request):\n"
                "  - Repeating the phrase 'the Ukraine-Russia conflict' for a report not about that topic\n"
                "  - Using the same paragraph structure for every chart\n"
                "  - Describing what a chart 'shows' without citing any actual numbers from it\n"
                "  - Generic statements like 'the market may face challenges due to regulatory scrutiny'\n"
                "\nThe report must be DATA-DRIVEN: charts and numbers are the spine; qualitative context is the flesh.\n"
            )

        summary_prompt = (
            "You are the reporter — the senior editor who synthesises work from a two-person research team:\n"
            "- **Qualitative researcher (OpenAI GPT-4o):** news, speeches, policy analysis, geopolitical context\n"
            "- **Quantitative researcher (Claude):** live market data, annotated charts, statistical analysis\n\n"
            "Your job: weave both threads into a single coherent, publication-quality executive summary "
            "that is strong both quantitatively AND qualitatively. Where the quant identified data anomalies "
            "and the qual explained them, make that cross-verification explicit — it's the most valuable part.\n\n"
            "Use these exact section headings:\n"
            "# [Project Title]\n"
            "## TL;DR\n"
            "## Executive Summary\n"
            "## Situation Overview\n"
            "## Core Analysis\n"
            "## Scenario Outlook\n"
            "## Financial Markets Implications\n"
            "## Historical Precedents & Lessons\n"
            "## Risks, Counterarguments, and What Would Change the View\n"
            "## Recommended Next Steps\n"
            "## Data & Charts\n\n"
            "Rules:\n"
            "- `## TL;DR` may use bullets. Every other section should be mostly full prose paragraphs.\n"
            "- **Inline citations are mandatory.** After every factual claim, statistic, or quoted position, "
            "add a parenthetical source: (Reuters, Mar 2026) or (BLS, Feb 2026) or (yfinance data). "
            "No claim may appear without a source. Data from charts must cite their dataset.\n"
            "- Cite specific data points from the quant research (exact prices, % changes, dates)\n"
            "- Cite named sources from the qual research (publications, officials, think tanks)\n"
            "- Let the plots lead the discussion: reference charts repeatedly in the body and explain what each plot changes about the thesis.\n"
            "- When a chart materially supports a body section, place the relevant `[CHART: filename]` inline near that discussion, not only in `## Data & Charts`.\n"
            "- Do not write generic filler between sections; each paragraph should advance the argument.\n"
            "- In `## Data & Charts`, write a detailed analytical paragraph for EVERY chart (see chart catalogue)\n"
            "- Include the cross-agent dialogue insights: moments where quant spotted something and qual explained it\n"
            "- Prefer claims marked `verified` when the evidence digest distinguishes them\n"
            "- This is the final deliverable for senior leadership making real financial decisions\n"
            "- DO NOT produce a report without data analysis — if charts exist, they MUST be explained in depth\n\n"
            f"{context_for_prompt}\n\n{digest_for_prompt}{chart_catalogue}"
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
            try:
                brief = self.call_claude(brief_prompt)
            except Exception as e:
                logger.warning(f"[reporter] Slack brief generation failed (non-fatal): {e}")
                brief = summary[:500]

        # Build key events table and inject into report after Situation Overview
        events_table = ""
        if not dry_run:
            events = self._extract_timeline_events(summary, context)
            if events:
                events_table = self._build_events_table(events)
                logger.info(f"[reporter] Key events table: {len(events)} entries")

        chart_paths: dict[str, Path] = {}  # reporter summary charts removed (scenario/market were fabricated)

        # Build markdown: apply citations, then resolve [CHART: filename] placeholders
        cited_summary = self._apply_inline_citations(summary)

        # Build a filename→path lookup for fast placeholder resolution.
        # Charts start in reports_dir/ but _organise_run_outputs() later moves them to
        # reports_dir/charts/. We write image refs as "charts/{fname}" relative paths so
        # they remain valid after the move. Check both locations so this works regardless
        # of when the reporter runs relative to the organise step.
        import re as _re
        chart_lookup: dict[str, Path] = {}
        for entry in quant_charts:
            fname = entry.get("filename", "")
            if not fname:
                continue
            # prefer charts/ subdir if already moved, fall back to root
            for candidate in (config.REPORTS_DIR / "charts" / fname, config.REPORTS_DIR / fname):
                if candidate.exists():
                    chart_lookup[fname] = candidate
                    break

        def _resolve_chart_placeholder(m: "_re.Match[str]") -> str:
            fname = m.group(1).strip()
            if fname in chart_lookup:
                alt = Path(fname).stem.replace("_", " ").title()
                return f"![{alt}](charts/{fname})"
            return m.group(0)  # leave unresolved placeholders as-is
        cited_summary = _re.sub(r"\[CHART:\s*([^\]]+)\]", _resolve_chart_placeholder, cited_summary)

        # Fallback: any charts not referenced by the reporter get appended at end of Data & Charts
        referenced_fnames = set(_re.findall(r"\[CHART:\s*([^\]]+)\]", summary))
        unreferenced = [e for e in quant_charts if e.get("filename", "") not in referenced_fnames
                        and e.get("filename", "") in chart_lookup]
        if unreferenced:
            fallback = "\n\n_The following charts were generated but not explicitly placed above:_\n\n"
            for entry in unreferenced:
                fname = entry.get("filename", "")
                title = entry.get("title", fname)
                fallback += f"### {title}\n\n![{title}](charts/{fname})\n\n"
            # Insert fallback before the references/evidence section
            if "## Data & Charts" in cited_summary:
                cited_summary = cited_summary.replace(
                    "## Data & Charts", "## Data & Charts" + fallback, 1
                )
            else:
                cited_summary += "\n\n---\n\n## Data & Charts\n\n" + fallback

        banner = self._confidence_banner()
        md_with_charts = f"{banner}\n{cited_summary}" if banner else cited_summary

        # Inject key events table after ## Situation Overview (or ## Executive Summary as fallback)
        if events_table:
            for anchor in ("## Situation Overview", "## Core Analysis", "## Executive Summary"):
                if anchor in md_with_charts:
                    # Insert the table BEFORE the anchor section so it appears right after the intro
                    md_with_charts = md_with_charts.replace(anchor, events_table + "\n" + anchor, 1)
                    break
            else:
                # No matching section — append before Data & Charts
                if "## Data & Charts" in md_with_charts:
                    md_with_charts = md_with_charts.replace("## Data & Charts", events_table + "\n## Data & Charts", 1)
                else:
                    md_with_charts += "\n\n" + events_table

        references_section = self._references_section()
        if evidence_digest:
            md_with_charts = md_with_charts + "\n\n---\n\n" + evidence_digest
        if references_section:
            md_with_charts = md_with_charts + "\n\n---\n\n" + references_section

        # Collect ALL chart paths for notebook embedding — quant builder uses slug names
        # (e.g. 01_rate_spread_environment.png), reporter summary charts use chart_*.png.
        # Also check charts/ subdir in case _organise_run_outputs already ran.
        _all_pngs: list[Path] = []
        for _pattern in ("*.png", "charts/*.png"):
            _all_pngs.extend(config.REPORTS_DIR.glob(_pattern))
        all_pngs = sorted(set(_all_pngs), key=lambda p: p.stat().st_mtime)
        chart_paths = {p.stem.removeprefix("chart_"): p for p in all_pngs}

        report_path = self.write_report("Executive Summary", md_with_charts)

        # Build Jupyter notebook — primary output, open in VS Code
        nb_path = self._build_notebook(md_with_charts, chart_paths, report_path) if not dry_run else None

        # Build all-plots outputs — notebook (self-contained) + markdown (GitHub-renderable)
        all_plots_path = self._build_all_plots_notebook(all_pngs) if not dry_run and all_pngs else None
        all_plots_md_path = self._build_all_plots_md(all_pngs) if not dry_run and all_pngs else None

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
            "all_plots": str(all_plots_path) if all_plots_path else None,
            "all_plots_md": str(all_plots_md_path) if all_plots_md_path else None,
            "pdf": str(pdf_path) if pdf_path else None,
        }


def main(dry_run: bool = False) -> None:
    ReporterAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
