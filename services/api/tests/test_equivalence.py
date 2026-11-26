"""T1.5 — Property test NFR-5: interpreter (pandas) ≡ encoder Z3 trên 5.000 giao dịch (docs/03 mục 6.1).

2.000 dòng lấy từ dữ liệu tổng hợp + 3.000 dòng sinh ngẫu nhiên trong miền, dồn về sát các mốc của luật.
So sánh cả decision, auth và từng luật có khớp hay không, trên hai bộ luật: seed + luật tay phủ mọi toán tử,
và 30 luật sinh ngẫu nhiên.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
import pytest
import z3

from app.backtest.interpreter import ACTIVE_STATUSES, condition_mask, domain_mask, interpret
from app.data.loader import seed_pack, seed_rules
from app.dsl.catalog import CATALOG, FIELD_NAMES, FIELDS
from app.dsl.validator import check_rule
from app.verify.encoder import enc, make_vars, outcome, tx_to_substitution
from tests.test_dsl import DRAFT_0001

N_DATA, N_RANDOM = 2_000, 3_000
RNG_SEED = 20261203


# ---------- luật dùng để so sánh ----------


def _valid(raw: dict[str, Any]) -> dict[str, Any]:
    rule, issues = check_rule(raw, seed_pack())
    assert issues == [], [i.message_vi for i in issues]
    return rule


def _rule(rid: str, when: dict, then: dict, status: str = "CANDIDATE") -> dict[str, Any]:
    return _valid({"id": rid, "name": rid, "kind": "FRAUD", "status": status, "when": when, "then": then})


def hand_rules() -> list[dict[str, Any]]:
    """Seed + DRAFT Demo 1 + bản sửa + các luật phủ mọi toán tử/kiểu."""
    fixed = copy.deepcopy(DRAFT_0001) | {"id": "DRAFT-0002"}
    fixed["when"] = {"all": fixed["when"]["all"] + [
        {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}},
        {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
    ]}
    extra = [
        _rule("X-01", {"all": [
            {"field": "channel", "op": "not_in", "value": ["P2P", "MERCHANT_QR"]},
            {"field": "amount", "op": "between", "value": [{"param": "small_merchant_payment_max"}, {"param": "biometric_daily_threshold"}]},
        ]}, {"decision": "BLOCK"}),
        _rule("X-02", {"any": [
            {"not": {"field": "sender_kyc_level", "op": "==", "value": "FULL"}},
            {"field": "is_new_device", "op": "!=", "value": False},
        ]}, {"auth": "OTP"}),
        _rule("X-03", {"all": [
            {"field": "channel", "op": "!=", "value": "TOPUP"},
            {"field": "receiver_inbound_count_30m", "op": ">", "value": 10},
            {"not": {"any": [{"const": False}, {"field": "hour", "op": "<", "value": 7}]}},
        ]}, {"decision": "MONITOR", "exempt_auth": True}),
        _rule("X-04", {"const": True}, {"auth": "NONE"}),
        _rule("X-05", {"field": "sender_outbound_count_24h", "op": ">=", "value": 20}, {"decision": "HOLD", "hold_seconds": 90}, "SHADOW"),
    ]
    return seed_rules() + [_valid(DRAFT_0001), _valid(fixed)] + extra


INTERESTING: dict[str, list[int]] = {
    "amount": [1, 20_000, 2_000_000, 5_000_000, 9_000_000, 10_000_000, 20_000_000, 500_000_000],
    "hour": [0, 5, 7, 10, 22, 23],
    "daily_total_after": [1, 10_000_000, 20_000_000, 2_000_000_000],
    "sender_account_age_days": [0, 7, 14, 30, 365, 3650],
    "sender_dormant_days": [0, 90, 365],
    "sender_inbound_amount_60m": [0, 1, 10_000_000],
    "sender_distinct_inbound_60m": [0, 1, 3, 5, 500],
    "sender_outbound_ratio_60m_pct": [0, 80, 90, 1000],
    "sender_outbound_count_24h": [0, 20, 1000],
    "receiver_account_age_days": [0, 7, 30, 3650],
    "receiver_inbound_count_30m": [0, 10, 30, 5000],
    "receiver_distinct_senders_30m": [0, 30, 5000],
}


def random_rules(n: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    params = ["biometric_per_tx_threshold", "biometric_daily_threshold", "small_merchant_payment_max"]

    def leaf() -> dict[str, Any]:
        f = FIELDS[int(rng.integers(len(FIELDS)))]
        if f.type == "bool":
            return {"field": f.name, "op": ["==", "!="][int(rng.integers(2))], "value": bool(rng.integers(2))}
        if f.type == "enum":
            op = ["==", "!=", "in", "not_in"][int(rng.integers(4))]
            if op in ("in", "not_in"):
                k = int(rng.integers(1, len(f.values) + 1))
                return {"field": f.name, "op": op, "value": [str(x) for x in rng.choice(f.values, k, replace=False)]}
            return {"field": f.name, "op": op, "value": str(f.values[int(rng.integers(len(f.values)))])}

        def val() -> Any:
            if f.unit == "VND" and rng.random() < 0.3:
                return {"param": params[int(rng.integers(len(params)))]}
            return int(rng.choice(INTERESTING[f.name]))

        op = [">", ">=", "<", "<=", "==", "!=", "between"][int(rng.integers(7))]
        if op == "between":
            a, b = val(), val()
            ra = a if isinstance(a, int) else seed_pack()["params"][a["param"]]["value"]
            rb = b if isinstance(b, int) else seed_pack()["params"][b["param"]]["value"]
            return {"field": f.name, "op": op, "value": [a, b] if ra <= rb else [b, a]}
        return {"field": f.name, "op": op, "value": val()}

    def cond(depth: int) -> dict[str, Any]:
        r = rng.random()
        if depth >= 3 or r < 0.45:
            return leaf()
        if r < 0.7:
            return {"all": [cond(depth + 1) for _ in range(int(rng.integers(1, 4)))]}
        if r < 0.9:
            return {"any": [cond(depth + 1) for _ in range(int(rng.integers(1, 4)))]}
        return {"not": cond(depth + 1)}

    out = []
    for i in range(n):
        then: dict[str, Any] = {}
        d = ["ALLOW", "MONITOR", "HOLD", "BLOCK", None][int(rng.integers(5))]
        if d:
            then["decision"] = d
            if d == "HOLD":
                then["hold_seconds"] = int(rng.integers(60, 181))
        a = ["NONE", "OTP", "BIOMETRIC", None][int(rng.integers(4))]
        if a:
            then["auth"] = a
        if rng.random() < 0.2:
            then["exempt_auth"] = True
        status = "SHADOW" if rng.random() < 0.1 else "ACTIVE"
        out.append(_rule(f"R-{i:03d}", cond(1), then, status))
    return out


# ---------- mẫu ngẫu nhiên trong miền ----------


def random_domain_samples(n: int, rng: np.random.Generator) -> pd.DataFrame:
    cols: dict[str, Any] = {}
    for f in FIELDS:
        if f.type == "bool":
            cols[f.name] = rng.integers(0, 2, n).astype(bool)
        elif f.type == "enum":
            cols[f.name] = rng.choice(np.array(f.values, dtype=object), n)
        else:
            base = np.array(INTERESTING[f.name], dtype=np.int64)
            near = rng.choice(base, n) + rng.integers(-1, 2, n)  # mốc ± 1
            uni = rng.integers(f.lo, f.hi + 1, n)
            cols[f.name] = np.clip(np.where(rng.random(n) < 0.6, near, uni), f.lo, f.hi).astype(np.int64)
    df = pd.DataFrame(cols)
    # Sửa cho thỏa ràng buộc miền phụ thuộc (docs/02 mục 1).
    df["daily_total_after"] = np.maximum(df["daily_total_after"], df["amount"])
    df["sender_dormant_days"] = np.minimum(df["sender_dormant_days"], df["sender_account_age_days"])
    df["receiver_distinct_senders_30m"] = np.minimum(df["receiver_distinct_senders_30m"], df["receiver_inbound_count_30m"])
    no_in = df["sender_inbound_amount_60m"] == 0
    df.loc[no_in, ["sender_distinct_inbound_60m", "sender_outbound_ratio_60m_pct"]] = 0
    young = df["receiver_is_verified_merchant"] & (df["receiver_account_age_days"] < 30)
    df.loc[young, "receiver_account_age_days"] = 30
    df.loc[df["channel"] == "TOPUP", "receiver_is_verified_merchant"] = False
    assert domain_mask(df).all()
    return df


@pytest.fixture(scope="module")
def samples(seed_df) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    data = seed_df.sample(N_DATA, random_state=RNG_SEED)[list(FIELD_NAMES)]
    rand = random_domain_samples(N_RANDOM, rng)
    return pd.concat([data, rand], ignore_index=True)


# ---------- so sánh ----------


def z3_eval(rules: list[dict[str, Any]], df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """decision, auth và ma trận khớp từng luật, tính bằng Z3 (substitute giá trị rồi simplify).
    Gói cả ba vào một số nguyên: dec + 4·auth + 16·Σ 2^i·[when_i] để mỗi dòng chỉ substitute một lần."""
    ctx = z3.Context()
    v = make_vars(ctx)
    params = seed_pack()["params"]
    dec, auth, _ = outcome(rules, v, params, ctx)
    active = [r for r in rules if r["status"] in ACTIVE_STATUSES]
    bits = z3.Sum([z3.If(enc(r["when"], v, params, ctx), z3.IntVal(2**i, ctx), z3.IntVal(0, ctx)) for i, r in enumerate(active)])
    packed = dec + 4 * auth + 16 * bits
    decs, auths, match = [], [], []
    for tx in df[list(FIELD_NAMES)].to_dict("records"):
        val = z3.simplify(z3.substitute(packed, *tx_to_substitution(tx, v, ctx))).as_long()
        decs.append(val % 4)
        auths.append((val // 4) % 4)
        b = val // 16
        match.append([(b >> i) & 1 == 1 for i in range(len(active))])
    return np.array(decs), np.array(auths), np.array(match, dtype=bool)


def assert_equivalent(rules: list[dict[str, Any]], df: pd.DataFrame) -> None:
    params = seed_pack()["params"]
    out = interpret(rules, df, params, with_matched=False)
    active = [r for r in rules if r["status"] in ACTIVE_STATUSES]
    i_match = np.column_stack([condition_mask(r["when"], df, params) for r in active])
    z_dec, z_auth, z_match = z3_eval(rules, df)

    for name, a, b in (("decision", out["decision"].to_numpy(), z_dec), ("auth", out["auth"].to_numpy(), z_auth)):
        bad = np.flatnonzero(a != b)
        assert bad.size == 0, f"{name} lệch ở {bad.size} dòng, ví dụ: {df.iloc[bad[0]].to_dict()} interpreter={a[bad[0]]} z3={b[bad[0]]}"
    bad_rows, bad_rules = np.nonzero(i_match != z_match)
    assert bad_rows.size == 0, f"luật {active[bad_rules[0]]['id']} lệch ở dòng {df.iloc[bad_rows[0]].to_dict()}"


def test_samples_cover_domain_and_thresholds(samples):
    assert len(samples) == N_DATA + N_RANDOM
    assert domain_mask(samples).all()
    for name in ("amount", "daily_total_after"):
        assert samples[name].isin([10_000_000, 10_000_001, 20_000_000, 20_000_001]).any()


def test_interpreter_equals_z3_on_hand_rules(samples):
    assert_equivalent(hand_rules(), samples)


def test_interpreter_equals_z3_on_random_rules(samples):
    rules = random_rules(30, np.random.default_rng(RNG_SEED))
    assert sum(r["status"] in ACTIVE_STATUSES for r in rules) >= 20
    assert_equivalent(rules, samples)


def test_property_test_catches_an_off_by_one(samples, monkeypatch):
    """Kiểm chính bài test: làm lệch '>=' thành '>' trong interpreter thì phải phát hiện."""
    import operator

    from app.backtest import interpreter

    monkeypatch.setitem(interpreter._CMP, ">=", operator.gt)
    with pytest.raises(AssertionError, match="lệch"):
        assert_equivalent(hand_rules(), samples)
