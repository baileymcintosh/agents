# Human Oversight, Approval Gates & HITL

**Compiled:** March 2026 | **Sources:** Cloudflare Agents docs, Permit.io HITL guide, ilwllc.com Adaptive HITL

---

## The Core Principle

Human in the Loop (HITL) is the deliberate placement of human oversight at specific decision points in an otherwise autonomous workflow. The key design question is not *whether* to include human oversight but *where* — the cost of a human intervention must be weighed against the cost of an agent error at that point.

> "HITL should be placed where the cost of an AI error exceeds the cost of a human intervention."

---

## Oversight Models (2025 Taxonomy)

### 1. Static Approval Gates
The agent pauses at predefined checkpoints and waits for human approval before proceeding. Standard in enterprise workflows with compliance requirements.

**Examples:**
- Approve the research brief before the session starts
- Approve the verifier report before the final synthesis publishes
- Approve any action that posts to external systems (GitHub, Slack)

**AgentOrg implementation:** Currently the user approves the brief and the tool permissions. The session runs autonomously. The report is published automatically after verifier PASS.

**Recommendation:** Add an optional approval gate before publishing to GitHub — especially for deep runs. A one-line `--require-approval` flag on the CLI that pauses before `git push`.

### 2. Adaptive HITL (2025 Cutting Edge)
The agent dynamically decides when to involve a human based on its own confidence, the stakes of the action, and the available evidence. Low-confidence claims or high-stakes actions trigger a human check; high-confidence, low-stakes actions proceed autonomously.

**Implementation:** The agent emits a `confidence_score` for its output. If confidence < threshold OR materiality == "core" AND confidence < 0.7, the system pauses for review rather than proceeding to verification.

**Research finding (ilwllc.com):** Adaptive HITL reduces unnecessary human interruptions by 60-80% vs. static gates while maintaining equivalent error rates. The human reviews only what genuinely needs review.

### 3. Tiered Oversight by Risk
High-risk actions (publishing, emailing, posting to external services) require human approval. Medium-risk actions (web search, reading files) are logged but not blocked. Low-risk actions (in-memory computation) run silently.

**AgentOrg mapping:**
- Low risk: In-context reasoning, agenda management, message bus writes
- Medium risk: Web search, Python code execution, file writes within the project directory
- High risk: git push, external API calls that have side effects, report publication

### 4. Feedback-Loop HITL (Our Current Model for Iteration)
Human reviews the prelim output, provides feedback, and the deep run incorporates it. This is not a gate — it is a feedback signal. It is already implemented via `run_deep(feedback=...)`.

---

## Regulatory Context

Multiple regulatory frameworks now explicitly require human oversight for high-stakes AI applications:
- **EU AI Act:** Requires human oversight for "high-risk" AI systems (financial advice, medical decisions)
- **NIST AI Risk Management Framework:** Recommends human review at key decision points
- **Financial services regulators** (SEC, FCA): Require auditability and human accountability for AI-driven recommendations

For AgentOrg producing financial/geopolitical research, the key requirement is **auditability** — can a human reconstruct how every claim in the report was derived? Our evidence layer (`claims.json` + `sources.json`) makes this possible in principle.

---

## Practical HITL Design for AgentOrg

### Current HITL Points
1. **Brief approval:** User writes and submits the brief — this is implicit HITL
2. **Tool permissions:** Claude Code asks for bash permissions (though this is being streamlined)
3. **Prelim review:** User reviews prelim output and provides feedback for deep run
4. **Report review:** User reads and acts on the final report

### Recommended Additions
1. **Verifier escalation:** If verifier returns `NEEDS REVISION` (not `FAIL`, not `PASS`), message the user via Slack/notification rather than blocking. The user decides whether to re-run or accept the caveated output.

2. **Confidence-gated publication:** If any core claim has confidence < 0.6 in the evidence store, flag it explicitly in the report header and require explicit user acknowledgment before pushing.

3. **Agenda overflow notification:** If at end of session there are >3 unresolved high-priority agenda items, notify the user rather than silently closing the session. These represent genuine research gaps.

4. **One-command approval workflow:** `agentorg approve <run_id>` — user reviews a summary diff (new claims, key sources, verifier verdict) and approves or rejects the push. Under 30 seconds for a typical run.

---

## The Right Balance for Research Agents

For a research agent (vs. an action-taking agent), the key insight from 2025 research is:

**Humans should review outputs, not process steps.** An agent searching the web or executing Python code 20 times per session doesn't need 20 approval gates — that defeats the point of automation. But a human should review the *output* of that process before it becomes an institutional artifact (a published report).

The approval gate should be at the **publication boundary**, not within the research loop. Everything inside the session is autonomous; everything that crosses the system boundary (push to GitHub, send to Slack) requires human sign-off.

---

## References
- Cloudflare Agents docs — Human-in-the-Loop
- Permit.io — Human in the Loop for AI Agents: Best Practices
- ilwllc.com — Balancing AI Autonomy & Human Oversight with Adaptive HITL (Dec 2025)
- EU AI Act (Article 14) — Human Oversight Requirements
- NIST AI RMF — Govern, Map, Measure, Manage framework
