"""T1.2 — generator S0–S4, đặc trưng chống leakage, parquet (docs/04 mục 8)."""

import hashlib

import pandas as pd
import pytest

from app.backtest.interpreter import domain_mask, interpret
from app.data.features import DAY, Account, compute_features
from app.data.generate import generate, write_parquet
from app.data.loader import seed_pack, seed_rules
from app.data.scenarios import START
from app.dsl.catalog import AUTH, CATALOG, FIELD_NAMES

LABELS = {"LEGIT", "APP_VICTIM", "MULE_LAYER", "ATO"}
SCENARIOS = {"S0_NORMAL", "S1_MULE", "S2_ATO", "S3_FLASH_SALE", "S4_FAMILIAR_HIGH"}


def test_shape_and_labels(seed_df):
    df = seed_df
    assert 18_000 <= len(df) <= 22_000
    assert set(df["label"]) == LABELS and set(df["scenario"]) == SCENARIOS
    fraud_bp = int(df["label"].isin(["APP_VICTIM", "ATO", "MULE_LAYER"]).sum()) * 10_000 // len(df)
    assert 80 <= fraud_bp <= 250  # ~1–2% theo số giao dịch
    assert df["tx_id"].is_unique and df["ts"].is_monotonic_increasing
    assert set(df["day"]) == set(range(1, 8))
    assert list(df.columns[-17:]) == list(FIELD_NAMES)


def test_domain_holds_on_every_row(seed_df):
    df = seed_df
    for name, f in CATALOG.items():
        col = df[name]
        if f.type == "int":
            assert col.dtype == "int64", name
            assert col.between(f.lo, f.hi).all(), name
        elif f.type == "enum":
            assert set(col) <= set(f.values), name
        else:
            assert col.dtype == bool, name
    assert domain_mask(df).all()


def test_no_transaction_exactly_at_10_million(seed_df):
    # Chủ ý (docs/04 S4): không có giao dịch đúng 10.000.000 đ — backtest không bắt được lỗi ở mốc, Z3 bắt được.
    assert not (seed_df["amount"] == 10_000_000).any()


def test_parquet_is_reproducible(tmp_path, seed_df):
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    write_parquet(seed_df, a)
    write_parquet(generate(), b)
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()
    pd.testing.assert_frame_equal(pd.read_parquet(a), seed_df)


def test_mules_stay_under_both_biometric_thresholds(seed_df):
    mule = seed_df[seed_df["label"] == "MULE_LAYER"]
    assert len(mule) > 50
    assert (mule["amount"] <= 9_900_000).all()
    assert (mule["daily_total_after"] <= 19_900_000).all()
    assert (mule["sender_account_age_days"].between(1, 13)).all()


def test_scenario_signatures(seed_df):
    df = seed_df
    ato = df[df["label"] == "ATO"]
    assert ato["hour"].between(0, 4).all() and ato["is_new_device"].all()
    first_ato = ato.groupby("sender_id").head(1)
    assert len(first_ato) == 6 and (first_ato["sender_dormant_days"] >= 90).all()
    s4 = df[df["scenario"] == "S4_FAMILIAR_HIGH"]
    assert s4["receiver_is_familiar"].all() and (s4["sender_account_age_days"] > 365).all()
    assert (s4["amount"] > 10_000_000).sum() >= 50
    s3 = df[df["scenario"] == "S3_FLASH_SALE"]
    assert s3.groupby("receiver_id")["receiver_distinct_senders_30m"].max().min() >= 30


def test_seed_rules_have_zero_compliance_exposure(seed_df):
    out = interpret(seed_rules(), seed_df, seed_pack()["params"], with_matched=False)
    weak = out["auth"] < AUTH["BIOMETRIC"]
    assert not ((seed_df["amount"] > 10_000_000) & weak).any()
    assert not ((seed_df["daily_total_after"] > 20_000_000) & weak).any()


# ---------- đặc trưng: 7 giao dịch dựng tay ----------

T0 = START + 20 * 3600  # 20:00 giờ VN ngày 1


@pytest.fixture
def hand():
    acc = {
        "M": Account("M", START - 5 * DAY, "BASIC"),
        "X": Account("X", START - 3 * DAY, "BASIC"),
        "V1": Account("V1", START - 1000 * DAY, last_active_ts=START - DAY),
        "V2": Account("V2", START - 1000 * DAY, last_active_ts=START - DAY),
        "V3": Account("V3", START - 1000 * DAY, last_active_ts=START - DAY),
    }
    rows = [
        ("t1", T0, "V1", "M", 4_000_000),
        ("t2", T0 + 600, "V2", "M", 3_000_000),
        ("t3", T0 + 1200, "V3", "M", 5_000_000),
        ("t4", T0 + 1800, "M", "X", 9_000_000),
        ("t5", T0 + 2400, "M", "X", 2_000_000),
        ("t6", T0 + 3601, "M", "X", 500_000),  # tx t1 vừa rơi khỏi cửa sổ 60 phút
        ("t7", START + DAY + 300, "M", "X", 100_000),  # 00:05 hôm sau: tổng ngày reset
    ]
    raw = pd.DataFrame(
        [
            {"tx_id": i, "ts": ts, "sender_id": s, "receiver_id": r, "amount": a, "channel": "P2P",
             "is_new_device": False, "sender_kyc_level": acc[s].kyc}
            for i, ts, s, r, a in rows
        ]
    )
    return compute_features(raw, acc, {("M", "X"): 1}).set_index("tx_id")


def test_features_hand_computed(hand):
    t3, t4, t5, t6, t7 = (hand.loc[k] for k in ("t3", "t4", "t5", "t6", "t7"))
    # Người nhận M thấy 2 lần nhận trước t3 trong 30 phút (không gồm chính t3).
    assert (t3["receiver_inbound_count_30m"], t3["receiver_distinct_senders_30m"]) == (2, 2)
    assert t3["sender_dormant_days"] == 1 and t3["hour"] == 20
    # t4: M nhận 12 tr từ 3 người trong 60 phút; tỷ lệ gồm cả lệnh này: 9/12 = 75%.
    assert (t4["sender_inbound_amount_60m"], t4["sender_distinct_inbound_60m"]) == (12_000_000, 3)
    assert t4["sender_outbound_ratio_60m_pct"] == 75
    assert (t4["daily_total_after"], t4["sender_outbound_count_24h"]) == (9_000_000, 0)
    assert (t4["sender_account_age_days"], t4["sender_dormant_days"], t4["receiver_account_age_days"]) == (5, 5, 3)
    assert t4["receiver_is_familiar"] == False  # noqa: E712 — 1 lần trước kỳ
    # t5: (9 + 2) / 12 = 91%; X đã nhận 1 lần trong 30 phút.
    assert t5["sender_outbound_ratio_60m_pct"] == 91 and t5["daily_total_after"] == 11_000_000
    assert (t5["receiver_inbound_count_30m"], t5["sender_outbound_count_24h"]) == (1, 1)
    # t6: t1 rơi khỏi cửa sổ → vào 8 tr từ 2 người; ra 11,5 tr → 143%; cặp M→X đủ 3 lần → quen.
    assert (t6["sender_inbound_amount_60m"], t6["sender_distinct_inbound_60m"]) == (8_000_000, 2)
    assert t6["sender_outbound_ratio_60m_pct"] == 143 and t6["receiver_is_familiar"] == True  # noqa: E712
    # t7: sang ngày mới (giờ VN) → tổng ngày reset; không có tiền vào → tỷ lệ 0.
    assert (t7["daily_total_after"], t7["hour"], t7["sender_dormant_days"]) == (100_000, 0, 0)
    assert (t7["sender_inbound_amount_60m"], t7["sender_outbound_ratio_60m_pct"]) == (0, 0)
