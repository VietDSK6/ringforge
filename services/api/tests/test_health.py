import z3
from fastapi.testclient import TestClient

from app.config import _split_csv
from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["z3_version"] == z3.get_version_string()
    assert body["app_env"]


def test_health_accepts_head_for_uptime_pings():
    res = client.head("/health")
    assert res.status_code == 200
    assert res.content == b""


def test_cors_allows_configured_origin_only():
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_split_csv_trims_and_drops_empty():
    assert _split_csv(" https://a.vercel.app , http://localhost:3000,, ") == [
        "https://a.vercel.app",
        "http://localhost:3000",
    ]
