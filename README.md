# AgentOrg

An autonomous multi-agent research system. Given a project brief, it assembles a custom team of AI agents, runs a fast preliminary pass to validate data and sources, then iterates into deep research based on feedback.

## How it works

1. **Brief** — describe a project (research, analysis, coding, dashboards, anything)
2. **Team proposal** — the system designs a custom agent team suited to the task
3. **Preliminary run** — fast pass with cheap models (<10 min), outputs to a dedicated GitHub repo
4. **Feedback** — review outputs, give feedback
5. **Deep run** — full models, full depth, iterate as many times as needed

All orchestration happens through Claude Code. No CLI commands needed — just describe what you want.

## Agent roster

| Agent | Model | Role |
|---|---|---|
| `team_planner` | Claude Opus | Reads brief, designs custom team |
| `qual_builder` | Groq Llama 3.3 70B (prelim) / GPT-4o (deep) | Qualitative research — news, policy, events |
| `quant_builder` | Claude Sonnet | Quantitative research — data, charts, market analysis |
| `reporter` | Claude Sonnet | Final synthesis → Markdown report + Jupyter notebook |
| `verifier` | Claude Sonnet | Fact-checking and QA |
| `debugger` | Claude Opus | Failure diagnosis and recovery |

## Model tiers

| Tier | Models | Used for |
|---|---|---|
| Expensive | Claude Opus | Planner, Debugger — called once per project |
| Mid | Claude Sonnet, GPT-4o | Deep research, synthesis, reporting |
| Cheap/free | Groq Llama 3.3 70B | Preliminary runs, search workers |

## Workflows

| Workflow | What it does |
|---|---|
| `prelim.yml` | Fast validation run (<10 min), outputs to project repo |
| `deep.yml` | Full research run with optional feedback incorporated |
| `research_session.yml` | Multi-cycle qual+quant collaborative session |

## Project outputs

Each project gets its own public GitHub repo under `baileymcintosh/<project-name>` containing reports, notebooks, and data.

## Required secrets

`ANTHROPIC_API_KEY` · `OPENAI_API_KEY` · `GROQ_API_KEY` · `TAVILY_API_KEY` · `FRED_API_KEY` · `EIA_API_KEY` · `PAT_TOKEN`
