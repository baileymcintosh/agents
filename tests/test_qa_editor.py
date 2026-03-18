from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from agentorg.agents.qa_editor import QAEditorAgent
from agentorg.evidence import EvidenceStore


def test_qa_editor_returns_revision_or_approval(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()
    report_path = reports_dir / "report.md"
    report_path.write_text("# Report\n\nSummary.", encoding="utf-8")
    (reports_dir / "charts_manifest.json").write_text(json.dumps([]), encoding="utf-8")

    store = EvidenceStore(reports_dir)
    store.write_verification("PASS", "ok", [])

    with patch("agentorg.config.REPORTS_DIR", reports_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"), \
         patch.object(QAEditorAgent, "call_claude", return_value='{"verdict":"REVISE","instructions":"1. Add chart explanation."}'):
        result = QAEditorAgent("Brief", "Plan").run(str(report_path), dry_run=False)

    assert result["verdict"] in {"APPROVED", "REVISE"}
    if result["verdict"] == "REVISE":
        assert result["instructions"]
