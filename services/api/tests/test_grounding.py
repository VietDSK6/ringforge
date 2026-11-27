"""T3.1 — grounding: vùng vi phạm trong dữ liệu (docs/03 mục 4)."""

import copy

from app.backtest.interpreter import condition_mask
from app.data.loader import seed_pack, seed_rules
from app.dsl.validator import check_rule
from app.verify.checks import verify_rules
from app.verify.grounding import ground_findings
from tests.test_dsl import DRAFT_0001


def valid(raw):
    rule, issues = check_rule(raw, seed_pack())
    assert issues == []
    return rule


def grounded(rules, df):
    report = verify_rules(rules, seed_pack())
    ground_findings(report["checks"], rules, seed_pack(), df)
    return {c["invariant"]: c for c in report["checks"] if c["code"] == "VC-04"}


def test_demo1_grounding_counts_real_transactions(seed_df):
    rules = seed_rules() + [valid(DRAFT_0001)]
    found = grounded(rules, seed_df)
    g = found["INV-AUTH-01"]["grounding"]
    assert g["days"] == [1, 2, 3, 4, 5, 6]
    assert g["tx_count"] > 50 and g["amount_sum"] > g["tx_count"] * 10_000_000
    assert "S4_FAMILIAR_HIGH" in g["by_scenario"] and g["by_label"].get("LEGIT", 0) > 0
    assert g["note_vi"].startswith("Trong 6 ngày dữ liệu tổng hợp:") and " đ lẽ ra phải xác thực sinh trắc học" in g["note_vi"]
    assert isinstance(g["amount_sum"], int)


def test_region_condition_matches_violation_count(seed_df):
    """Vùng theo đặc tả (inv.when ∧ when luật miễn trừ) đếm ra đúng số giao dịch vi phạm."""
    rules = seed_rules() + [valid(DRAFT_0001)]
    part = seed_df[seed_df["day"].between(1, 6)]
    for c in grounded(rules, seed_df).values():
        g = c["grounding"]
        assert int(condition_mask(g["region"], part, seed_pack()["params"]).sum()) == g["tx_count"]


def test_boundary_only_violation_has_zero_grounding(seed_df):
    """Lỗi chỉ ở sát mốc 10.000.001 đ: dữ liệu không có giao dịch nào → backtest không bắt được, Z3 bắt được."""
    narrow = copy.deepcopy(DRAFT_0001)
    narrow["when"]["all"].append({"field": "amount", "op": "between", "value": [10_000_001, 10_005_000]})
    found = grounded(seed_rules() + [valid(narrow)], seed_df)
    g = found["INV-AUTH-01"]["grounding"]
    assert found["INV-AUTH-01"]["counterexample"]["amount"] == 10_000_001
    assert g["tx_count"] == 0 and g["amount_sum"] == 0
    assert "backtest sẽ KHÔNG phát hiện" in g["note_vi"]


def test_decision_violation_grounding_without_region(seed_df):
    old = copy.deepcopy(next(r for r in seed_rules() if r["id"] == "FR-02"))
    old["when"]["all"] = old["when"]["all"][:3]
    rules = [r for r in seed_rules() if r["id"] != "FR-02"] + [old]
    g = grounded(rules, seed_df)["INV-CX-01"]["grounding"]
    assert "region" not in g and g["tx_count"] >= 0
