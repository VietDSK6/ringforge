"""API theo phiên sandbox (docs/06 mục 4): tạo/reset phiên, luật, Policy Pack, kiểm chứng, backtest, audit."""

from __future__ import annotations

import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.client import LLMError, get_client
from app.ai.tasks import MAX_TEXT, cache_key, compile_requirement, lookup_cache
from app.api.errors import AppError
from app.backtest.metrics import Assumptions, delta, run_backtest
from app.config import settings
from app.data.loader import transactions
from app.dsl.render_vi import render_rule
from app.dsl.validator import Issue, check_rule, check_rules
from app.store import repo
from app.store.db import get_db
from app.verify.checks import verify_rules

router = APIRouter(prefix="/sessions", tags=["sessions"])
Db = Annotated[Session, Depends(get_db)]

MAX_VARIANTS = 4


def with_sentence(rule: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    return rule | {"render": render_rule(rule, pack)}


def merge_rules(base: list[dict[str, Any]], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Luật trong `changes` thay luật cùng id trong `base`; luật mới thêm vào cuối."""
    by_id = {r["id"]: r for r in changes}
    merged = [by_id.pop(r["id"], r) for r in base]
    return merged + [r for r in changes if r["id"] in by_id]


def vc01_report(issues: list[Issue]) -> dict[str, Any]:
    return {"verdict": "FAIL", "ms": 0, "checked": {"rules": [], "invariants": []}, "checks": [i.to_dict() for i in issues]}


# ---------- phiên ----------


@router.post("", summary="Tạo phiên sandbox mới từ dữ liệu seed")
def create_session(db: Db) -> dict[str, Any]:
    s = repo.create_session(db)
    return {"session_id": s.id, "pack_version": repo.current_pack(db, s.id)["version"], "rules": len(repo.current_rules(db, s.id))}


@router.post("/{sid}/reset", summary="Đưa phiên về trạng thái seed")
def reset_session(sid: str, db: Db) -> dict[str, Any]:
    repo.reset_session(db, sid)
    return {"session_id": sid, "reset": True}


@router.get("/{sid}/pack", summary="Policy Pack hiện hành của phiên")
def get_pack(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    return repo.current_pack(db, sid)


@router.get("/{sid}/rules", summary="Luật hiện hành + candidate (kèm câu tiếng Việt)")
def get_rules(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    db.commit()
    return {"pack_version": pack["version"], "rules": [with_sentence(r, pack) for r in repo.current_rules(db, sid)]}


@router.put("/{sid}/rules/{rule_id}", summary="Lưu phiên bản mới của một luật")
def put_rule(sid: str, rule_id: str, rule: Annotated[dict[str, Any], Body()], db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    clean, issues = check_rule(rule | {"id": rule_id}, pack)
    if clean is None:
        return {"saved": False, "checks": [i.to_dict() for i in issues]}
    saved = repo.save_rule(db, sid, clean)
    return {"saved": True, "rule": with_sentence(saved, pack)}


@router.get("/{sid}/audit", summary="Nhật ký thao tác của phiên")
def get_audit(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    db.commit()
    return {"events": repo.list_audit(db, sid)}


# ---------- biên dịch bằng AI (T1) ----------

LLM_DOWN_VI = (
    "AI tạm thời không khả dụng — đang dùng kết quả đã lưu cho câu mẫu; "
    "bạn vẫn có thể sửa luật bằng JSON hoặc dùng sửa tất định."
)


class CompileRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT, description="Yêu cầu luật bằng tiếng Việt")


@router.post("/{sid}/compile", summary="Biên dịch yêu cầu tiếng Việt thành luật DSL (AI đề xuất, server kiểm VC-01)")
def compile_session(sid: str, req: CompileRequest, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    rules = repo.current_rules(db, sid)
    client = get_client()
    cached = lookup_cache(db, cache_key(req.text, pack, rules)) is not None
    if not cached:
        if not client.available:
            raise AppError(503, "LLM_UNAVAILABLE", LLM_DOWN_VI)
        if not repo.use_llm_quota(db, sid, settings.llm_session_daily_cap, settings.llm_daily_call_cap):
            db.commit()
            raise AppError(429, "LLM_QUOTA", "Đã hết lượt gọi AI hôm nay cho phiên này. " + LLM_DOWN_VI)
    try:
        result = compile_requirement(db, sid, req.text, pack, rules, client)
    except LLMError as e:
        raise AppError(503, "LLM_UNAVAILABLE", LLM_DOWN_VI, {"reason": e.code}) from e
    repo.audit(db, sid, "ai", "rule.compile", {
        "ai_call_id": result.ai_call_id, "status": result.status, "source": result.source,
        "rule_id": result.rule["id"] if result.rule else None, "model": result.model,
    })
    db.commit()
    return result.to_dict(pack)


# ---------- kiểm chứng ----------


class SessionVerifyRequest(BaseModel):
    rules: list[dict[str, Any]] = Field(default_factory=list, max_length=20, description="Luật mới/đổi; cùng id thì thay luật hiện hành")


@router.post("/{sid}/verify", summary="Kiểm chứng toàn bộ bộ luật của phiên cùng các luật thay đổi (FR-V2)")
def verify_session(sid: str, req: SessionVerifyRequest, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    changes, issues = check_rules(req.rules, pack)
    if issues:
        return vc01_report(issues)
    rules = merge_rules(repo.current_rules(db, sid), changes)
    report = verify_rules(rules, pack)
    report["rules_vi"] = {r["id"]: render_rule(r, pack)["sentence_vi"] for r in rules}
    run_id = repo.add_verify_run(db, sid, {"rules": rules, "pack": pack["version"]}, report)
    repo.audit(db, sid, "system", "verify.run", {"verify_run_id": run_id, "verdict": report["verdict"], "changed": [r["id"] for r in changes]})
    db.commit()
    return report | {"verify_run_id": run_id}


# ---------- backtest ----------


class RuleChange(BaseModel):
    op: Literal["add", "replace", "retire"]
    rule: dict[str, Any] | None = None
    rule_id: str | None = None


class Variant(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rule_changes: list[RuleChange] = Field(default_factory=list, max_length=10)


class BacktestRequest(BaseModel):
    variants: list[Variant] = Field(default_factory=list, max_length=MAX_VARIANTS)
    assumptions: Assumptions = Field(default_factory=Assumptions)


def _apply_changes(base: list[dict[str, Any]], changes: list[RuleChange], pack: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Issue]]:
    rules = [dict(r) for r in base]
    issues: list[Issue] = []
    for i, ch in enumerate(changes):
        if ch.op == "retire":
            rid = ch.rule_id or (ch.rule or {}).get("id")
            rules = [r | {"status": "RETIRED"} if r["id"] == rid else r for r in rules]
            continue
        clean, errs = check_rule(ch.rule, pack, i)
        if clean is None:
            issues += errs
            continue
        rules = merge_rules(rules, [clean])
    return rules, issues


@router.post("/{sid}/backtest", summary="Backtest bộ luật hiện hành và các phương án (L_net, phân rã kịch bản)")
def backtest_session(sid: str, req: BacktestRequest, db: Db) -> dict[str, Any]:
    started = time.perf_counter_ns()
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    base_rules = repo.current_rules(db, sid)
    df = transactions()
    baseline = run_backtest(base_rules, df, pack, req.assumptions)
    variants = []
    for v in req.variants:
        rules, issues = _apply_changes(base_rules, v.rule_changes, pack)
        if issues:
            variants.append({"name": v.name, "error": vc01_report(issues)})
            continue
        result = run_backtest(rules, df, pack, req.assumptions)
        variants.append({"name": v.name, "result": result, "delta": delta(result, baseline)})
    ms = (time.perf_counter_ns() - started) // 1_000_000
    body = {"baseline": baseline, "variants": variants, "ms": ms}
    run_id = repo.add_backtest_run(db, sid, req.model_dump(), body, ms)
    repo.audit(db, sid, "system", "backtest.run", {"backtest_run_id": run_id, "variants": [v.name for v in req.variants]})
    db.commit()
    return body | {"backtest_run_id": run_id}
