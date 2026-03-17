# System Architecture

## Overview

AgentOrg is an autonomous multi-agent research organization. A pipeline of AI agents — each with a distinct role — works continuously to plan research, execute tasks, verify quality, and report results to leadership.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   PLANNER   │ →  │   BUILDER   │ →  │  VERIFIER   │ →  │  REPORTER   │
│             │    │             │    │             │    │             │
│ Identifies  │    │ Executes    │    │ QA reviews  │    │ Writes exec │
│ top tasks   │    │ highest-    │    │ builder     │    │ summary +   │
│ each week   │    │ priority    │    │ output      │    │ posts Slack │
│             │    │ task        │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       ↓                  ↓                  ↓                  ↓
  reports/           reports/           reports/           reports/
  *_planner_*        *_builder_*        *_verifier_*       *_reporter_*
```

## Agent Roles

| Agent | Runs When | Writes To | Reads From |
|---|---|---|---|
| Planner | Monday 8 AM UTC | `reports/*_planner_*` | `agent_docs/planner.md`, task context |
| Builder | After Planner | `reports/*_builder_*` | Latest planner report |
| Verifier | After Builder | `reports/*_verifier_*` | Latest builder report |
| Reporter | After Verifier | `reports/*_reporter_*` | All three above; posts to Slack |

## Autonomy Level

The system is designed for **Level 3 autonomy**: agents identify and pursue useful tasks themselves, without requiring a human to specify each task. The Planner surveys the research landscape and decides what to work on. Humans review outputs but do not direct individual tasks.

## Execution Environments

1. **GitHub Actions** — primary production environment. Agents run as scheduled jobs.
2. **Docker / docker-compose** — local development and testing.
3. **Local Python (uv)** — development, debugging, and one-off runs.

## File Layout

```
agents/
├── src/agentorg/          # Python package (source)
│   ├── agents/            # Agent implementations (planner, builder, verifier, reporter)
│   ├── reporting/         # Markdown + PDF report generation
│   └── slack_bot/         # Slack API client
├── agent_docs/            # System prompts for each agent role
├── reports/
│   └── templates/         # Jinja2 report templates (not generated outputs)
├── data/
│   ├── raw/               # Input data, unprocessed
│   ├── processed/         # Cleaned and transformed data
│   ├── external/          # Third-party datasets
│   └── cache/             # Temporary computation cache
├── docs/                  # Technical documentation (this folder)
├── tests/                 # Automated tests
├── scripts/               # Setup, test, and export helper scripts
├── notebooks/             # Jupyter notebooks for exploration
└── .github/workflows/     # GitHub Actions automation
```

## Data Flow

1. Planner generates a prioritized task list → saved as Markdown report
2. Builder reads the latest planner report → executes top task → saves output report
3. Verifier reads builder output → scores and critiques it → saves QA report
4. Reporter reads all three → synthesizes executive summary → posts to Slack + saves report
5. All reports are committed to the repository by the GitHub Actions bot

## Report Naming Convention

```
{YYYYMMDD_HHMMSS}_{role}_{title_slug}.md
```

Example: `20260316_020312_planner_weekly_research_plan.md`

## Security & Secrets

All credentials (API keys, Slack tokens) are stored as **GitHub Actions Secrets** and **never committed to the repository**. Local development uses `.env` (gitignored). See `.env.example` for the full list of required variables.
