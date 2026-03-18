from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agentorg.agents.critic import CriticAgent
from agentorg.evidence import EvidenceStore


def test_critic_skips_with_empty_evidence(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()
    store = EvidenceStore(reports_dir)

    with patch("agentorg.config.REPORTS_DIR", reports_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"):
        result = CriticAgent(store, "Research plan").run(dry_run=False)

    assert result["status"] == "skipped"
    assert result["count"] == 0


def test_critic_adds_agenda_items_in_dry_run_with_mocked_call(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()
    store = EvidenceStore(reports_dir)
    report_path = reports_dir / "qual.md"
    report_path.write_text("report", encoding="utf-8")
    store.ingest_payload(
        agent_role="qual_builder",
        payload={
            "sources": [{"id": "S1", "title": "Reuters", "url": "https://example.com", "tier": "tier2_journalism"}],
            "claims": [{"statement": "Claim", "confidence": 0.8, "materiality": "core", "kind": "finding", "source_ids": ["S1"]}],
            "addressed_agenda_ids": [],
            "new_agenda_items": [],
        },
        report_path=report_path,
    )

    with patch("agentorg.config.REPORTS_DIR", reports_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"), \
         patch.object(CriticAgent, "call_claude", return_value='[{"question":"Address counterargument","owner":"shared","priority":"high","note":"Missing"}]'):
        result = CriticAgent(store, "Research plan").run(dry_run=False)

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert any("counterargument" in item.question.lower() for item in store.agenda())
