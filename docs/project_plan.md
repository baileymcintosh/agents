# Project Plan

## Phase 1 — Foundation (Current)

**Goal:** Get the infrastructure running end-to-end with real agent loops.

### Milestones

- [x] Repository structure and Python project initialized
- [x] Docker and docker-compose configured
- [x] GitHub Actions workflows created (planner, builder, verifier, nightly)
- [x] Agent role documentation (system prompts) written
- [x] Report templates created (executive summary, experiment report)
- [x] Slack integration scaffolded
- [ ] GitHub repository created and secrets configured
- [ ] First successful nightly pipeline run
- [ ] First Slack executive summary posted

### Blockers / Dependencies

- Requires: Anthropic API key
- Requires: Slack app created and bot token configured
- Requires: GitHub repository created and Actions enabled

---

## Phase 2 — Active Research

**Goal:** Agents are running autonomously and producing useful research outputs.

### Milestones

- [ ] Planner producing meaningful weekly plans
- [ ] Builder executing tasks and producing verifiable outputs
- [ ] Verifier catching quality issues before they reach leadership
- [ ] Reporter producing clear, actionable executive summaries
- [ ] `data/` directory populated with first research datasets

---

## Phase 3 — Level 3 Autonomy

**Goal:** Agents proactively identify new research directions without human prompting.

### Milestones

- [ ] Planner scanning external sources for research opportunities
- [ ] Agents spawning sub-tasks and tracking them in `TASKS.md`
- [ ] Notebook evidence of research quality (visualizations, data analysis)
- [ ] Feedback loop: Verifier scores influence Planner priorities

---

## Open Questions

1. What is the primary research domain? (The system is currently domain-agnostic)
2. Should agents have access to external APIs (web search, databases)?
3. What Slack channels should reports go to, and who has access?
4. How should the system handle tasks that require human judgment?
