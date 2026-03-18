# Multi-Agent Orchestration: Architectures & Protocols

**Compiled:** March 2026 | **Sources:** arxiv survey literature, Langchain State of Agent Engineering 2025

---

## The Orchestration Problem

The core challenge in multi-agent systems is not building individual agents — it is coordinating them reliably. Research in 2025-2026 converges on several findings:

1. **Static topologies fail at scale.** Hand-designed graphs of "agent A talks to agent B" break when task complexity exceeds design assumptions.
2. **Centralized orchestrators outperform peer-to-peer for most tasks.** A single orchestrator that directs agents based on evolving task state beats fully decentralized agent meshes on reliability and debuggability.
3. **Graph-based state machines are winning in production.** The practical shift is toward controllable orchestration with explicit state transitions, checkpointing, and human approval gates — not fully autonomous meshes.

---

## Architecture Patterns (2025 State of the Art)

### Hierarchical Orchestration
A planner/orchestrator agent decomposes the goal and assigns subtasks to worker agents. Workers report back; orchestrator synthesises and decides next steps.

- **Best for:** Complex, multi-domain research tasks with unclear decomposition upfront
- **Risk:** Orchestrator becomes a single point of failure; requires a strong model at the top level
- **Key paper:** "The Orchestration of Multi-Agent Systems: Architectures, Protocols, and Enterprise Adoption" (arxiv 2601.13671) — comprehensive taxonomy of orchestration patterns

### Parallel Specialised Workers + Synthesiser
Multiple specialist agents run concurrently on different aspects of the same task. A synthesiser agent integrates their outputs.

- **Best for:** Tasks with clear, separable dimensions (e.g., qual vs. quant research — what AgentOrg does)
- **Risk:** Workers produce incoherent outputs if they don't share enough context; synthesiser becomes a bottleneck
- **Key finding:** Cross-agent messaging (workers informing each other mid-run) substantially improves coherence vs. fully isolated workers

### Evolving Orchestration (2025 Cutting Edge)
The orchestration topology itself adapts during execution. "Multi-Agent Collaboration via Evolving Orchestration" (arxiv 2505.19591) shows agents can dynamically reassign tasks, spawn sub-agents, and restructure communication graphs based on emerging results.

- **Best for:** Long-running, genuinely open-ended research where the shape of the problem changes as you investigate it
- **Practical barrier:** Much harder to debug; requires robust observability

### Conductor Models (RL-Trained Orchestrators)
"Learning to Orchestrate Agents in Natural Language with the Conductor" (arxiv 2512.04388): A centralized model trained via reinforcement learning to discover optimal agent communication topologies and task assignments. Outperforms hand-designed orchestration significantly.

- **Key insight:** The orchestrator should be *trained*, not just prompted. Static system prompts for orchestration are much less effective than a model that has learned to coordinate.
- **Practical status:** Research-stage; requires significant training data. Aspirational for AgentOrg.

---

## Communication Protocols

### Shared Message Bus
Agents post messages to a shared store; other agents poll for relevant messages. Simple, debuggable, fits well with async agent execution.

**AgentOrg's `AgentMessenger`** implements this pattern. This is the right call for a small agent team.

### Direct Semantic Communication (Cache-to-Cache, 2025)
Agents communicate via internal KV-cache representations rather than text. Richer inter-model collaboration, but requires model-level integration. Research-stage only.

### Model Context Protocol (MCP) — Industry Standard
Anthropic's MCP (November 2024, donated to Linux Foundation December 2025) is now the de facto standard for agent-to-tool and agent-to-data-source communication. OpenAI, Google, Microsoft have all adopted it.

**What MCP does:** Standardises how agents discover, call, and receive results from external tools and data sources. Replaces bespoke API integrations with a universal connector layer.

**November 2025 update:** MCP expanded to support asynchronous execution, authorization, and long-running workflows — not just synchronous tool calls.

**Implication for AgentOrg:** Our current tool integrations (Tavily search, Python executor, FRED) are custom. Migrating to MCP-compatible tool servers would make the system more composable and allow reuse of the growing MCP ecosystem (thousands of MCP servers exist as of early 2026).

---

## Key Production Findings (LangChain State of Agent Engineering 2025)

- **57% of respondents have agents in production** — this is no longer experimental
- **Reliability is the #1 barrier to enterprise adoption** (survey of 306 practitioners)
- **89% have implemented observability** for their agents — before evals (52%)
- **Bad tool orchestration creates infinite loops and cascading failures** — the primary failure mode in production, not model quality
- Controllable, graph-based orchestration with explicit state and human approvals is preferred over fully autonomous meshes in enterprise contexts

---

## Difficulty-Aware Routing: Cost vs. Quality

Key finding from arxiv 2509.11079: Routing subtasks to different models based on query difficulty achieves:
- **+11.21% accuracy** over prior multi-agent baselines
- **Using only 64% of inference cost**

The mechanism: classify each subtask by difficulty, route easy tasks to cheap/fast models (Groq Llama, etc.), reserve expensive models (Opus) for tasks requiring deep reasoning.

**Direct implication for AgentOrg:** We already do this at the session level (prelim = Groq, deep = Claude). The next step is doing it at the *subtask* level within a single session — routing individual agenda items to the appropriate model tier.

---

## References
- arxiv 2601.13671 — The Orchestration of Multi-Agent Systems
- arxiv 2505.19591 — Multi-Agent Collaboration via Evolving Orchestration
- arxiv 2512.04388 — Learning to Orchestrate Agents (Conductor)
- arxiv 2501.06322 — Multi-Agent Collaboration Mechanisms: A Survey
- arxiv 2511.15755 — Multi-Agent LLM Orchestration for Incident Response
- arxiv 2509.11079 — Difficulty-Aware Agent Orchestration
- modelcontextprotocol.io/specification/2025-11-25
- LangChain State of Agent Engineering 2025
