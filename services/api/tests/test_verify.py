"""T1.4 — Z3 encoder, VC-03, VC-04, phản ví dụ dễ đọc (docs/03 mục 6)."""

import copy

import pandas as pd
import pytest

from app.backtest.interpreter import domain_mask, interpret
from app.data.loader import load_seed_pack_raw, seed_pack, seed_rules
from app.dsl.catalog import AUTH
from app.dsl.validator import check_pack, check_rule
from app.verify import checks
from app.verify.checks import verify_rules
from tests.test_dsl import DRAFT_0001


def valid(raw):
    rule, issues = check_rule(raw, seed_pack())
    assert issues == [], issues
    return rule


def by_inv(report):
    return {c["invariant"]: c for c in report["checks"] if c["code"] == "VC-04"}


def draft_fixed():
    r = copy.deepcopy(DRAFT_0001)
    r["when"]["all"] += [
        {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}},
        {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
    ]
    return valid(r)


def test_seed_rules_pass_vc03_and_vc04_fast():
    report = verify_rules(seed_rules(), seed_pack())
    assert report["verdict"] == "PASS" and report["checks"] == []
    assert len(report["checked"]["rules"]) == 9 and len(report["checked"]["invariants"]) == 3
    assert report["ms"] < 3_000  # FR-V9


def test_demo1_draft_violates_both_auth_invariants():
    report = verify_rules(seed_rules() + [valid(DRAFT_0001)], seed_pack())
    assert report["verdict"] == "FAIL"
    found = by_inv(report)
    assert set(found) == {"INV-AUTH-01", "INV-AUTH-02"}
    inv1, inv2 = found["INV-AUTH-01"], found["INV-AUTH-02"]
    assert inv1["counterexample"]["amount"] == 10_000_001
    assert inv1["counterexample"]["receiver_is_familiar"] is True
    assert inv1["counterexample"]["sender_account_age_days"] > 365
    assert inv2["counterexample"]["daily_total_after"] == 20_000_001
    for c in (inv1, inv2):
        assert c["blamed_rules"] == ["DRAFT-0001"] and c["outcome"] == {"decision": "ALLOW", "auth": "NONE"}
        assert "DRAFT-0001" in c["message_vi"]


def test_counterexample_is_feasible_and_interpreter_agrees():
    """Phản ví dụ phải là giao dịch hợp lệ trong miền, và interpreter cũng cho auth NONE (NFR-5)."""
    rules = seed_rules() + [valid(DRAFT_0001)]
    for c in by_inv(verify_rules(rules, seed_pack())).values():
        row = pd.DataFrame([c["counterexample"]])
        assert domain_mask(row).all()
        out = interpret(rules, row, seed_pack()["params"]).iloc[0]
        assert out["auth"] == AUTH["NONE"] and "DRAFT-0001" in out["matched"]


def test_fixed_draft_passes():
    assert verify_rules(seed_rules() + [draft_fixed()], seed_pack())["verdict"] == "PASS"


def test_decision_at_most_violation_blames_hold_rule():
    """FR-02 bản cũ (không giới hạn kênh) giữ thanh toán QR nhỏ cho merchant đã xác minh → vi phạm INV-CX-01."""
    old = copy.deepcopy(next(r for r in seed_rules() if r["id"] == "FR-02"))
    old["when"]["all"] = old["when"]["all"][:3]
    rules = [r for r in seed_rules() if r["id"] != "FR-02"] + [old]
    c = by_inv(verify_rules(rules, seed_pack()))["INV-CX-01"]
    assert c["blamed_rules"] == ["FR-02"] and c["outcome"]["decision"] == "HOLD"
    cx = c["counterexample"]
    assert (cx["channel"], cx["receiver_is_verified_merchant"], cx["amount"]) == ("MERCHANT_QR", True, 1)
    assert cx["hour"] == 5 and cx["sender_dormant_days"] == 90  # sát mốc, gần giá trị trung tính nhất


def test_missing_implementation_reported_without_blame():
    rules = [r for r in seed_rules() if r["id"] != "REG-01"]
    c = by_inv(verify_rules(rules, seed_pack()))["INV-AUTH-01"]
    assert c["blamed_rules"] == [] and "không luật nào hiện thực" in c["message_vi"]
    assert c["counterexample"]["amount"] == 10_000_001


@pytest.mark.parametrize(
    "when, conflict",
    [
        ({"all": [{"field": "amount", "op": "<", "value": 5}, {"field": "hour", "op": "==", "value": 3},
                  {"field": "amount", "op": ">", "value": 10}]}, ["số tiền nhỏ hơn 5 đ", "số tiền lớn hơn 10 đ"]),
        ({"field": "amount", "op": ">", "value": 600_000_000}, ["số tiền lớn hơn 600.000.000 đ"]),
        ({"all": [{"field": "channel", "op": "==", "value": "TOPUP"},
                  {"field": "receiver_is_verified_merchant", "op": "==", "value": True}]},
         ["kênh là nạp tiền điện thoại", "người nhận là merchant đã xác minh"]),
    ],
)
def test_dead_rule_with_conflicting_conditions(when, conflict):
    dead = valid(copy.deepcopy(DRAFT_0001) | {"id": "DRAFT-0009", "when": when})
    report = verify_rules(seed_rules() + [dead], seed_pack())
    assert report["verdict"] == "FAIL"
    (c,) = [c for c in report["checks"] if c["code"] == "VC-03"]
    assert c["rule_id"] == "DRAFT-0009" and c["status"] == "DEAD"
    assert c["conflicting_conditions_vi"] == conflict


def test_retired_rules_are_not_checked_and_do_not_apply():
    r = valid(copy.deepcopy(DRAFT_0001) | {"status": "RETIRED"})
    report = verify_rules(seed_rules() + [r], seed_pack())
    assert report["verdict"] == "PASS" and "DRAFT-0001" not in report["checked"]["rules"]


def test_param_change_is_respected():
    raw = load_seed_pack_raw()
    raw["params"]["biometric_per_tx_threshold"]["value"] = 5_000_000
    pack, issues = check_pack(raw)
    assert issues == []
    c = by_inv(verify_rules(seed_rules() + [valid(DRAFT_0001)], pack))["INV-AUTH-01"]
    assert c["counterexample"]["amount"] == 5_000_001


def test_timeout_is_unknown_never_pass(monkeypatch):
    monkeypatch.setattr(checks, "_check", lambda solver, *a: "unknown")
    report = verify_rules(seed_rules(), seed_pack())
    assert report["verdict"] == "UNKNOWN"
    assert report["checks"] and all(c["status"] == "UNKNOWN" for c in report["checks"])
    assert checks.verdict_of([{"severity": "ERROR", "status": "UNKNOWN"}]) != "PASS"
