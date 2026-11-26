"""T1.3 — interpreter: 12 dòng tính tay trên bộ luật seed (+ DRAFT-0001)."""

import copy

import pandas as pd
import pytest

from app.backtest.interpreter import domain_mask, interpret
from app.data.loader import seed_pack, seed_rules
from app.dsl.catalog import AUTH, DEC
from app.dsl.validator import check_rule
from tests.test_dsl import DRAFT_0001

NEUTRAL = {
    "amount": 100_000,
    "channel": "P2P",
    "hour": 10,
    "daily_total_after": 100_000,
    "is_new_device": False,
    "sender_account_age_days": 400,
    "sender_dormant_days": 0,
    "sender_kyc_level": "FULL",
    "sender_inbound_amount_60m": 0,
    "sender_distinct_inbound_60m": 0,
    "sender_outbound_ratio_60m_pct": 0,
    "sender_outbound_count_24h": 0,
    "receiver_account_age_days": 400,
    "receiver_is_verified_merchant": False,
    "receiver_is_familiar": False,
    "receiver_inbound_count_30m": 0,
    "receiver_distinct_senders_30m": 0,
}

MULE = {"sender_account_age_days": 5, "sender_dormant_days": 0, "sender_inbound_amount_60m": 20_000_000}

# (mô tả, ghi đè, decision, auth, hold_seconds, matched)
CASES = [
    ("trung tính", {}, "ALLOW", "NONE", 0, []),
    ("trên ngưỡng/lần 1 đồng", {"amount": 10_000_001, "daily_total_after": 10_000_001}, "ALLOW", "BIOMETRIC", 0, ["REG-01"]),
    ("đúng ngưỡng/lần", {"amount": 10_000_000, "daily_total_after": 10_000_000}, "ALLOW", "NONE", 0, []),
    ("vượt ngưỡng ngày", {"amount": 5_000_000, "daily_total_after": 20_000_001}, "ALLOW", "BIOMETRIC", 0, ["REG-02"]),
    (
        "mule P2P rất mới",
        MULE | {"sender_distinct_inbound_60m": 5, "sender_outbound_ratio_60m_pct": 95},
        "HOLD", "NONE", 120, ["FR-01", "LG-09"],
    ),
    (
        "mule rút tiền",
        MULE | {"sender_account_age_days": 10, "channel": "WITHDRAW", "sender_distinct_inbound_60m": 3, "sender_outbound_ratio_60m_pct": 80},
        "HOLD", "NONE", 120, ["FR-01"],
    ),
    (
        "chiếm tài khoản ban đêm sát ngưỡng",
        {"sender_account_age_days": 800, "sender_dormant_days": 120, "is_new_device": True, "hour": 3,
         "amount": 9_500_000, "daily_total_after": 9_500_000},
        "HOLD", "BIOMETRIC", 180, ["FR-02", "LG-07"],
    ),
    (
        "QR nhỏ cho merchant đã xác minh",
        {"channel": "MERCHANT_QR", "receiver_is_verified_merchant": True, "amount": 1_500_000, "daily_total_after": 1_500_000},
        "ALLOW", "NONE", 0, ["FX-01"],
    ),
    (
        "flash-sale merchant chưa xác minh",
        {"channel": "MERCHANT_QR", "amount": 200_000, "daily_total_after": 200_000,
         "receiver_inbound_count_30m": 50, "receiver_distinct_senders_30m": 45},
        "HOLD", "NONE", 60, ["FR-04"],
    ),
    (
        "chuyển lớn đêm cho tài khoản rất mới",
        {"amount": 6_000_000, "daily_total_after": 6_000_000, "receiver_account_age_days": 3, "hour": 23},
        "MONITOR", "NONE", 0, ["FR-03"],
    ),
]


def frame(rows):
    return pd.DataFrame([NEUTRAL | r for r in rows])


def draft(status="CANDIDATE"):
    r = copy.deepcopy(DRAFT_0001)
    r["status"] = status
    rule, issues = check_rule(r, seed_pack())
    assert issues == []
    return rule


@pytest.mark.parametrize("name, override, decision, auth, hold, matched", CASES, ids=[c[0] for c in CASES])
def test_seed_rules_hand_computed(name, override, decision, auth, hold, matched):
    out = interpret(seed_rules(), frame([override]), seed_pack()["params"]).iloc[0]
    assert out["decision"] == DEC[decision]
    assert out["auth"] == AUTH[auth]
    assert out["hold_seconds"] == hold
    assert out["matched"] == matched


def test_exemption_overrides_biometric():
    df = frame([{"amount": 15_000_000, "daily_total_after": 15_000_000, "receiver_is_familiar": True}])
    out = interpret(seed_rules() + [draft()], df, seed_pack()["params"]).iloc[0]
    assert out["auth"] == AUTH["NONE"] and bool(out["exempt"]) is True
    assert out["matched"] == ["REG-01", "DRAFT-0001"]


def test_shadow_and_retired_rules_are_ignored():
    df = frame([{"amount": 15_000_000, "daily_total_after": 15_000_000, "receiver_is_familiar": True}])
    for status in ("SHADOW", "RETIRED"):
        out = interpret(seed_rules() + [draft(status)], df, seed_pack()["params"]).iloc[0]
        assert out["auth"] == AUTH["BIOMETRIC"] and out["matched"] == ["REG-01"]


def test_all_rows_at_once_and_dtypes():
    df = frame([c[1] for c in CASES])
    out = interpret(seed_rules(), df, seed_pack()["params"])
    assert list(out["decision"]) == [DEC[c[2]] for c in CASES]
    assert str(out["decision"].dtype) == "int8" and str(out["hold_seconds"].dtype) == "int16"


def test_domain_mask_flags_infeasible_rows():
    df = frame([
        {},
        {"amount": 5_000_000, "daily_total_after": 1_000_000},
        {"sender_dormant_days": 500},
        {"sender_distinct_inbound_60m": 2},
        {"channel": "TOPUP", "receiver_is_verified_merchant": True},
        {"receiver_is_verified_merchant": True, "receiver_account_age_days": 10},
    ])
    assert list(domain_mask(df)) == [True, False, False, False, False, False]
