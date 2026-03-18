from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentorg import approval as approval_state
from agentorg import cli
from agentorg.agents.verifier import VerifierAgent
from agentorg.runner import run_deep
from agentorg.session_state import ProjectSession
from typer.testing import CliRunner


def test_publication_approval_roundtrip(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    reports_dir.mkdir()

    created = approval_state.create(
        reports_dir,
        run_id="run-123",
        project_name="alpha",
        project_dir=str(temp_dir),
        mode="deep",
        requires_approval=True,
        verifier_verdict="PASS",
        report_path=str(reports_dir / "report.md"),
        outputs=["one.md"],
        summary="Approval summary",
    )

    loaded = approval_state.load(reports_dir)
    assert loaded is not None
    assert loaded.status == "pending"
    assert created.requires_approval is True

    approved = approval_state.approve(reports_dir, approved_by="Tester", notes="ok")
    assert approved.status == "approved"
    assert approved.approved_by == "Tester"
    assert approval_state.load(reports_dir).status == "approved"


def test_runner_skips_push_when_approval_required(temp_dir: Path) -> None:
    project_dir = temp_dir / "project"
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True)
    (project_dir / "BRIEF.md").write_text("Brief", encoding="utf-8")

    session = ProjectSession(
        name="alpha",
        brief="Brief",
        project_dir=str(project_dir),
        team=["qual_builder", "quant_builder"],
    )

    with patch("agentorg.config.PUBLICATION_APPROVAL_REQUIRED", True), \
         patch("agentorg.runner._push") as push_mock, \
         patch("agentorg.runner.run_collaborative_session") as session_mock, \
         patch.object(VerifierAgent, "run", return_value={"verdict": "PASS", "report": "verifier.md"}), \
         patch("agentorg.runner.ReporterAgent") as reporter_cls, \
         patch("agentorg.runner.QAEditorAgent") as qa_cls:

        session_mock.return_value = {
            "qual_report": "qual.md",
            "quant_report": "quant.md",
            "dialogue_report": "dialogue.md",
            "charts": [],
            "messages": 3,
            "unresolved_agenda_items": 0,
            "critic": None,
        }
        reporter = MagicMock()
        reporter.run.return_value = {
            "status": "ok",
            "report": str(reports_dir / "report.md"),
            "notebook": str(reports_dir / "report.ipynb"),
            "pdf": None,
        }
        reporter_cls.return_value = reporter

        qa = MagicMock()
        qa.run.return_value = {
            "verdict": "APPROVED",
            "instructions": "",
            "report": str(reports_dir / "qa.md"),
        }
        qa_cls.return_value = qa

        result = run_deep(session)

    assert not push_mock.called
    assert result["approval"] is not None
    assert result["approval"]["status"] == "pending"
    assert session.publication_approval_status == "pending"
    assert (reports_dir / "_state" / "publication_approval.json").exists()
    assert (project_dir / "project_memory.json").exists()
    assert (temp_dir / "source_registry.json").exists()


def test_cli_approval_commands(temp_dir: Path) -> None:
    project_dir = temp_dir / "project"
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True)
    approval_state.create(
        reports_dir,
        run_id="run-456",
        project_name="alpha",
        project_dir=str(project_dir),
        mode="deep",
        requires_approval=True,
        verifier_verdict="PASS",
        report_path=str(reports_dir / "report.md"),
        summary="Approval summary",
    )

    session = ProjectSession(
        name="alpha",
        brief="Brief",
        project_dir=str(project_dir),
        team=["qual_builder", "quant_builder"],
        publication_approval_required=True,
        publication_approval_status="pending",
        publication_approval_run_id="run-456",
        publication_approval_path=str(reports_dir / "_state" / "publication_approval.json"),
    )

    runner = CliRunner()
    with patch("agentorg.session_state.load", return_value=session), \
         patch("agentorg.session_state.save"):
        inspect_result = runner.invoke(cli.app, ["approval"])
        approve_result = runner.invoke(cli.app, ["approve", "--by", "Tester"])

    assert inspect_result.exit_code == 0
    assert approve_result.exit_code == 0
    assert approval_state.load(reports_dir).status == "approved"
