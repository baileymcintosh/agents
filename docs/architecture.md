# System Architecture

## Overview

AgentOrg is now built around a collaborative research pair, not a single builder. The system uses:

1. `team_planner` to define the research agenda
2. a collaborative qual/quant session to execute that agenda
3. a verifier that checks structured claims and provenance
4. a reporter that synthesizes only after verification passes

## Data Flow

```text
Brief -> PLAN.md -> collaborative session -> reports/_state/{sources,claims,agenda}
      -> verifier -> verification.json -> reporter -> final deliverables
```

## Collaborative Session

The collaborative engine lives in `src/agentorg/agents/session.py`.

Behavior:

- qual and quant run in parallel threads
- each agent claims agenda items assigned to it or marked shared
- each agent can close agenda items and open new ones
- the loop stops when work is exhausted, time is nearly exhausted, or the max-cycle cap is reached

This replaces the older fixed single-builder assembly line as the intended product path.

## Evidence Model

Structured evidence is persisted via `src/agentorg/evidence.py`.

Objects:

- `SourceRecord`
- `ClaimRecord`
- `AgendaItem`

State files:

- `reports/_state/sources.json`
- `reports/_state/claims.json`
- `reports/_state/agenda.json`
- `reports/_state/verification.json`

The evidence layer is the substrate for provenance, verification, and future claim-level citation rendering.

## Verification Gate

The verifier consumes the structured evidence store rather than only raw markdown.

Current checks:

- core claims need 2+ corroborating tier 1-3 sources
- every claim needs provenance and/or artifacts
- quant claims need dataset provenance and/or charts

If verification does not return `PASS`, the reporter is skipped by the canonical runner.

## Runtime Configuration

`config.set_reports_dir()` and the updated `RunClock` allow project-scoped runs without leaking report directories across sessions.

`project_manager.py` now supports:

- env-configurable project root
- env-configurable GitHub repo creation
- `gh` discovery from PATH instead of a hardcoded machine path

## File Layout

```text
agents/
  src/agentorg/
    agents/
    evidence.py
    reporting/
    slack_bot/
  agent_docs/
  reports/
    templates/
  tests/
```

## Remaining Gaps

- legacy `builder` path still exists and should eventually be removed or clearly marked deprecated everywhere
- pytest is still environment-sensitive here because this shell has temp-directory permission issues
- verification is currently rules-based; future work should add richer claim/source contradiction handling and report-native citation rendering
