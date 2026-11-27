"""T4.2 — VC-07 semantic diff: nhân chứng theo từng kiểu khác biệt + đếm trên dữ liệu."""

import copy

import pandas as pd

from app.api.verify import DEMO1_RULE
from app.backtest.interpreter import interpret
from app.data.loader import seed_pack, seed_rules
from app.dsl.catalog import AUTH_LEVELS, DECISIONS
from app.verify.semantic_diff import semantic_diff


def _params(value=None):
    p = copy.deepcopy(seed_pack()["params"])
    if value is not None:
        p["biometric_per_tx_threshold"]["value"] = value
    return p


def _outcome_of(tx, rules, params):
    out = interpret(rules, pd.DataFrame([tx]), params, with_matched=False).iloc[0]
    return {"decision": DECISIONS[int(out["decision"])], "auth": AUTH_LEVELS[int(out["auth"])]}


def test_identical_rulesets_are_equivalent(seed_df):
    d = semantic_diff(seed_rules(), _params(), seed_rules(), _params(), seed_df)
    assert d["status"] == "EQUIVALENT" and d["complete"] and d["diffs"] == []
    assert d["grounding"]["tx_count"] == 0 and d["severity"] == "INFO"


def test_pack_threshold_change_adds_biometric(seed_df):
    rules = seed_rules()
    d = semantic_diff(rules, _params(), rules, _params(5_000_000), seed_df)
    assert d["status"] == "DIFFERENT" and d["complete"] and len(d["diffs"]) == 1
    k = d["diffs"][0]
    assert k["decision"] is None and k["auth"] == ["NONE", "BIOMETRIC"] and k["direction"] == "stricter"
    assert k["counterexample"]["amount"] == 5_000_001  # Optimize đẩy nhân chứng về sát mốc mới
    # Đếm trên dữ liệu khớp với interpreter, và phần hợp lệ = tăng ma sát sinh trắc học.
    part = seed_df[seed_df["day"].isin(range(1, 7))]
    before = interpret(rules, part, _params(), with_matched=False)
    after = interpret(rules, part, _params(5_000_000), with_matched=False)
    changed = (before["auth"] != after["auth"]) | (before["decision"] != after["decision"])
    assert k["data"]["tx_count"] == d["grounding"]["tx_count"] == int(changed.sum()) > 0
    legit_added = int(((after["auth"] == 2) & (before["auth"] != 2) & (part["label"] == "LEGIT")).sum())
    assert k["data"]["by_label"]["LEGIT"] == legit_added
    assert d["grounding"]["other_tx_count"] == 0


def test_witnesses_match_interpreter(seed_df):
    """Nhân chứng Z3 khi chạy qua interpreter phải ra đúng before/after (quy tắc 3: interpreter ≡ Z3)."""
    a = seed_rules()
    b = seed_rules() + [DEMO1_RULE]
    b = [r | {"then": {"decision": "BLOCK"}} if r["id"] == "FR-01" else r for r in b]
    d = semantic_diff(a, _params(), b, _params(), seed_df)
    assert d["status"] == "DIFFERENT" and d["complete"] and len(d["diffs"]) >= 2
    labels = {(tuple(x["decision"] or ()), tuple(x["auth"] or ())) for x in d["diffs"]}
    assert ((), ("BIOMETRIC", "NONE")) in labels  # mất sinh trắc học do miễn trừ
    assert any(dec == ("HOLD", "BLOCK") for dec, _ in labels)
    for x in d["diffs"]:
        assert _outcome_of(x["counterexample"], a, _params()) == x["before"]
        assert _outcome_of(x["counterexample"], b, _params()) == x["after"]
    looser = next(x for x in d["diffs"] if x["auth"] == ["BIOMETRIC", "NONE"] and x["decision"] is None)
    assert looser["direction"] == "looser" and looser["data"]["tx_count"] > 0


def test_max_witnesses_marks_incomplete(seed_df):
    a = seed_rules()
    b = [r | {"then": {"decision": "BLOCK"}} if r["id"] in ("FR-01", "FR-04") else r for r in seed_rules()] + [DEMO1_RULE]
    d = semantic_diff(a, _params(), b, _params(), seed_df, max_witnesses=1)
    assert len(d["diffs"]) == 1 and not d["complete"]
    assert d["grounding"]["other_tx_count"] > 0 and "+" in d["message_vi"]


def test_impact_includes_semantic_diff(seed_df):
    from app.verify.impact import SetParam, apply_patch, pack_impact

    old = seed_pack()
    new, _, changes = apply_patch(old, [SetParam(op="set_param", param="biometric_per_tx_threshold", value=5_000_000)])
    res = pack_impact(seed_rules(), old, new, changes, seed_df)
    vc07 = res["semantic_diff"]
    assert vc07["code"] == "VC-07" and vc07["diffs"][0]["auth"] == ["NONE", "BIOMETRIC"]
    assert vc07["diffs"][0]["data"]["by_label"]["LEGIT"] == res["friction"]["delta"]["friction_biometric"]
