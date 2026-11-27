"""T5.5 — sửa luật không còn tương thích sau khi đổi Policy Pack: tất định + AI (LLM giả), chấm theo pack mới."""

import pytest
from fastapi.testclient import TestClient

from app.ai.client import UnavailableClient
from app.api import pack as pack_api
from app.main import app
from tests.test_ai import FakeLLM

PATCH = [{"op": "set_param", "param": "biometric_per_tx_threshold", "value": 5_000_000}]
NIGHT = {"field": "hour", "op": "between", "value": [0, 5]}
ACTION = {"decision": "MONITOR", "auth": None, "exempt_auth": False, "hold_seconds": None}


def cand(when_parts, strategy="NARROW_SCOPE"):
    return {"strategy": strategy, "rationale": "Giữ dải 1 triệu sát dưới ngưỡng mới.", "intent_preserved": "Giám sát giao dịch sát ngưỡng ban đêm.",
            "intent_lost": "", "rules": [{"name": "Sát ngưỡng ban đêm", "description": "", "kind": "FRAUD",
                                           "when": {"all": when_parts + [NIGHT]}, "then": ACTION}]}


GOOD = cand([{"field": "amount", "op": ">", "value": 4_000_000},
             {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}}])
STALE = cand([{"field": "amount", "op": ">", "value": 4_000_000}, {"field": "amount", "op": "<", "value": 10_000_000}])
DEAD = cand([{"field": "amount", "op": ">", "value": 9_000_000},
             {"field": "amount", "op": "<", "value": {"param": "biometric_per_tx_threshold"}}], "OTHER")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def run(client, monkeypatch, fake, rule_id="LG-07"):
    monkeypatch.setattr(pack_api, "get_client", lambda: fake)
    sid = client.post("/sessions").json()["session_id"]
    return client.post(f"/sessions/{sid}/pack/repair", json={"patch": PATCH, "rule_id": rule_id}).json()


def test_det_fix_alone_when_ai_unavailable(client, monkeypatch):
    body = run(client, monkeypatch, UnavailableClient("no key"))
    assert body["llm"] == "unavailable" and [c["source"] for c in body["candidates"]] == ["det"]
    det = body["candidates"][0]
    assert det["passes"] and det["stale_params"] == [] and det["relation_ok"] and det["uses_param"]
    assert det["relations"][0]["before"] == det["relations"][0]["after"] == "outside"


def test_ai_candidates_are_judged_against_new_pack(client, monkeypatch):
    fake = FakeLLM([{"candidates": [GOOD, STALE, DEAD]}])
    body = run(client, monkeypatch, fake)
    assert body["llm"] == "used" and len(fake.calls) == 1
    assert sorted(c["source"] for c in body["candidates"]) == ["ai", "det"]
    ai = next(c for c in body["candidates"] if c["source"] == "ai")
    assert ai["relation_ok"] and ai["uses_param"] and ai["rules"][0]["provenance"]["created_by"] == "ai_repair"
    reasons = {r["strategy"]: r["reason_vi"] for r in body["rejected"]}
    assert "viết cứng" in reasons["NARROW_SCOPE"] and reasons["OTHER"].startswith("Không qua kiểm chứng")
    # Prompt riêng cho sửa sau khi đổi pack, có dữ liệu thay đổi và lý do không tương thích.
    assert "Policy Pack (bộ tham số và invariant quy định) VỪA THAY ĐỔI" in fake.calls[0]["system"]
    assert "<pack_change>" in fake.calls[0]["user"] and "STALE_LITERAL" in fake.calls[0]["user"]


def test_second_round_gets_feedback(client, monkeypatch):
    fake = FakeLLM([{"candidates": [STALE]}, {"candidates": [GOOD]}])
    body = run(client, monkeypatch, fake)
    assert len(fake.calls) == 2 and "bị bộ kiểm chứng loại" in fake.calls[1]["user"]
    assert any(c["source"] == "ai" for c in body["candidates"])


def test_compatible_or_locked_rules(client, monkeypatch):
    body = run(client, monkeypatch, UnavailableClient("no key"), "FR-01")
    assert body["needed"] is False
    monkeypatch.setattr(pack_api, "get_client", lambda: UnavailableClient("no key"))
    sid = client.post("/sessions").json()["session_id"]
    res = client.post(f"/sessions/{sid}/pack/repair", json={"patch": PATCH, "rule_id": "REG-01"})
    assert res.status_code == 403
