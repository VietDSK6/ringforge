"""GET /catalog, POST /verify (T1.6). Bản có phiên (/sessions/{sid}/verify) làm ở T2.4."""

from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.data.loader import seed_pack, seed_rules
from app.dsl.catalog import catalog_payload
from app.dsl.render_vi import render_rule
from app.dsl.validator import check_pack, check_rules
from app.verify.checks import verify_rules

router = APIRouter()

MAX_RULES = 50

DEMO1_RULE = {
    "id": "DRAFT-0001",
    "name": "Fast-path khách thân thiết",
    "kind": "FRICTION",
    "status": "CANDIDATE",
    "when": {
        "all": [
            {"field": "sender_account_age_days", "op": ">", "value": 365},
            {"field": "receiver_is_familiar", "op": "==", "value": True},
        ]
    },
    "then": {"exempt_auth": True},
}


class VerifyRequest(BaseModel):
    rules: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_RULES, description="Luật theo rf-dsl/0.1")
    include_seed_rules: bool = Field(
        default=False,
        description="Gộp thêm bộ luật seed đang chạy; luật gửi lên cùng id sẽ thay luật seed (FR-V2: kiểm trên toàn bộ bộ luật).",
    )
    policy_pack: dict[str, Any] | None = Field(default=None, description="Bỏ trống để dùng Policy Pack seed.")


EXAMPLES = {
    "demo1": {
        "summary": "Demo 1 — luật miễn xác thực cho khách thân thiết",
        "value": {"rules": [DEMO1_RULE], "include_seed_rules": True},
    },
    "seed": {"summary": "Chỉ bộ luật seed", "value": {"rules": [], "include_seed_rules": True}},
}


@router.get("/catalog", summary="Danh mục trường, toán tử, quyết định của Policy DSL")
def get_catalog() -> dict[str, Any]:
    return catalog_payload()


def _vc01_report(issues: list, started: int) -> dict[str, Any]:
    return {
        "verdict": "FAIL",
        "ms": (time.perf_counter_ns() - started) // 1_000_000,
        "checked": {"rules": [], "invariants": []},
        "checks": [i.to_dict() for i in issues],
    }


@router.post("/verify", summary="Kiểm chứng bộ luật với Policy Pack (VC-01, VC-03, VC-04)")
def post_verify(req: Annotated[VerifyRequest, Body(openapi_examples=EXAMPLES)]) -> dict[str, Any]:
    started = time.perf_counter_ns()
    if req.policy_pack is None:
        pack = seed_pack()
    else:
        pack, issues = check_pack(req.policy_pack)
        if pack is None:
            return _vc01_report(issues, started)

    rules, issues = check_rules(req.rules, pack)
    if issues:
        return _vc01_report(issues, started)
    if not rules and not req.include_seed_rules:
        return _vc01_report([], started) | {
            "checks": [{"code": "VC-01", "severity": "ERROR", "message_vi": "Bộ luật rỗng: gửi ít nhất một luật hoặc bật include_seed_rules."}]
        }
    if req.include_seed_rules:
        own = {r["id"] for r in rules}
        rules = [r for r in seed_rules() if r["id"] not in own] + rules

    report = verify_rules(rules, pack)
    report["rules_vi"] = {r["id"]: render_rule(r, pack)["sentence_vi"] for r in rules}
    report["ms"] = (time.perf_counter_ns() - started) // 1_000_000
    return report
