"""Cross-session memory and source reputation helpers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agentorg.evidence import EvidenceStore, tier_rank


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{4,}", text.lower())}


def _memory_candidates(project_dir: Path) -> list[Path]:
    root = project_dir.parent
    return [
        path for path in root.glob("*/project_memory.json")
        if path.parent != project_dir
    ]


def load_relevant_memories(
    project_dir: Path,
    project_name: str,
    brief: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    query_tokens = _tokenize(project_name) | _tokenize(brief)
    scored: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for path in _memory_candidates(project_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        memory_tokens = _tokenize(payload.get("project", "")) | _tokenize(payload.get("brief_excerpt", ""))
        memory_tokens |= {
            token
            for question in payload.get("open_questions", [])
            for token in _tokenize(str(question.get("question", "")))
        }
        overlap = len(query_tokens & memory_tokens)
        if overlap <= 0:
            continue
        scored.append(
            (
                (-overlap, -len(payload.get("key_findings", [])), path.as_posix()),
                payload,
            )
        )
    scored.sort(key=lambda item: item[0])
    return [payload for _, payload in scored[:limit]]


def build_memory_context(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return ""
    lines = ["## Related Project Memory"]
    for memory in memories:
        lines.append(f"### {memory.get('project', 'Unknown Project')}")
        findings = memory.get("key_findings", [])[:3]
        if findings:
            lines.append("Key findings:")
            for finding in findings:
                lines.append(
                    f"- {finding.get('statement', '')} "
                    f"(confidence={float(finding.get('confidence', 0.0)):.2f})"
                )
        open_questions = memory.get("open_questions", [])[:3]
        if open_questions:
            lines.append("Open questions carried forward:")
            for item in open_questions:
                lines.append(f"- {item.get('question', '')}")
        key_sources = memory.get("key_sources", [])[:3]
        if key_sources:
            lines.append("Useful sources from that project:")
            for source in key_sources:
                lines.append(f"- [{source.get('tier', '')}] {source.get('title', '')}")
    return "\n".join(lines)


def memory_seed_questions(memories: list[dict[str, Any]], limit: int = 6) -> list[str]:
    seeds: list[str] = []
    seen: set[str] = set()
    for memory in memories:
        for item in memory.get("open_questions", []):
            question = str(item.get("question", "")).strip()
            if not question:
                continue
            key = question.lower()
            if key in seen:
                continue
            seeds.append(question)
            seen.add(key)
            if len(seeds) >= limit:
                return seeds
    return seeds


def write_project_memory(
    project_dir: Path,
    project_name: str,
    brief: str,
    store: EvidenceStore,
) -> Path:
    claims = sorted(
        [claim for claim in store.claims() if claim.status == "verified"],
        key=lambda claim: (
            0 if claim.materiality == "core" else 1,
            -claim.confidence,
        ),
    )
    sources = sorted(store.sources(), key=lambda source: (tier_rank(source.tier), source.title))
    open_questions = [item.to_dict() for item in store.high_priority_open_items(limit=10)]

    payload = {
        "project": project_name,
        "brief_excerpt": brief[:500],
        "key_sources": [source.to_dict() for source in sources[:10]],
        "key_findings": [claim.to_dict() for claim in claims[:10]],
        "open_questions": open_questions,
    }
    path = project_dir / "project_memory.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def update_source_registry(project_dir: Path, store: EvidenceStore) -> Path:
    registry_path = project_dir.parent / "source_registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        registry = {}

    claims = store.claims()
    source_claims: dict[str, list[str]] = {}
    for claim in claims:
        for source_id in claim.source_ids:
            source_claims.setdefault(source_id, []).append(claim.status)

    for source in store.sources():
        key = source.url or source.title
        entry = registry.setdefault(
            key,
            {
                "title": source.title,
                "url": source.url,
                "publisher": source.publisher,
                "best_tier": source.tier,
                "projects": [],
                "verified_claim_count": 0,
                "flagged_claim_count": 0,
            },
        )
        if tier_rank(source.tier) < tier_rank(str(entry.get("best_tier", source.tier))):
            entry["best_tier"] = source.tier
        if project_dir.name not in entry["projects"]:
            entry["projects"].append(project_dir.name)
        statuses = source_claims.get(source.id, [])
        entry["verified_claim_count"] += sum(1 for status in statuses if status == "verified")
        entry["flagged_claim_count"] += sum(1 for status in statuses if status == "needs_revision")

    tmp_path = registry_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    os.replace(tmp_path, registry_path)
    return registry_path


def source_registry_guidance(project_dir: Path, memories: list[dict[str, Any]], limit: int = 6) -> str:
    registry_path = project_dir.parent / "source_registry.json"
    if not registry_path.exists():
        return ""
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    candidate_keys = {
        source.get("url") or source.get("title")
        for memory in memories
        for source in memory.get("key_sources", [])
    }
    lines = ["## Source Reputation Hints"]
    count = 0
    for key in candidate_keys:
        if not key or key not in registry:
            continue
        entry = registry[key]
        lines.append(
            f"- {entry.get('title', key)} [{entry.get('best_tier', '')}] "
            f"verified={entry.get('verified_claim_count', 0)} "
            f"flagged={entry.get('flagged_claim_count', 0)}"
        )
        count += 1
        if count >= limit:
            break
    return "\n".join(lines) if count else ""
