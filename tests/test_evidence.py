from __future__ import annotations

from pathlib import Path

from agentorg.evidence import EvidenceStore, extract_json_block


def test_extract_json_block_returns_clean_text_and_payload() -> None:
    text = (
        "## Findings\nSomething happened.\n\n"
        "```evidence_json\n"
        '{"sources":[{"id":"S1","title":"Reuters","url":"https://example.com","tier":"tier2_journalism"}],'
        '"claims":[{"statement":"Oil rose","confidence":0.8,"materiality":"core","kind":"finding","source_ids":["S1"]}],'
        '"addressed_agenda_ids":["A_1"],"new_agenda_items":[]}\n'
        "```"
    )
    clean, payload = extract_json_block(text)
    assert "evidence_json" not in clean
    assert payload["sources"][0]["title"] == "Reuters"


def test_evidence_store_bootstrap_and_ingest(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.bootstrap_agenda(["Check oil prices", "Review official statements"])

    report_path = tmp_path / "report.md"
    report_path.write_text("Report", encoding="utf-8")
    result = store.ingest_payload(
        agent_role="qual_builder",
        payload={
            "sources": [
                {
                    "id": "S1",
                    "title": "Reuters",
                    "url": "https://example.com/reuters",
                    "tier": "tier2_journalism",
                    "publisher": "Reuters",
                }
            ],
            "claims": [
                {
                    "statement": "Officials confirmed the policy shift.",
                    "confidence": 0.9,
                    "materiality": "core",
                    "kind": "finding",
                    "source_ids": ["S1"],
                }
            ],
            "addressed_agenda_ids": [],
            "new_agenda_items": [{"question": "Quantify market response", "owner": "quant", "priority": "high"}],
        },
        report_path=report_path,
    )

    assert result == {"sources": 1, "claims": 1}
    assert len(store.sources()) == 1
    assert len(store.claims()) == 1
    assert any(item.owner == "quant" for item in store.agenda())
