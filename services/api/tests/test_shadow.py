"""T5.5 — shadow mô phỏng trên ngày 7 (FR-A4): bộ luật cũ và mới chạy song song, chỉ dùng ngày phát lại."""

import pytest
from fastapi.testclient import TestClient

from app.api.verify import DEMO1_RULE, MULE_RULE
from app.backtest.shadow import run_shadow
from app.data.loader import seed_pack, seed_rules
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_shadow_uses_only_replay_day(seed_df):
    r = run_shadow(seed_rules(), seed_rules() + [MULE_RULE], seed_pack(), seed_df)
    assert r["days"] == [7] and r["n_tx"] == int((seed_df["day"] == 7).sum())
    assert r["changed"]["tx_count"] == r["stricter_count"] > 0 and r["looser_count"] == 0
    assert r["fraud_newly_stopped"] > 0 and r["legit_newly_stopped"] == 0
    assert r["delta"]["l_net"] < 0 and r["before"]["n_tx"] == r["n_tx"]
    s = r["samples"][0]
    assert s["label"] in ("APP_VICTIM", "ATO") and s["before"]["decision"] == "ALLOW" and s["after"]["decision"] == "HOLD"


def test_identical_rulesets_have_no_shadow_difference(seed_df):
    r = run_shadow(seed_rules(), seed_rules(), seed_pack(), seed_df)
    assert r["changed"]["tx_count"] == 0 and r["samples"] == [] and r["delta"]["l_net"] == 0


def test_shadow_endpoint_flow(client):
    sid = client.post("/sessions").json()["session_id"]
    cs = client.post(f"/sessions/{sid}/change-sets", json={"items": [{"rule": MULE_RULE}]}).json()
    assert cs["state"] == "VERIFIED" and len(cs["summary"]["base_rules"]) == 9
    sh = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/shadow").json()
    assert sh["state"] == "SHADOW" and sh["summary"]["shadow"]["changed"]["tx_count"] > 0
    ok = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/decision", json={"decision": "approve"}).json()
    assert ok["state"] == "APPROVED"
    # Sau khi duyệt vẫn chạy lại shadow được và vẫn so với bộ luật GỐC lúc tạo change set.
    again = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/shadow").json()
    assert again["state"] == "APPROVED" and again["summary"]["shadow"]["changed"]["tx_count"] == sh["summary"]["shadow"]["changed"]["tx_count"]
    assert "changeset.shadow" in [e["action"] for e in client.get(f"/sessions/{sid}/audit").json()["events"]]


def test_shadow_refused_for_failing_change_set(client):
    sid = client.post("/sessions").json()["session_id"]
    cs = client.post(f"/sessions/{sid}/change-sets", json={"items": [{"rule": DEMO1_RULE}]}).json()
    res = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/shadow")
    assert res.status_code == 409 and res.json()["error_code"] == "SHADOW_NOT_ALLOWED"
