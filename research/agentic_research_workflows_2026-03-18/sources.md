# Primary Sources

Cutoff: March 18, 2026.

This is a deliberately selective list of the most useful primary sources for designing state-of-the-art agentic research workflows. It emphasizes research systems, browsing/search agents, tool-use reliability, memory/context, evaluation, and scientific-workflow automation.

## 1. Foundational Agent Patterns

| Date | Source | Why it matters |
|---|---|---|
| 2022-10-06 | [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | Still the canonical foundation for interleaving reasoning with external actions. The key implication for research workflows is that reasoning should be grounded by iterative evidence collection, not done in one shot. |
| 2023-03-20 | [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | Introduced verbal self-critique and episodic memory as a practical way to improve multi-step agents without weight updates. Important for repair loops and research retrospection. |
| 2024-12-19 | [Building Effective AI Agents](https://resources.anthropic.com/building-effective-ai-agents) | The most useful high-level architecture guide from industry. Frames when to use workflows, single agents, evaluator-optimizer loops, and multi-agent orchestration. |

## 2. Research-Agent Systems and Deep Research

| Date | Source | Why it matters |
|---|---|---|
| 2025-02-02 | [Introducing deep research](https://openai.com/index/introducing-deep-research/) | One of the clearest primary-source descriptions of a production research agent: multi-step web research, source control, long-horizon browsing, Python, and documented outputs. Strong evidence that research tasks deserve a distinct harness, not just a generic chat agent. |
| 2025-02-25 | [Deep research System Card](https://openai.com/index/deep-research-system-card/) | Essential for the failure modes of research agents: prompt injection, privacy, malicious webpages, uncertainty, and citation reliability. Important because research workflows operate on untrusted open-web evidence. |
| 2025-02-02, updated 2026-03-12 | [Deep research in ChatGPT](https://help.openai.com/en/articles/10500283-deep-research) | Important product evolution signal: plan review before execution, real-time progress, interruptibility, source restrictions, and app/MCP connections. This is directly relevant to research workflow UX and operator control. |
| 2025-06-13 | [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) | The single most directly relevant source for this repo. Strong evidence for orchestrator-worker structure, parallel subagents, memory handoffs, filesystem artifacts, and breadth-first search before narrowing. |
| 2025-03-12 | [The AI Scientist Generates its First Peer-Reviewed Scientific Publication](https://sakana.ai/ai-scientist-first-publication/) | Important not because it proves full autonomy is solved, but because it shows the frontier is moving from “assistive drafting” toward autonomous research cycles. Useful for ambition-setting and for separating hype from actual workflow needs. |

## 3. Benchmarks for Research, Browsing, and Scientific Work

| Date | Source | Why it matters |
|---|---|---|
| 2023-11-21 | [GAIA benchmark](https://huggingface.co/datasets/gaia-benchmark/GAIA) | One of the most important broad assistant benchmarks. Useful because it measures multi-step, tool-augmented, evidence-seeking assistance rather than pure static QA. |
| 2024-07-01 | [MIRAI: Evaluating LLM Agents for Event Forecasting](https://mirai-llm.github.io/) | Very relevant for macro/policy/geopolitical research. Shows how tool-using agents perform on temporally structured forecasting tasks using historical events and news. |
| 2025-04-10 | [BrowseComp: a benchmark for browsing agents](https://openai.com/index/browsecomp/) | One of the best benchmarks for “needle in a haystack” research. Critical if your system is meant to do analyst-grade web research, not just answer easy search queries. |
| 2025-04-02 | [PaperBench](https://openai.com/index/paperbench/) | Important because it measures whether agents can replicate frontier ML research workflows. Strongly relevant to any ambition around institutional-grade research or technical replication. |
| 2024-10-10 | [MLE-bench](https://openai.com/index/mle-bench/) | Useful for understanding what it takes for agents to execute serious ML engineering tasks end-to-end, including data prep, experiments, and iteration. |
| 2025-07-28 update | [OSWorld / OSWorld-Verified](https://os-world.github.io/) | Best current primary source on open-ended computer-use tasks. Relevant for any research workflow that must leave chat and operate across real software environments. |
| 2026-01-07 release note | [WebArena-Verified](https://github.com/ServiceNow/webarena-verified) | Important because reproducibility and deterministic evaluation matter. Verified variants are a major signal that agent benchmarks need environment control, not just task lists. |
| 2026-03-xx current project page | [WebChoreArena](https://webchorearena.github.io/) | Particularly relevant to research workflows because it stresses massive memory, calculation, and long-term memory across many pages, which are all core research-agent demands. |
| 2025-03-xx | [SafeArena](https://safearena.github.io/) | Important reminder that stronger web agents also become stronger misuse agents. Research systems need misuse, adversarial, and prompt-injection-aware evaluation, not just capability evals. |

## 4. Evaluation, Reliability, and Benchmark Integrity

| Date | Source | Why it matters |
|---|---|---|
| 2026-01-09 | [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Probably the best current practical guide for agent eval design. Especially important for research agents because it explicitly discusses groundedness, coverage, and source-quality checks. |
| 2026-03-xx | [Eval awareness in Claude Opus 4.6's BrowseComp performance](https://www.anthropic.com/engineering/eval-awareness-browsecomp) | Cutting-edge evidence that agent benchmarks are becoming adversarial environments. Important for your workflow because research agents can learn to “solve the benchmark” rather than solve the task. |
| 2025-02-18 | [SWE-Lancer](https://openai.com/index/swe-lancer/) | Not research-specific, but highly relevant for understanding long-horizon economic tasks, realistic grading, and where current agents still fail on valuable real-world work. |
| 2025-05-16 | [Introducing Codex](https://openai.com/index/introducing-codex/) | Important for practical long-horizon execution patterns: sandboxed parallel tasks, repository-local work, asynchronous execution, and cloud task isolation. These ideas transfer cleanly to research workflows. |

## 5. Context, Memory, and Tooling

| Date | Source | Why it matters |
|---|---|---|
| 2024-09-19 | [Introducing Contextual Retrieval](https://www.anthropic.com/research/contextual-retrieval) | Strong evidence that retrieval quality is a workflow problem, not just a model problem. Important for evidence stores, citation recall, and research continuity. |
| 2025-01-23 | [Introducing Citations on the Anthropic API](https://www.anthropic.com/news/introducing-citations-api) | Important because research systems need source-grounded outputs as a native capability, not an afterthought. |
| 2025-03-20 | [The "think" tool](https://www.anthropic.com/engineering/claude-think-tool) | Useful for research workflows because complex tool chains often fail when the model has no explicit scratchpad between tool results and next actions. |
| 2025-09-11 | [Writing effective tools for agents — with agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | Very relevant to search/data tools. Tool ergonomics, namespacing, structured outputs, and eval-driven tool refinement directly affect research quality. |
| 2025-09-29 | [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk/) | Useful because it makes the case that a general agent harness can power many workflows, including deep research, if the loop, tools, and evals are strong. |
| 2025-09-29 | [Managing context on the Claude Developer Platform](https://www.anthropic.com/news/context-management) | Important for long-running research sessions: context editing, memory tools, and preserving only salient state. |
| 2025-10-20 | [Beyond permission prompts: making Claude Code more secure and autonomous](https://www.anthropic.com/engineering/claude-code-sandboxing) | Strong practical evidence for bounded autonomy, sandboxing, and secure long-running execution. Relevant to any research agent allowed to browse, execute code, or write files. |

## 6. Protocols and Interoperability

| Date | Source | Why it matters |
|---|---|---|
| current docs, relevant 2025 spec evolution | [Model Context Protocol: Architecture](https://modelcontextprotocol.io/specification/draft/architecture) | MCP is increasingly important for research workflows because serious research needs authenticated data sources, internal repositories, and specialized tools, not just open-web search. |
| 2025-06-23 | [Linux Foundation launches the Agent2Agent protocol project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents) | Relevant for multi-agent interoperability and long-running task coordination across systems. |
| current official docs | [A2A Protocol documentation](https://a2a-protocol.org/latest/) | Important because research workflows are likely to become multi-agent and cross-system; A2A is a serious candidate for standardized inter-agent task and capability exchange. |

## 7. Working Interpretation for AgentOrg

The strongest cross-source pattern is:

1. The best research agents are not just “bigger chatbots.”
2. They use explicit planning, parallel search, structured memory, artifact handoffs, and verifier-grade evidence handling.
3. The frontier is moving toward:
   - deeper browsing and search fan-out
   - more externalized memory and artifact systems
   - stronger eval harnesses
   - more explicit citation and provenance controls
   - more careful sandboxing and protocol design

## 8. Claude's Repo-Specific Priorities

Claude's parallel review of this repo highlighted the following research themes as highest-value for this codebase:

1. evidence-first orchestration
2. agenda-driven replanning
3. verifier/critic loops that repair rather than only gate
4. tool-use reliability
5. long-horizon memory
6. evaluation and benchmarks
7. multi-agent coordination protocols
8. budget-aware execution
9. citation rendering and evidence surfacing
10. robustness against hallucination and stale context

That prioritization is reflected in `workflow_synthesis.md`.
