"""T5.2 — harness ablation: A/G chạy không cần AI; B/C/D phủ bằng LLM giả "trả về gold" (không phải số liệu báo cáo)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.ai.client import LLMResult
from app.api import sessions as sessions_api

ROOT = Path(__file__).resolve().parents[3]
CASES = {"T-09", "T-21", "T-28"}


def _load():
    spec = importlib.util.spec_from_file_location("run_ablation", ROOT / "eval" / "run_ablation.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_ablation"] = mod
    spec.loader.exec_module(mod)
    return mod


class GoldEchoLLM:
    """Biên dịch đúng gold; tự đánh giá (B) luôn nói 'không lỗi'; không đề xuất bản sửa."""

    available = True
    model = "fake-gold"

    def __init__(self, cases):
        self.cases = cases
        self.calls: list[str] = []

    def complete_json(self, system, user, schema, schema_name):
        self.calls.append(schema_name)
        if schema_name == "rf_compile":
            case = next(c for c in self.cases if c["requirement_vi"] in user)
            g = case["gold_rule"]
            then = {"decision": None, "auth": None, "exempt_auth": False, "hold_seconds": None} | g["then"]
            data = {
                "status": "OK",
                "rule": {"name": case["id"], "description": "", "kind": "FRAUD", "when": g["when"], "then": then},
                "assumptions": [{"phrase": p, "interpretation": "giả định", "editable": True} for p in case["gold_assumptions"]],
                "clarifying_questions": [],
                "unsupported_parts": [],
            }
        elif schema_name == "rf_selfcheck":
            data = {"violated_invariants": [], "never_fires": False, "redundant": False, "exemption_conflict": False, "repaired_rule": None}
        else:
            data = {"candidates": []}
        return LLMResult(data=data, model=self.model, tokens_in=1, tokens_out=1, latency_ms=1)


@pytest.fixture(scope="module")
def mod():
    return _load()


def test_without_llm_only_a_and_g_run(mod):
    from app.ai.client import UnavailableClient

    res = mod.run(["A", "G", "C"], "test", client=UnavailableClient("no key"), only=CASES)
    assert res["skipped"] == ["C"] and {r["config"] for r in res["rows"]} == {"A", "G"}
    s = mod.summarize(res)
    assert s["G"]["exact_cases"] == 1.0
    assert s["A"]["detect"]["per_code"]["VC-05"]["recall"] == 0  # backtest không có khái niệm luật thừa
    report = mod.report_md(res, s)
    assert "Chưa chạy" in report and "thiếu `LLM_API_KEY`" in report


def test_llm_configs_with_gold_echo(mod, monkeypatch):
    cases = [c for c in mod.load_cases("test") if c["id"] in CASES]
    fake = GoldEchoLLM(cases)
    monkeypatch.setattr(sessions_api, "get_client", lambda: fake)
    res = mod.run(["B", "C", "D"], "test", client=fake, only=CASES)
    rows = {(r["config"], r["case"]): r for r in res["rows"]}
    assert len(rows) == 9 and not res["skipped"]
    for cid in CASES:
        c = rows[("C", cid)]
        assert c["compile"]["semantic_equiv"] is True and set(c["found"]) == set(c["gold"])
        assert rows[("B", cid)]["found"] == []  # LLM giả tự đánh giá "không lỗi" → B bỏ sót
    assert rows[("C", "T-28")]["compile"]["injection_safe"] is True
    assert rows[("C", "T-09")]["repair_ok"] and rows[("D", "T-09")]["repair_ok"]
    assert rows[("B", "T-09")]["repair_ok"] is False
    s = mod.summarize(res)
    assert s["B"]["detect"]["recall"] == 0 and s["C"]["detect"]["recall"] == 1.0
    assert "rf_selfcheck" in fake.calls and "rf_repair" in fake.calls
