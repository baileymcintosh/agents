"""Publication-boundary approval artifacts for research deliverables."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APPROVAL_JSON = "publication_approval.json"
APPROVAL_MD = "publication_approval.md"


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _approval_dir(reports_dir: Path) -> Path:
    return reports_dir / "_state"


def approval_json_path(reports_dir: Path) -> Path:
    return _approval_dir(reports_dir) / APPROVAL_JSON


def approval_md_path(reports_dir: Path) -> Path:
    return _approval_dir(reports_dir) / APPROVAL_MD


@dataclass
class PublicationApproval:
    run_id: str
    project_name: str
    project_dir: str
    mode: str
    status: str = "pending"
    requires_approval: bool = True
    verifier_verdict: str = ""
    report_path: str = ""
    notebook_path: str = ""
    pdf_path: str = ""
    qa_report_path: str = ""
    outputs: list[str] = field(default_factory=list)
    summary: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    approved_at: str = ""
    approved_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PublicationApproval":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]

    def is_pending(self) -> bool:
        return self.status == "pending" and self.requires_approval


def load(reports_dir: Path) -> PublicationApproval | None:
    path = approval_json_path(reports_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict):
        return PublicationApproval.from_dict(data)
    return None


def render_markdown(approval: PublicationApproval) -> str:
    lines = [
        "# Publication Approval",
        "",
        f"**Run ID:** {approval.run_id}",
        f"**Project:** {approval.project_name}",
        f"**Mode:** {approval.mode}",
        f"**Status:** {approval.status}",
        f"**Requires Approval:** {str(approval.requires_approval).lower()}",
        f"**Verifier Verdict:** {approval.verifier_verdict or 'unknown'}",
        f"**Created:** {approval.created_at}",
        f"**Updated:** {approval.updated_at}",
    ]
    if approval.approved_at:
        lines.append(f"**Approved At:** {approval.approved_at}")
    if approval.approved_by:
        lines.append(f"**Approved By:** {approval.approved_by}")
    if approval.report_path:
        lines.append(f"**Report:** {approval.report_path}")
    if approval.notebook_path:
        lines.append(f"**Notebook:** {approval.notebook_path}")
    if approval.pdf_path:
        lines.append(f"**PDF:** {approval.pdf_path}")
    if approval.qa_report_path:
        lines.append(f"**QA Report:** {approval.qa_report_path}")
    if approval.summary:
        lines += ["", "## Summary", approval.summary]
    if approval.notes:
        lines += ["", "## Notes", approval.notes]
    if approval.outputs:
        lines += ["", "## Outputs"]
        lines.extend(f"- {path}" for path in approval.outputs)
    return "\n".join(lines)


def save(reports_dir: Path, approval: PublicationApproval) -> Path:
    state_dir = _approval_dir(reports_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    approval.updated_at = _now_iso()
    json_path = approval_json_path(reports_dir)
    md_path = approval_md_path(reports_dir)
    json_path.write_text(json.dumps(approval.to_dict(), indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(approval), encoding="utf-8")
    return json_path


def create(
    reports_dir: Path,
    *,
    run_id: str,
    project_name: str,
    project_dir: str,
    mode: str,
    requires_approval: bool,
    verifier_verdict: str,
    report_path: str = "",
    notebook_path: str = "",
    pdf_path: str = "",
    qa_report_path: str = "",
    outputs: list[str] | None = None,
    summary: str = "",
    notes: str = "",
) -> PublicationApproval:
    approval = PublicationApproval(
        run_id=run_id,
        project_name=project_name,
        project_dir=project_dir,
        mode=mode,
        status="pending" if requires_approval else "approved",
        requires_approval=requires_approval,
        verifier_verdict=verifier_verdict,
        report_path=report_path,
        notebook_path=notebook_path,
        pdf_path=pdf_path,
        qa_report_path=qa_report_path,
        outputs=list(outputs or []),
        summary=summary,
        notes=notes,
        approved_at=_now_iso() if not requires_approval else "",
        approved_by="system" if not requires_approval else "",
    )
    save(reports_dir, approval)
    return approval


def approve(
    reports_dir: Path,
    *,
    approved_by: str = "",
    notes: str = "",
) -> PublicationApproval:
    approval = load(reports_dir)
    if approval is None:
        raise FileNotFoundError("No publication approval artifact found.")
    approval.status = "approved"
    approval.approved_at = _now_iso()
    approval.approved_by = approved_by or "manual"
    if notes:
        approval.notes = notes
    save(reports_dir, approval)
    return approval
