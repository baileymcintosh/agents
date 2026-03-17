"""
TeamPlanner — reads a task brief and designs a custom agent team.

Uses Opus (smart, expensive) but only called once per project.
Returns a structured team plan that gets written to PLAN.md and
shown to the user for approval before any research starts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger

from agentorg import config
from agentorg.agents.base import BaseAgent


# All available agent roles and what they're good for
AVAILABLE_AGENTS = {
    "researcher": "Web search + qualitative synthesis. Good for: news, policy, events, narrative.",
    "data_analyst": "Python execution + live market data (yfinance, FRED, EIA). Good for: charts, numbers, time-series.",
    "coder": "Writes and executes code. Good for: building tools, interfaces, scripts, data pipelines.",
    "quant_builder": "Deep quantitative research + annotated charts. Good for: macro/finance data work.",
    "qual_builder": "Deep qualitative research + policy analysis. Good for: geopolitics, events, opinions.",
    "verifier": "Fact-checks and stress-tests outputs. Good for: any project needing QA.",
    "reporter": "Final synthesis into polished report/notebook. Always included.",
}

PLAN_SCHEMA = """
Return a JSON object with this exact structure:
{
  "team": ["agent1", "agent2", ...],
  "rationale": "one sentence on why this team fits the task",
  "prelim_goals": ["goal 1", "goal 2", "goal 3"],
  "deep_goals": ["goal 1", "goal 2", "goal 3", "goal 4", "goal 5"],
  "key_data_sources": ["source 1", "source 2"],
  "expected_outputs": ["output 1", "output 2"],
  "project_name": "short-slug-no-spaces"
}

Rules:
- team must be chosen from: """ + ", ".join(AVAILABLE_AGENTS.keys()) + """
- reporter is always included
- prelim_goals: 3 fast validation goals achievable in <10 min with cheap models
- deep_goals: 5 substantive research goals for the full run
- project_name: lowercase, hyphens only, max 30 chars
"""


class TeamPlannerAgent(BaseAgent):
    role = "team_planner"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.PLANNER_MODEL  # Opus — worth it, called once

    def plan(self, brief: str) -> dict:
        """Read a brief, design a team, return structured plan."""
        logger.info("[team_planner] Designing team for brief...")

        prompt = f"""You are a research director designing a custom agent team for a specific project.

Available agents:
{chr(10).join(f'- {name}: {desc}' for name, desc in AVAILABLE_AGENTS.items())}

Task brief:
{brief}

{PLAN_SCHEMA}

Think carefully about what this task actually needs. A poker interface needs a coder.
A macro research project needs data_analyst + qual_builder. Don't over-staff — pick the right 3-5 agents.
"""
        raw = self.call_claude(prompt)

        # Extract JSON from response
        match = re.search(r'\{[\s\S]+\}', raw)
        if not match:
            raise ValueError(f"TeamPlanner returned no JSON:\n{raw[:500]}")

        plan = json.loads(match.group())

        # Always ensure reporter is in team
        if "reporter" not in plan.get("team", []):
            plan["team"].append("reporter")

        return plan

    def write_plan_md(self, brief: str, plan: dict, plan_path: Path) -> None:
        """Write a human-readable PLAN.md for approval."""
        team_lines = []
        for agent in plan["team"]:
            desc = AVAILABLE_AGENTS.get(agent, "")
            team_lines.append(f"| `{agent}` | {desc} |")

        prelim = "\n".join(f"- {g}" for g in plan.get("prelim_goals", []))
        deep = "\n".join(f"- {g}" for g in plan.get("deep_goals", []))
        sources = "\n".join(f"- {s}" for s in plan.get("key_data_sources", []))
        outputs = "\n".join(f"- {o}" for o in plan.get("expected_outputs", []))

        content = f"""# Project Plan: {plan.get('project_name', 'untitled')}

## Brief
{brief}

## Proposed Team
{plan.get('rationale', '')}

| Agent | Role |
|---|---|
{chr(10).join(team_lines)}

## Preliminary Run Goals (< 10 min)
{prelim}

## Deep Research Goals
{deep}

## Key Data Sources
{sources}

## Expected Outputs
{outputs}

---
**To approve:** tell me "looks good" or "approve"
**To change:** tell me what to adjust and I'll revise the plan
"""
        plan_path.write_text(content, encoding="utf-8")
        logger.info(f"[team_planner] Plan written → {plan_path}")

    def run(self, dry_run: bool = False) -> dict:
        return {"status": "use plan() directly"}
