"""Mid-session critic that adds adversarial agenda items while there is still time to recover."""

from __future__ import annotations

import json
from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.agents.base import BaseAgent
from agentorg.evidence import EvidenceStore


class CriticAgent(BaseAgent):
    role = "critic"

    def __init__(self, evidence: EvidenceStore, research_plan: str) -> None:
        super().__init__()
        self.evidence = evidence
        self.research_plan = research_plan
        self.model = config.VERIFIER_MODEL

    def _current_turn_reports(self) -> str:
        sections: list[str] = []
        for role in ("qual_builder", "quant_builder"):
            files = sorted(
                config.REPORTS_DIR.glob(f"*_{role}_turn01.md"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if not files:
                continue
            content = files[0].read_text(encoding="utf-8")
            sections.append(f"## {role}\n\n{content}")
        return "\n\n---\n\n".join(sections)

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        claims = self.evidence.claims()
        if not claims:
            logger.warning("[critic] No structured claims found; skipping critic checkpoint")
            return {"status": "skipped", "count": 0}

        sources = self.evidence.sources()
        claims_blob = "\n".join(
            f"- {claim.id} | {claim.agent_role} | {claim.confidence:.2f} | {claim.statement}"
            for claim in claims
        )
        sources_blob = "\n".join(
            f"- {source.id} | {source.tier} | {source.title} | {source.publisher or source.url}"
            for source in sources[:20]
        )
        reports_blob = self._current_turn_reports()

        prompt = (
            "You are a rigorous intellectual critic reviewing preliminary research findings.\n"
            "Your job is NOT to summarise — it is to identify weaknesses.\n\n"
            "Look for:\n"
            "1. Claims that assert more than the evidence supports\n"
            "2. Contradictions between the qual and quant findings\n"
            "3. Important counterarguments or alternative interpretations not addressed\n"
            "4. Gaps: significant questions the brief implies but no agent has addressed\n"
            "5. Confirmation bias: sources selected only from one perspective\n\n"
            "Output ONLY a JSON array of challenge objects with this shape:\n"
            '[{"question":"...","owner":"qual|quant|shared","priority":"high","note":"..."}]\n'
            "Max 5 challenges. Prioritise ruthlessly.\n\n"
            f"## Research Plan\n{self.research_plan}\n\n"
            f"## Current Claims\n{claims_blob}\n\n"
            f"## Current Sources\n{sources_blob}\n\n"
            f"## Turn 1 Reports\n{reports_blob}"
        )

        if dry_run:
            payload: list[dict[str, Any]] = []
        else:
            raw = self.call_claude(prompt).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                raw = raw.removeprefix("json").strip()
            payload = json.loads(raw) if raw else []

        challenges = payload if isinstance(payload, list) else []
        self.evidence.add_agenda_items(challenges[:5], created_by=self.role)
        report_path = self.write_report(
            "Critic Checkpoint",
            json.dumps(challenges[:5], indent=2) if challenges else "[]",
        )
        logger.info(f"[critic] Added {len(challenges[:5])} challenge(s) to the agenda")
        return {"status": "ok", "count": len(challenges[:5]), "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    CriticAgent(EvidenceStore(config.REPORTS_DIR), "Standalone critic run").run(dry_run=dry_run)


if __name__ == "__main__":
    main()
