"""T4.6 — nhập/xuất JSON bộ luật + Policy Pack, /backtest công khai, giới hạn tần suất."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.api.io import EXAMPLE_RULE
from app.api.ratelimit import RateLimiter
from app.api.verify import MULE_RULE
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def new_sid(client) -> str:
    return client.post("/sessions").json()["session_id"]


def test_export_then_import_roundtrip(client):
    a = new_sid(client)
    client.post(f"/sessions/{a}/pack/apply", json={"patch": [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": 5_000_000}]})
    exported = client.get(f"/sessions/{a}/export").json()
    assert exported["format"] == "ringforge-export/1" and exported["dsl_version"] == "rf-dsl/0.1"
    assert len(exported["rules"]) == 9 and exported["policy_pack"]["version"] == "2026.11-sim.2"
    assert "params_vi" not in exported["policy_pack"]  # file xuất là dữ liệu sạch, không kèm nhãn hiển thị

    b = new_sid(client)
    res = client.post(f"/sessions/{b}/import", json=exported)  # nhập nguyên file xuất
    assert res.status_code == 200
    body = res.json()
    assert body["imported"] == {"rules": 9, "policy_pack": "2026.11-sim.2", "mode": "replace"}
    assert body["verify"]["verdict"] == "PASS_WITH_WARNINGS"
    assert client.get(f"/sessions/{b}/pack").json()["params"]["biometric_per_tx_threshold"]["value"] == 5_000_000
    assert "ruleset.import" in [e["action"] for e in client.get(f"/sessions/{b}/audit").json()["events"]]


def test_import_foreign_ruleset_is_verified_immediately(client):
    """Bộ luật lạ không có luật sinh trắc học → kiểm chứng ngay báo không luật nào hiện thực INV-AUTH-01/02."""
    sid = new_sid(client)
    body = client.post(f"/sessions/{sid}/import", json={"rules": [EXAMPLE_RULE]}).json()
    assert body["rules_total"] == 1 and body["verify"]["verdict"] == "FAIL"
    msgs = [c["message_vi"] for c in body["verify"]["checks"] if c.get("invariant") == "INV-AUTH-01"]
    assert msgs and "không luật nào hiện thực" in msgs[0]


def test_import_merge_adds_rule_and_protects_locked(client):
    sid = new_sid(client)
    body = client.post(f"/sessions/{sid}/import", json={"mode": "merge", "rules": [EXAMPLE_RULE]}).json()
    assert body["rules_total"] == 10 and body["verify"]["verdict"] == "PASS_WITH_WARNINGS"
    reg = copy.deepcopy(client.get(f"/sessions/{sid}/export").json()["rules"][0])
    res = client.post(f"/sessions/{sid}/import", json={"mode": "merge", "rules": [reg | {"then": {"auth": "OTP"}}]})
    assert res.status_code == 422 and "bị khóa" in res.json()["details"][0]["message_vi"]


def test_import_rejects_invalid_json_rules(client):
    sid = new_sid(client)
    bad = EXAMPLE_RULE | {"when": {"field": "amount", "op": ">", "value": "10tr"}}
    res = client.post(f"/sessions/{sid}/import", json={"rules": [bad]})
    assert res.status_code == 422 and res.json()["error_code"] == "VALIDATION_ERROR"
    assert "10tr" in res.json()["details"][0]["message_vi"]
    assert client.post(f"/sessions/{sid}/import", json={}).status_code == 422
    assert len(client.get(f"/sessions/{sid}/rules").json()["rules"]) == 9  # không đổi gì


def test_public_backtest_without_session(client):
    body = client.post("/backtest", json={"rules": [MULE_RULE]}).json()
    assert body["delta_vs_seed"]["l_net"] < 0 and body["result"]["valid"] is True
    assert body["result"]["by_scenario"]["S1_MULE"]["prevented"] > 0
    err = client.post("/backtest", json={"rules": [MULE_RULE | {"then": {"decision": "HOLD"}}]}).json()
    assert err["error"]["verdict"] == "FAIL" and "hold_seconds" in err["error"]["checks"][0]["message_vi"]


def test_openapi_lists_public_endpoints_with_examples(client):
    spec = client.get("/openapi.json").json()
    assert "curl" in spec["info"]["description"]
    for path in ("/verify", "/backtest", "/sessions/{sid}/import", "/sessions/{sid}/pack/impact"):
        assert path in spec["paths"]
    examples = spec["paths"]["/backtest"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert "demo3" in examples


def test_rate_limiter_window():
    rl = RateLimiter(2)
    assert rl.allow("ip", 0.0) == (True, 0) and rl.allow("ip", 1.0)[0]
    ok, retry = rl.allow("ip", 2.0)
    assert not ok and 1 <= retry <= 59
    assert rl.allow("other", 2.0)[0]  # IP khác không bị ảnh hưởng
    assert rl.allow("ip", 61.0)[0]  # sau 60 giây
    assert RateLimiter(0).allow("ip", 0.0)[0]  # 0 = tắt


def test_rate_limit_middleware_returns_429(client):
    old = app.state.rate_limiter
    app.state.rate_limiter = RateLimiter(2)
    try:
        assert client.get("/catalog").status_code == 200
        assert client.get("/catalog").status_code == 200
        res = client.get("/catalog")
        assert res.status_code == 429 and res.json()["error_code"] == "RATE_LIMITED" and res.headers["Retry-After"]
        assert client.get("/health").status_code == 200  # ping giữ ấm không bị tính
    finally:
        app.state.rate_limiter = old
