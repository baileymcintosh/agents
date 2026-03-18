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
