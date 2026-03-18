"""Post-report QA editor that requests one bounded reporter revision pass when needed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.agents.base import BaseAgent
from agentorg.evidence import EvidenceStore


class QAEditorAgent(BaseAgent):
    role = "qa_editor"

    def __init__(self, brief: str, research_plan: str) -> None:
        super().__init__()
        self.brief = brief
        self.research_plan = research_plan
        self.model = config.VERIFIER_MODEL
        self.store = EvidenceStore(config.REPORTS_DIR)

    def run(self, report_path: str, dry_run: bool = False) -> dict[str, Any]:
        if not report_path:
            raise ValueError("report_path is required for QAEditorAgent.run()")
        report_text = Path(report_path).read_text(encoding="utf-8")

        manifest_path = config.REPORTS_DIR / "charts_manifest.json"
        charts_manifest = []
        if manifest_path.exists():
            try:
                charts_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                charts_manifest = []

        claims = [claim.to_dict() for claim in self.store.claims() if claim.status == "verified"]
        agenda = [item.to_dict() for item in self.store.agenda() if item.priority == "high" and item.status != "done"]

        # In fast/prelim mode, truncate the report to avoid exceeding Groq's context limit.
        # Groq's llama-3.3-70b-versatile has a ~32k token context; a full report with
        # quant charts can exceed this. We send only the first portion of the report.
        report_for_qa = report_text[:8000] if config.FAST_MODE else report_text
        if config.FAST_MODE and len(report_text) > 8000:
            report_for_qa += "\n\n[... report truncated for fast-mode QA review ...]"

        prompt = (
            "You are a rigorous editor reviewing a research report before publication.\n"
            "You have: the original brief, the finished report, the list of charts produced,\n"
            "the list of verified claims, and any unresolved research questions.\n\n"
            "Score each dimension PASS or FAIL with a one-line reason:\n"
            "1. CHART COVERAGE: Every chart in the manifest is referenced and explained in the report narrative.\n"
            "2. CLAIM-NARRATIVE ALIGNMENT: The report's conclusions reflect the claims in claims.json. No major verified claim is absent from the narrative.\n"
            "3. BRIEF COMPLETENESS: The report answers what the brief asked. No major question from the brief is unaddressed.\n"
            "4. FORMATTING: Consistent headers, no broken markdown, tables render correctly, section flow is logical.\n"
            "5. EXECUTIVE ACCESSIBILITY: A smart non-specialist can read the executive summary and understand the key finding and its implications.\n\n"
            'If ALL five pass: output {"verdict": "APPROVED"}.\n\n'
            'If ANY fail: output {"verdict": "REVISE", "instructions": "Numbered list of specific fixes."}.\n'
            "Be ruthless but specific. Vague feedback is useless.\n\n"
            f"## Brief\n{self.brief}\n\n"
            f"## Research Plan\n{self.research_plan[:2000]}\n\n"
            f"## Charts Manifest\n{json.dumps(charts_manifest[:20], indent=2)}\n\n"
            f"## Verified Claims\n{json.dumps(claims[:20], indent=2)}\n\n"
            f"## Unresolved High-Priority Agenda\n{json.dumps(agenda[:10], indent=2)}\n\n"
            f"## Report\n{report_for_qa}"
        )

        if dry_run:
            payload = {"verdict": "APPROVED"}
        else:
            raw = self.call_claude(prompt).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                raw = raw.removeprefix("json").strip()
            payload = json.loads(raw)

        verdict = payload.get("verdict", "REVISE")
        instructions = payload.get("instructions", "")
        qa_report = self.write_report(
            "QA Editor Review",
            json.dumps({"verdict": verdict, "instructions": instructions}, indent=2),
        )
        logger.info(f"[qa_editor] Verdict: {verdict}")
        return {"verdict": verdict, "instructions": instructions, "report": str(qa_report)}


def main(dry_run: bool = False) -> None:
    raise SystemExit("QAEditorAgent is not intended to run standalone without a report path.")


if __name__ == "__main__":
    main()
