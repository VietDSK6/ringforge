"""Truy cập dữ liệu theo phiên sandbox (mỗi giám khảo một phiên, clone từ seed — quyết định D6)."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.data.loader import seed_pack, seed_rules
from app.store.models import (
    AICallRow,
    AuditRow,
    BacktestRunRow,
    ChangeSetRow,
    PolicyPackRow,
    RuleRow,
    SessionRow,
    VerifyRunRow,
    now,
)

SESSION_TTL = timedelta(days=3)  # docs/06: xóa phiên không hoạt động > 3 ngày


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ---------- phiên ----------


def _seed_into(db: Session, sid: str) -> None:
    pack = seed_pack()
    db.add(PolicyPackRow(session_id=sid, version=pack["version"], body=copy.deepcopy(pack), is_current=True))
    for i, r in enumerate(seed_rules()):
        db.add(RuleRow(session_id=sid, rule_id=r["id"], version=r["version"], body=copy.deepcopy(r), status=r["status"], ordinal=i))


def create_session(db: Session, label: str | None = None) -> SessionRow:
    s = SessionRow(label=label)
    db.add(s)
    db.flush()
    _seed_into(db, s.id)
    audit(db, s.id, "system", "session.create", {"pack_version": seed_pack()["version"], "rules": len(seed_rules())})
    db.commit()
    return s


def get_session(db: Session, sid: str) -> SessionRow:
    s = db.get(SessionRow, sid)
    if s is None:
        raise NotFound(sid)
    s.last_seen_at = now()
    return s


def reset_session(db: Session, sid: str) -> None:
    get_session(db, sid)
    db.execute(delete(RuleRow).where(RuleRow.session_id == sid))
    db.execute(delete(PolicyPackRow).where(PolicyPackRow.session_id == sid))
    db.execute(delete(ChangeSetRow).where(ChangeSetRow.session_id == sid))
    _seed_into(db, sid)
    audit(db, sid, "system", "session.reset", None)
    db.commit()


def cleanup_stale_sessions(db: Session) -> int:
    cutoff = now() - SESSION_TTL
    ids = list(db.scalars(select(SessionRow.id).where(SessionRow.last_seen_at < cutoff)))
    if ids:
        db.execute(delete(SessionRow).where(SessionRow.id.in_(ids)))
        db.commit()
    return len(ids)


# ---------- Policy Pack & luật ----------


def current_pack(db: Session, sid: str) -> dict[str, Any]:
    row = db.scalars(
        select(PolicyPackRow).where(PolicyPackRow.session_id == sid, PolicyPackRow.is_current.is_(True))
    ).first()
    if row is None:
        raise NotFound(f"pack:{sid}")
    return copy.deepcopy(row.body)


def save_pack(db: Session, sid: str, pack: dict[str, Any], actor: str = "user:proposer", ref: dict[str, Any] | None = None) -> dict[str, Any]:
    """Lưu Policy Pack phiên bản mới và đặt làm hiện hành (bản cũ giữ lại để truy vết)."""
    get_session(db, sid)
    for row in db.scalars(select(PolicyPackRow).where(PolicyPackRow.session_id == sid, PolicyPackRow.is_current.is_(True))):
        row.is_current = False
    db.add(PolicyPackRow(session_id=sid, version=pack["version"], body=copy.deepcopy(pack), is_current=True))
    audit(db, sid, actor, "pack.apply", (ref or {}) | {"version": pack["version"]})
    db.commit()
    return copy.deepcopy(pack)


def pack_history(db: Session, sid: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(PolicyPackRow).where(PolicyPackRow.session_id == sid).order_by(PolicyPackRow.created_at)).all()
    return [{"version": r.version, "is_current": r.is_current, "created_at": r.created_at.isoformat()} for r in rows]


def current_rules(db: Session, sid: str) -> list[dict[str, Any]]:
    """Phiên bản mới nhất của mỗi luật, giữ thứ tự tạo (seed trước, luật mới sau)."""
    latest = (
        select(RuleRow.rule_id, func.max(RuleRow.version).label("v"))
        .where(RuleRow.session_id == sid)
        .group_by(RuleRow.rule_id)
        .subquery()
    )
    rows = db.scalars(
        select(RuleRow)
        .join(latest, (RuleRow.rule_id == latest.c.rule_id) & (RuleRow.version == latest.c.v))
        .where(RuleRow.session_id == sid)
    ).all()
    rows = sorted(rows, key=lambda r: (r.ordinal, r.rule_id))
    return [copy.deepcopy(r.body) for r in rows]


def save_rule(db: Session, sid: str, rule: dict[str, Any], actor: str = "user:proposer") -> dict[str, Any]:
    """Lưu phiên bản mới của luật (đã qua VC-01). Luật pháp lý bị khóa không sửa được qua UI."""
    existing = {r["id"]: r for r in current_rules(db, sid)}
    old = existing.get(rule["id"])
    if old is not None and old.get("locked"):
        raise Forbidden(rule["id"])
    version = 1 + (db.scalar(
        select(func.max(RuleRow.version)).where(RuleRow.session_id == sid, RuleRow.rule_id == rule["id"])
    ) or 0)
    ordinal = db.scalar(select(func.min(RuleRow.ordinal)).where(RuleRow.session_id == sid, RuleRow.rule_id == rule["id"]))
    if ordinal is None:
        ordinal = 1 + (db.scalar(select(func.max(RuleRow.ordinal)).where(RuleRow.session_id == sid)) or 0)
    body = copy.deepcopy(rule) | {"version": version}
    db.add(RuleRow(session_id=sid, rule_id=rule["id"], version=version, body=body, status=body["status"], ordinal=ordinal))
    audit(db, sid, actor, "rule.save", {"rule_id": rule["id"], "version": version, "status": body["status"]})
    db.commit()
    return body


def next_draft_id(db: Session, sid: str) -> str:
    ids = set(db.scalars(select(RuleRow.rule_id).where(RuleRow.session_id == sid, RuleRow.rule_id.like("DRAFT-%"))))
    n = 1
    while f"DRAFT-{n:04d}" in ids:
        n += 1
    return f"DRAFT-{n:04d}"


# ---------- kết quả chạy, AI, audit ----------


def add_verify_run(db: Session, sid: str, input_obj: Any, result: dict[str, Any]) -> str:
    row = VerifyRunRow(session_id=sid, input_hash=stable_hash(input_obj), result=result, ms=int(result.get("ms", 0)))
    db.add(row)
    db.flush()
    return row.id


def add_backtest_run(db: Session, sid: str, input_obj: Any, result: dict[str, Any], ms: int) -> str:
    row = BacktestRunRow(session_id=sid, input_hash=stable_hash(input_obj), result=result, ms=ms)
    db.add(row)
    db.flush()
    return row.id


def add_ai_call(db: Session, sid: str | None, **fields: Any) -> str:
    row = AICallRow(session_id=sid, **fields)
    db.add(row)
    db.flush()
    return row.id


def use_llm_quota(db: Session, sid: str, session_cap: int, global_cap: int) -> bool:
    """Trừ một lượt gọi LLM; False nếu vượt hạn mức phiên/ngày hoặc toàn hệ thống/ngày (NFR-7)."""
    s = get_session(db, sid)
    today = now().date().isoformat()
    if s.llm_calls_day != today:
        s.llm_calls_day, s.llm_calls_today = today, 0
    start_of_day = now().replace(hour=0, minute=0, second=0, microsecond=0)
    global_used = db.scalar(
        select(func.count(AICallRow.id)).where(AICallRow.created_at >= start_of_day, AICallRow.from_cache.is_(False))
    ) or 0
    if s.llm_calls_today >= session_cap or global_used >= global_cap:
        return False
    s.llm_calls_today += 1
    return True


# ---------- change set ----------


def change_set_dict(row: ChangeSetRow) -> dict[str, Any]:
    return {
        "id": row.id, "state": row.state, "items": row.items, "pack_version": row.pack_version,
        "verify_run_id": row.verify_run_id, "backtest_run_id": row.backtest_run_id, "summary": row.summary,
        "note": row.note, "decision_note": row.decision_note,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None, "created_at": row.created_at.isoformat(),
    }


def add_change_set(db: Session, sid: str, **fields: Any) -> ChangeSetRow:
    row = ChangeSetRow(session_id=sid, **fields)
    db.add(row)
    db.flush()
    return row


def get_change_set(db: Session, sid: str, cs_id: str) -> ChangeSetRow:
    row = db.get(ChangeSetRow, cs_id)
    if row is None or row.session_id != sid:
        raise NotFound(cs_id)
    return row


def list_change_sets(db: Session, sid: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(ChangeSetRow).where(ChangeSetRow.session_id == sid).order_by(ChangeSetRow.created_at.desc())).all()
    return [change_set_dict(r) for r in rows]


def audit(db: Session, sid: str, actor: str, action: str, ref: dict[str, Any] | None) -> None:
    db.add(AuditRow(session_id=sid, actor=actor, action=action, ref=ref))


def list_audit(db: Session, sid: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AuditRow).where(AuditRow.session_id == sid).order_by(AuditRow.id.desc()).limit(limit)
    ).all()
    # FR-A3: bản ghi của AI kèm model, phiên bản prompt và hash prompt (lấy từ ai_calls).
    call_ids = {r.ref["ai_call_id"] for r in rows if isinstance(r.ref, dict) and r.ref.get("ai_call_id")}
    calls = {c.id: c for c in db.scalars(select(AICallRow).where(AICallRow.id.in_(call_ids)))} if call_ids else {}
    out = []
    for r in rows:
        e = {"id": r.id, "actor": r.actor, "action": r.action, "ref": r.ref, "created_at": r.created_at.isoformat()}
        c = calls.get((r.ref or {}).get("ai_call_id")) if isinstance(r.ref, dict) else None
        if c is not None:
            e["ai_call"] = {"model": c.model, "prompt_version": c.prompt_version, "prompt_hash": c.prompt_hash[:12],
                            "from_cache": c.from_cache, "schema_valid": c.schema_valid, "latency_ms": c.latency_ms}
        out.append(e)
    return out
