"""T2.4 — phiên sandbox, versioning luật, reset, verify/backtest theo phiên, audit."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.api.verify import DEMO1_RULE
from app.config import normalize_db_url
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def new_session(client) -> str:
    res = client.post("/sessions")
    assert res.status_code == 200
    body = res.json()
    assert body["rules"] == 9 and body["pack_version"] == "2026.11-sim.1"
    return body["session_id"]


def test_db_url_normalization():
    assert normalize_db_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_db_url("").startswith("sqlite:///")


def test_create_session_clones_seed(client):
    sid = new_session(client)
    rules = client.get(f"/sessions/{sid}/rules").json()["rules"]
    assert [r["id"] for r in rules][:2] == ["REG-01", "REG-02"] and len(rules) == 9
    assert rules[0]["render"]["sentence_vi"].startswith("NẾU số tiền lớn hơn ngưỡng sinh trắc học/lần")
    assert client.get(f"/sessions/{sid}/pack").json()["params"]["biometric_per_tx_threshold"]["value"] == 10_000_000


def test_sessions_are_isolated_and_reset(client):
    a, b = new_session(client), new_session(client)
    res = client.put(f"/sessions/{a}/rules/DRAFT-0001", json=DEMO1_RULE).json()
    assert res["saved"] and res["rule"]["version"] == 1 and res["rule"]["render"]["has_exemption"]
    again = client.put(f"/sessions/{a}/rules/DRAFT-0001", json=DEMO1_RULE | {"name": "Bản 2"}).json()
    assert again["rule"]["version"] == 2
    ids_a = [r["id"] for r in client.get(f"/sessions/{a}/rules").json()["rules"]]
    assert ids_a[-1] == "DRAFT-0001" and ids_a.count("DRAFT-0001") == 1
    assert len(client.get(f"/sessions/{b}/rules").json()["rules"]) == 9  # phiên khác không bị ảnh hưởng
    client.post(f"/sessions/{a}/reset")
    assert len(client.get(f"/sessions/{a}/rules").json()["rules"]) == 9


def test_locked_regulatory_rule_cannot_be_edited(client):
    sid = new_session(client)
    reg = next(r for r in client.get(f"/sessions/{sid}/rules").json()["rules"] if r["id"] == "REG-01")
    reg.pop("render")
    res = client.put(f"/sessions/{sid}/rules/REG-01", json=reg | {"then": {"auth": "OTP"}})
    assert res.status_code == 403 and res.json()["error_code"] == "FORBIDDEN"


def test_invalid_rule_not_saved(client):
    sid = new_session(client)
    bad = copy.deepcopy(DEMO1_RULE)
    bad["when"] = {"field": "amount", "op": ">", "value": "10tr"}
    res = client.put(f"/sessions/{sid}/rules/DRAFT-0001", json=bad).json()
    assert res["saved"] is False and "không dùng chuỗi" in res["checks"][0]["message_vi"]


def test_session_verify_demo1_and_audit(client):
    sid = new_session(client)
    assert client.post(f"/sessions/{sid}/verify", json={}).json()["verdict"] == "PASS"
    body = client.post(f"/sessions/{sid}/verify", json={"rules": [DEMO1_RULE]}).json()
    assert body["verdict"] == "FAIL" and body["verify_run_id"]
    inv = {c["invariant"]: c for c in body["checks"]}
    assert inv["INV-AUTH-01"]["counterexample"]["amount"] == 10_000_001
    actions = [e["action"] for e in client.get(f"/sessions/{sid}/audit").json()["events"]]
    assert actions[0] == "verify.run" and actions[-1] == "session.create"


def test_session_backtest_with_variants(client):
    sid = new_session(client)
    body = client.post(f"/sessions/{sid}/backtest", json={
        "variants": [
            {"name": "Thêm DRAFT-0001", "rule_changes": [{"op": "add", "rule": DEMO1_RULE}]},
            {"name": "Bỏ FR-04", "rule_changes": [{"op": "retire", "rule_id": "FR-04"}]},
            {"name": "Luật lỗi", "rule_changes": [{"op": "add", "rule": DEMO1_RULE | {"when": {"field": "x", "op": ">", "value": 1}}}]},
        ],
        "assumptions": {"hold_stop_bp": 6_000},
    }).json()
    assert body["baseline"]["valid"] is True and body["baseline"]["assumptions"]["hold_stop_bp"] == 6_000
    v1, v2, v3 = body["variants"]
    assert v1["result"]["valid"] is False and v1["delta"]["friction_biometric"] < 0
    assert v2["result"]["fp_hold"] == 0 and v2["delta"]["fp_hold"] < 0
    assert v3["error"]["checks"][0]["code"] == "VC-01"
    assert body["ms"] < 5_000


def test_unknown_session_is_404_in_vietnamese(client):
    res = client.get("/sessions/khong-ton-tai/rules")
    assert res.status_code == 404 and res.json()["error_code"] == "NOT_FOUND"
    assert "Vào sandbox" in res.json()["message_vi"]


def test_draft_ids_increment(client):
    from app.store import repo
    from app.store.db import session_factory

    sid = new_session(client)
    with session_factory()() as db:
        assert repo.next_draft_id(db, sid) == "DRAFT-0001"
    client.put(f"/sessions/{sid}/rules/DRAFT-0001", json=DEMO1_RULE)
    with session_factory()() as db:
        assert repo.next_draft_id(db, sid) == "DRAFT-0002"
