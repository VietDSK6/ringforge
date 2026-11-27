"""T3.2 — repair tất định + pipeline đánh giá/xếp hạng bản sửa (docs/03 mục 5, docs/05 mục 4)."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.api.verify import DEMO1_RULE
from app.backtest.metrics import run_backtest
from app.data.loader import seed_pack, seed_rules
from app.dsl.validator import check_rule
from app.main import app
from app.verify.checks import verify_rules
from app.verify.det_repair import conjoin, deterministic_repair, negate
from app.verify.relations import equivalent
from app.verify.repair import condition_diff, coverage_bp, evaluate, rank_key
from tests.test_dsl import DRAFT_0001

P = {"param": "biometric_per_tx_threshold"}


def valid(raw):
    rule, issues = check_rule(raw, seed_pack())
    assert issues == [], [i.message_vi for i in issues]
    return rule


@pytest.mark.parametrize(
    "cond, expected",
    [
        ({"field": "amount", "op": ">", "value": P}, {"field": "amount", "op": "<=", "value": P}),
        ({"field": "amount", "op": ">=", "value": 5}, {"field": "amount", "op": "<", "value": 5}),
        ({"field": "channel", "op": "in", "value": ["P2P"]}, {"field": "channel", "op": "not_in", "value": ["P2P"]}),
        ({"field": "is_new_device", "op": "==", "value": True}, {"field": "is_new_device", "op": "==", "value": False}),
        ({"field": "hour", "op": "between", "value": [0, 5]}, {"not": {"field": "hour", "op": "between", "value": [0, 5]}}),
        ({"not": {"const": True}}, {"const": True}),
    ],
)
def test_negate_leaf(cond, expected):
    assert negate(cond) == expected
    assert equivalent(negate(cond), {"not": cond}, seed_pack()["params"]) == "YES"


def test_negate_de_morgan_is_equivalent():
    inv = seed_pack()["invariants"][2]["when"]  # INV-CX-01: all[...]
    assert "any" in negate(inv)
    assert equivalent(negate(inv), {"not": inv}, seed_pack()["params"]) == "YES"


def test_conjoin_flattens_and_dedupes():
    base = {"all": [{"field": "hour", "op": "==", "value": 1}]}
    extra = {"field": "amount", "op": ">", "value": 1}
    assert conjoin(base, [extra, extra]) == {"all": [base["all"][0], extra]}


def test_demo1_det_repair_matches_expected_spec_repair():
    draft = valid(DRAFT_0001)
    report = verify_rules(seed_rules() + [draft], seed_pack())
    fixed = deterministic_repair(draft, report["checks"], seed_pack())
    # Đúng bản sửa mong đợi ở docs/02 mục 8, tham chiếu tham số Policy Pack.
    assert fixed["when"]["all"][2:] == [
        {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}},
        {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
    ]
    assert fixed["provenance"] == {"created_by": "det_repair", "parent": "DRAFT-0001@v1"} and fixed["version"] == 2
    assert verify_rules(seed_rules() + [valid(fixed)], seed_pack())["verdict"] in ("PASS", "PASS_WITH_WARNINGS")


def test_det_repair_none_when_rule_not_blamed():
    report = verify_rules(seed_rules(), seed_pack())
    assert deterministic_repair(seed_rules()[2], report["checks"], seed_pack()) is None


def test_evaluate_ranks_by_gate_scope_coverage(seed_df):
    draft = valid(DRAFT_0001)
    report = verify_rules(seed_rules() + [draft], seed_pack())
    fixed = deterministic_repair(draft, report["checks"], seed_pack())
    baseline = run_backtest(seed_rules(), seed_df, seed_pack())
    inv = ["INV-AUTH-01", "INV-AUTH-02"]
    good = evaluate([fixed], draft, seed_rules(), seed_pack(), seed_df, inv, baseline)
    assert good["passes"] and good["scope_ok"] and good["coverage_bp"] == 10_000
    assert good["diff"]["added_vi"][0].startswith("số tiền không quá ngưỡng sinh trắc học/lần")
    # Thu hẹp quá mức: vẫn qua cổng nhưng mất ý định (coverage thấp hơn).
    narrow = copy.deepcopy(fixed)
    narrow["when"]["all"].append({"field": "amount", "op": "<=", "value": 1_000_000})
    worse = evaluate([narrow], draft, seed_rules(), seed_pack(), seed_df, inv, baseline)
    assert worse["passes"] and worse["coverage_bp"] < 10_000
    # Mở rộng phạm vi: bỏ điều kiện tuổi → scope_ok sai.
    wide = copy.deepcopy(fixed)
    wide["when"]["all"] = wide["when"]["all"][1:]
    broad = evaluate([wide], draft, seed_rules(), seed_pack(), seed_df, inv, baseline)
    assert broad["passes"] and not broad["scope_ok"]
    # Không sửa gì → không qua cổng.
    bad = evaluate([draft], draft, seed_rules(), seed_pack(), seed_df, inv, baseline)
    assert not bad["passes"]
    ranked = sorted([bad, broad, worse, good], key=rank_key)
    assert ranked[0] is good and ranked[-1] is bad


def test_coverage_none_when_original_never_matches_outside_violation(seed_df):
    orig = {"when": {"field": "amount", "op": ">", "value": 499_000_000}}
    viol = [{"field": "amount", "op": ">", "value": P}]
    assert coverage_bp(orig, [orig], viol, seed_df, seed_pack()["params"]) is None


def test_condition_diff_lists_added_and_removed():
    d = condition_diff({"all": [{"const": True}]}, {"all": [{"field": "hour", "op": "==", "value": 3}]}, seed_pack())
    assert d == {"added_vi": ["giờ giao dịch bằng 3h"], "removed_vi": ["luôn đúng"]}


# ---------- endpoint ----------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_repair_endpoint_det_only_passes_for_demo1(client):
    sid = client.post("/sessions").json()["session_id"]
    body = client.post(f"/sessions/{sid}/repair", json={"rule": DEMO1_RULE, "use_ai": False}).json()
    assert body["needed"] is True and body["violated_invariants"] == ["INV-AUTH-01", "INV-AUTH-02"]
    assert body["llm"] == "not_requested" and body["rejected"] == []
    (c,) = body["candidates"]
    assert c["source"] == "det" and c["rank"] == 1 and c["passes"] and c["scope_ok"] and c["coverage_bp"] == 10_000
    assert c["rules"][0]["render"]["has_exemption"] is True
    assert c["delta"]["friction_biometric"] <= 0 and isinstance(c["l_net"], int)


def test_repair_endpoint_not_needed_for_clean_rule(client):
    sid = client.post("/sessions").json()["session_id"]
    clean = copy.deepcopy(DEMO1_RULE)
    clean["then"] = {"decision": "MONITOR"}
    body = client.post(f"/sessions/{sid}/repair", json={"rule": clean, "use_ai": False}).json()
    assert body["needed"] is False and "không cần sửa" in body["message_vi"]
