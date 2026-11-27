"""Kiểm chính các gold fixture (docs/08): gold phải hợp lệ và vi phạm đúng những gì đã ghi."""

import json
from pathlib import Path

import pytest

from app.ai.tasks import _prompt_files
from app.data.loader import seed_pack, seed_rules
from app.dsl.validator import check_rule
from app.verify.checks import verify_rules
from app.verify.relations import equivalent, implies

FIXTURES = Path(__file__).resolve().parents[3] / "eval" / "fixtures"
CATEGORIES = {"CLEAN", "REG_BYPASS", "DEAD", "DOMAIN", "REDUNDANT", "CONFLICT", "AMBIGUOUS", "INJECTION", "OUT_OF_SCOPE"}
CASES = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*/*.json"))]


def as_rule(case):
    g = case["gold_rule"]
    return {"id": "DRAFT-0001", "name": case["id"], "kind": "FRAUD", "status": "CANDIDATE", "when": g["when"], "then": g["then"]}


def test_ten_tune_cases_with_unique_ids():
    tune = [c for c in CASES if c["id"].startswith("TU-")]
    assert len(tune) == 10
    assert len({c["id"] for c in CASES}) == len(CASES)


def test_tune_does_not_overlap_few_shot_examples():
    _, examples = _prompt_files("compile.v1")
    shots = {e["requirement"] for e in examples}
    assert not shots & {c["requirement_vi"] for c in CASES}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_gold_is_valid_and_violations_match(case):
    assert case["category"] in CATEGORIES
    if case["gold_rule"] is None:
        assert case["gold_status"] in ("OUT_OF_SCOPE", "NEEDS_CLARIFICATION")
        return
    rule, issues = check_rule(as_rule(case), seed_pack())
    assert issues == [], [i.message_vi for i in issues]
    report = verify_rules(seed_rules() + [rule], seed_pack())
    found = {c["invariant"] for c in report["checks"] if c["code"] == "VC-04"}
    found |= {"VC-03"} if any(c["code"] == "VC-03" for c in report["checks"]) else set()
    found |= {"VC-05"} if any(c.get("redundant") == "DRAFT-0001" for c in report["checks"]) else set()
    expected = {v for v in case["gold_violations"] if v.startswith("INV-") or v in ("VC-03", "VC-05")}
    assert found == expected


def test_relations_helpers():
    p = seed_pack()["params"]
    a = {"field": "amount", "op": ">", "value": 10_000_000}
    b = {"field": "amount", "op": ">=", "value": 10_000_001}
    c = {"field": "amount", "op": ">", "value": {"param": "small_merchant_payment_max"}}
    assert equivalent(a, b, p) == "YES"
    assert implies(a, c, p) == "YES" and implies(c, a, p) == "NO"
    assert equivalent({"field": "hour", "op": "between", "value": [0, 23]}, {"const": True}, p) == "YES"
