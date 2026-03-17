# TASKS.md — Research Priority Backlog

This file is the authoritative list of tasks for the Planner agent.
Add items here to direct the research organization's priorities.
The Planner reads this file at the start of each cycle.

---

## Priority Queue

Items at the top are worked on first.

| Priority | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 1 | Define the primary research domain and goals | Bailey | 🔴 Not Started | Needed before agents can pursue meaningful work |
| 2 | Configure Slack integration and test executive report delivery | Engineering | 🔴 Not Started | Requires SLACK_BOT_TOKEN in .env |
| 3 | Run first end-to-end pipeline and validate output quality | Engineering | 🔴 Not Started | Use `--dry-run` first, then live |
| 4 | Set up Jupyter notebook environment for data analysis | Engineering | 🔴 Not Started | |

---

## Completed

| Task | Completed | Notes |
|---|---|---|
| Initialize repository infrastructure | 2026-03-16 | Done by Claude Code |

---

## How to Add a Task

1. Add a row to the **Priority Queue** table above
2. Set Priority = 1 if it should be worked on immediately
3. The Planner agent will pick it up in the next cycle

You can describe the task in plain English — the Planner will figure out how to execute it.
