"""T1.1 — catalog, schema, validator (VC-01), render_vi, seed."""

import copy

import pytest

from app.data.loader import load_seed_pack_raw, load_seed_rules_raw, seed_pack, seed_rules
from app.dsl.catalog import CATALOG, DOMAIN_CONSTRAINTS, FIELD_NAMES, catalog_payload
from app.dsl.render_vi import render_rule
from app.dsl.validator import check_pack, check_rule, check_rules

DRAFT_0001 = {
    "id": "DRAFT-0001",
    "version": 1,
    "name": "Fast-path khách thân thiết",
    "kind": "FRICTION",
    "status": "CANDIDATE",
    "locked": False,
    "when": {
        "all": [
            {"field": "sender_account_age_days", "op": ">", "value": 365},
            {"field": "receiver_is_familiar", "op": "==", "value": True},
        ]
    },
    "then": {"exempt_auth": True},
    "assumptions": ["'trên 1 năm' = tuổi tài khoản > 365 ngày"],
    "provenance": {"created_by": "ai_compile", "parent": None, "ai_call_id": "call_test"},
}


def leaf(field, op, value):
    return {"field": field, "op": op, "value": value}


def rule_with(when=None, then=None, **kw):
    r = copy.deepcopy(DRAFT_0001)
    if when is not None:
        r["when"] = when
    if then is not None:
        r["then"] = then
    r.update(kw)
    return r


def messages(issues):
    return " | ".join(i.message_vi for i in issues)


# ---------- catalog ----------


def test_catalog_has_17_fields_and_no_label_fields():
    assert len(FIELD_NAMES) == 17
    assert "label" not in CATALOG and "scenario" not in CATALOG
    assert all(f.label_vi for f in CATALOG.values())
    assert all(f.available_at_decision for f in CATALOG.values())


def test_catalog_domains_match_spec():
    assert (CATALOG["amount"].lo, CATALOG["amount"].hi) == (1, 500_000_000)
    assert (CATALOG["daily_total_after"].lo, CATALOG["daily_total_after"].hi) == (1, 2_000_000_000)
    assert (CATALOG["hour"].lo, CATALOG["hour"].hi) == (0, 23)
    assert (CATALOG["channel"].lo, CATALOG["channel"].hi) == (0, 4)
    assert CATALOG["sender_outbound_ratio_60m_pct"].hi == 1000


def test_domain_constraints_reference_catalog_fields():
    for c in DOMAIN_CONSTRAINTS:
        if c[0] == "ge":
            assert c[1] in CATALOG and c[2] in CATALOG
    payload = catalog_payload()
    assert payload["dsl_version"] == "rf-dsl/0.1" and len(payload["fields"]) == 17


# ---------- seed ----------


def test_seed_pack_and_nine_rules_validate():
    pack, issues = check_pack(load_seed_pack_raw())
    assert issues == [] and pack is not None
    rules, issues = check_rules(load_seed_rules_raw(), pack)
    assert issues == [], messages(issues)
    assert [r["id"] for r in rules] == ["REG-01", "REG-02", "FR-01", "FR-02", "FR-03", "FR-04", "FX-01", "LG-07", "LG-09"]
    assert all(r["locked"] for r in rules if r["kind"] == "REGULATORY")


def test_seed_rules_render_vietnamese():
    for r in seed_rules():
        out = render_rule(r, seed_pack())
        assert out["sentence_vi"].startswith("NẾU ") and " THÌ " in out["sentence_vi"]
    reg01 = render_rule(seed_rules()[0], seed_pack())
    assert reg01["when_vi"] == "số tiền lớn hơn ngưỡng sinh trắc học/lần (hiện 10.000.000 đ)"
    assert reg01["then_vi"] == "yêu cầu sinh trắc học"


def test_render_draft_flags_exemption_and_nesting():
    rule, issues = check_rule(DRAFT_0001, seed_pack())
    assert issues == []
    out = render_rule(rule, seed_pack())
    assert out["has_exemption"] is True
    assert out["sentence_vi"] == "NẾU tuổi tài khoản gửi lớn hơn 365 ngày VÀ người nhận quen THÌ miễn xác thực bổ sung"
    fr03 = next(r for r in seed_rules() if r["id"] == "FR-03")
    assert "(giờ giao dịch từ 22h đến 23h HOẶC giờ giao dịch từ 0h đến 5h)" in render_rule(fr03)["when_vi"]
    fr02 = next(r for r in seed_rules() if r["id"] == "FR-02")
    assert render_rule(fr02)["then_vi"] == "giữ 180 giây để xác minh · yêu cầu sinh trắc học"


# ---------- validator ----------


def test_draft_rule_canonical_form():
    rule, issues = check_rule(DRAFT_0001, seed_pack())
    assert issues == []
    assert rule["then"] == {"exempt_auth": True}
    assert rule["provenance"] == {"created_by": "ai_compile", "ai_call_id": "call_test"}


@pytest.mark.parametrize(
    "when, expected",
    [
        (leaf("amount", ">", "10tr"), "không dùng chuỗi"),
        (leaf("amount", ">", 1.5), "không dùng số thực"),
        (leaf("amount", ">", 10_000_000.0), "không dùng số thực"),
        (leaf("amount", ">", True), "số nguyên"),
        (leaf("label", "==", "ATO"), "không có trong danh mục"),
        (leaf("scenario", "==", "S1_MULE"), "không có trong danh mục"),
        (leaf("is_new_device", ">", True), "Toán tử '>'"),
        (leaf("is_new_device", "==", 1), "true/false"),
        (leaf("channel", "<", "P2P"), "Toán tử '<'"),
        (leaf("channel", "==", "CASH"), "không hợp lệ"),
        (leaf("channel", "in", []), "không rỗng"),
        (leaf("channel", "in", ["P2P", "CASH"]), "'CASH'"),
        (leaf("amount", "between", [5, 1]), "≤"),
        (leaf("amount", "between", [1]), "đúng 2"),
        (leaf("amount", "in", [1, 2]), "Toán tử 'in'"),
        (leaf("amount", ">", {"param": "no_such"}), "Tham số không tồn tại"),
        (leaf("amount", "~", 1), "cho phép"),
        ({"all": []}, "không được rỗng"),
        ({"foo": 1}, "khóa không được phép"),
    ],
)
def test_invalid_conditions_rejected_with_vietnamese_message(when, expected):
    rule, issues = check_rule(rule_with(when=when), seed_pack())
    assert rule is None and issues
    assert expected in messages(issues)
    assert all(i.code == "VC-01" and i.severity == "ERROR" for i in issues)


def test_depth_and_leaf_limits():
    deep = leaf("amount", ">", 1)
    for _ in range(6):
        deep = {"not": deep}
    _, issues = check_rule(rule_with(when=deep), seed_pack())
    assert "quá sâu" in messages(issues)
    wide = {"all": [leaf("amount", ">", i) for i in range(21)]}
    _, issues = check_rule(rule_with(when=wide), seed_pack())
    assert "Quá nhiều điều kiện lá" in messages(issues)
    ok = {"all": [leaf("amount", ">", i) for i in range(20)]}
    assert check_rule(rule_with(when=ok), seed_pack())[1] == []


def test_hold_requires_seconds_in_pack_range():
    _, issues = check_rule(rule_with(then={"decision": "HOLD"}), seed_pack())
    assert "cần 'hold_seconds'" in messages(issues)
    _, issues = check_rule(rule_with(then={"decision": "HOLD", "hold_seconds": 30}), seed_pack())
    assert "60–180" in messages(issues)
    assert check_rule(rule_with(then={"decision": "HOLD", "hold_seconds": 60}), seed_pack())[1] == []


def test_bad_action_and_ids():
    _, issues = check_rule(rule_with(then={"decision": "DENY"}), seed_pack())
    assert "cho phép" in messages(issues)
    _, issues = check_rule(rule_with(id="draft 1"), seed_pack())
    assert "sai định dạng" in messages(issues)
    _, issues = check_rules([DRAFT_0001, DRAFT_0001], seed_pack())
    assert "Trùng mã luật" in messages(issues)


def test_pack_invariant_level_checked():
    raw = load_seed_pack_raw()
    raw["invariants"][0]["level"] = "BLOCK"
    pack, issues = check_pack(raw)
    assert pack is None and "không hợp lệ cho AUTH_AT_LEAST" in messages(issues)
    raw = load_seed_pack_raw()
    raw["params"]["biometric_per_tx_threshold"]["value"] = 10_000_000.5
    pack, issues = check_pack(raw)
    assert pack is None
