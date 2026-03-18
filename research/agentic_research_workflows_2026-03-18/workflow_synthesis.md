# Workflow Synthesis

## Bottom Line

Yes: generic agent workflows and research workflows share the same core architecture.

The stable pattern is:

`planner -> workers -> memory/evidence store -> verifier -> reporter -> eval harness`

But research workflows need much stricter controls than generic task agents. The difference is not mainly the number of agents. The difference is:

- stronger evidence acquisition
- stronger provenance and citation handling
- stronger contradiction management
- stronger verifier and repair loops
- stronger evaluation of truthfulness and source use

If you are building a research system rather than a general assistant, the architecture should become **evidence-first**, not just **agent-first**.

## What The Research Says

Across the strongest sources in `sources.md`, five ideas repeat:

1. The best agents are looped systems, not single prompts.
   ReAct, Reflexion, deep research, and Anthropic's multi-agent research writeup all reinforce this.

2. Long-horizon performance depends on artifacts and memory.
   Frontier systems externalize intermediate state into files, summaries, plans, tools, and structured memory rather than keeping everything in the live transcript.

3. Search and tool quality matter as much as model quality.
   Research agents fail when search is shallow, tools are underspecified, or outputs are not structured enough for downstream checking.

4. Evaluation quality determines product quality.
   Anthropic's eval guidance, BrowseComp, PaperBench, MLE-bench, and OSWorld all point the same way: serious agent systems need serious harnesses.

5. More agents are not automatically better.
   Multi-agent systems help when there is true decomposability and parallel evidence gathering. They hurt when coordination, memory, or grading is weak.

## Recommended Design Principles For AgentOrg

## 1. Keep the Core Team Small

For research workflows, the best default is not a giant swarm. It is:

- `team_planner`
- `qual_builder`
- `quant_builder`
- `verifier`
- `reporter`

Optionally:

- a specialist retriever or data-collector
- a debugger / recovery agent

Do not add more analyst agents until you can show measurable gains in:

- citation quality
- contradiction detection
- chart correctness
- end-to-end completion rate

The frontier research strongly favors better harnesses and better evaluation before larger swarms.

## 2. Make The Evidence Store The System's Center Of Gravity

For research, the main object is not the report. It is the evidence graph behind the report.

The core persisted objects should be:

- source
- claim
- artifact
- unresolved question
- contradiction
- verdict

Each claim should carry:

- claim ID
- text
- source IDs
- confidence
- materiality
- freshness timestamp
- verifier status
- linked chart/table/artifact IDs

This is the right abstraction because research quality comes from whether each major conclusion can survive audit.

## 3. Split The Workflow Into Explicit Research Phases

The process should be staged, even if a single orchestrator runs it.

### Phase A: Research framing

Outputs:

- key questions
- hypotheses / scenarios
- metrics to watch
- source plan
- stop conditions

This phase should decide:

- what would count as evidence
- what would falsify an early thesis
- which topics need qual vs quant vs both

### Phase B: Evidence acquisition

Use search fan-out and parallel evidence collection.

The agents should gather:

- primary documents
- tier-1 journalism
- analytical reports
- datasets / time series
- historical analogues

The system should prefer breadth first, then depth:

1. map the landscape
2. find the strongest sources
3. narrow into key unknowns

### Phase C: Claim formation

Agents should not go straight from notes to prose.

They should first produce:

- candidate claims
- support level
- linked sources
- unresolved counterpoints

This is where contradiction detection belongs.

### Phase D: Verification and repair

The verifier should not only say pass/fail.
It should generate a repair queue:

- unsupported claim
- weak source tier
- stale source
- numerical inconsistency
- chart mismatch
- unresolved contradiction

Then the workers should get a bounded revision pass.

### Phase E: Report synthesis

The reporter should synthesize only verified claims, and should show uncertainty explicitly.

## 4. Use A Dual-Track Qual + Quant Research Loop

For your use case, the qual/quant split is the right architecture.

The qualitative track should focus on:

- events
- policy
- institutions
- actor statements
- historical analogues
- expert disagreement

The quantitative track should focus on:

- market series
- macro data
- scenario sensitivities
- event studies
- chart generation
- base-rate comparisons

The two tracks should meet at explicit interfaces:

- "what happened in the world that should show up in the data?"
- "what moved in the data that needs explanation?"

That interface is the core advantage of the architecture.

## 5. Use Agenda-Driven Replanning, Not Fixed Turns

The literature and the strongest industrial systems imply that fixed turn counts are mostly a convenience hack.

For research, continue until one of these conditions is true:

- the major agenda items are closed
- marginal evidence quality has stopped improving
- the time/cost budget is exhausted
- the verifier says the current draft is decision-grade

The agenda should be prioritized by:

- expected decision value
- uncertainty reduction
- source accessibility
- whether quant and qual both depend on it

## 6. Treat Search As A First-Class Research Subsystem

Search should not be a generic "web_search" call with a string in and snippets out.

For research workflows, search should support:

- trusted-source mode
- domain restrictions
- source tier labeling
- duplicate clustering
- result diversification
- historical date filtering
- query fan-out
- saved source objects

The research on deep research and BrowseComp strongly suggests that good search orchestration is a major determinant of research quality.

## 7. Build Three Layers Of Memory

Research workflows need more than transcript memory.

### Working memory

Current agenda, active claims, latest contradictions, high-salience findings.

### Episodic memory

What the system already tried:

- failed searches
- dead ends
- previous drafts
- why a claim was downgraded

### Archival memory

Long-lived reusable knowledge:

- curated sources
- topic packs
- historical analogues
- repeatable metrics and charts

This prevents repeated work and makes long-duration research runs economically viable.

## 8. Make Verification Closer To Scientific Peer Review

The verifier should check more than formatting and source count.

It should grade:

- claim-source linkage
- corroboration
- source freshness
- source tier
- internal consistency
- quant/qual agreement
- chart-to-claim consistency
- whether uncertainty is honestly stated

Then it should assign one of:

- verified
- plausible but under-supported
- contradicted
- stale
- requires human review

This is where research workflows differ most sharply from normal task agents.

## 9. Render Citations In The Final Deliverable

Invisible provenance in JSON is not enough.

The final report should surface:

- inline citation IDs for major claims
- a source appendix grouped by source tier
- chart provenance
- "what we know / what we infer / what remains uncertain"

This turns the system from "agent wrote a memo" into "auditable research process produced a memo."

## 10. Build An Evaluation Program Around Research Quality

You should maintain an internal benchmark suite for research workflows, not just generic agent benchmarks.

Recommended eval categories:

- source retrieval: did the system find the strongest sources?
- citation grounding: are material claims linked to real supporting sources?
- contradiction handling: does the system surface conflicts instead of averaging them away?
- quantitative correctness: do tables/charts match raw calculations?
- freshness: did it use current information where required?
- synthesis quality: does the final thesis stay within the evidence?
- cost/time efficiency: how much quality improvement per extra 10 minutes or extra dollar?

Use public benchmarks as reference signals, not as the only target:

- GAIA
- BrowseComp
- PaperBench
- MLE-bench
- OSWorld
- WebChoreArena
- MIRAI

## 11. Watch For Benchmark Gaming And Eval Contamination

One of the most important frontier lessons from 2025-2026 is that stronger agents may learn to game static evals.

That means:

- do not overfit to public benchmarks
- rotate internal tasks
- isolate eval environments
- grade outcome quality, not exact trajectories
- treat eval integrity as adversarial

This matters a lot for research systems, because web-enabled agents can discover benchmark artifacts or stale public answer keys.

## 12. Keep Human Escalation Minimal But Explicit

You want high autonomy, but research systems still need explicit escalation thresholds.

Escalate when:

- evidence is materially contradictory
- high-impact claims have only one weak source
- quantitative results depend on unstable or broken tools
- the verifier cannot resolve whether a thesis is real or hallucinated
- a decision with meaningful legal, financial, or reputational consequences depends on the output

This is not a failure of autonomy. It is part of a serious research process.

## Recommended Target Workflow For AgentOrg

1. `team_planner` produces a question tree, scenario set, source plan, and agenda seeds.
2. `qual_builder` and `quant_builder` run in parallel on the highest-value agenda items.
3. Each writes structured source and claim records, not just markdown.
4. The orchestrator periodically reprioritizes the agenda based on uncertainty reduction and verifier findings.
5. The verifier runs mid-cycle and end-cycle:
   - mid-cycle to produce repair tasks
   - end-cycle to gate publication
6. The reporter only composes from verified or explicitly caveated claims.
7. The final output includes citations, artifact provenance, and a structured uncertainty section.
8. Every run feeds an eval harness and postmortem memory store.

## What To Prioritize Next In This Repo

Given the current state of AgentOrg, the highest-leverage next steps are:

1. Render citations from `claims.json` and `sources.json` into final report output.
2. Turn the verifier into a repair engine, not only a gate.
3. Add contradiction objects to the evidence model.
4. Upgrade search into a trusted-source, deduplicated, source-tier-aware subsystem.
5. Add eval suites for sourcing, contradiction handling, chart correctness, and freshness.
6. Add long-horizon memory layers beyond the current agenda/evidence store.

## Final Recommendation

The right way to think about a cutting-edge research agent in March 2026 is:

not a chatbot with tools,
not a swarm of loosely coordinated agents,
but a **research production system** with:

- explicit agendas
- strong evidence acquisition
- structured memory
- rigorous verification
- auditable outputs
- evaluation-driven iteration

That is the design direction most consistent with the best available research and the strongest industrial systems available by March 18, 2026.
