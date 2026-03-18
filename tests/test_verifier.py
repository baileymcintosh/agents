from __future__ import annotations

from unittest.mock import patch

from agentorg.agents.verifier import VerifierAgent
from agentorg.evidence import EvidenceStore


def test_verifier_fails_core_claim_without_corroboration(temp_dir) -> None:
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()
    store = EvidenceStore(reports_dir)
    report_path = reports_dir / "qual.md"
    report_path.write_text("qual", encoding="utf-8")
    store.ingest_payload(
        agent_role="qual_builder",
        payload={
            "sources": [
                {
                    "id": "S1",
                    "title": "Single Source",
                    "url": "https://example.com/source",
                    "tier": "tier4_expert",
                }
            ],
            "claims": [
                {
                    "statement": "Material claim",
                    "confidence": 0.9,
                    "materiality": "core",
                    "kind": "finding",
                    "source_ids": ["S1"],
                }
            ],
            "addressed_agenda_ids": [],
            "new_agenda_items": [],
        },
        report_path=report_path,
    )

    with patch("agentorg.config.REPORTS_DIR", reports_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"):
        agent = VerifierAgent()
        result = agent.run(dry_run=False)

    assert result["verdict"] == "FAIL"
