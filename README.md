# AgentOrg — Autonomous Multi-Agent Research Organization

> A team of AI agents that plans, executes, verifies, and reports research work — continuously and autonomously.

---

## For Bailey (Executive Overview)

You manage this system through **two touchpoints**:

1. **Slack** — Every night, an executive summary is posted to your channel. Read it. If it says "Decisions Needed," respond to your engineering contact.
2. **TASKS.md** — Add priorities here in plain English. The system picks them up automatically.

You do not need to understand the code. See [docs/executive_model.md](docs/executive_model.md) for a plain-English guide to overseeing this system.

---

## How It Works

Four AI agents run in sequence, every night:

```
Planner → Builder → Verifier → Reporter → Slack
```

| Agent | What It Does |
|---|---|
| **Planner** | Reads `TASKS.md` and decides what to work on this week |
| **Builder** | Executes the top-priority task and produces outputs |
| **Verifier** | Reviews the Builder's work and issues a quality verdict |
| **Reporter** | Writes an executive summary and posts it to Slack |

All outputs are saved as Markdown files in `reports/` and committed to this repository.

---

## Quick Start (Developers)

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker (optional, for containerized runs)

### Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd agents

# 2. Run setup (installs dependencies, creates .env)
bash scripts/setup.sh

# 3. Edit .env — add your API keys
#    Required: ANTHROPIC_API_KEY
#    Optional: SLACK_BOT_TOKEN, SLACK_EXECUTIVE_CHANNEL_ID

# 4. Test the setup (no API calls)
uv run agentorg run planner --dry-run

# 5. Run the full pipeline (dry run)
bash scripts/run_pipeline.sh --dry-run
```

### Run a Live Pipeline

```bash
# Run individual agents
uv run agentorg run planner
uv run agentorg run builder
uv run agentorg run verifier
uv run agentorg run reporter

# Run the full pipeline
bash scripts/run_pipeline.sh

# Check status
uv run agentorg status
```

### Run with Docker

```bash
# Build
docker-compose build

# Run a single agent
docker-compose run --rm planner

# Run the full pipeline
docker-compose up planner && docker-compose up builder && \
  docker-compose up verifier && docker-compose up reporter
```

---

## GitHub Actions

Five workflows run automatically:

| Workflow | Schedule | What It Does |
|---|---|---|
| `nightly.yml` | Every night at 2 AM UTC | Full pipeline: plan → build → verify → report |
| `planner.yml` | Every Monday 8 AM UTC | Planner only |
| `builder.yml` | After Planner completes | Builder only |
| `verifier.yml` | After Builder completes | Verifier only |
| `ci.yml` | On every push/PR | Lint, type check, tests |

### Required GitHub Secrets

Add these at **Settings → Secrets and Variables → Actions**:

| Secret | Where to Get It |
|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `SLACK_BOT_TOKEN` | [api.slack.com/apps](https://api.slack.com/apps) — create an app, add `chat:write` and `files:write` scopes |
| `SLACK_EXECUTIVE_CHANNEL_ID` | Right-click channel in Slack → Copy Link — the ID starts with `C` |
| `SLACK_ENGINEERING_CHANNEL_ID` | Same as above |
| `SLACK_ALERTS_CHANNEL_ID` | Same as above |

### Manual Trigger

Any workflow can be triggered manually from **GitHub → Actions → [Workflow] → Run workflow**.

---

## Project Structure

```
agents/
├── src/agentorg/          # Python package
│   ├── agents/            # Planner, Builder, Verifier, Reporter
│   ├── reporting/         # Markdown + PDF generation
│   └── slack_bot/         # Slack API client
├── agent_docs/            # System prompts for each agent (edit to change behavior)
├── reports/
│   └── templates/         # Report templates (Jinja2)
├── data/                  # Research data
│   ├── raw/               # Raw inputs
│   ├── processed/         # Cleaned data
│   ├── external/          # Third-party sources
│   └── cache/             # Temporary cache
├── docs/                  # Documentation
│   ├── architecture.md    # How the system is built
│   ├── executive_model.md # Guide for non-technical oversight
│   └── project_plan.md    # Milestones and roadmap
├── tests/                 # Automated tests
├── scripts/               # Setup, test, and export helpers
├── notebooks/             # Jupyter notebooks
├── .github/workflows/     # GitHub Actions automation
├── TASKS.md               # Research priority backlog ← add priorities here
├── pyproject.toml         # Python project config
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-service orchestration
└── .env.example           # Environment variable template
```

---

## Customizing Agent Behavior

Each agent reads its system prompt from `agent_docs/<role>.md`. To change how an agent thinks or writes, edit the corresponding file:

- `agent_docs/planner.md` — How the Planner prioritizes tasks
- `agent_docs/builder.md` — How the Builder approaches execution
- `agent_docs/verifier.md` — What the Verifier checks for
- `agent_docs/reporter.md` — How the Reporter writes summaries

---

## Development

```bash
# Run all checks
bash scripts/test.sh

# Run tests only
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# Export reports to PDF
bash scripts/export_reports.sh
```

---

## Support

- **Engineering questions:** Open an issue in this repository
- **Executive questions:** See [docs/executive_model.md](docs/executive_model.md)
- **Agent behavior:** Edit the relevant file in `agent_docs/`
