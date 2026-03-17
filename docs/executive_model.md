# Executive Model — How to Oversee This System

This document is written for **Bailey**, the non-technical executive overseeing AgentOrg.

## What This System Does

AgentOrg is a team of AI researchers that works for you continuously — planning, building, checking its own work, and reporting results. You don't need to direct individual tasks. The system identifies what's worth working on and does it.

Think of it like managing a research department where:
- You see a daily or weekly summary in Slack
- You can ask questions or redirect priorities at any time
- The team keeps a public record of everything it does

## Your Touchpoints

### 1. Slack (primary)
Every night, the Reporter agent posts an executive summary to your Slack channel. It contains:
- What was accomplished
- Key findings
- Any risks or blockers
- What the team plans to do next

**You don't need to do anything** unless the report asks for a decision.

### 2. GitHub (audit trail)
Every report is committed to the repository as a Markdown file. You can browse them at any time. The file names include the date and agent role so you can find specific reports easily.

### 3. Direct commands (optional)
If you want to trigger something specific, ask your engineering contact to run:
```
agentorg run planner
agentorg run builder
agentorg run reporter
```
Or trigger any workflow manually from the GitHub Actions tab.

## How to Redirect Priorities

If you want the agents to focus on something specific:
1. Edit `TASKS.md` in the repository root — add your priority to the top of the list
2. The Planner will pick it up in the next cycle

You can also describe the goal in plain English and ask your engineering contact to add it.

## What "Done" Looks Like

Each research cycle ends with an Executive Summary report that includes:
- A one-line status
- Bullet-point accomplishments
- A quality verdict from the Verifier
- Recommended next steps

If the Verifier flags problems, they'll appear clearly in the report. Nothing is hidden.

## Escalation

If a report contains the words **"FAIL"** or **"Decisions Needed from Leadership"**, that means the system needs your input before it can proceed. The report will tell you exactly what's needed.

## What You Can Ignore

- Individual planner, builder, and verifier reports — these are working documents for the engineering team
- GitHub commit history (unless you're curious)
- Docker and Python configuration

## Glossary

| Term | What It Means |
|---|---|
| Planner | The AI that decides what to work on |
| Builder | The AI that does the work |
| Verifier | The AI that checks the work |
| Reporter | The AI that summarizes everything for you |
| GitHub Actions | The scheduling system that runs the agents automatically |
| Report | A Markdown (text) file with structured findings |
| Executive Summary | The one-page report posted to your Slack every night |
