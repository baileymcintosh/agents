# Executive Model — How to Oversee This System

This document is for the non-technical owner of AgentOrg.

## What The System Does

AgentOrg behaves like a small research team:

- a planner defines the scope
- a qualitative researcher gathers current intelligence and narrative context
- a quantitative researcher runs data analysis and produces charts
- a verifier checks whether claims are properly supported
- a reporter assembles the final memo

The system is designed so you mainly provide the brief and then review the final output.

## What You See

The primary outputs are:

- a final written report
- an optional notebook/PDF
- supporting charts and datasets
- an audit trail of claims, sources, and verification results

## What Matters To You

### PASS vs FAIL

The key control point is the verifier:

- `PASS`: the final report is allowed to publish
- `NEEDS REVISION` or `FAIL`: final synthesis is blocked until evidence quality improves

This means the system now has a real quality gate rather than only a narrative review step.

### Audit Trail

Every project keeps structured state in `reports/_state/`:

- `sources.json`
- `claims.json`
- `agenda.json`
- `verification.json`

You do not need to read these files routinely, but they are the evidence trail behind the final report.

## How To Redirect Priorities

You can steer the system by:

1. changing the project brief
2. adding feedback before a deeper run
3. asking the engineering contact to rerun the project with a different time budget

The internal agenda is then updated by the agents as research proceeds.

## What You Can Ignore

- old `builder` terminology in some legacy files
- most intermediate agent reports unless a verifier failure requires review
- Python, Docker, or GitHub CLI details

## When To Escalate

Escalate to engineering when:

- verification repeatedly fails on a strategically important project
- a source or claim in the final memo appears materially wrong
- the system stops producing charts or artifacts for quantitative sections

## Short Version

Think of the system as:

`Brief -> collaborative research -> verification gate -> final memo`

If the verification gate fails, trust that failure signal and treat the run as incomplete.
