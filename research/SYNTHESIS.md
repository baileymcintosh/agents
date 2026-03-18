# Research Synthesis: How to Build AgentOrg Into a Best-in-Class Research System

**Authors:** Claude Code + Codex (collaborative)
**Date:** March 18, 2026
**Based on:** Research compiled in `research/` folder — foundational patterns, orchestration, evidence, memory, evaluation, HITL

---

## The Honest Starting Point

AgentOrg is a real research agent system that produces real output. The Iran-USA-Israel War 2026 report is materially better than what a single LLM call produces — it has parallel qual/quant threads, cross-agent evidence, structured charts, and a verification pass. That puts it ahead of most "agent" demos.

But compared to what the 2025-2026 research literature describes as best practice, there are four gaps that matter:

1. **No cross-session memory** — every project starts from zero
2. **No inline citation chain** — the report doesn't connect claims to sources
3. **No adaptive orchestration** — agents run for a fixed loop, don't genuinely replan
4. **No publication-boundary HITL** — the report pushes automatically after verifier PASS

These are not architectural flaws — they are missing capabilities on top of a sound foundation. The architecture Codex established (planner → collaborative session → verifier → reporter, with agenda-driven stopping and a structured evidence store) is exactly right. The gaps are incremental improvements, not rebuilds.

---

## What the Research Says Actually Matters Most

### 1. Reliability > Capability (Most Important Finding)

The single most consistent finding across all 2025-2026 research: **reliability is the #1 barrier to agent adoption**, ranked above cost and raw capability in surveys of 306 practitioners.

The compounding error problem is mathematically severe: a 95% per-step success rate yields only 60% task completion across a 10-step pipeline. For a research session with 20+ internal steps, the effective reliability of the whole system is the product of individual component reliabilities.

**What this means for us:** Every verification gate we add is not bureaucratic overhead — it is a multiplier on overall system reliability. The verifier is not optional. Neither is the claim-source matching. These are load-bearing components.

The most unreliable parts of our current system are:
- Qual builder's web search citations (text snippets, not structured records)
- Reporter's narrative (claims not linked to `claims.json`)
- No cross-session memory (no way to check if we've found conflicting evidence before)

### 2. Evidence Is Infrastructure, Not Feature (Second Most Important)

"Chain of Agents" (2025) established that long-context collaborative tasks require structured evidence handoff between agents — not text snippets. The `EvidenceStore` Codex built is the right substrate. The question is whether it's being fully used.

Currently the evidence store is written to but not *read from* mid-session. Agents don't query it to check what the other agent has found. This defeats a significant portion of its value.

**The key improvement:** At the start of each turn, both qual and quant should receive a brief summary of what the other agent has found so far — not the full text, but the claims and top sources from `claims.json` and `sources.json`. This creates genuine cross-agent evidence sharing, which is what the multi-agent literature identifies as the primary driver of quality improvement over single-agent.

### 3. Memory Is the Gap Between Prototype and Product

Right now AgentOrg has no memory across sessions. After the Iran project completes, the next project starts with zero knowledge of:
- Which sources were reliable for geopolitical topics
- What we found about oil market dynamics
- Which agenda items we failed to resolve

A-MEM (arxiv 2502.12110) is the most applicable design: structured notes with links between related findings, queryable at the start of each new project. This is the single highest-leverage unimplemented capability.

**The minimum viable memory implementation:**
After each project closes, write a `project_memory.json` to the project directory:
```json
{
  "project": "iran-us-economy-2026",
  "key_sources": [...],  // top 10 sources by tier rank
  "key_findings": [...], // core claims that passed verification
  "open_questions": [...] // unresolved high-priority agenda items
}
```
At the start of related future projects, retrieve relevant entries. This is 80% of the value with 20% of the complexity of a full A-MEM implementation.

### 4. Adaptive Orchestration Compounds Gains

Difficulty-aware routing (arxiv 2509.11079) achieves 11% accuracy improvement at 36% lower cost. For AgentOrg, this means:
- Simple agenda items (e.g., "retrieve Brent crude prices from yfinance") → Groq Llama (fast, cheap)
- Complex agenda items (e.g., "synthesize geopolitical implications of X for US fiscal policy") → Claude Opus
- Classification happens at agenda item creation time, not at session start

This is distinct from our current prelim/deep model selection, which applies at the session level. Subtask-level routing would dramatically reduce cost per deep run.

---

## Recommended Roadmap (Priority Order)

### Phase 1: Close the Evidence Loop (Immediate — 1 week)
**Goal:** Make the evidence store bidirectional during sessions.

1. **Reporter cites evidence.** Reporter reads `claims.json` and `sources.json`, embeds inline citations in the narrative (`[SRC_abc123]`), and appends a references section. This is the single highest-impact visible change — the report becomes auditable.

2. **Cross-agent evidence summary.** At the start of each turn, inject a brief of what the *other* agent has found (top 3 claims, top 3 sources). Qual gets quant's findings; quant gets qual's findings. This creates genuine cross-validation, not just parallel running.

3. **Verifier escalation message.** `NEEDS REVISION` sends a Slack/notification rather than blocking silently. User decides whether to re-run.

### Phase 2: Add Cross-Session Memory (Next — 2 weeks)
**Goal:** Each project benefits from prior projects.

1. **Project memory file.** Write `project_memory.json` at session close with key sources, verified findings, and open questions.
   Status: implemented in the current repo pass.

2. **Memory-seeded agenda.** When a new project is similar to a prior one (same domain, overlapping topics), load the prior open questions as seed agenda items.
   Status: implemented in the current repo pass.

3. **Source reputation registry.** A shared `source_registry.json` across all projects — sources that have been consistently Tier 1-2, sources that have been flagged by the verifier. Loaded at session start to weight source selection.
   Status: implemented in lightweight form in the current repo pass.

### Phase 3: Adaptive Cost Routing (Following — 1 month)
**Goal:** Cut deep run cost by 30-40% without quality loss.

1. **Agenda item difficulty classification.** At bootstrap, classify each agenda item as `simple` / `complex` / `synthesis`. Store in `AgendaItem.difficulty`.
   Status: implemented in the current repo pass.

2. **Model selection per item.** `simple` → Groq Llama; `complex` → Claude Sonnet; `synthesis` → Claude Opus. The session loop passes the appropriate model config to each `run_turn()` call.

3. **Dynamic agenda expansion cap.** Limit total agenda items per session to `budget / avg_item_cost` to prevent runaway sessions.
   Status: implemented in simple capped form in the current repo pass; per-item cost routing remains future work.

### Phase 4: Publication Boundary HITL (Following — 2 weeks)
**Goal:** Human signs off before any output leaves the system.

1. **`agentorg approve <run_id>`** command. Shows: verifier verdict, claim count, source count, unresolved agenda items, list of core claims with confidence scores. User types `yes` or `no`.

2. **Confidence-flagged report header.** If any core claim confidence < 0.6, the report header includes: "This report contains claims with limited source corroboration. See verification report for details."

3. **Automated Slack summary.** After session completes (before approval gate), post a one-paragraph summary to Slack with a link to the approval command. User gets notified, reviews in < 1 minute, approves from their phone.

---

## What Codex Should Build Next

Per the CODEX_LOG handoff, three targets remain from the refactor:

**1. Surface citations from `claims.json`/`sources.json` in reporter output**
This is Phase 1, item 1 above. Most impactful immediate change. The reporter already reads `charts_manifest.json` — the same pattern works for evidence. At the end of the report, append:

```markdown
## Sources
| ID | Title | Tier | Publisher |
|---|---|---|---|
| SRC_abc123 | IEA March 11 Release | tier1_primary | IEA |
...
```

And inline in the narrative: "The supply shortfall is estimated at 8 million bpd [SRC_abc123, SRC_def456]."

**2. Fix temp-dir permission issue blocking pytest**
This is a Windows-specific issue with pytest's tmp_path fixture. Fix: add `tmp_path_retention_policy = "none"` to `pyproject.toml` under `[tool.pytest.ini_options]`, and ensure `conftest.py` uses `tempfile.mkdtemp()` with explicit cleanup rather than pytest's `tmp_path`.

**3. Deprecate stale builder/planner code paths**
Move legacy `builder` agents to `src/agentorg/legacy/` with a deprecation warning in their `__init__`. Don't delete — keep for compatibility — but make the directory name communicate that these are not the primary path.

---

## The Vision: What This System Looks Like in 6 Months

A user opens VSCode, pastes a research brief, runs `agentorg new`. Within 2 minutes, they receive a Slack message: "Prelim complete. Here's what we found and what we still don't know. Approve deep run? [yes/no]"

They approve. 45-60 minutes later, another Slack message: "Deep run complete. 23 claims verified, 2 flagged for review. Report ready. Approve publication? [yes/no]"

They review the two flagged claims (takes 90 seconds), approve, and the report is live on GitHub with full citation trail.

The report itself reads like a high-quality analyst note — every factual claim linked to a source, every chart explained with both data interpretation and qualitative context, a scenario table with explicit probability weights.

This is achievable with 4-6 weeks of incremental work on top of what Codex has built.

---

## Papers Worth Reading in Full (Priority Order)

1. **arxiv 2512.13564** — Memory in the Age of AI Agents (Dec 2025) — the most comprehensive treatment of agent memory; directly applicable
2. **arxiv 2502.12110** — A-MEM: Agentic Memory for LLM Agents (Feb 2025) — the specific implementation most relevant to AgentOrg
3. **arxiv 2509.11079** — Difficulty-Aware Agent Orchestration — the cost-routing paper; quantifies the gains precisely
4. **arxiv 2501.06322** — Multi-Agent Collaboration Mechanisms Survey — best overview of collaboration patterns
5. **arxiv 2601.13671** — The Orchestration of Multi-Agent Systems (Jan 2026) — most up-to-date orchestration taxonomy
6. **LangChain State of Agent Engineering 2025** — the practitioner survey; most grounded in production reality
7. **AFlow (arxiv 2410.10762)** — Automating Agentic Workflow Generation — most applicable to adaptive planning
