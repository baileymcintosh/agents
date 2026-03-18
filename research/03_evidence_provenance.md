# Evidence, Provenance & Source Reliability

**Compiled:** March 2026 | **Sources:** arxiv survey literature, applied AI research 2025

---

## Why Provenance Is Now Non-Negotiable

Research in 2025 has converged on a hard finding: agent systems that cannot trace their claims to specific sources are not fit for high-stakes use. The problem is not that LLMs hallucinate (known since 2020) — it is that agent systems amplify hallucination by using hallucinated claims as inputs to downstream agents, compounding errors across the pipeline.

"Chain of Agents" (2025) demonstrates that long-context tasks handled by collaborating agents require explicit evidence handoff between agents — passing raw text snippets is insufficient; agents need structured claims with source metadata.

---

## The Evidence Layer: What Best Systems Do

### Source Records
Every piece of external information that enters the pipeline should be represented as a structured record with:
- URL, title, publisher
- Publication date
- Reliability tier (primary/T1 journalism/analytical/expert/unverified)
- Summary of what was retrieved

### Claim Records
Every factual assertion in the research output should be:
- Stated as a discrete claim (not buried in prose)
- Linked to one or more source record IDs
- Assigned a confidence score
- Marked as core (must verify) or supporting (soft-check)
- Tagged with the agent that generated it

### Verification Records
A separate verification pass checks:
- Core claims have 2+ independent tier 1-3 sources
- Quant claims have dataset provenance or chart artifacts
- No claims with confidence < 0.5 are presented as conclusions

This is now what Codex implemented in `evidence.py` — it maps directly to what the literature says best systems do.

---

## Source Reliability Frameworks

### The 5-Tier Model (AgentOrg Implementation)
AgentOrg's qual builder doc defines:
- **Tier 1 [Primary — Official]:** Government sources, central banks, UN/IAEA, official regulatory bodies
- **Tier 2 [T1 Journalism]:** Reuters, AP, FT, Bloomberg, WSJ, Economist — corroborated by 2+ outlets
- **Tier 3 [Analysis]:** RAND, Brookings, CFR, IISS, peer-reviewed academic work
- **Tier 4 [Expert Opinion]:** Verified expert commentary, institutional blogs
- **Tier 5 [Unverified]:** Anonymous sources, unverified claims

**Research validation:** This structure maps closely to the source reliability frameworks used in fact-checking research (Full Fact, IFCN-affiliated organizations). The key rule — core claims need 2+ independent Tier 1-3 sources — is standard in computational journalism and verified information systems.

### Corroboration Rule
A claim is not considered verified if both corroborating sources cite the same upstream source. Independence must be verified, not assumed. This is harder to enforce programmatically but matters most for high-stakes claims.

---

## Tool Use Reliability and Grounding

### The Hallucination-in-Tool-Calls Problem
Research from 2025 identifies tool hallucination as distinct from factual hallucination:
- Models invoke tools with incorrect parameters even when they know the correct answer
- Models claim tool calls succeeded when they failed
- Models fabricate tool outputs without calling the tool

"Reducing Tool Hallucination via Reliability Alignment" (2025) shows that finetuning on execution feedback — training models on whether their tool calls actually succeeded — substantially reduces this failure mode.

### ReAct as Grounding Mechanism
The ReAct paradigm (Reason + Act) remains the most reliable approach: agents interleave explicit reasoning steps with tool invocations, using tool outputs to ground subsequent reasoning rather than continuing from prior LLM outputs. This substantially reduces hallucination in tool-heavy workflows.

**AgentOrg implication:** The qual builder's web search results should be fed back into the reasoning chain explicitly — not just appended as context but referenced in the evidence payload as specific source records that specific claims are built on.

### Execution-Based Evaluation
2025 research consensus: evaluate tool use by *running the tool and checking the outcome*, not by asking the model whether it used the tool correctly. This is the gold standard — and it means our `PythonExecutor` pattern (which actually runs the code and captures the output) is architecturally correct.

---

## From RAG to Context Engines (2025 Shift)

RAG (Retrieval-Augmented Generation) has evolved. The 2025 picture:

- **Old RAG:** Query → retrieve chunks → stuff into context → generate
- **New approach:** Query → intelligent retrieval → structured evidence objects → claim-linked generation → provenance-annotated output

The key shift: retrieval no longer just provides *text* — it provides *structured source records* that travel with the generated claims through the entire pipeline.

**AgentOrg's EvidenceStore** implements this correctly: sources are records, not text blobs, and claims reference source IDs rather than embedding source text inline.

---

## Practical Notes for AgentOrg

1. **The reporter should surface citations.** Currently the reporter generates prose with no inline citations. The evidence layer now exists — the next step is having the reporter emit `[Source: SRC_abc123]` inline and include a references section drawn from `sources.json`.

2. **Cross-agent evidence handoff is not yet implemented.** When qual generates a source record, quant cannot currently see it (and vice versa). The shared `EvidenceStore` makes this possible in principle — agents just need to be prompted to check the store before each turn.

3. **Confidence calibration matters.** A 0.5 threshold for core claims is a reasonable starting point, but calibration research suggests models systematically over-report confidence. Consider normalizing confidence scores within a session against observed evidence quality.

---

## References
- "Chain of Agents: Large Language Models Collaborating on Long-Context Tasks" (2025)
- "Reducing Tool Hallucination via Reliability Alignment" (2025, referenced in Boosting LLM Tool-Calling, NAACL 2025)
- RAGFlow 2025 year-end review: From RAG to Context
- arxiv 2507.21504 — Evaluation and Benchmarking of LLM Agents: A Survey
- Computational journalism source reliability literature (Full Fact, IFCN)
