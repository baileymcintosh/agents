# Agent Evaluation & Benchmarks

**Compiled:** March 2026 | **Sources:** o-mega.ai benchmark guide, arxiv 2601.01743, Evidently AI, simmering.dev

---

## Why Evaluation Is Hard for Agents

Standard model evaluation (accuracy on a fixed test set) does not transfer to agents. Agents are evaluated on:
- **Long-horizon tasks** where errors compound across steps
- **Tool-use correctness** which requires execution, not just output inspection
- **Non-deterministic behavior** that makes reproducibility difficult
- **Emergent failure modes** that only appear at the system level, not the component level

The AI Agent Evaluation Crisis (Adaline Labs, 2025) documents that most popular benchmarks contain significant evaluation flaws that produce misleading performance estimates when taken at face value.

---

## Key Benchmarks (2025-2026)

### GAIA (General AI Assistant)
466 human-curated tasks requiring multi-step reasoning, tool use, and multimodal understanding. Designed to test realistic, open-ended assistant capability.

**Current SOTA (end 2025):** 90% overall; Level 3 (hardest) top score: 61% (Writer's Action Agent)
**What it tests:** Can the agent complete realistic multi-step tasks that require web search, document reading, and synthesis?
**Limitation:** Tasks are relatively bounded; doesn't test sustained autonomous research over hours

### SWE-bench (Software Engineering)
2,200+ real GitHub issues requiring code patches. Tests whether an agent can understand a large codebase and fix real bugs.

**Current SOTA (end 2025):** 74.4% (SWE-bench Verified variant)
**What it tests:** Code understanding, planning, tool use in a real-world software context
**Relevance to AgentOrg:** Low for research output quality; high for agent infrastructure correctness

### WebArena / WorkArena
Agents complete realistic web-based tasks (booking, form submission, information retrieval) in simulated browser environments.
**What it tests:** Multi-step tool use reliability, error recovery

### BFCL (Berkeley Function Calling Leaderboard)
Evaluates tool/function calling accuracy across diverse APIs.
**Current SOTA:** 77.5%
**What it tests:** Whether agents call tools with correct parameters — directly relevant to our `PythonExecutor` and search tool reliability

### AgentBench
Multi-environment benchmark covering web, database, OS, and game tasks. Tests generalisation across domains.

---

## The Reliability Gap for Enterprise

Paul Simmering's analysis (simmering.dev) is the clearest statement of the practical problem:

> Agent benchmarks measure peak capability in controlled conditions. Enterprise deployment requires *reliable* capability across diverse, uncontrolled inputs. These are different things.

Key findings from the 2025 survey of 306 AI agent practitioners:
- **Reliability is the #1 barrier** to enterprise adoption — above cost, capability, and compliance
- Long-horizon tasks amplify compounding errors — a 95% per-step success rate yields 60% task completion over 10 steps
- Nondeterminism makes debugging difficult without standardised protocols

**The 10-step compounding problem:**
| Per-step success | 5-step task | 10-step task | 20-step task |
|---|---|---|---|
| 99% | 95% | 90% | 82% |
| 95% | 77% | 60% | 36% |
| 90% | 59% | 35% | 12% |

This table explains why research agents that run for many turns fail more than short single-turn agents — and why verification gates (like AgentOrg's verifier) are not just nice-to-haves but essential reliability infrastructure.

---

## What Good Agent Evaluation Looks Like

### Execution-Based Evaluation (2025 Standard)
Run the tool call and check the outcome. Don't ask the model whether it succeeded — observe whether it did. Our `PythonExecutor` captures stdout/stderr/charts; this is execution-based evaluation for code.

### Process Traces, Not Just Outputs
Evaluate the reasoning chain, not just the final answer. An agent that gets the right answer for the wrong reason is unreliable on variants of the task.

### Failure Mode Taxonomy
Distinguish between:
1. **Hallucination failures** — agent generates false claims
2. **Tool failures** — agent calls tools incorrectly or ignores tool output
3. **Planning failures** — agent pursues a strategy that cannot succeed
4. **Verification failures** — agent does not catch its own errors

AgentOrg's verifier addresses failure modes 1 and 4. Tool observability addresses failure mode 2. Agenda-driven planning addresses failure mode 3.

---

## Recommended Internal Evals for AgentOrg

Since standard benchmarks don't cover research agent quality, we should define our own:

1. **Claim-source match rate:** % of claims in the final report that have 2+ tier 1-3 sources in `sources.json`
2. **Agenda completion rate:** % of seeded agenda items marked `done` by end of session
3. **Verifier pass rate:** % of sessions achieving `PASS` on first verification attempt
4. **Chart-claim alignment:** % of quant charts that have at least one corresponding claim in `claims.json`
5. **Cross-session source reuse:** % of sources in a follow-up session that were already in the project's source registry (measures memory effectiveness)

---

## References
- arxiv 2601.01743 — AI Agent Systems: Architectures, Applications, and Evaluation
- o-mega.ai 2025-2026 AI Benchmark Guide
- arxiv 2507.02825 — Establishing Best Practices for Rigorous Agentic Benchmarks
- simmering.dev — The Reliability Gap: Agent Benchmarks for Enterprise
- Adaline Labs — The AI Agent Evaluation Crisis
- evidentlyai.com — 10 AI Agent Benchmarks
