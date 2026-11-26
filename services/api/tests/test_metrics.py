"""T2.1 — metrics backtest, L_net tính tay, exposure (docs/04 mục 6, 8)."""

import pandas as pd
import pytest

from app.backtest.interpreter import interpret
from app.backtest.metrics import Assumptions, compute_metrics, delta, run_backtest
from app.data.loader import seed_pack, seed_rules
from app.dsl.catalog import AUTH, DEC
from app.dsl.validator import check_rule
from tests.test_dsl import DRAFT_0001
from tests.test_interpreter import NEUTRAL

# (label, scenario, amount, decision, auth)
HAND = [
    ("APP_VICTIM", "S1_MULE", 5_000_000, "BLOCK", "NONE"),
    ("APP_VICTIM", "S1_MULE", 3_000_001, "HOLD", "NONE"),
    ("ATO", "S2_ATO", 4_000_000, "HOLD", "NONE"),
    ("ATO", "S2_ATO", 2_000_000, "ALLOW", "NONE"),
    ("ATO", "S2_ATO", 1_000_000, "MONITOR", "NONE"),
    ("LEGIT", "S0_NORMAL", 1_000_000, "BLOCK", "NONE"),
    ("LEGIT", "S3_FLASH_SALE", 300_000, "HOLD", "NONE"),
    ("LEGIT", "S3_FLASH_SALE", 200_001, "HOLD", "NONE"),
    ("LEGIT", "S4_FAMILIAR_HIGH", 12_000_000, "ALLOW", "BIOMETRIC"),
    ("MULE_LAYER", "S1_MULE", 9_000_000, "HOLD", "NONE"),
]


def hand_frames(rows=HAND):
    df = pd.DataFrame([
        NEUTRAL | {"label": lb, "scenario": sc, "amount": amt, "daily_total_after": amt, "day": 1}
        for lb, sc, amt, _, _ in rows
    ])
    out = pd.DataFrame({
        "decision": [DEC[r[3]] for r in rows],
        "auth": [AUTH[r[4]] for r in rows],
    })
    return df, out


def test_l_net_hand_computed_10_rows():
    df, out = hand_frames()
    m = compute_metrics(df, out, seed_pack(), Assumptions())
    # Tổn thất: 5.000.000 + 3.000.001 + 4.000.000 + 2.000.000 + 1.000.000
    assert m["loss_total"] == 15_000_001
    # Ngăn được: BLOCK 5.000.000 + floor((3.000.001 + 4.000.000) × 5.000 / 10.000) = 5.000.000 + 3.500.000
    assert m["prevented"] == 8_500_000
    assert m["fn_loss"] == 6_500_001
    assert m["review_cost"] == 30_000  # 1 giao dịch hợp lệ bị BLOCK × 30.000
    # floor(500.001 × 500 × 50 / 10^8) + floor(1.000.000 × 3.000 × 50 / 10^8) = 125 + 1.500
    assert m["churn_loss"] == 1_625
    assert m["l_net"] == 6_531_626
    assert (m["recall_amount_bp"], m["recall_count_bp"]) == (5_666, 6_000)
    assert (m["fp_hold"], m["fp_block"], m["fp_rate_bp"]) == (2, 1, 7_500)
    assert m["friction_biometric"] == 1
    assert (m["mule_flow_stopped"], m["mule_flow_total"]) == (9_000_000, 9_000_000)
    assert m["valid"] is True


def test_every_money_value_is_int():
    df, out = hand_frames()
    m = compute_metrics(df, out, seed_pack(), Assumptions())
    for k, v in m.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            assert type(v) is int, k
    for sc in m["by_scenario"].values():
        assert all(type(v) is int or v is None for k, v in sc.items() if k != "label_vi")


def test_scenario_breakdown_adds_up():
    df, out = hand_frames()
    m = compute_metrics(df, out, seed_pack(), Assumptions())
    s = m["by_scenario"]
    assert set(s) == {"S0_NORMAL", "S1_MULE", "S2_ATO", "S3_FLASH_SALE", "S4_FAMILIAR_HIGH"}
    assert s["S1_MULE"]["prevented"] == 5_000_000 + 3_000_001 * 5_000 // 10_000
    assert s["S3_FLASH_SALE"]["fp_hold"] == 2 and s["S2_ATO"]["recall_count_bp"] == 3_333


def test_assumption_sliders_change_result():
    df, out = hand_frames()
    a = Assumptions(hold_stop_bp=10_000, monitor_stop_bp=10_000, c_review_hold=5_000)
    m = compute_metrics(df, out, seed_pack(), a)
    assert m["prevented"] == 5_000_000 + 7_000_001 + 1_000_000
    assert m["review_cost"] == 30_000 + 2 * 5_000
    with pytest.raises(ValueError):
        Assumptions(hold_stop_bp=10_001)
    with pytest.raises(ValueError):
        Assumptions(margin_bp=0.5)


def test_exposure_counts_auth_and_decision_invariants():
    rows = [
        ("LEGIT", "S4_FAMILIAR_HIGH", 12_000_000, "ALLOW", "NONE"),
        ("LEGIT", "S0_NORMAL", 10_000_000, "ALLOW", "NONE"),
    ]
    df, out = hand_frames(rows)
    df.loc[1, ["channel", "receiver_is_verified_merchant", "amount", "daily_total_after"]] = ["MERCHANT_QR", True, 500_000, 500_000]
    out.loc[1, "decision"] = DEC["HOLD"]
    m = compute_metrics(df, out, seed_pack(), Assumptions())
    exp = {e["invariant"]: e for e in m["compliance_exposure"]}
    assert (exp["INV-AUTH-01"]["count"], exp["INV-AUTH-01"]["amount_sum"]) == (1, 12_000_000)
    assert exp["INV-AUTH-02"]["count"] == 0
    assert (exp["INV-CX-01"]["count"], exp["INV-CX-01"]["amount_sum"]) == (1, 500_000)
    assert m["valid"] is False


def test_seed_backtest_on_generated_data(seed_df):
    r = run_backtest(seed_rules(), seed_df, seed_pack())
    assert r["days"] == [1, 2, 3, 4, 5, 6] and r["n_tx"] == int(seed_df["day"].between(1, 6).sum())
    assert r["valid"] is True and all(e["count"] == 0 for e in r["compliance_exposure"])  # docs/04 mục 8.3
    assert r["l_net"] == r["fn_loss"] + r["review_cost"] + r["churn_loss"]
    assert r["fp_hold"] > 0  # FR-04 bắt nhầm flash-sale
    assert r["ms"] < 3_000  # FR-B7


def test_day_7_is_excluded(seed_df):
    r_all = run_backtest(seed_rules(), seed_df, seed_pack(), days=(1, 2, 3, 4, 5, 6, 7))
    r = run_backtest(seed_rules(), seed_df, seed_pack())
    assert r_all["n_tx"] - r["n_tx"] == int((seed_df["day"] == 7).sum())


def test_demo1_draft_creates_exposure_and_delta(seed_df):
    draft, issues = check_rule(DRAFT_0001, seed_pack())
    assert issues == []
    base = run_backtest(seed_rules(), seed_df, seed_pack())
    with_draft = run_backtest(seed_rules() + [draft], seed_df, seed_pack())
    exp = {e["invariant"]: e for e in with_draft["compliance_exposure"]}
    assert exp["INV-AUTH-01"]["count"] > 0 and with_draft["valid"] is False
    d = delta(with_draft, base)
    assert d["friction_biometric"] < 0  # miễn trừ làm giảm ma sát — nhưng phạm quy định
    out = interpret(seed_rules() + [draft], seed_df, seed_pack()["params"], with_matched=False)
    assert ((seed_df["amount"] > 10_000_000) & (out["auth"] < AUTH["BIOMETRIC"])).sum() >= exp["INV-AUTH-01"]["count"]
