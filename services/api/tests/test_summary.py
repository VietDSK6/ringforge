"""T5.5 — tóm tắt cho người duyệt: AI chỉ viết lời; số nào không có trong dữ liệu đầu vào thì bỏ bản AI (G5)."""

import pytest
from fastapi.testclient import TestClient

from app.ai.client import UnavailableClient
from app.ai.summary_task import build_facts, invented_numbers, template_summary
from app.api import approvals as approvals_api
from app.api.verify import DEMO1_RULE, MULE_RULE
from app.main import app
from tests.test_ai import FakeLLM


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_cs(client, rule):
    sid = client.post("/sessions").json()["session_id"]
    return sid, client.post(f"/sessions/{sid}/change-sets", json={"items": [{"rule": rule}]}).json()


def test_template_uses_only_input_numbers(client):
    _, cs = make_cs(client, MULE_RULE)
    facts = build_facts(cs)
    text = template_summary(facts)
    assert invented_numbers(text, facts) == []
    assert "thêm FR-05" in text and "giảm" in text and facts["ton_that_rong_sau_d"] in text


def test_codes_are_not_numbers_but_new_figures_are():
    facts = {"a": "445.252.695", "b": ["thêm FR-05"]}
    assert invented_numbers("FR-05 và INV-AUTH-01: 445.252.695 đ", facts) == []
    assert invented_numbers("giảm 17% còn 445.252.695 đ", facts) == ["17"]
    assert invented_numbers("khoảng 445 triệu", facts) == ["445"]  # làm tròn cũng là số mới


def test_ai_summary_accepted_when_numbers_match(client, monkeypatch):
    sid, cs = make_cs(client, MULE_RULE)
    f = build_facts(cs)
    text = f"Thêm FR-05; kiểm chứng {f['ket_luan_kiem_chung']}. Tổn thất ròng còn {f['ton_that_rong_sau_d']} đ."
    monkeypatch.setattr(approvals_api, "get_client", lambda: FakeLLM([{"summary_vi": text, "numbers_used": [f["ton_that_rong_sau_d"]]}]))
    out = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/summary").json()["summary"]["review_summary"]
    assert out["source"] == "ai" and out["summary_vi"] == text and out["model"] == "fake-model"
    ai = [e for e in client.get(f"/sessions/{sid}/audit").json()["events"] if e["action"] == "changeset.summary"]
    assert ai and ai[0]["ai_call"]["prompt_version"] == "summary.v1"


def test_ai_summary_with_invented_number_falls_back(client, monkeypatch):
    sid, cs = make_cs(client, DEMO1_RULE)
    bad = {"summary_vi": "Luật này giảm 37% gian lận và tiết kiệm 1.234.567 đ.", "numbers_used": ["37", "1.234.567"]}
    monkeypatch.setattr(approvals_api, "get_client", lambda: FakeLLM([bad]))
    out = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/summary").json()["summary"]["review_summary"]
    assert out["source"] == "template" and out["ai"] == "rejected" and set(out["rejected_numbers"]) == {"37", "1.234.567"}
    assert "không phê duyệt được" in out["summary_vi"]  # change set FAIL


def test_without_ai_template_is_used(client, monkeypatch):
    sid, cs = make_cs(client, MULE_RULE)
    monkeypatch.setattr(approvals_api, "get_client", lambda: UnavailableClient("no key"))
    out = client.post(f"/sessions/{sid}/change-sets/{cs['id']}/summary").json()["summary"]["review_summary"]
    assert out["source"] == "template" and out["ai"] == "unavailable"
