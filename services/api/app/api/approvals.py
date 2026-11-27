"""Change set + phê duyệt (FR-A1, FR-A2, docs/06 mục 4, T4.5).

Change set = ảnh chụp các luật thay đổi + kết quả kiểm chứng, backtest trước/sau, semantic diff (VC-07).
Phê duyệt KIỂM CHỨNG LẠI với bộ luật và Policy Pack hiện tại (có thể đã đổi từ lúc tạo); FAIL hoặc
không kết luận được thì từ chối phê duyệt. Mọi bước ghi audit (người đề xuất, người duyệt, hệ thống).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.backtest.metrics import Assumptions, delta, run_backtest
from app.data.loader import transactions
from app.dsl.render_vi import render_rule
from app.dsl.validator import Issue, check_rule
from app.store import repo
from app.store.db import get_db
from app.store.models import now
from app.verify.checks import verify_rules
from app.verify.grounding import ground_findings
from app.verify.semantic_diff import semantic_diff

router = APIRouter(prefix="/sessions", tags=["approvals"])
Db = Annotated[Session, Depends(get_db)]

PASSING = ("PASS", "PASS_WITH_WARNINGS")
SUMMARY_KEYS = ("l_net", "fn_loss", "review_cost", "churn_loss", "fp_hold", "fp_block", "friction_biometric",
                "mule_flow_stopped", "valid", "compliance_exposure")


class ChangeItem(BaseModel):
    op: Literal["add", "replace", "retire"] = Field(default="add", description="add/replace tự nhận theo id luật đã có hay chưa")
    rule: dict[str, Any] | None = None
    rule_id: str | None = Field(default=None, max_length=32)


class ChangeSetRequest(BaseModel):
    items: list[ChangeItem] = Field(min_length=1, max_length=10)
    note: str = Field(default="", max_length=1000, description="Ghi chú của người đề xuất")
    assumptions: Assumptions = Field(default_factory=Assumptions)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=1000, description="Lý do (bắt buộc khi từ chối)")
    role: Literal["approver"] = "approver"


def _normalize(items: list[ChangeItem], current: list[dict[str, Any]], pack: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Issue]]:
    """Kiểm từng mục (VC-01, luật khóa, luật tồn tại) → danh sách mục chuẩn hóa có câu tiếng Việt trước/sau."""
    by_id = {r["id"]: r for r in current}
    out: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for i, it in enumerate(items):
        if it.op == "retire":
            rid = it.rule_id or (it.rule or {}).get("id")
            old = by_id.get(rid)
            if old is None:
                issues.append(Issue(f"Không có luật '{rid}' để ngừng.", f"items[{i}].rule_id"))
            elif old.get("locked"):
                issues.append(Issue(f"Luật {rid} là luật pháp lý bị khóa, không ngừng được.", f"items[{i}].rule_id", rid))
            else:
                out.append({"op": "retire", "rule_id": rid, "before_vi": render_rule(old, pack)["sentence_vi"]})
            continue
        if it.rule is None:
            issues.append(Issue("Thiếu nội dung luật cho mục thêm/sửa.", f"items[{i}].rule"))
            continue
        clean, errs = check_rule(it.rule, pack, i)
        if clean is None:
            issues += errs
            continue
        old = by_id.get(clean["id"])
        if old is not None and old.get("locked"):
            issues.append(Issue(f"Luật {clean['id']} là luật pháp lý bị khóa, không sửa qua change set.", f"items[{i}].rule.id", clean["id"]))
            continue
        out.append({
            "op": "replace" if old is not None else "add",
            "rule_id": clean["id"],
            "rule": clean,
            "before_vi": render_rule(old, pack)["sentence_vi"] if old is not None else None,
            "after_vi": render_rule(clean, pack)["sentence_vi"],
        })
    return out, issues


def _proposed(current: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = [dict(r) for r in current]
    for it in items:
        if it["op"] == "retire":
            rules = [r | {"status": "RETIRED"} if r["id"] == it["rule_id"] else r for r in rules]
        elif it["op"] == "replace":
            rules = [it["rule"] if r["id"] == it["rule_id"] else r for r in rules]
        else:
            rules.append(it["rule"])
    return rules


def _errors(report: dict[str, Any]) -> list[str]:
    return [c["message_vi"] for c in report["checks"] if c["severity"] == "ERROR"]


def _get(db: Session, sid: str, cs_id: str):
    try:
        return repo.get_change_set(db, sid, cs_id)
    except repo.NotFound as e:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy change set trong phiên này.") from e


@router.post("/{sid}/change-sets", summary="Tạo change set: kiểm chứng + backtest trước/sau + semantic diff")
def create_change_set(sid: str, req: ChangeSetRequest, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    pack = repo.current_pack(db, sid)
    current = repo.current_rules(db, sid)
    items, issues = _normalize(req.items, current, pack)
    if issues:
        raise AppError(422, "VALIDATION_ERROR", "Change set không hợp lệ.", [i.to_dict() for i in issues])
    proposed = _proposed(current, items)
    df = transactions()

    report = verify_rules(proposed, pack)
    ground_findings(report["checks"], proposed, pack, df)
    report["rules_vi"] = {r["id"]: render_rule(r, pack)["sentence_vi"] for r in proposed}
    verify_run_id = repo.add_verify_run(db, sid, {"rules": proposed, "pack": pack["version"]}, report)

    before = run_backtest(current, df, pack, req.assumptions)
    after = run_backtest(proposed, df, pack, req.assumptions)
    pick = lambda b: {k: b[k] for k in SUMMARY_KEYS}  # noqa: E731
    backtest = {"before": pick(before), "after": pick(after), "delta": delta(after, before), "days": after["days"]}
    backtest_run_id = repo.add_backtest_run(db, sid, {"change_set": [i["rule_id"] for i in items]}, backtest, int(after["ms"]))

    diff = semantic_diff(current, pack["params"], proposed, pack["params"], df)
    state = "VERIFIED" if report["verdict"] in PASSING else "DRAFT"
    row = repo.add_change_set(
        db, sid, items=items, pack_version=pack["version"], state=state, verify_run_id=verify_run_id,
        backtest_run_id=backtest_run_id, note=req.note,
        summary={"verify": report, "backtest": backtest, "semantic_diff": diff},
    )
    repo.audit(db, sid, "user:proposer", "changeset.create", {
        "change_set_id": row.id, "items": [f"{i['op']}:{i['rule_id']}" for i in items], "verdict": report["verdict"],
        "verify_run_id": verify_run_id,
    })
    db.commit()
    return repo.change_set_dict(row)


@router.get("/{sid}/change-sets", summary="Danh sách change set của phiên (mới nhất trước)")
def list_change_sets(sid: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    db.commit()
    return {"change_sets": repo.list_change_sets(db, sid)}


@router.get("/{sid}/change-sets/{cs_id}", summary="Chi tiết một change set")
def get_change_set(sid: str, cs_id: str, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    row = _get(db, sid, cs_id)
    db.commit()
    return repo.change_set_dict(row)


@router.post("/{sid}/change-sets/{cs_id}/decision", summary="Phê duyệt / từ chối; từ chối phê duyệt nếu kiểm chứng FAIL")
def decide(sid: str, cs_id: str, req: DecisionRequest, db: Db) -> dict[str, Any]:
    repo.get_session(db, sid)
    row = _get(db, sid, cs_id)
    if row.state in ("APPROVED", "REJECTED"):
        raise AppError(409, "ALREADY_DECIDED", f"Change set đã được {'phê duyệt' if row.state == 'APPROVED' else 'từ chối'} trước đó.")
    note = req.note.strip()
    if req.decision == "reject":
        if not note:
            raise AppError(422, "VALIDATION_ERROR", "Cần ghi lý do khi từ chối change set.")
        row.state, row.decision_note, row.decided_at = "REJECTED", note, now()
        repo.audit(db, sid, "user:approver", "changeset.reject", {"change_set_id": row.id, "note": note})
        db.commit()
        return repo.change_set_dict(row)

    # Phê duyệt: kiểm chứng lại với bộ luật + Policy Pack HIỆN TẠI.
    pack = repo.current_pack(db, sid)
    proposed = _proposed(repo.current_rules(db, sid), row.items)
    report = verify_rules(proposed, pack)
    if report["verdict"] not in PASSING:
        repo.audit(db, sid, "user:approver", "changeset.approve_blocked", {
            "change_set_id": row.id, "verdict": report["verdict"], "errors": _errors(report)[:5],
        })
        db.commit()
        raise AppError(409, "APPROVAL_BLOCKED",
                       "Không thể phê duyệt: bộ luật sau thay đổi không qua kiểm chứng (còn vi phạm invariant hoặc không kết luận được).",
                       {"verdict": report["verdict"], "errors": _errors(report)})
    for it in row.items:
        if it["op"] == "retire":
            old = next(r for r in repo.current_rules(db, sid) if r["id"] == it["rule_id"])
            repo.save_rule(db, sid, old | {"status": "RETIRED"}, actor="user:approver")
        else:
            repo.save_rule(db, sid, it["rule"] | {"status": "ACTIVE"}, actor="user:approver")
    row.state, row.decision_note, row.decided_at = "APPROVED", note or None, now()
    repo.audit(db, sid, "user:approver", "changeset.approve", {
        "change_set_id": row.id, "verdict": report["verdict"], "pack_version": pack["version"], "note": note or None,
    })
    db.commit()
    return repo.change_set_dict(row)
