# AgentOrg

AgentOrg is an autonomous multi-agent research system for producing institutional-style research outputs from a short brief. The canonical execution path is now:

`team_planner -> memory-seeded collaborative qual/quant session -> verifier -> reporter -> qa_editor -> approval`

The system is designed to run with minimal human involvement after the initial brief while preserving a structured audit trail of sources, claims, charts, and verification results.

## How It Works

1. **Brief**: describe the project in plain English.
2. **Team proposal**: `team_planner` writes a `PLAN.md` with goals, expected outputs, and a project slug.
3. **Preliminary cycle**: qual + quant run collaboratively with cheaper settings to validate sources, datasets, and output shape.
4. **Deep cycle**: the same collaborative engine runs at fuller depth, expanding the agenda until time or open questions run out.
   In deep mode, a mid-session `critic` checkpoint runs after both builders complete turn 1 and adds adversarial follow-up agenda items.
   Related prior projects can seed carry-forward questions into the agenda, and agenda items now carry rough `simple|complex|synthesis` difficulty tags.
5. **Verification gate**: structured claims are checked against source records and data artifacts.
6. **Reporting**: the reporter synthesizes only after verification passes, adds inline source tags from the evidence store, and appends a references table.
   The report is now prompted as a prose-first research memo: only the opening TL;DR may use bullets, while the rest should read as full narrative analysis led by chart discussion.
7. **Editorial QA**: a `qa_editor` checks the finished report against the brief, verified claims, charts, and unresolved agenda items, then allows one bounded reporter revision pass.
8. **Publication approval**: a persisted approval artifact records the final publish-ready state; `agentorg approval` inspects it and `agentorg approve` marks it approved.
9. **Cross-session memory**: each completed project writes `project_memory.json`, and a shared `source_registry.json` tracks which sources have historically supported verified or flagged claims.

## Core Agents

| Agent | Typical model | Role |
|---|---|---|
| `team_planner` | Claude Opus | Designs the project team and research agenda |
| `qual_builder` | Groq Llama 3.3 70B (prelim) / GPT-4o (deep) | Current intelligence, policy, narrative context, source collection |
| `quant_builder` | Claude Sonnet | Data work, charts, market analysis, dataset-backed claims |
| `critic` | Claude Sonnet | Mid-session adversarial challenge pass that writes high-priority follow-up agenda items |
| `verifier` | Groq Llama (prelim) / Claude Sonnet (deep) | Claim-level provenance checks and pass/fail gating |
| `reporter` | Claude Sonnet | Final memo, chart embedding, notebook/PDF generation |
| `qa_editor` | Claude Sonnet | Publication-boundary quality review with one bounded rewrite request |
| `debugger` | Claude Opus | Recovery and failure diagnosis |

## What Changed

The old sequential `planner -> builder -> verifier -> reporter` path is no longer the primary workflow. The default product path now uses:

- A collaborative qual/quant session instead of a single builder
- A shared evidence brief passed between qual and quant at each turn
- A mid-session critic checkpoint in deep runs
- A persisted evidence layer for sources, claims, and agenda state
- Cross-session memory and source reputation across related projects
- Verification based on structured provenance, not just markdown review
- A reporter gate that blocks final synthesis when verification fails
- A post-report QA editor that can request one revision pass before publication
- A publication approval artifact plus CLI inspect/approve commands

## Evidence Layer

Research artifacts are persisted under `reports/_state/`:

- `sources.json`: normalized source records with reliability tier
- `claims.json`: explicit claims with confidence, provenance, and verification status
- `agenda.json`: unresolved and completed research questions
- `verification.json`: latest verifier verdict and findings

This sits alongside `charts_manifest.json`, which remains the handoff between quant chart generation and reporting. The evidence store is now also read during the session: each builder receives a compact brief of the other builder's top claims and sources before each turn.

Notebook output now embeds charts directly as base64-backed markdown images so the notebook does not depend on external image paths at view time.

Project-level memory artifacts are also persisted outside `reports/`:

- `project_memory.json`: verified findings, useful sources, and unresolved high-priority questions from the completed run
- `source_registry.json`: cross-project source reputation summary keyed by source URL/title

## Main Commands

```bash
agentorg new "Your project brief"
agentorg prelim
agentorg iterate "Incorporate this feedback"
agentorg session --time-budget 2h
agentorg status
agentorg approval
agentorg approve
```

`prelim` and `iterate` now run the canonical collaborative pipeline through `runner.py`.

## Browsing Capability

- `qual_builder` can search and then fetch full article text with `fetch_url`
- Claude-backed agents now also expose `fetch_url` in addition to web search
- `quant_builder` can search, fetch full URLs directly, and also fetch full URLs from inside Python
- search results now request Tavily `raw_content` when available instead of relying only on snippets

Current limitation:
- the system still does not have a dedicated PDF/paper parsing pipeline beyond URL fetch through Jina Reader, so research-paper ingestion is improved but not yet specialized

## Project Outputs

Each project directory contains:

```text
<project>/
  BRIEF.md
  PLAN.md
  FEEDBACK.md
  project_memory.json
  reports/
    _state/
    *.md
    *.ipynb
    *.pdf
    charts_manifest.json
  data/
  notebooks/
```

The projects root also accumulates a shared `source_registry.json`. GitHub repo creation is optional and now controlled by environment variables rather than machine-specific path assumptions.

## Configuration

Important environment variables:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `TAVILY_API_KEY`
- `FRED_API_KEY`
- `AGENTORG_PROJECTS_ROOT`
- `AGENTORG_CREATE_GITHUB_REPO`
- `PUBLICATION_APPROVAL_REQUIRED`
- `MEMORY_RETRIEVAL_LIMIT`

## Verification Notes

In this shell environment, `pytest` still encounters temp-directory permission issues. The refactor was validated with:

- `C:\Users\baile\anaconda3\python.exe -m compileall src`
- targeted import checks
- a direct smoke test of `EvidenceStore` and `VerifierAgent`

When architectural changes materially alter the execution path, this root `README.md` and `ARCHITECTURE.md` should be updated in the same pass.
