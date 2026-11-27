"""T4.5 — change set, phê duyệt (chặn khi FAIL), audit có bản ghi AI."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.api import sessions as sessions_api
from app.api.verify import DEMO1_RULE
from app.main import app
from tests.test_ai import FakeLLM
from tests.test_repair_ai import GOOD_HARDCODED

FIXED = copy.deepcopy(DEMO1_RULE)
FIXED["when"]["all"] += [
    {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}},
    {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
]
HARDCODED = copy.deepcopy(DEMO1_RULE)
HARDCODED["when"]["all"] += [
    {"field": "amount", "op": "<=", "value": 10_000_000},
    {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def new_sid(client) -> str:
    return client.post("/sessions").json()["session_id"]


def create(client, sid, items, note="Đề xuất thử"):
    return client.post(f"/sessions/{sid}/change-sets", json={"items": items, "note": note})


def decide(client, sid, cs_id, decision, note=""):
    return client.post(f"/sessions/{sid}/change-sets/{cs_id}/decision", json={"decision": decision, "note": note})


def rule_ids(client, sid) -> dict[str, dict]:
    return {r["id"]: r for r in client.get(f"/sessions/{sid}/rules").json()["rules"]}


def actions(client, sid) -> list[str]:
    return [e["action"] for e in client.get(f"/sessions/{sid}/audit").json()["events"]]


def test_failing_change_set_cannot_be_approved(client):
    sid = new_sid(client)
    cs = create(client, sid, [{"rule": DEMO1_RULE}]).json()
    assert cs["state"] == "DRAFT" and cs["summary"]["verify"]["verdict"] == "FAIL"
    assert cs["items"][0]["op"] == "add" and cs["items"][0]["before_vi"] is None
    assert cs["summary"]["semantic_diff"]["diffs"][0]["direction"] == "looser"
    res = decide(client, sid, cs["id"], "approve")
    assert res.status_code == 409 and res.json()["error_code"] == "APPROVAL_BLOCKED"
    assert any("INV-AUTH-01" in e for e in res.json()["details"]["errors"])
    assert "DRAFT-0001" not in rule_ids(client, sid)  # không có gì được áp dụng
    assert "changeset.approve_blocked" in actions(client, sid)
    # Vẫn từ chối được, nhưng phải có lý do.
    assert decide(client, sid, cs["id"], "reject").status_code == 422
    rej = decide(client, sid, cs["id"], "reject", "Phá QĐ 2345").json()
    assert rej["state"] == "REJECTED" and rej["decision_note"] == "Phá QĐ 2345"
    assert decide(client, sid, cs["id"], "approve").json()["error_code"] == "ALREADY_DECIDED"


def test_verified_change_set_is_applied_on_approval(client):
    sid = new_sid(client)
    cs = create(client, sid, [{"rule": FIXED}]).json()
    assert cs["state"] == "VERIFIED" and cs["summary"]["verify"]["verdict"] == "PASS_WITH_WARNINGS"
    bt = cs["summary"]["backtest"]
    assert bt["after"]["valid"] and bt["delta"]["l_net"] == bt["after"]["l_net"] - bt["before"]["l_net"]
    ok = decide(client, sid, cs["id"], "approve", "Đã xem phản ví dụ").json()
    assert ok["state"] == "APPROVED" and ok["decided_at"]
    rule = rule_ids(client, sid)["DRAFT-0001"]
    assert rule["status"] == "ACTIVE" and rule["version"] == 1
    events = client.get(f"/sessions/{sid}/audit").json()["events"]
    assert [e["actor"] for e in events[:2]] == ["user:approver", "user:approver"]  # approve + rule.save
    assert events[0]["action"] == "changeset.approve" and "changeset.create" in actions(client, sid)
    listed = client.get(f"/sessions/{sid}/change-sets").json()["change_sets"]
    assert [c["id"] for c in listed] == [cs["id"]]


def test_retiring_redundant_rule_is_semantically_equivalent(client):
    """Bỏ LG-09 (thừa, VC-05): VC-07 chứng minh bộ luật cho cùng kết quả trên mọi giao dịch."""
    sid = new_sid(client)
    cs = create(client, sid, [{"op": "retire", "rule_id": "LG-09"}]).json()
    assert cs["state"] == "VERIFIED" and cs["summary"]["verify"]["verdict"] == "PASS"
    assert cs["summary"]["semantic_diff"]["status"] == "EQUIVALENT"
    decide(client, sid, cs["id"], "approve")
    assert rule_ids(client, sid)["LG-09"]["status"] == "RETIRED"


def test_approval_re_verifies_against_current_pack(client):
    """Change set đạt lúc tạo; sau đó hạ ngưỡng 10tr → 5tr; lúc duyệt kiểm chứng lại thì phải chặn."""
    sid = new_sid(client)
    cs = create(client, sid, [{"rule": HARDCODED}]).json()
    assert cs["state"] == "VERIFIED"
    patch = [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": 5_000_000}]
    client.post(f"/sessions/{sid}/pack/apply", json={"patch": patch})
    res = decide(client, sid, cs["id"], "approve")
    assert res.status_code == 409 and res.json()["details"]["verdict"] == "FAIL"


def test_invalid_items_rejected(client):
    sid = new_sid(client)
    reg = rule_ids(client, sid)["REG-01"]
    reg.pop("render")
    res = create(client, sid, [{"rule": reg | {"then": {"auth": "OTP"}}}])
    assert res.status_code == 422 and "bị khóa" in res.json()["details"][0]["message_vi"]
    res = create(client, sid, [{"op": "retire", "rule_id": "KHONG-CO"}])
    assert res.status_code == 422
    assert client.get(f"/sessions/{sid}/change-sets/khong-co").status_code == 404


def test_audit_has_ai_records_with_model_and_prompt_hash(client, monkeypatch):
    monkeypatch.setattr(sessions_api, "get_client", lambda: FakeLLM([{"candidates": [GOOD_HARDCODED]}]))
    sid = new_sid(client)
    client.post(f"/sessions/{sid}/repair", json={"rule": DEMO1_RULE})
    ai = [e for e in client.get(f"/sessions/{sid}/audit").json()["events"] if e["actor"] == "ai"]
    assert ai and ai[0]["action"] == "rule.repair_propose"
    call = ai[0]["ai_call"]
    assert call["model"] == "fake-model" and call["prompt_version"] == "repair.v1" and len(call["prompt_hash"]) == 12
