"""Structured evidence, claims, and agenda persistence for research sessions."""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


SourceTier = Literal[
    "tier1_primary",
    "tier2_journalism",
    "tier3_analysis",
    "tier4_expert",
    "tier5_unverified",
    "dataset",
]
AgendaOwner = Literal["qual", "quant", "shared"]
AgendaPriority = Literal["high", "medium", "low"]
AgendaStatus = Literal["open", "in_progress", "done"]
AgendaDifficulty = Literal["simple", "complex", "synthesis"]


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _slug_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def extract_json_block(text: str, block_name: str = "evidence_json") -> tuple[str, dict[str, Any]]:
    """
    Extract a fenced JSON block from an agent response and return (clean_text, payload).
    If parsing fails, returns the original text and an empty dict.
    """
    pattern = rf"```{re.escape(block_name)}\s*(\{{[\s\S]*?\}})\s*```"
    match = re.search(pattern, text)
    if not match:
        return text, {}

    payload_text = match.group(1).strip()
    clean = (text[:match.start()] + text[match.end():]).strip()
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return text, {}
    return clean, payload


def agenda_owner_from_text(text: str) -> AgendaOwner:
    ll = text.lower()
    quant_markers = (
        "chart", "price", "prices", "spread", "yield", "market", "returns",
        "correlation", "series", "ticker", "fred", "data", "volatility", "cpi",
    )
    qual_markers = (
        "policy", "speech", "statement", "official", "timeline", "actor",
        "diplomatic", "political", "regulatory", "geopolitical", "historical",
    )
    has_quant = any(token in ll for token in quant_markers)
    has_qual = any(token in ll for token in qual_markers)
    if has_quant and not has_qual:
        return "quant"
    if has_qual and not has_quant:
        return "qual"
    return "shared"


def priority_rank(priority: AgendaPriority) -> int:
    return {"high": 0, "medium": 1, "low": 2}[priority]


def difficulty_rank(difficulty: str) -> int:
    return {"simple": 0, "complex": 1, "synthesis": 2}.get(difficulty, 1)


def tier_rank(tier: str) -> int:
    return {
        "tier1_primary": 1,
        "tier2_journalism": 2,
        "tier3_analysis": 3,
        "dataset": 3,
        "tier4_expert": 4,
        "tier5_unverified": 5,
    }.get(tier, 99)


def classify_agenda_difficulty(text: str) -> AgendaDifficulty:
    ll = text.lower()
    simple_markers = (
        "price", "prices", "chart", "fetch", "retrieve", "download", "series",
        "fred", "ticker", "dataset", "table", "timeline", "count", "list",
    )
    synthesis_markers = (
        "synthesize", "implications", "thesis", "scenario", "compare perspectives",
        "conclusion", "recommendation", "memo", "outlook", "weight the evidence",
    )
    if any(token in ll for token in synthesis_markers):
        return "synthesis"
    if any(token in ll for token in simple_markers):
        return "simple"
    return "complex"


@dataclass
class SourceRecord:
    id: str
    title: str
    url: str
    tier: str
    publisher: str = ""
    published_at: str = ""
    summary: str = ""
    source_type: str = "web"
    agent_role: str = ""
    report_path: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimRecord:
    id: str
    statement: str
    agent_role: str
    confidence: float
    materiality: str = "supporting"
    kind: str = "finding"
    source_ids: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    report_path: str = ""
    status: str = "unverified"
    verification_notes: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgendaItem:
    id: str
    question: str
    owner: str
    priority: str = "medium"
    difficulty: str = "complex"
    status: str = "open"
    created_by: str = "system"
    note: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceStore:
    """Simple JSON-backed store for research evidence and agenda state."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir
        self.state_dir = reports_dir / "_state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.sources_path = self.state_dir / "sources.json"
        self.claims_path = self.state_dir / "claims.json"
        self.agenda_path = self.state_dir / "agenda.json"
        self.verification_path = self.state_dir / "verification.json"

    def _load_json(self, path: Path) -> list[dict[str, Any]] | dict[str, Any]:
        if not path.exists():
            return [] if path.suffix == ".json" and path.name != "verification.json" else {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [] if path.name != "verification.json" else {}

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def sources(self) -> list[SourceRecord]:
        raw = self._load_json(self.sources_path)
        return [SourceRecord(**item) for item in raw] if isinstance(raw, list) else []

    def claims(self) -> list[ClaimRecord]:
        raw = self._load_json(self.claims_path)
        return [ClaimRecord(**item) for item in raw] if isinstance(raw, list) else []

    def agenda(self) -> list[AgendaItem]:
        raw = self._load_json(self.agenda_path)
        return [AgendaItem(**item) for item in raw] if isinstance(raw, list) else []

    def save_sources(self, sources: list[SourceRecord]) -> None:
        self._write_json(self.sources_path, [s.to_dict() for s in sources])

    def save_claims(self, claims: list[ClaimRecord]) -> None:
        self._write_json(self.claims_path, [c.to_dict() for c in claims])

    def save_agenda(self, items: list[AgendaItem]) -> None:
        self._write_json(self.agenda_path, [i.to_dict() for i in items])

    def bootstrap_agenda(self, questions: list[str], created_by: str = "planner") -> None:
        existing = self.agenda()
        known = {item.question.strip().lower() for item in existing}
        for question in questions:
            clean = question.strip()
            if not clean or clean.lower() in known:
                continue
            existing.append(
                AgendaItem(
                    id=_slug_id("A"),
                    question=clean,
                    owner=agenda_owner_from_text(clean),
                    priority="high",
                    difficulty=classify_agenda_difficulty(clean),
                    created_by=created_by,
                )
            )
            known.add(clean.lower())
        self.save_agenda(existing)

    def add_agenda_items(
        self,
        items: list[dict[str, Any]],
        created_by: str,
        max_open_items: int | None = None,
    ) -> None:
        agenda = self.agenda()
        known = {item.question.strip().lower() for item in agenda}
        for item in items:
            if max_open_items is not None:
                open_count = sum(1 for existing in agenda if existing.status != "done")
                if open_count >= max_open_items:
                    break
            question = str(item.get("question", "")).strip()
            if not question or question.lower() in known:
                continue
            owner = str(item.get("owner", agenda_owner_from_text(question))).strip() or "shared"
            priority = str(item.get("priority", "medium")).strip().lower()
            if priority not in {"high", "medium", "low"}:
                priority = "medium"
            difficulty = str(item.get("difficulty", classify_agenda_difficulty(question))).strip().lower()
            if difficulty not in {"simple", "complex", "synthesis"}:
                difficulty = classify_agenda_difficulty(question)
            agenda.append(
                AgendaItem(
                    id=_slug_id("A"),
                    question=question,
                    owner=owner,
                    priority=priority,
                    difficulty=difficulty,
                    created_by=created_by,
                    note=str(item.get("note", "")).strip(),
                )
            )
            known.add(question.lower())
        self.save_agenda(agenda)

    def mark_agenda_done(self, item_ids: list[str], note: str = "") -> None:
        if not item_ids:
            return
        agenda = self.agenda()
        wanted = set(item_ids)
        for item in agenda:
            if item.id in wanted:
                item.status = "done"
                item.updated_at = _now_iso()
                if note:
                    item.note = note
        self.save_agenda(agenda)

    def claim_work_started(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        agenda = self.agenda()
        wanted = set(item_ids)
        for item in agenda:
            if item.id in wanted and item.status == "open":
                item.status = "in_progress"
                item.updated_at = _now_iso()
        self.save_agenda(agenda)

    def open_items(self, owner: str, limit: int = 3) -> list[AgendaItem]:
        agenda = [
            item for item in self.agenda()
            if item.status != "done" and item.owner in {owner, "shared"}
        ]
        agenda.sort(
            key=lambda item: (
                priority_rank(item.priority),
                difficulty_rank(item.difficulty),
                item.created_at,
            )
        )
        return agenda[:limit]

    def unresolved_count(self) -> int:
        return sum(1 for item in self.agenda() if item.status != "done")

    def claims_for_agent(self, agent_role: str, limit: int = 3) -> list[ClaimRecord]:
        claims = [claim for claim in self.claims() if claim.agent_role == agent_role]
        claims.sort(key=lambda claim: (-claim.confidence, claim.created_at))
        return claims[:limit]

    def sources_for_agent(self, agent_role: str, limit: int = 3) -> list[SourceRecord]:
        sources = [source for source in self.sources() if source.agent_role == agent_role]
        sources.sort(key=lambda source: (tier_rank(source.tier), source.created_at))
        return sources[:limit]

    def format_cross_agent_brief(self, agent_role: str, limit: int = 3) -> str:
        other_role = "quant_builder" if agent_role == "qual_builder" else "qual_builder"
        claims = self.claims_for_agent(other_role, limit=limit)
        sources = self.sources_for_agent(other_role, limit=limit)
        if not claims and not sources:
            return ""

        lines = [f"## Evidence From Your Partner ({other_role})"]
        if claims:
            lines.append("### Top Claims")
            for claim in claims:
                lines.append(
                    f"- [{claim.id}] ({claim.status}) {claim.statement} "
                    f"(confidence={claim.confidence:.2f})"
                )
        if sources:
            lines.append("### Top Sources")
            for source in sources:
                lines.append(
                    f"- [{source.id}] [{source.tier}] {source.title} — "
                    f"{source.publisher or source.url or 'unknown source'}"
                )
        return "\n".join(lines)

    def latest_verification(self) -> dict[str, Any]:
        raw = self._load_json(self.verification_path)
        return raw if isinstance(raw, dict) else {}

    def high_priority_open_items(self, limit: int = 10) -> list[AgendaItem]:
        items = [
            item for item in self.agenda()
            if item.status != "done" and item.priority == "high"
        ]
        items.sort(key=lambda item: (difficulty_rank(item.difficulty), item.created_at))
        return items[:limit]

    def write_verification(self, verdict: str, summary: str, findings: list[dict[str, Any]]) -> None:
        payload = {
            "verdict": verdict,
            "summary": summary,
            "findings": findings,
            "created_at": _now_iso(),
        }
        self._write_json(self.verification_path, payload)

    def ingest_payload(
        self,
        agent_role: str,
        payload: dict[str, Any],
        report_path: Path,
        artifact_paths: list[str] | None = None,
        max_open_items: int | None = None,
    ) -> dict[str, int]:
        artifact_paths = artifact_paths or []
        sources = self.sources()
        claims = self.claims()

        source_lookup: dict[str, str] = {}
        for raw_source in payload.get("sources", []):
            title = str(raw_source.get("title", "")).strip()
            url = str(raw_source.get("url", "")).strip()
            if not title and not url:
                continue
            existing = next(
                (
                    source for source in sources
                    if (url and source.url == url) or (
                        not url and source.title.strip().lower() == title.lower()
                    )
                ),
                None,
            )
            if existing:
                canonical_id = existing.id
            else:
                canonical_id = _slug_id("SRC")
                tier = str(raw_source.get("tier", "tier4_expert")).strip().lower()
                sources.append(
                    SourceRecord(
                        id=canonical_id,
                        title=title or url or canonical_id,
                        url=url,
                        tier=tier,
                        publisher=str(raw_source.get("publisher", "")).strip(),
                        published_at=str(raw_source.get("published_at", "")).strip(),
                        summary=str(raw_source.get("summary", "")).strip(),
                        source_type=str(raw_source.get("source_type", "web")).strip() or "web",
                        agent_role=agent_role,
                        report_path=str(report_path),
                    )
                )
            local_id = str(raw_source.get("id", canonical_id)).strip() or canonical_id
            source_lookup[local_id] = canonical_id

        for raw_claim in payload.get("claims", []):
            statement = str(raw_claim.get("statement", "")).strip()
            if not statement:
                continue
            confidence = raw_claim.get("confidence", 0.5)
            try:
                confidence_float = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence_float = 0.5
            mapped_sources = [
                source_lookup.get(str(source_id).strip(), str(source_id).strip())
                for source_id in raw_claim.get("source_ids", [])
                if str(source_id).strip()
            ]
            claims.append(
                ClaimRecord(
                    id=_slug_id("CLM"),
                    statement=statement,
                    agent_role=agent_role,
                    confidence=confidence_float,
                    materiality=str(raw_claim.get("materiality", "supporting")).strip().lower() or "supporting",
                    kind=str(raw_claim.get("kind", "finding")).strip().lower() or "finding",
                    source_ids=mapped_sources,
                    artifact_paths=list(artifact_paths),
                    report_path=str(report_path),
                )
            )

        self.save_sources(sources)
        self.save_claims(claims)
        self.mark_agenda_done([str(item_id).strip() for item_id in payload.get("addressed_agenda_ids", [])])
        self.add_agenda_items(
            payload.get("new_agenda_items", []),
            created_by=agent_role,
            max_open_items=max_open_items,
        )
        return {"sources": len(payload.get("sources", [])), "claims": len(payload.get("claims", []))}

    def annotate_claim_statuses(self, updates: dict[str, tuple[str, str]]) -> None:
        claims = self.claims()
        for claim in claims:
            if claim.id in updates:
                claim.status, claim.verification_notes = updates[claim.id]
        self.save_claims(claims)
