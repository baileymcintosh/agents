# Codex ↔ Claude Code — Collaboration Log
**Project:** `baileymcintosh/agents` (AgentOrg)
**Started:** 2026-03-17
**Purpose:** Codex leads structural refactoring; Claude Code provides context and flags disagreements inline.

---

## Green Light

Codex — you have full authorisation to make fixes and commits to this repo. Document every meaningful decision here as you go. If Claude Code adds a note marked **[CC NOTE]**, treat it as context or a disagreement worth reading before proceeding, not a blocker unless it says so explicitly.

---

## Priority Order (agreed)

1. **Collapse to one orchestration path** — `team_planner → collaborative session → verifier → reporter`. Retire or clearly demote the legacy `runner.py` sequential flow.
2. **Introduce a first-class evidence layer** — source objects, claim objects, citation IDs, confidence scores, per-claim provenance carried end-to-end.
3. **Upgrade verification** — check explicit claims against source records and data artifacts; gate final synthesis on pass/fail, not just "review the markdown."
4. **Agenda-driven replanning** — replace fixed-turn collaboration with unresolved-question tracking, assigned owners, stopping criteria, and budget-aware continuation.
5. **Developer ergonomics** — one-command local setup, reliable tests, importable package defaults, no user/machine-specific path assumptions.

---

## Context Codex Should Know Before Starting

### Why there are two orchestration paths
The `runner.py` sequential flow came first and was the working default. The `session.py` collaborative engine was added later in a separate session and never fully wired as the default — it was left behind a separate CLI command while work continued on output quality (charts, reports). This was deliberate deferral, not design. It is now tech debt.

### Why Groq routing exists in qual_builder.py
`QUAL_BUILDER_MODEL` can be set to a Groq model (e.g. `llama-3.3-70b-versatile`) for preliminary/cheap runs. The `_is_groq_model()` check routes to `https://api.groq.com/openai/v1` using the OpenAI SDK's `base_url` param. This is intentional and should be preserved — it's the cost-control lever for prelim runs vs. deep runs.

### Why charts_manifest.json exists
The quant builder writes a manifest after each chart; the reporter reads it to embed all charts with descriptions. This decouples the two agents — quant doesn't need to know the report format, reporter doesn't need to know how charts were generated. Keep this pattern.

### Why AgentMessenger accepts optional args
`AgentMessenger.__init__` was recently made to accept optional `session_dir` and `run_id` because standalone `run()` methods on each builder call it without a session context. This was a bug fix, not a design choice — feel free to redesign if the standalone `run()` pattern goes away.

### The source reliability framework
A 5-tier source framework lives in `agent_docs/qual_builder.md`. It is currently documentation only — not enforced in code. Priority 2 (evidence layer) should make this enforceable.

### Package / env
- Python package: `src/agentorg/`
- Dependency manager: `uv` (see `pyproject.toml`)
- Key env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `FRED_API_KEY`, `TAVILY_API_KEY`
- Models: Opus 4.6 for planner/debugger, Sonnet 4.6 for quant/reporter, Groq Llama 3.3 70B for prelim qual

---

## Log

### [2026-03-17] — Codex initial assessment
Codex reviewed the repo cold and identified:
- Dual orchestration paths (runner.py vs session.py)
- Verifier only checks `*_builder_*.md` — misses collaborative session output
- Fixed-turn collaboration cap (48 turns, 10-min subprocess limit)
- No source/claim/citation objects — provenance is text-only
- Hardcoded reporter metadata, machine-specific path assumptions
- pytest fails from defaults (pytest-cov missing, src import issues)

Full assessment: see user conversation 2026-03-17.

---

_Codex: add entries below as you work. Format: `### [DATE] — Brief title` followed by what you changed and why._
