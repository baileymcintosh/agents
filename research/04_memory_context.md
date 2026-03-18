# Memory & Context Management in Agent Systems

**Compiled:** March 2026 | **Sources:** arxiv 2512.13564, arxiv 2502.12110, ICLR 2026 MemAgents workshop, RAGFlow 2025

---

## Why Memory Is the Hardest Unsolved Problem in Agentic AI

An agent with no memory across sessions is a sophisticated single-turn system, not a true autonomous agent. Memory is what enables an agent to:
- Build on previous research rather than starting from scratch
- Recognize when a new question was already partially answered
- Accumulate source reliability judgments over time
- Transfer learned patterns across projects

The field has become fragmented, with inconsistent terminology obscuring what "memory" actually means in different systems. The most useful framework distinguishes four types:

---

## The Four Memory Types (2025 Research Consensus)

### 1. Working Memory (In-Context)
What the agent holds in its active context window for the current task. Includes the current research plan, recent tool outputs, messages from other agents, and the current turn's evidence payload.

**Limit:** Context windows are large (200K+ tokens for Claude) but finite and expensive. Working memory should hold only what is immediately relevant.

**AgentOrg current state:** This is what agents receive in each `run_turn()` call. The research plan, messenger context, and agenda items constitute working memory.

### 2. Episodic Memory (Session Records)
Records of specific past events — what was researched, what was found, what sources were used. Episodic memory allows agents to say "in the Iran project, we found X from source Y."

**Best implementation:** Structured JSON records (like our `sources.json`, `claims.json`) that can be queried efficiently. The key is *not* storing raw text but storing structured records with metadata that allow targeted retrieval.

**AgentOrg current state:** The `EvidenceStore` (`_state/`) is episodic memory for a single session. Cross-session episodic memory does not yet exist.

### 3. Semantic Memory (Parametric / Distilled)
Generalised knowledge extracted from episodes — not "we found X in the Iran project" but "when researching oil supply disruptions, Hormuz throughput figures from IEA are the most reliable source." This is knowledge that has been consolidated from specific instances into general principles.

**Best implementation:** A small knowledge base (vector store or structured document) that is updated after each project and consulted at the start of new ones. A-MEM (arxiv 2502.12110) implements this with dynamic note-creation and linking, analogous to how Zettelkasten note-taking works.

**AgentOrg current state:** Not implemented. This is one of the highest-leverage gaps.

### 4. Procedural Memory (Skills)
Knowledge of *how* to do things — which search queries work for which topics, which Python libraries are reliable for which data sources, how to structure a qual finding for maximum verifier pass rate.

**Best implementation:** Tool use histories + structured playbooks that agents can reference. In practice, this is often embedded in agent system prompts and updated based on observed outcomes.

**AgentOrg current state:** Partially in `agent_docs/` (qual_builder.md, etc.) but not dynamically updated based on session outcomes.

---

## A-MEM: Agentic Memory for LLM Agents (Feb 2025)

arxiv 2502.12110 — the most directly applicable memory paper for AgentOrg.

A-MEM proposes a dynamic memory system inspired by Zettelkasten:
- **Note creation:** When an agent makes a significant finding, it creates a structured "note" with content, keywords, tags, and links to related notes
- **Note evolution:** Notes are updated and linked as new related findings arrive
- **Retrieval:** Agents query the memory network, retrieving not just matching notes but their linked neighbors

**Key advantage over vector RAG:** A-MEM preserves the *relationships between findings*, not just individual facts. This is critical for research where conclusions depend on how multiple findings interact.

**Implementation complexity:** Moderate — requires a vector store for retrieval plus a graph structure for note linking.

---

## Memory Architecture for Research Agents (ICLR 2026 Workshop)

The ICLR 2026 MemAgents workshop identifies three key challenges:
1. **Single-shot learning:** Agents should be able to learn from a single new example without retraining
2. **Context-aware retrieval:** What to retrieve depends on the current query, not just semantic similarity
3. **Consolidation:** How to merge overlapping memories without losing specificity

The workshop consensus: **retrieval quality matters more than storage quantity**. A small, well-structured memory with good retrieval beats a large unstructured memory every time.

---

## Practical Recommendations for AgentOrg

### Near-term (implement now)
1. **Cross-session evidence persistence.** After each project, write a summary of key sources and findings to a project-level memory file that can be loaded at the start of a follow-up session. This is episodic memory across sessions.

2. **Agenda persistence across sessions.** If a project runs multiple sessions (prelim → feedback → deep), the agenda from the previous session should seed the next one's unresolved items.

### Medium-term
3. **Source reputation tracking.** Build a lightweight registry of sources that have proved reliable or unreliable across projects. "Last time we cited this source, the verifier flagged it" is valuable procedural memory.

4. **Project knowledge base.** After each project, distill key findings into a structured summary that becomes retrievable context for related future projects.

### Longer-term
5. **A-MEM style note graph.** Implement linked note creation so the agent builds a growing research knowledge base across all projects, not just within one session.

---

## References
- arxiv 2512.13564 — Memory in the Age of AI Agents (comprehensive survey, Dec 2025)
- arxiv 2502.12110 — A-MEM: Agentic Memory for LLM Agents (Feb 2025)
- ICLR 2026 Workshop: MemAgents — Memory for LLM-Based Agentic Systems
- RAGFlow 2025 year-end review: From RAG to Context
- MachineLearningMastery.com — The 6 Best AI Agent Memory Frameworks 2026
