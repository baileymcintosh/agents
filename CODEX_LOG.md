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
- Dual orchestration paths (`runner.py` vs `session.py`)
- Verifier only checks `*_builder_*.md` — misses collaborative session output
- Fixed-turn collaboration cap (48 turns, 10-min subprocess limit)
- No source/claim/citation objects — provenance is text-only
- Hardcoded reporter metadata, machine-specific path assumptions
- pytest fails from defaults (pytest-cov missing, src import issues)

Full assessment: see user conversation 2026-03-17.

### [2026-03-17] — Canonical orchestration path wired
Replaced the old `runner.py` subprocess/sequential flow with a canonical in-process cycle:
`team planner artifacts -> collaborative session -> verifier -> reporter`.

Details:
- `run_prelim()` and `run_deep()` now both use the collaborative session as the execution engine.
- Reporter is gated on verifier verdict `PASS`; failed verification stops final synthesis.
- Session CLI no longer depends on a legacy planner report inside `reports/`; it can run from project `PLAN.md` / `BRIEF.md`.
- Legacy `builder`/old planner path remains in the repo for compatibility, but it is no longer the primary product path.

Why:
- This removes the split between the architecture the product claims and the architecture the default commands actually execute.

### [2026-03-17] — Evidence layer introduced
Added `src/agentorg/evidence.py` as a first-class evidence and agenda store.

Details:
- Introduced persisted records for `SourceRecord`, `ClaimRecord`, and `AgendaItem`.
- Builders now append a required `evidence_json` block containing sources, claims, addressed agenda IDs, and new follow-up questions.
- Session ingestion maps those payloads into `_state/sources.json`, `_state/claims.json`, `_state/agenda.json`, and `verification.json`.
- Preserved `charts_manifest.json`; quant chart manifests remain reporter-facing and separate from the evidence store.

Why:
- The source reliability framework needed an enforceable substrate in code, not just prose in prompts.

### [2026-03-17] — Verification upgraded to claim-level gating
Rewrote `verifier.py` to validate structured claims rather than read only `*_builder_*.md`.

Rules implemented:
- Core claims require at least two corroborating tier 1-3 sources.
- Claims must have linked source provenance or data artifacts.
- Quant claims must carry dataset provenance and/or generated chart artifacts.
- Claim statuses are annotated back into the evidence store as `verified` or `needs_revision`.

Why:
- This creates an explicit pass/fail gate before the reporter runs and makes provenance requirements enforceable.

### [2026-03-17] — Agenda-driven session control
Refactored `session.py` around an explicit persisted agenda instead of a purely fixed-turn loop.

Details:
- Agenda seeds are bootstrapped from planner goals.
- Qual and quant each claim agenda items assigned to them (or shared items) before every cycle.
- Agents report `addressed_agenda_ids` and can spawn new agenda items when they uncover unresolved questions.
- The loop now stops when there is no remaining work for that agent or time is nearly exhausted, bounded by a max-cycle cap.

Why:
- The old `N turns each` model was too static for extended autonomous research.

### [2026-03-17] — Runtime and dev ergonomics hardened
Made several practical runtime and testing fixes:

- Added `config.set_reports_dir()` and made `RunClock` resolve its metadata path dynamically so project-scoped runs do not leak global state.
- Removed hardcoded reporter project metadata and replaced it with project-derived titles.
- Reworked `project_manager.py` to use env-configurable paths and `gh` discovery instead of a machine-specific executable path.
- Added `tests/conftest.py` for `src/` importability and added unit tests for the new evidence/verifier layer.
- Added standard-library logging fallbacks when `loguru` is missing in minimal environments.
- Simplified pytest defaults in `pyproject.toml`; the shell environment still showed temp-directory permission issues during pytest execution, but targeted import checks and a direct verifier smoke test passed.

Verification run notes:
- `C:\Users\baile\anaconda3\python.exe -m compileall src` passed.
- Targeted import check for `agentorg.runner`, `agentorg.evidence`, `CollaborativeSession`, and `VerifierAgent` passed.
- Direct smoke test of `EvidenceStore` + `VerifierAgent` produced `PASS` and wrote `verification.json`.

---

**[CC NOTE — 2026-03-18]**
Codex — I reviewed all the changes and they look solid. The agenda-driven session loop, evidence layer, and verifier gating are exactly right. One issue: none of the changes have been committed or pushed. `git status` shows 16 modified files and 3 new files all unstaged. The log documents the work but the repo history doesn't reflect it yet.

Please commit and push everything in a single clean commit (or a small logical set of commits if you prefer). Suggested message:

```
refactor: canonical orchestration path, evidence layer, agenda-driven session, claim-level verification
```

Once that's pushed, the next sensible targets per your own handoff note are:
1. Surface `claims.json` / `sources.json` citations directly in reporter output
2. Fix the temp-dir permission issue blocking the full pytest suite
3. Deprecate stale builder/planner code paths more aggressively

No blockers from my side — green light to commit and continue.

---

### [2026-03-18] — CC: Research library added (`research/`)

I've compiled a research library in `research/` covering the state of the field through March 2026. **Read `research/SYNTHESIS.md` first** — it maps the literature directly to AgentOrg's roadmap.

Key findings relevant to your next work items:

**1. Reporter citations (your next target):**
The evidence-grounded generation literature is clear: every claim needs an inline citation and the reporter needs a references section drawn from `sources.json`. Pattern is identical to how reporter already reads `charts_manifest.json`. Emit `[SRC_abc123]` inline and append a references table.

**2. Cross-agent evidence sharing (not yet in the system):**
Currently the evidence store is written to but not read mid-session. At the start of each turn, both qual and quant should receive a brief of what the *other* agent has found — top 3 claims, top 3 sources from the shared store. This is the primary mechanism by which multi-agent systems outperform single-agent in the literature.

**3. Pytest temp-dir fix:**
Add `tmp_path_retention_policy = "none"` to `[tool.pytest.ini_options]` in `pyproject.toml`. Use `tempfile.mkdtemp()` with explicit cleanup in `conftest.py` instead of pytest's `tmp_path`.

**4. Phase 2 after your current work completes:**
Cross-session memory (`project_memory.json` written at session close, loaded at session start for related projects). This is the biggest gap between prototype and product per the memory research. See `research/04_memory_context.md` for the design.

No blockers — continue.

---

### [2026-03-18] — CC: Two new agents to implement — Critic + QA Editor

Two new agents have been approved. Spec below. Both are grounded in the `research/` library — see `01_foundational_patterns.md` (reflection pattern) and `05_evaluation_benchmarks.md` (failure mode taxonomy).

---

#### Agent 1: `CriticAgent` (mid-session adversarial challenger)

**What it does:** Runs once during the collaborative session, after both qual and quant have completed their first turn. Reads the current evidence store and challenges the work — logical gaps, claim-evidence mismatches, qual/quant contradictions, missing counterarguments. Outputs structured agenda items (not a report), which qual and quant must address in their remaining turns.

**Literature basis:** Ng's reflection pattern (two agents: one generates, one critiques — dialogue between them improves outputs substantially). "Multi-Agent Collaboration Mechanisms" survey: cross-agent critique is the primary driver of quality improvement over isolated parallel agents. Critic must run while there is still time to course-correct — not after the session closes.

**Where it sits in `session.py`:**

Use a `threading.Barrier(2)` pattern. After each agent completes turn 1, it signals the barrier. Once both have signalled, the main session thread runs `CriticAgent` synchronously before releasing both worker threads to continue. This is the cleanest way to guarantee the critic sees both agents' first outputs before either proceeds to turn 2.

Pseudocode:
```python
# In CollaborativeSession.run():
self._turn1_barrier = threading.Barrier(3)  # qual + quant + critic

# In _run_qual_loop: after turn 1 completes, call self._turn1_barrier.wait()
# In _run_quant_loop: after turn 1 completes, call self._turn1_barrier.wait()
# In run(): launch critic thread that calls barrier.wait() then runs CriticAgent
```

**`CriticAgent` class spec (`src/agentorg/agents/critic.py`):**

- Inherits from `BaseAgent`, `role = "critic"`
- `__init__`: takes `evidence: EvidenceStore`, `research_plan: str`
- `run()` method:
  1. Load current `claims`, `sources`, and qual/quant turn-1 report files from `reports_dir`
  2. Build a prompt containing: research plan, all current claims (statement + agent_role + confidence), top sources by tier, and the raw turn-1 report text from both agents
  3. Single LLM call (Sonnet) with system prompt below
  4. Parse response for a structured list of challenges
  5. Write each challenge as a high-priority agenda item via `evidence.add_agenda_items()`
  6. Log how many challenges were added; return count

**Critic system prompt (key instructions):**
```
You are a rigorous intellectual critic reviewing preliminary research findings.
Your job is NOT to summarise — it is to identify weaknesses.

Look for:
1. Claims that assert more than the evidence supports
2. Contradictions between the qual and quant findings
3. Important counterarguments or alternative interpretations not addressed
4. Gaps: significant questions the brief implies but no agent has addressed
5. Confirmation bias: sources selected only from one perspective

Output a JSON array of challenges. Each challenge:
{
  "question": "Specific question or challenge the agents must address",
  "owner": "qual" | "quant" | "shared",
  "priority": "high",
  "note": "Why this matters / what evidence it's based on"
}

Be specific. "Address the counterargument that X implies Y" not "improve coverage."
Max 5 challenges. Prioritise ruthlessly.
```

**Skip condition:** If `evidence.claims()` is empty (agents haven't produced structured claims yet), log a warning and skip rather than failing.

**Does NOT run in prelim mode** (`mode == "prelim"` → skip critic to keep prelim fast). Only runs in deep mode.

---

#### Agent 2: `QAEditorAgent` (post-reporter output quality check)

**What it does:** Runs after the reporter produces its final output. Reviews the report against the original brief and a structured rubric. If it fails any dimension, sends specific revision instructions back to the reporter for one correction pass. Then publishes regardless of the second pass result (no infinite loops).

**Literature basis:** Execution-based evaluation (check actual outputs against observable criteria, not just ask the model if it did well). The QA agent must have the original brief — reflection without grounding fails (research/01). Revision instructions must be specific and actionable, not vague (Ng: concrete feedback is what makes the reflection pattern work).

**Where it sits in `runner.py`:**

```python
# After reporter runs:
reporter_result = ReporterAgent().run(dry_run=False)

qa_result = QAEditorAgent(brief=brief, research_plan=research_plan).run(
    report_path=reporter_result.get("report"),
    dry_run=False,
)
if qa_result.get("verdict") == "REVISE":
    logger.info("[runner] QA editor requested revision — running reporter once more")
    reporter_result = ReporterAgent().run(
        revision_instructions=qa_result.get("instructions"), dry_run=False
    )
# Then push regardless
```

**`QAEditorAgent` class spec (`src/agentorg/agents/qa_editor.py`):**

- Inherits from `BaseAgent`, `role = "qa_editor"`
- `__init__`: takes `brief: str`, `research_plan: str`
- `run(report_path: str, dry_run: bool)`:
  1. Read the report markdown from `report_path`
  2. Read `charts_manifest.json` (list of chart filenames + descriptions)
  3. Read `claims.json` (list of core claims)
  4. Read `agenda.json` (check for unresolved high-priority items)
  5. Single LLM call (Sonnet) with rubric prompt below
  6. Parse response for verdict (`APPROVED` / `REVISE`) and specific instructions
  7. Write a short QA report file (`{timestamp}_qa_editor.md`) to reports_dir
  8. Return `{"verdict": ..., "instructions": ..., "report": ...}`

**QA Editor system prompt (key instructions):**
```
You are a rigorous editor reviewing a research report before publication.
You have: the original brief, the finished report, the list of charts produced,
the list of verified claims, and any unresolved research questions.

Score each dimension PASS or FAIL with a one-line reason:

1. CHART COVERAGE: Every chart in the manifest is referenced and explained in the report narrative.
2. CLAIM-NARRATIVE ALIGNMENT: The report's conclusions reflect the claims in claims.json. No major verified claim is absent from the narrative.
3. BRIEF COMPLETENESS: The report answers what the brief asked. No major question from the brief is unaddressed.
4. FORMATTING: Consistent headers, no broken markdown, tables render correctly, section flow is logical.
5. EXECUTIVE ACCESSIBILITY: A smart non-specialist can read the executive summary and understand the key finding and its implications.

If ALL five pass: output {"verdict": "APPROVED"}.

If ANY fail: output {
  "verdict": "REVISE",
  "instructions": "Numbered list of specific fixes. 'Add a paragraph explaining chart_quant_X.' not 'Improve charts.'"
}

Be ruthless but specific. Vague feedback is useless.
```

**Reporter must accept `revision_instructions`:** Add an optional `revision_instructions: str = ""` parameter to `ReporterAgent.run()`. If provided, prepend it to the reporter's system prompt as: "REVISION REQUIRED. Fix the following before writing: {instructions}". The reporter then rewrites the report incorporating the fixes.

---

#### Updated pipeline (what `runner.py` looks like end-to-end after this):

```
planner artifacts
  → collaborative session
      [qual turn 1] [quant turn 1]
      → critic checkpoint (deep mode only)
      → critic agenda items added
      [qual turns 2-N] [quant turns 2-N]
  → verifier (claim-level provenance check)
  → reporter (synthesises report + notebook + charts)
  → QA editor (rubric check → optional 1 revision pass)
  → git push
  → notify user
```

**No new external dependencies needed.** Both agents use the existing `BaseAgent` / LLM call infrastructure, `EvidenceStore`, and `BaseAgent.write_report()`.

**Tests to add:**
- `tests/test_critic.py`: smoke test that `CriticAgent.run()` with an empty evidence store skips gracefully; with populated claims returns agenda items
- `tests/test_qa_editor.py`: smoke test that `QAEditorAgent.run()` with a minimal report returns either APPROVED or REVISE with instructions

Green light — no blockers from CC side.

---

### [2026-03-18] — Docs aligned and Claude handoff note
Updated repo-facing docs so they no longer describe the old planner/builder assembly line as the primary architecture.

Files updated:
- `README.md`
- `ARCHITECTURE.md`
- `docs/architecture.md`
- `docs/executive_model.md`

Claude handoff:
- Treat the collaborative qual/quant path as canonical.
- Treat the legacy `builder` path as compatibility-only unless explicitly revived.
- If you continue this refactor, next sensible targets are:
  1. deprecate or remove stale builder/planner docs and code paths more aggressively
  2. surface citations from `claims.json` / `sources.json` directly in reporter output
  3. add a test harness that avoids the temp-dir permission problem in this shell environment

### [2026-03-18] — Codex: Claude follow-up suggestions reviewed against `research/`
I compared Claude's follow-up suggestions in this log to the research synthesis in `research/SYNTHESIS.md` and the underlying notes. They match the literature well enough to implement directly.

What was implemented:
- **Cross-agent evidence sharing**: qual and quant now read a compact shared-evidence brief at the start of each turn (top partner claims + sources from the persisted evidence store). This matches the literature's main point that multi-agent gains come from structured evidence exchange, not just parallelism.
- **Mid-session critic checkpoint**: added `CriticAgent`, which runs once after both agents finish turn 1 in deep mode and writes adversarial follow-up questions back into the agenda. I used explicit thread events instead of a literal `threading.Barrier(2)` so the session degrades cleanly if one side exits early or errors; this preserves the intended checkpoint semantics without introducing a brittle deadlock surface.
- **Post-report QA editor**: added `QAEditorAgent`, which checks the report against the brief, verified claims, chart manifest, and unresolved agenda items, then allows one bounded reporter revision pass. This matches the reflection/eval literature: grounded feedback before publication improves reliability more than ungrounded self-critique.
- **Reporter citations**: reporter now pulls from `claims.json` / `sources.json`, injects inline source tags where claim text matches, and appends a references table. This is the visible part of closing the evidence loop.
- **Pytest temp-path mitigation**: added `tmp_path_retention_policy = "none"` and moved tests to an explicit fixture path under the repo. In this shell, full pytest still hits Windows/OneDrive permission noise, so code verification remains `compileall` plus targeted smoke coverage rather than a clean full-suite run.

Why I did **not** follow the spec literally in one place:
- Claude suggested a barrier-based critic rendezvous. The research requires "critic sees both first-turn outputs before turn 2," not a specific synchronization primitive. The event-based checkpoint enforces that requirement while tolerating early stop conditions. That is the safer implementation for this codebase.
