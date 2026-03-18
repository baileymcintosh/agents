from __future__ import annotations

import json
from pathlib import Path

from agentorg.evidence import EvidenceStore
from agentorg.memory import (
    build_memory_context,
    load_relevant_memories,
    memory_seed_questions,
    source_registry_guidance,
    update_source_registry,
    write_project_memory,
)


def test_write_project_memory_and_reload_relevant_memories(temp_dir: Path) -> None:
    projects_root = temp_dir / "projects"
    old_project = projects_root / "oil-shock-2025"
    new_project = projects_root / "oil-shock-2026"
    old_reports = old_project / "reports"
    new_reports = new_project / "reports"
    old_reports.mkdir(parents=True)
    new_reports.mkdir(parents=True)

    old_store = EvidenceStore(old_reports)
    old_report = old_reports / "qual.md"
    old_report.write_text("report", encoding="utf-8")
    old_store.ingest_payload(
        agent_role="qual_builder",
        payload={
            "sources": [
                {"id": "S1", "title": "Reuters Oil", "url": "https://example.com/oil", "tier": "tier2_journalism"}
            ],
            "claims": [
                {"statement": "Oil markets repriced rapidly.", "confidence": 0.9, "materiality": "core", "kind": "finding", "source_ids": ["S1"]}
            ],
            "addressed_agenda_ids": [],
            "new_agenda_items": [
                {"question": "Quantify oil shipping disruption", "owner": "quant", "priority": "high"}
            ],
        },
        report_path=old_report,
    )
    old_store.annotate_claim_statuses({old_store.claims()[0].id: ("verified", "ok")})
    write_project_memory(old_project, "oil-shock-2025", "Research oil market shock", old_store)

    memories = load_relevant_memories(new_project, "oil-shock-2026", "Research oil market shock", limit=3)
    assert len(memories) == 1
    assert "oil-shock-2025" in build_memory_context(memories)
    assert "Quantify oil shipping disruption" in memory_seed_questions(memories)


def test_source_registry_guidance_reflects_verified_history(temp_dir: Path) -> None:
    projects_root = temp_dir / "projects"
    project_dir = projects_root / "macro-2026"
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True)

    store = EvidenceStore(reports_dir)
    report_path = reports_dir / "quant.md"
    report_path.write_text("report", encoding="utf-8")
    store.ingest_payload(
        agent_role="quant_builder",
        payload={
            "sources": [
                {"id": "S1", "title": "FRED Oil Series", "url": "https://fred.example/oil", "tier": "dataset", "source_type": "dataset"}
            ],
            "claims": [
                {"statement": "Brent rose 8%.", "confidence": 0.8, "materiality": "core", "kind": "data_point", "source_ids": ["S1"]}
            ],
            "addressed_agenda_ids": [],
            "new_agenda_items": [],
        },
        report_path=report_path,
    )
    store.annotate_claim_statuses({store.claims()[0].id: ("verified", "ok")})

    registry_path = update_source_registry(project_dir, store)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert "https://fred.example/oil" in registry

    memories = [{
        "project": "macro-2025",
        "key_sources": [{"title": "FRED Oil Series", "url": "https://fred.example/oil", "tier": "dataset"}],
    }]
    guidance = source_registry_guidance(project_dir, memories)
    assert "FRED Oil Series" in guidance
