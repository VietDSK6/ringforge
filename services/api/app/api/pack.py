"""Policy Pack theo phiên: xem, phân tích tác động của bản vá, áp dụng (FR-P1..P3, docs/06 mục 4, T4.1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.client import LLMError, get_client
from app.ai.interpret_task import MAX_TEXT, interpret_regulation
from app.ai.repair_task import _data_json, propose_repairs
from app.dsl.render_vi import render_rule
from app.api.errors import AppError
from app.backtest.metrics import Assumptions
from app.config import settings
from app.data.loader import transactions
from app.store import repo
from app.store.db import get_db
from app.backtest.metrics import run_backtest
from app.verify.impact import PatchOp, apply_patch, evaluate_pack_fix, pack_fix_rank_key, pack_impact

router = APIRouter(prefix="/sessions", tags=["pack"])
Db = Annotated[Session, Depends(get_db)]

DEMO2_PATCH = [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": 5_000_000, "source": "Kịch bản giả lập Demo 2 — không phải quy định thật"}]
EXAMPLES = {"demo2": {"summary": "Demo 2 — hạ ngưỡng sinh trắc học/lần 10tr → 5tr (giả lập)", "value": {"patch": DEMO2_PATCH}}}


class PatchRequest(BaseModel):
    patch: list[PatchOp] = Field(min_length=1, max_length=20, description="set_param | add_invariant | remove_invariant")
    assumptions: Assumptions = Field(default_factory=Assumptions)


def _patched(db: Session, sid: str, req: PatchRequest) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    repo.get_session(db, sid)
    old = repo.current_pack(db, sid)
    new, issues, changes = apply_patch(old, req.patch)
    if new is None:
        raise AppError(422, "VALIDATION_ERROR", "Bản vá Policy Pack không hợp lệ.", [i.to_dict() for i in issues])
    if not changes:
        raise AppError(422, "VALIDATION_ERROR", "Bản vá không thay đổi gì so với Policy Pack hiện hành.")
    return old, new, changes


@router.get("/{sid}/pack/history", summary="Các phiên bản Policy Pack của phiên")
def pack_history(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    db.commit()
    return {"versions": repo.pack_history(db, sid)}


@router.post("/{sid}/pack/impact", summary="Phân tích tác động của bản vá Policy Pack: kiểm chứng lại + luật bị ảnh hưởng + ma sát trước/sau")
def impact(sid: str, req: Annotated[PatchRequest, Body(openapi_examples=EXAMPLES)], db: Db) -> dict[str, Any]:
    old, new, changes = _patched(db, sid, req)
    result = pack_impact(repo.current_rules(db, sid), old, new, changes, transactions(), req.assumptions)
    repo.audit(db, sid, "system", "pack.impact", {
        "from": old["version"], "changes": changes, "verdict_after": result["verify_after"]["verdict"],
        "incompatible": [r["id"] for r in result["rules"] if r["category"] == "incompatible"],
    })
    db.commit()
    return result


@router.post("/{sid}/pack/apply", summary="Áp dụng bản vá → Policy Pack phiên bản mới (người dùng đã xác nhận)")
def apply(sid: str, req: Annotated[PatchRequest, Body(openapi_examples=EXAMPLES)], db: Db) -> dict[str, Any]:
    old, new, changes = _patched(db, sid, req)
    saved = repo.save_pack(db, sid, new, ref={"from": old["version"], "changes": changes})
    return {"pack": saved, "previous_version": old["version"], "changes": changes}


LLM_DOWN_VI = "AI tạm thời không khả dụng — bạn vẫn sửa tham số trực tiếp ở bảng Tham số và phân tích tác động như bình thường."
INTERPRET_EXAMPLE = {"demo": {"summary": "Quy định giả lập: hạ ngưỡng sinh trắc học/lần",
                              "value": {"text": "Từ 01/01/2027, giao dịch chuyển tiền trên 5 triệu đồng/lần phải xác thực sinh trắc học (kịch bản giả lập)."}}}


class InterpretRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT, description="Đoạn mô tả quy định mới (tiếng Việt)")


@router.post("/{sid}/pack/interpret", summary="AI đọc mô tả quy định mới → ĐỀ XUẤT bản vá Policy Pack (không tự áp dụng)")
def interpret(sid: str, req: Annotated[InterpretRequest, Body(openapi_examples=INTERPRET_EXAMPLE)], db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    client = get_client()
    if not client.available:
        raise AppError(503, "LLM_UNAVAILABLE", LLM_DOWN_VI)
    if not repo.use_llm_quota(db, sid, settings.llm_session_daily_cap, settings.llm_daily_call_cap):
        db.commit()
        raise AppError(429, "LLM_QUOTA", "Đã hết lượt gọi AI hôm nay cho phiên này. " + LLM_DOWN_VI)
    try:
        result = interpret_regulation(db, sid, req.text, pack, client)
    except LLMError as e:
        db.commit()
        raise AppError(503, "LLM_UNAVAILABLE", LLM_DOWN_VI, {"reason": e.code}) from e
    repo.audit(db, sid, "ai", "pack.interpret", {
        "ai_call_id": result["ai_call_id"], "status": result["status"], "changes": result.get("changes", []), "model": result["model"],
    })
    db.commit()
    return result


# ---------- Sửa luật không còn tương thích sau khi đổi Policy Pack (tất định + AI) ----------

PACK_REPAIR_VERSION = "pack_repair.v1"
MAX_AI_ROUNDS = 2


class PackRepairRequest(PatchRequest):
    rule_id: str = Field(min_length=1, max_length=32, description="Luật cần sửa (thường là luật không còn tương thích)")
    use_ai: bool = Field(default=True, description="Gọi AI đề xuất thêm bản sửa (nếu khả dụng)")


def _pack_repair_user(original, entry, changes, old_pack, feedback: list[str] | None) -> str:
    rule = {k: original.get(k) for k in ("name", "description", "kind", "when", "then")}
    rule["sentence_vi_truoc_khi_doi"] = render_rule(original, old_pack)["sentence_vi"]
    reasons = [{k: r.get(k) for k in ("code", "message_vi", "counterexample", "outcomes")} for r in entry["reasons"]]
    msg = (f"<original_rule>{_data_json(rule)}</original_rule>\n<pack_change>{_data_json(changes)}</pack_change>\n"
           f"<impact>{_data_json(reasons)}</impact>")
    if feedback:
        msg += "\n\nCác bản sửa trước đều bị bộ kiểm chứng loại vì:\n" + "\n".join(f"- {f}" for f in feedback) + "\nHãy đề xuất lại."
    return msg


def _reject_reason(ev: dict[str, Any]) -> str | None:
    if not ev["passes"]:
        return "Không qua kiểm chứng: " + " ".join(c["message_vi"] for c in ev["remaining_checks"] if c["severity"] == "ERROR")
    if ev["stale_params"]:
        return "Vẫn viết cứng giá trị cũ của tham số vừa đổi."
    return None


@router.post("/{sid}/pack/repair", summary="Bản sửa cho luật không còn tương thích với Policy Pack mới (tất định + AI), đã kiểm chứng lại")
def pack_repair(sid: str, req: PackRepairRequest, db: Db) -> dict[str, Any]:
    old, new, changes = _patched(db, sid, req)
    rules = repo.current_rules(db, sid)
    original = next((r for r in rules if r["id"] == req.rule_id), None)
    if original is None:
        raise AppError(404, "NOT_FOUND", f"Không có luật {req.rule_id} trong phiên này.")
    if original.get("locked"):
        raise AppError(403, "FORBIDDEN", f"Luật {req.rule_id} là luật pháp lý bị khóa, không sửa qua giao diện.")
    df = transactions()
    impact_result = pack_impact(rules, old, new, changes, df, req.assumptions)
    entry = next(r for r in impact_result["rules"] if r["id"] == req.rule_id)
    if entry["category"] not in ("incompatible", "review"):
        return {"needed": False, "rule_id": req.rule_id, "candidates": [], "rejected": [], "llm": "not_needed",
                "message_vi": f"Luật {req.rule_id} vẫn tương thích với Policy Pack mới — không cần sửa."}
    baseline = run_backtest(rules, df, new, req.assumptions)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    def judge(proposals: list[dict[str, Any]]) -> list[str]:
        reasons = []
        for p in proposals:
            sig = [(r["when"], r["then"]) for r in p["rules"]]
            if any(sig == [(r["when"], r["then"]) for r in c["rules"]] for c in candidates):
                continue
            ev = evaluate_pack_fix(p["rules"], original, rules, old, new, changes, df, baseline)
            entry_ = {k: v for k, v in p.items() if k != "rules"} | ev
            why = _reject_reason(ev)
            if why is None:
                candidates.append(entry_)
            else:
                rejected.append({"source": p["source"], "strategy": p["strategy"], "reason_vi": why})
                reasons.append(f"{p['strategy']}: {why}")
        return reasons

    fix = entry.get("fix")
    if fix and fix.get("rule"):
        det_rule = {k: v for k, v in fix["rule"].items() if k != "render"}
        judge([{"source": "det", "strategy": "PARAM_REF", "rationale_vi": " ".join(fix["notes_vi"]),
                "intent_preserved_vi": "Giữ nguyên các điều kiện khác và hành động gốc.", "intent_lost_vi": "", "rules": [det_rule]}])

    llm = "not_requested"
    if req.use_ai:
        client = get_client()
        llm = "unavailable" if not client.available else "used"
        feedback: list[str] | None = None
        for _ in range(MAX_AI_ROUNDS if client.available else 0):
            if not repo.use_llm_quota(db, sid, settings.llm_session_daily_cap, settings.llm_daily_call_cap):
                llm = "quota"
                break
            try:
                proposals, bad = propose_repairs(db, sid, original, [], new, client, version=PACK_REPAIR_VERSION,
                                                 user=_pack_repair_user(original, entry, changes, old, feedback))
            except LLMError:
                llm = "error"
                break
            rejected.extend(bad)
            reasons = judge(proposals)
            if proposals and len(reasons) < len(proposals):
                break
            feedback = reasons + [r["reason_vi"] for r in bad]
    candidates.sort(key=pack_fix_rank_key)
    for i, c in enumerate(candidates, 1):
        c["rank"] = i
    repo.audit(db, sid, "system", "pack.repair", {"rule_id": req.rule_id, "accepted": len(candidates), "rejected": len(rejected), "llm": llm})
    db.commit()
    return {"needed": True, "rule_id": req.rule_id, "category": entry["category"], "reasons": entry["reasons"],
            "pack_after_version": new["version"], "candidates": candidates, "rejected": rejected, "llm": llm}
