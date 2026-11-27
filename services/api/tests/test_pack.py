"""T4.1 — Policy Pack: bản vá, phân tích tác động (Demo 2: 10tr → 5tr thì LG-07 bị báo), áp dụng."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.data.loader import seed_pack, seed_rules
from app.main import app
from app.verify.impact import SetParam, apply_patch, next_version, pack_impact, substitute_literal

DEMO2 = [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": 5_000_000}]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _impact(rules, value, seed_df, param="biometric_per_tx_threshold"):
    old = seed_pack()
    new, issues, changes = apply_patch(old, [SetParam(op="set_param", param=param, value=value)])
    assert new is not None, issues
    return pack_impact(rules, old, new, changes, seed_df)


def _by_id(result):
    return {r["id"]: r for r in result["rules"]}


def test_next_version():
    assert next_version("2026.11-sim.1") == "2026.11-sim.2"
    assert next_version("2026.11-sim.9") == "2026.11-sim.10"
    assert next_version("v") == "v.1"


def test_apply_patch_validates():
    pack = seed_pack()
    new, issues, changes = apply_patch(pack, [SetParam(op="set_param", param="khong_co", value=1)])
    assert new is None and "không tồn tại" in issues[0].message_vi
    new, issues, _ = apply_patch(pack, [SetParam(op="set_param", param="hold_min_seconds", value=200)])
    assert new is None and "tối thiểu" in issues[0].message_vi
    new, issues, changes = apply_patch(pack, [SetParam(op="set_param", param="biometric_per_tx_threshold", value=5_000_000)])
    assert new["version"] == "2026.11-sim.2" and new["params"]["biometric_per_tx_threshold"]["value"] == 5_000_000
    assert changes == [{"op": "set_param", "param": "biometric_per_tx_threshold", "label_vi": "ngưỡng sinh trắc học/lần",
                        "old": 10_000_000, "new": 5_000_000, "unit": "VND"}]
    assert pack["params"]["biometric_per_tx_threshold"]["value"] == 10_000_000  # bản gốc không bị sửa


def test_substitute_literal_only_matching_values():
    c = {"all": [{"field": "amount", "op": ">", "value": 9_000_000}, {"field": "amount", "op": "between", "value": [1, 10_000_000]}]}
    out = substitute_literal(c, "amount", 10_000_000, "p")
    assert out["all"][0]["value"] == 9_000_000 and out["all"][1]["value"] == [1, {"param": "p"}]


def test_demo2_lg07_reported_with_counterexample(seed_df):
    """DoD T4.1: đổi 10tr → 5tr thì LG-07 (viết cứng 10.000.000) bị báo không còn tương thích, kèm phản ví dụ."""
    res = _impact(seed_rules(), 5_000_000, seed_df)
    rules = _by_id(res)
    assert res["counts"] == {"incompatible": 1, "review": 0, "adaptive": 1, "unaffected": 7}
    lg07 = rules["LG-07"]
    assert lg07["category"] == "incompatible"
    stale = next(r for r in lg07["reasons"] if r["code"] == "STALE_LITERAL")
    tx = stale["counterexample"]
    assert 9_000_000 < tx["amount"] < 10_000_000 and 0 <= tx["hour"] <= 5
    assert stale["outcomes"]["before"]["auth"] == "NONE" and stale["outcomes"]["after"]["auth"] == "BIOMETRIC"
    shift = stale["scope_shift"][0]
    assert (shift["invariant"], shift["before"], shift["after"]) == ("INV-AUTH-01", "outside", "inside")
    assert stale["grounding"]["tx_count"] >= 0 and "10.000.000 đ" in stale["message_vi"]
    # Luật tham chiếu tham số tự thích ứng; luật không liên quan không bị đụng.
    assert rules["REG-01"]["category"] == "adaptive" and rules["REG-01"]["params_referenced"] == ["biometric_per_tx_threshold"]
    assert rules["FR-01"]["category"] == "unaffected" and rules["FX-01"]["category"] == "unaffected"
    assert res["verify_after"]["verdict"] == "PASS_WITH_WARNINGS"
    # Ma sát: thêm giao dịch hợp lệ phải sinh trắc học (FR-P3).
    f = res["friction"]
    assert f["delta"]["friction_biometric"] > 0
    assert f["after"]["friction_biometric"] - f["before"]["friction_biometric"] == f["delta"]["friction_biometric"]
    assert f["after"]["valid"] is True


def test_demo2_fix_references_param_and_passes(seed_df):
    fix = _by_id(_impact(seed_rules(), 5_000_000, seed_df))["LG-07"]["fix"]
    assert fix["passes"] and fix["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    parts = fix["rule"]["when"]["all"]
    assert {"field": "amount", "op": "<", "value": {"param": "biometric_per_tx_threshold"}} in parts
    assert {"field": "amount", "op": ">", "value": 4_000_000} in parts  # dải 1 triệu sát dưới ngưỡng được giữ
    assert fix["rule"]["provenance"]["created_by"] == "det_repair" and fix["rule"]["version"] == 2


def test_hardcoded_exemption_becomes_violation(seed_df):
    """Fast-path viết cứng 10.000.000 → sau khi hạ ngưỡng thì vi phạm INV-AUTH-01; bản tham chiếu tham số thì không."""
    base = {"name": "Fast-path", "kind": "FRICTION", "status": "CANDIDATE", "then": {"exempt_auth": True}}
    hard = base | {"id": "DRAFT-0001", "when": {"all": [
        {"field": "receiver_is_familiar", "op": "==", "value": True},
        {"field": "amount", "op": "<=", "value": 10_000_000},
        {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}}]}}
    param = copy.deepcopy(hard) | {"id": "DRAFT-0002"}
    param["when"]["all"][1]["value"] = {"param": "biometric_per_tx_threshold"}
    rules = _by_id(_impact(seed_rules() + [hard, param], 5_000_000, seed_df))
    d1 = rules["DRAFT-0001"]
    assert d1["category"] == "incompatible"
    codes = {r["code"] for r in d1["reasons"]}
    assert {"VC-04", "STALE_LITERAL"} <= codes
    vc04 = next(r for r in d1["reasons"] if r["code"] == "VC-04")
    assert vc04["invariant"] == "INV-AUTH-01" and 5_000_000 < vc04["counterexample"]["amount"] <= 10_000_000
    assert d1["fix"]["passes"]
    assert rules["DRAFT-0002"]["category"] == "adaptive"


def test_scope_shift_without_literal_is_review(seed_df):
    """Hạ ngưỡng xuống 4tr: FR-03 (từ 5tr) chuyển từ 'giao một phần' sang 'nằm trọn' trong phạm vi INV-AUTH-01 → cần xem lại."""
    fr03 = _by_id(_impact(seed_rules(), 4_000_000, seed_df))["FR-03"]
    assert fr03["category"] == "review"
    r = fr03["reasons"][0]
    assert r["code"] == "SCOPE_SHIFT" and (r["before"], r["after"]) == ("partial", "inside") and "counterexample" in r


def test_hold_bounds_change_flags_vc01(seed_df):
    rules = _by_id(_impact(seed_rules(), 150, seed_df, param="hold_max_seconds"))
    assert rules["FR-02"]["category"] == "incompatible"  # HOLD 180 s > tối đa mới 150 s
    assert rules["FR-02"]["reasons"][0]["code"] == "VC-01"
    assert rules["FR-01"]["category"] == "unaffected"  # HOLD 120 s vẫn hợp lệ


# ---------- API ----------


def test_api_impact_apply_and_reset(client):
    sid = client.post("/sessions").json()["session_id"]
    res = client.post(f"/sessions/{sid}/pack/impact", json={"patch": DEMO2})
    assert res.status_code == 200
    body = res.json()
    assert [r["id"] for r in body["rules"] if r["category"] == "incompatible"] == ["LG-07"]
    # Phân tích không đổi pack.
    assert client.get(f"/sessions/{sid}/pack").json()["version"] == "2026.11-sim.1"

    applied = client.post(f"/sessions/{sid}/pack/apply", json={"patch": DEMO2}).json()
    assert applied["pack"]["version"] == "2026.11-sim.2" and applied["previous_version"] == "2026.11-sim.1"
    pack = client.get(f"/sessions/{sid}/pack").json()
    assert pack["params"]["biometric_per_tx_threshold"]["value"] == 5_000_000
    assert [v["version"] for v in client.get(f"/sessions/{sid}/pack/history").json()["versions"]] == ["2026.11-sim.1", "2026.11-sim.2"]
    rules = {r["id"]: r for r in client.get(f"/sessions/{sid}/rules").json()["rules"]}
    assert "5.000.000 đ" in rules["REG-01"]["render"]["sentence_vi"]
    actions = [e["action"] for e in client.get(f"/sessions/{sid}/audit").json()["events"]]
    assert "pack.apply" in actions and "pack.impact" in actions

    # Áp lại cùng bản vá: không có gì thay đổi → từ chối.
    again = client.post(f"/sessions/{sid}/pack/apply", json={"patch": DEMO2})
    assert again.status_code == 422 and again.json()["error_code"] == "VALIDATION_ERROR"

    client.post(f"/sessions/{sid}/reset")
    assert client.get(f"/sessions/{sid}/pack").json()["version"] == "2026.11-sim.1"


def test_api_rejects_bad_patch(client):
    sid = client.post("/sessions").json()["session_id"]
    bad = client.post(f"/sessions/{sid}/pack/impact", json={"patch": [{"op": "set_param", "param": "x", "value": 1}]})
    assert bad.status_code == 422 and bad.json()["details"][0]["message_vi"].startswith("Tham số không tồn tại")
    wrong_type = client.post(f"/sessions/{sid}/pack/impact", json={"patch": [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": "5tr"}]})
    assert wrong_type.status_code == 422
