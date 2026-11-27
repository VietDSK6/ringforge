"""Policy Pack theo phiên: xem, phân tích tác động của bản vá, áp dụng (FR-P1..P3, docs/06 mục 4, T4.1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.backtest.metrics import Assumptions
from app.data.loader import transactions
from app.store import repo
from app.store.db import get_db
from app.verify.impact import PatchOp, apply_patch, pack_impact

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
