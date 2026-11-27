"""T5.3 — cache AI cho câu mẫu + chế độ dự phòng khi không có LLM."""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai import tasks
from app.ai.client import UnavailableClient
from app.api import sessions as sessions_api
from app.data.loader import seed_pack, seed_rules
from app.main import app
from app.store.repo import stable_hash
from tests.test_ai import FakeLLM

ROOT = Path(__file__).resolve().parents[3]

DEMO1_OUT = {
    "status": "OK",
    "rule": {
        "name": "Fast-path khách thân thiết", "description": "", "kind": "FRICTION",
        "when": {"all": [{"field": "sender_account_age_days", "op": ">", "value": 365},
                         {"field": "receiver_is_familiar", "op": "==", "value": True}]},
        "then": {"decision": None, "auth": None, "exempt_auth": True, "hold_seconds": None},
    },
    "assumptions": [{"phrase": "người nhận quen", "interpretation": "đã chuyển ≥ 3 lần trong 90 ngày", "editable": True}],
    "clarifying_questions": [],
    "unsupported_parts": [],
}


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_ai_cache", ROOT / "eval" / "build_ai_cache.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_ai_cache"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_samples_match_web_studio_suggestions():
    """Câu mẫu trong script ghi cache phải trùng từng chữ với câu mẫu trên giao diện, nếu không cache không bao giờ trúng."""
    studio = (ROOT / "apps" / "web" / "components" / "StudioView.tsx").read_text(encoding="utf-8")
    for text in _load_builder().SAMPLES:
        assert f'"{text}"' in studio, text


def test_session_ruleset_hash_matches_seed(client):
    """Khóa cache dựng từ bộ luật seed phải trùng với bộ luật của một phiên mới (lưu qua DB)."""
    from app.store import repo
    from app.store.db import session_factory

    sid = client.post("/sessions").json()["session_id"]
    with session_factory()() as db:
        assert stable_hash(repo.current_rules(db, sid)) == stable_hash(seed_rules())
        assert repo.current_pack(db, sid)["version"] == seed_pack()["version"]


def test_build_cache_keeps_only_valid_llm_outputs():
    mod = _load_builder()
    bad = copy.deepcopy(DEMO1_OUT)
    bad["rule"]["when"] = {"field": "ip_country", "op": "==", "value": "VN"}
    fake = FakeLLM([DEMO1_OUT, bad, bad, DEMO1_OUT])
    cache, failed = mod.build_cache(fake, mod.SAMPLES[:3])
    assert failed == [mod.SAMPLES[1]]  # sai 2 lần → không ghi, không đoán
    assert set(cache) == {tasks.cache_key(t, seed_pack(), seed_rules()) for t in (mod.SAMPLES[0], mod.SAMPLES[2])} | {"_meta"}
    assert cache["_meta"]["model"] == "fake-model" and cache["_meta"]["samples"] == 2


def test_fallback_compiles_sample_from_cache_without_llm(client, monkeypatch):
    mod = _load_builder()
    cache, _ = mod.build_cache(FakeLLM([DEMO1_OUT]), mod.SAMPLES[:1])
    monkeypatch.setattr(tasks, "_seed_cache", lambda: cache)
    monkeypatch.setattr(sessions_api, "get_client", lambda: UnavailableClient("no key"))
    sid = client.post("/sessions").json()["session_id"]

    hit = client.post(f"/sessions/{sid}/compile", json={"text": mod.SAMPLES[0]})
    assert hit.status_code == 200
    body = hit.json()
    assert body["source"] == "cache" and body["rule"]["then"]["exempt_auth"] is True and body["model"] == "cache"
    # Câu khác (không có trong cache) → báo AI không khả dụng, không đoán.
    miss = client.post(f"/sessions/{sid}/compile", json={"text": "Chặn mọi giao dịch lúc 3 giờ sáng"})
    assert miss.status_code == 503 and miss.json()["error_code"] == "LLM_UNAVAILABLE"
    events = client.get(f"/sessions/{sid}/audit").json()["events"]
    assert events[0]["action"] == "rule.compile" and events[0]["ai_call"]["from_cache"] is True


def test_health_reports_fallback_and_cache_size(client, monkeypatch):
    monkeypatch.setattr(tasks, "_seed_cache", lambda: {"k1": {}, "k2": {}, "_meta": {}})
    body = client.get("/health").json()
    assert body["llm"] == "fallback" and body["ai_cache_entries"] == 2
