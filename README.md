# AgentOrg

AgentOrg is an autonomous multi-agent research system for producing institutional-style research outputs from a short brief. The canonical execution path is now:

`team_planner -> collaborative qual/quant session -> verifier -> reporter -> qa_editor -> approval`

The system is designed to run with minimal human involvement after the initial brief while preserving a structured audit trail of sources, claims, charts, and verification results.

## How It Works

1. **Brief**: describe the project in plain English.
2. **Team proposal**: `team_planner` writes a `PLAN.md` with goals, expected outputs, and a project slug.
3. **Preliminary cycle**: qual + quant run collaboratively with cheaper settings to validate sources, datasets, and output shape.
4. **Deep cycle**: the same collaborative engine runs at fuller depth, expanding the agenda until time or open questions run out.
   In deep mode, a mid-session `critic` checkpoint runs after both builders complete turn 1 and adds adversarial follow-up agenda items.
5. **Verification gate**: structured claims are checked against source records and data artifacts.
6. **Reporting**: the reporter synthesizes only after verification passes, adds inline source tags from the evidence store, and appends a references table.
7. **Editorial QA**: a `qa_editor` checks the finished report against the brief, verified claims, charts, and unresolved agenda items, then allows one bounded reporter revision pass.
8. **Publication approval**: a persisted approval artifact records the final publish-ready state; `agentorg approval` inspects it and `agentorg approve` marks it approved.

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

## Main Commands

```bash
agentorg new "Your project brief"
agentorg prelim
agentorg iterate "Incorporate this feedback"
agentorg session --time-budget 2h
agentorg status
```

`prelim` and `iterate` now run the canonical collaborative pipeline through `runner.py`.

## Project Outputs

Each project directory contains:

```text
<project>/
  BRIEF.md
  PLAN.md
  FEEDBACK.md
  reports/
    _state/
    *.md
    *.ipynb
    *.pdf
    charts_manifest.json
  data/
  notebooks/
```

GitHub repo creation is optional and now controlled by environment variables rather than machine-specific path assumptions.

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

## Verification Notes

In this shell environment, `pytest` still encounters temp-directory permission issues. The refactor was validated with:

- `C:\Users\baile\anaconda3\python.exe -m compileall src`
- targeted import checks
- a direct smoke test of `EvidenceStore` and `VerifierAgent`

When architectural changes materially alter the execution path, this root `README.md` and `ARCHITECTURE.md` should be updated in the same pass.
