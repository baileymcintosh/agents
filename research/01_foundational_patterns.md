# Foundational Agentic Design Patterns

**Compiled:** March 2026 | **Sources:** Andrew Ng / DeepLearning.AI, academic survey literature

---

## Andrew Ng's Four Patterns (2024 — Still Canonical)

Andrew Ng's 2024 framework remains the clearest taxonomy for agentic system design. One year on, all four patterns have been validated in production — though with important caveats about how they interact.

### 1. Reflection
An agent critiques its own output (or a separate critic agent does) and iterates before returning a final answer. Ng's preferred implementation: two separate agents — one to generate, one to critique — with the resulting dialogue improving quality substantially over single-pass generation.

**What research shows (2025):** Reflection significantly reduces hallucination rates on factual tasks. The key finding is that *self-reflection without external grounding is insufficient* — models tend to reinforce confident errors rather than catch them. Effective reflection requires at least one agent to have access to external evidence (search, data) that can contradict the generator.

**Implication for AgentOrg:** Our qual/quant cross-verification is a form of reflection. The verifier agent should be treated as the reflection layer — it needs real evidence access, not just markdown review.

---

### 2. Tool Use
Agents call external APIs, run code, query databases, browse the web. Tool use is the single most productivity-unlocking pattern — it converts the LLM from a knowledge retrieval system into an action-taking system.

**What research shows (2025):** Tool hallucination remains a major failure mode. "Reducing Tool Hallucination via Reliability Alignment" (2025) shows that models frequently invoke tools incorrectly even when they know the correct answer. Execution-based evaluation — running the tool call and checking the outcome — is now considered the gold standard for assessing tool use quality.

**Key stat:** 89% of production agent deployments have implemented observability for tool calls; only 52% have evals. Observability comes before evals in practice.

**Implication for AgentOrg:** Our `PythonExecutor` is a form of tool use. The charts manifest is implicit observability. We should add explicit logging of every tool call outcome, not just chart outputs.

---

### 3. Planning
The agent decomposes a complex task into a directed sequence of sub-tasks, executes them, and adapts the plan based on intermediate results.

**What research shows (2025-2026):** Static planning (generate the full plan upfront, then execute) consistently underperforms adaptive planning (replan after each step). The AFlow paper (2024-2025) demonstrates that flexible workflow search — where the agent can modify its own workflow structure based on observations — outperforms fixed-topology pipelines.

Difficulty-Aware Orchestration (arxiv 2509.11079) shows that routing subtasks to different models based on query difficulty achieves 11% higher accuracy at 36% lower cost — a major practical finding for cost-controlled research systems.

**Implication for AgentOrg:** Our fixed `max_cycles` cap with agenda-driven stopping (Codex's refactor) is step one. Step two is adaptive replanning: agents should be able to reshape the agenda mid-session, not just mark items done.

---

### 4. Multi-Agent Collaboration
Specialized agents run in parallel or sequence, with shared state and explicit communication.

**What research shows (2025):** Multi-agent systems for incident response achieve 100% actionable recommendation rate vs. 1.7% for single-agent approaches, with *zero quality variance* — enabling SLA commitments impossible with single-agent systems. The key mechanism is that agents catch each other's errors by default.

The Conductor model paper (arxiv 2512.04388) shows that RL-trained orchestrators automatically discover optimal communication topologies — which agents talk to which, in what order — rather than requiring hand-designed graphs.

**Implication for AgentOrg:** Qual and quant are not just parallel workers — they should actively cross-validate. A qual finding that contradicts quant data should spawn a new agenda item for quant to investigate, and vice versa.

---

## Beyond the Four Patterns: 2025 Additions

### 5. Evidence-Grounded Generation
Agents anchor all claims in explicit, traceable source records. This is distinct from RAG (which retrieves context) — it's about *provenance*: every claim in the output can be traced to a specific source with a tier rating and a URL.

This is now considered a prerequisite for any agent system used in high-stakes domains (finance, research, legal).

### 6. Agenda-Driven Stopping
Rather than running for a fixed number of turns, agents stop when their work queue is empty or confidence thresholds are met. This is the difference between "8 turns of qual" and "qual runs until all open qual questions are answered."

### 7. Budget-Aware Decomposition
Agents are given explicit time/cost budgets and choose which tasks to tackle in priority order. Combined with difficulty-aware routing (lighter models for simpler tasks), this is the primary cost-control mechanism in production systems.

---

## Key Reference
- Andrew Ng, Snowflake BUILD 2024 keynote; DeepLearning.AI Agentic AI course
- AFlow: Automating Agentic Workflow Generation (arxiv 2410.10762)
- Difficulty-Aware Agent Orchestration (arxiv 2509.11079)
- Multi-Agent Collaboration Mechanisms: A Survey of LLMs (arxiv 2501.06322)
