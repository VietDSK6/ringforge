"""Nhập/xuất bộ luật + Policy Pack dạng JSON (FR-S8, T4.6): giám khảo mang bộ luật của mình vào sandbox
và được kiểm chứng ngay. File xuất ra nhập lại được nguyên vẹn."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.data.loader import transactions
from app.dsl.catalog import DSL_VERSION
from app.dsl.render_vi import render_rule
from app.dsl.validator import Issue, check_pack, check_rules
from app.store import repo
from app.store.db import get_db
from app.verify.checks import verify_rules
from app.verify.grounding import ground_findings

router = APIRouter(prefix="/sessions", tags=["import-export"])
Db = Annotated[Session, Depends(get_db)]

EXPORT_FORMAT = "ringforge-export/1"
MAX_IMPORT_RULES = 50


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # chấp nhận nguyên file xuất (format, dsl_version, exported_at…)
    rules: list[dict[str, Any]] | None = Field(default=None, max_length=MAX_IMPORT_RULES)
    policy_pack: dict[str, Any] | None = None
    mode: Literal["replace", "merge"] = Field(default="replace", description="replace: thay toàn bộ bộ luật; merge: thêm/thay từng luật")


EXAMPLE_RULE = {
    "id": "MY-01", "name": "Giữ chuyển lớn ban đêm cho tài khoản nhận mới", "kind": "FRAUD", "status": "ACTIVE",
    "when": {"all": [{"field": "amount", "op": ">=", "value": 3_000_000},
                     {"field": "receiver_account_age_days", "op": "<", "value": 3},
                     {"field": "hour", "op": "between", "value": [0, 5]}]},
    "then": {"decision": "HOLD", "hold_seconds": 120},
}
EXAMPLES = {"merge": {"summary": "Thêm một luật của bạn vào bộ luật đang chạy", "value": {"mode": "merge", "rules": [EXAMPLE_RULE]}}}


@router.get("/{sid}/export", summary="Xuất bộ luật + Policy Pack hiện hành (JSON, nhập lại được)")
def export(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    rules = repo.current_rules(db, sid)
    repo.audit(db, sid, "user:proposer", "ruleset.export", {"rules": len(rules), "pack_version": pack["version"]})
    db.commit()
    return {
        "format": EXPORT_FORMAT,
        "dsl_version": DSL_VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "policy_pack": pack,
        "rules": rules,
    }


@router.post("/{sid}/import", summary="Nhập bộ luật và/hoặc Policy Pack JSON rồi kiểm chứng ngay")
def import_(sid: str, req: Annotated[ImportRequest, Body(openapi_examples=EXAMPLES)], db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    if req.rules is None and req.policy_pack is None:
        raise AppError(422, "VALIDATION_ERROR", "Cần ít nhất 'rules' hoặc 'policy_pack' để nhập.")
    pack = repo.current_pack(db, sid)
    new_pack = None
    if req.policy_pack is not None:
        new_pack, issues = check_pack(req.policy_pack)
        if new_pack is None:
            raise AppError(422, "VALIDATION_ERROR", "Policy Pack nhập vào không hợp lệ.", [i.to_dict() for i in issues])
        pack = new_pack
    rules = None
    if req.rules is not None:
        rules, issues = check_rules(req.rules, pack)
        if req.mode == "merge" and not issues:
            locked = {r["id"] for r in repo.current_rules(db, sid) if r.get("locked")}
            issues = [Issue(f"Luật {r['id']} là luật pháp lý bị khóa, không ghi đè khi nhập kiểu merge.", "", r["id"]) for r in rules if r["id"] in locked]
        if issues:
            raise AppError(422, "VALIDATION_ERROR", "Bộ luật nhập vào không hợp lệ.", [i.to_dict() for i in issues])
        if req.mode == "replace" and not rules:
            raise AppError(422, "VALIDATION_ERROR", "Bộ luật nhập vào rỗng.")
    elif new_pack is not None:
        # Chỉ đổi pack: luật hiện có phải còn hợp lệ với pack mới (ví dụ tham số mà luật tham chiếu).
        _, issues = check_rules(repo.current_rules(db, sid), new_pack)
        if issues:
            raise AppError(422, "VALIDATION_ERROR", "Bộ luật hiện tại không hợp lệ với Policy Pack nhập vào.", [i.to_dict() for i in issues])

    repo.import_ruleset(db, sid, rules, new_pack, replace=req.mode == "replace")
    current = repo.current_rules(db, sid)
    report = verify_rules(current, pack)
    ground_findings(report["checks"], current, pack, transactions())
    report["rules_vi"] = {r["id"]: render_rule(r, pack)["sentence_vi"] for r in current}
    run_id = repo.add_verify_run(db, sid, {"rules": current, "pack": pack["version"]}, report)
    repo.audit(db, sid, "system", "verify.run", {"verify_run_id": run_id, "verdict": report["verdict"], "after": "import"})
    db.commit()
    return {
        "imported": {"rules": len(rules or []), "policy_pack": new_pack["version"] if new_pack else None, "mode": req.mode},
        "rules_total": len(current),
        "verify": report | {"verify_run_id": run_id},
    }
