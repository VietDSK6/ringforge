"""T1.6 — GET /catalog, POST /verify."""

import copy

from fastapi.testclient import TestClient

from app.api.verify import DEMO1_RULE
from app.data.loader import load_seed_pack_raw, load_seed_rules_raw
from app.main import app

client = TestClient(app)


def checks_by_inv(body):
    return {c["invariant"]: c for c in body["checks"] if c.get("code") == "VC-04"}


def test_catalog():
    body = client.get("/catalog").json()
    assert body["dsl_version"] == "rf-dsl/0.1"
    assert len(body["fields"]) == 17
    amount = next(f for f in body["fields"] if f["name"] == "amount")
    assert amount == {"name": "amount", "type": "int", "label_vi": "số tiền", "ops": [">", ">=", "<", "<=", "==", "!=", "between"],
                      "available_at_decision": True, "min": 1, "max": 500_000_000, "unit": "VND"}
    assert body["decisions"] == ["ALLOW", "MONITOR", "HOLD", "BLOCK"]


def test_verify_seed_only_passes():
    body = client.post("/verify", json={"include_seed_rules": True}).json()
    assert body["verdict"] == "PASS" and body["checks"] == []
    assert len(body["rules_vi"]) == 9 and body["ms"] < 3_000


def test_verify_demo1_fails_with_counterexample():
    res = client.post("/verify", json={"rules": [DEMO1_RULE], "include_seed_rules": True})
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "FAIL"
    found = checks_by_inv(body)
    assert found["INV-AUTH-01"]["counterexample"]["amount"] == 10_000_001
    assert found["INV-AUTH-02"]["counterexample"]["daily_total_after"] == 20_000_001
    assert found["INV-AUTH-01"]["blamed_rules"] == ["DRAFT-0001"]
    assert body["rules_vi"]["DRAFT-0001"].endswith("THÌ miễn xác thực bổ sung")


def test_verify_full_ruleset_in_body_without_seed_flag():
    rules = load_seed_rules_raw() + [DEMO1_RULE]
    body = client.post("/verify", json={"rules": rules}).json()
    assert body["verdict"] == "FAIL" and set(checks_by_inv(body)) == {"INV-AUTH-01", "INV-AUTH-02"}


def test_body_rule_replaces_seed_rule_with_same_id():
    old_fr02 = copy.deepcopy(next(r for r in load_seed_rules_raw() if r["id"] == "FR-02"))
    old_fr02["when"]["all"] = old_fr02["when"]["all"][:3]
    body = client.post("/verify", json={"rules": [old_fr02], "include_seed_rules": True}).json()
    assert list(checks_by_inv(body)) == ["INV-CX-01"]
    assert list(body["rules_vi"]).count("FR-02") == 1


def test_custom_policy_pack_threshold():
    pack = load_seed_pack_raw()
    pack["params"]["biometric_per_tx_threshold"]["value"] = 5_000_000
    body = client.post("/verify", json={"rules": [DEMO1_RULE], "include_seed_rules": True, "policy_pack": pack}).json()
    assert checks_by_inv(body)["INV-AUTH-01"]["counterexample"]["amount"] == 5_000_001


def test_invalid_rule_returns_vc01_in_vietnamese():
    bad = copy.deepcopy(DEMO1_RULE)
    bad["when"] = {"field": "amount", "op": ">", "value": "10tr"}
    body = client.post("/verify", json={"rules": [bad]}).json()
    assert body["verdict"] == "FAIL"
    (c,) = body["checks"]
    assert c["code"] == "VC-01" and "không dùng chuỗi" in c["message_vi"] and c["path"] == "rules[0].when.value"


def test_invalid_pack_returns_vc01():
    pack = load_seed_pack_raw()
    pack["invariants"][0]["level"] = "BLOCK"
    body = client.post("/verify", json={"rules": [DEMO1_RULE], "policy_pack": pack}).json()
    assert body["verdict"] == "FAIL" and body["checks"][0]["code"] == "VC-01"


def test_empty_ruleset_rejected():
    body = client.post("/verify", json={"rules": []}).json()
    assert body["verdict"] == "FAIL" and "Bộ luật rỗng" in body["checks"][0]["message_vi"]


def test_malformed_body_uses_error_format():
    res = client.post("/verify", json={"rules": "không phải danh sách"})
    assert res.status_code == 422
    body = res.json()
    assert body["error_code"] == "VALIDATION_ERROR" and body["message_vi"]


def test_too_many_rules_and_too_large_body():
    res = client.post("/verify", json={"rules": [DEMO1_RULE] * 51})
    assert res.status_code == 422
    res = client.post("/verify", content=b'{"rules": []}' + b" " * 70_000, headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json()["error_code"] == "VALIDATION_ERROR"


def test_openapi_has_examples():
    spec = client.get("/openapi.json").json()
    examples = spec["paths"]["/verify"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert "demo1" in examples
