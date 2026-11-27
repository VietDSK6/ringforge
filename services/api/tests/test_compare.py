"""T4.4 — backtest nhiều phương án cho Demo 3: luật phía người nhận, cửa sổ 15/30/60 phút, HOLD/BLOCK, cổng invariant."""

import pytest
from fastapi.testclient import TestClient

from app.api.verify import DEMO1_RULE
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def mule_rule(window: str = "30m", senders: int = 2, max_age: int | None = 14, decision: str = "HOLD") -> dict:
    parts = [
        {"field": f"receiver_distinct_senders_{window}", "op": ">=", "value": senders},
        {"field": "channel", "op": "==", "value": "P2P"},
    ]
    if max_age is not None:
        parts.insert(0, {"field": "receiver_account_age_days", "op": "<", "value": max_age})
    then = {"decision": decision} | ({"hold_seconds": 120} if decision == "HOLD" else {})
    return {"id": "FR-05", "name": "Tài khoản nhận mới gom tiền", "kind": "FRAUD", "status": "CANDIDATE",
            "when": {"all": parts}, "then": then}


def variant(name: str, rule: dict) -> dict:
    return {"name": name, "rule_changes": [{"op": "add", "rule": rule}]}


DEMO3 = [
    variant("15 phút · HOLD", mule_rule("15m")),
    variant("30 phút · HOLD", mule_rule("30m")),
    variant("60 phút · HOLD", mule_rule("60m")),
    variant("60 phút · BLOCK · mọi tuổi", mule_rule("60m", max_age=None, decision="BLOCK")),
]


def _run(client, variants, **assumptions):
    sid = client.post("/sessions").json()["session_id"]
    res = client.post(f"/sessions/{sid}/backtest", json={"variants": variants, "assumptions": assumptions})
    assert res.status_code == 200
    return res.json()


def test_windows_change_victim_loss(client):
    body = _run(client, DEMO3)
    base = body["baseline"]
    v15, v30, v60, block = body["variants"]
    # Cửa sổ dài hơn bắt nhiều khoản nạn nhân → mule hơn → lọt gian lận giảm (L_net thật sự đổi).
    assert base["fn_loss"] > v15["result"]["fn_loss"] > v30["result"]["fn_loss"] > v60["result"]["fn_loss"]
    s1 = lambda v: v["result"]["by_scenario"]["S1_MULE"]["prevented"]  # noqa: E731
    assert 0 < s1(v15) < s1(v30) < s1(v60) < s1(block)
    # Luật có giới hạn tuổi tài khoản nhận không chặn nhầm; bản "mọi tuổi" chặn nhầm vài giao dịch thật.
    assert all(v["result"]["fp_block"] == base["fp_block"] for v in (v15, v30, v60))
    assert block["result"]["fp_block"] > base["fp_block"]
    assert all(v["eligible"] and v["verify"]["verdict"] in ("PASS", "PASS_WITH_WARNINGS") for v in body["variants"])
    assert "15 phút" in v15["rules_vi"]["FR-05"] and "trong 60 phút" in v60["rules_vi"]["FR-05"]
    assert [v["rank"] for v in body["variants"]] == [4, 3, 2, 1]  # mặc định: BLOCK ngăn 100% → tốt nhất


def test_assumption_slider_can_flip_ranking(client):
    """Khoảng dừng hiệu quả 100%: HOLD ngăn bằng BLOCK mà không tốn chi phí duyệt chặn nhầm → HOLD 60 phút vượt lên."""
    body = _run(client, DEMO3, hold_stop_bp=10_000)
    ranks = {v["name"]: v["rank"] for v in body["variants"]}
    assert ranks["60 phút · HOLD"] == 1 and ranks["60 phút · BLOCK · mọi tuổi"] == 2


def test_invariant_gate_excludes_violating_variant(client):
    body = _run(client, [variant("Miễn trừ khách thân thiết", DEMO1_RULE), DEMO3[0]])
    bad, ok = body["variants"]
    assert bad["verify"]["verdict"] == "FAIL" and not bad["eligible"] and "rank" not in bad
    assert bad["result"]["valid"] is False  # exposure tuân thủ > 0 trên dữ liệu
    assert ok["eligible"] and ok["rank"] == 1


def test_invalid_variant_reports_vc01(client):
    broken = mule_rule() | {"when": {"field": "receiver_distinct_senders_45m", "op": ">=", "value": 2}}
    body = _run(client, [variant("Sai trường", broken)])
    v = body["variants"][0]
    assert v["eligible"] is False and v["error"]["verdict"] == "FAIL"
    assert "45m" in v["error"]["checks"][0]["message_vi"]
