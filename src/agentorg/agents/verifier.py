"""Verifier agent — validates structured claims, sources, and quantitative artifacts."""

from __future__ import annotations

from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.agents.base import BaseAgent
from agentorg.evidence import EvidenceStore, tier_rank


class VerifierAgent(BaseAgent):
    role = "verifier"

    def __init__(self) -> None:
        super().__init__()
        if not config.FAST_MODE:
            self.model = config.VERIFIER_MODEL
        self.store = EvidenceStore(config.REPORTS_DIR)

    def _evaluate_claims(self) -> tuple[str, list[dict[str, str]], dict[str, tuple[str, str]]]:
        sources = {source.id: source for source in self.store.sources()}
        claims = self.store.claims()

        findings: list[dict[str, str]] = []
        updates: dict[str, tuple[str, str]] = {}
        hard_failures = 0
        soft_failures = 0

        if not claims:
            return "FAIL", [{"severity": "high", "claim": "No structured claims recorded.", "note": "Builders did not emit any evidence payloads."}], {}

        for claim in claims:
            linked_sources = [sources[source_id] for source_id in claim.source_ids if source_id in sources]
            corroborating = [source for source in linked_sources if tier_rank(source.tier) <= 3]
            issues: list[str] = []

            # For quant_builder claims, dataset provenance + generated chart is sufficient
            # evidence — do not require 2 independent tier 1-3 sources, as data claims have
            # inherently different provenance requirements from narrative claims.
            has_dataset = any(source.source_type == "dataset" for source in linked_sources)
            quant_has_provenance = (
                claim.agent_role == "quant_builder"
                and (has_dataset or claim.artifact_paths)
            )

            # In fast/prelim mode, accept 1 tier 1-3 source (cheap models are less thorough).
            # In deep mode, require 2 independent sources for full corroboration.
            min_sources = 1 if config.FAST_MODE else 2
            if claim.materiality == "core" and len(corroborating) < min_sources and not quant_has_provenance:
                issues.append(
                    f"Core claim lacks {'one' if min_sources == 1 else 'two independent'} "
                    f"tier 1-3 source{'s' if min_sources > 1 else ''}."
                )

            # Track whether this claim has NO sources at all (separate from having
            # insufficient tier 1-3 sources). Zero-source claims are often caused by
            # search infrastructure failures (e.g. Tavily quota exhaustion) rather than
            # research quality issues, so they are always treated as soft failures.
            has_no_sources = not linked_sources and not claim.artifact_paths
            if has_no_sources:
                issues.append("Claim has no linked sources or data artifacts.")

            if claim.agent_role == "quant_builder":
                if not has_dataset and not claim.artifact_paths:
                    issues.append("Quant claim lacks dataset provenance or generated charts.")

            if claim.confidence < 0.5 and claim.materiality == "core":
                issues.append("Core claim confidence is below 0.5.")

            if issues:
                # "No sources at all" is always a soft failure — often caused by search
                # infrastructure being down, not by low-quality research.
                # Other issues on core claims are hard failures.
                if has_no_sources and len(issues) == 1:
                    severity = "medium"
                else:
                    severity = "high" if claim.materiality == "core" else "medium"
                findings.append(
                    {
                        "severity": severity,
                        "claim": claim.statement,
                        "note": " ".join(issues),
                    }
                )
                updates[claim.id] = ("needs_revision", " ".join(issues))
                if severity == "high":
                    hard_failures += 1
                else:
                    soft_failures += 1
            else:
                updates[claim.id] = ("verified", "Claim has sufficient provenance.")

        if hard_failures:
            verdict = "FAIL"
        elif soft_failures:
            verdict = "NEEDS REVISION"
        else:
            verdict = "PASS"
        return verdict, findings, updates

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[verifier] Starting evidence verification cycle.")
        verdict, findings, updates = self._evaluate_claims()

        summary_lines = [
            "# Verification Report",
            "",
            f"**Verdict:** {verdict}",
            f"**Claims reviewed:** {len(self.store.claims())}",
            f"**Sources reviewed:** {len(self.store.sources())}",
            f"**Open agenda items:** {self.store.unresolved_count()}",
            "",
        ]

        if findings:
            summary_lines.append("## Findings")
            for idx, finding in enumerate(findings, start=1):
                summary_lines.append(
                    f"{idx}. [{finding['severity'].upper()}] {finding['claim']} — {finding['note']}"
                )
        else:
            summary_lines.append("## Findings\nAll recorded claims satisfied the current provenance checks.")

        report_content = "\n".join(summary_lines)
        report_path = self.write_report("Verification Report", report_content)

        if not dry_run:
            self.store.annotate_claim_statuses(updates)
            self.store.write_verification(verdict, report_content, findings)
            if verdict != "PASS":
                self.post_slack_progress(
                    "🚨",
                    "needs review",
                    f"Verifier verdict {verdict}. {len(findings)} finding(s) require attention.",
                )

        return {
            "status": "ok",
            "report": str(report_path),
            "verdict": verdict,
            "findings": findings,
        }


def main(dry_run: bool = False) -> None:
    VerifierAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
