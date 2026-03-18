# AgentOrg Research Library

**Compiled:** March 18, 2026 | **Authors:** Claude Code + Codex

A curated collection of the most important research on agentic AI workflows, compiled to inform AgentOrg's development roadmap. Covers the state of the field through March 2026.

---

## Contents

| File | Topic | TL;DR |
|---|---|---|
| [01_foundational_patterns.md](01_foundational_patterns.md) | Ng's 4 patterns + 2025 extensions | Reflection, tool use, planning, multi-agent — plus evidence grounding and agenda-driven stopping |
| [02_multi_agent_orchestration.md](02_multi_agent_orchestration.md) | Orchestration architectures & MCP | Hierarchical > peer-to-peer; MCP is the emerging standard; difficulty-routing cuts cost 36% |
| [03_evidence_provenance.md](03_evidence_provenance.md) | Evidence layers & source reliability | Structured claim+source records are non-negotiable for high-stakes output |
| [04_memory_context.md](04_memory_context.md) | Agent memory types & A-MEM | 4 memory types; cross-session memory is the biggest gap; A-MEM is the best implementation model |
| [05_evaluation_benchmarks.md](05_evaluation_benchmarks.md) | Benchmarks & internal evals | Reliability > capability; define 5 internal evals; compounding error maths |
| [06_human_oversight.md](06_human_oversight.md) | HITL & approval gates | Gate at publication boundary, not process steps; adaptive HITL reduces interruptions 60-80% |
| **[SYNTHESIS.md](SYNTHESIS.md)** | **Our roadmap recommendations** | **Read this first — 4-phase improvement roadmap based on the research** |

---

## Key Numbers to Remember

- **Reliability barrier:** 95% per-step success = 60% task completion over 10 steps
- **Difficulty routing:** +11% accuracy at 64% inference cost (arxiv 2509.11079)
- **Enterprise adoption:** 57% have agents in production; reliability is #1 barrier (LangChain 2025)
- **GAIA SOTA:** 90% overall; 61% at hardest level (end 2025)
- **MCP adoption:** Donated to Linux Foundation Dec 2025; OpenAI, Google, Microsoft all adopted
- **Memory gap:** Cross-session memory is the biggest capability gap between prototype and product

---

## Most Important Papers (Ranked)

1. arxiv 2512.13564 — Memory in the Age of AI Agents
2. arxiv 2502.12110 — A-MEM: Agentic Memory for LLM Agents
3. arxiv 2509.11079 — Difficulty-Aware Agent Orchestration
4. arxiv 2501.06322 — Multi-Agent Collaboration Mechanisms Survey
5. arxiv 2601.13671 — The Orchestration of Multi-Agent Systems (Jan 2026)
6. LangChain State of Agent Engineering 2025
7. arxiv 2410.10762 — AFlow: Automating Agentic Workflow Generation
