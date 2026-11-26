import z3
from fastapi.testclient import TestClient

from app.main import app
from app.spike_z3 import (
    DRAFT_0001,
    DRAFT_0001_FIXED,
    INVARIANTS,
    REG_01,
    REG_02,
    check_auth_invariant,
    run_spike,
    solver_status,
    verify_rules,
)

INV_01, INV_02 = INVARIANTS


def test_seed_rules_satisfy_both_invariants():
    report = verify_rules([REG_01, REG_02])
    assert report["verdict"] == "PASS"
    assert [c["status"] for c in report["checks"]] == ["HOLDS", "HOLDS"]


def test_draft_violates_inv_auth_01_at_threshold_plus_one():
    check = check_auth_invariant([REG_01, REG_02, DRAFT_0001], INV_01)
    assert check["status"] == "VIOLATED"
    cx = check["counterexample"]
    assert cx["amount"] == 10_000_001
    assert cx["sender_account_age_days"] == 366
    assert cx["receiver_is_familiar"] is True
    assert cx["daily_total_after"] >= cx["amount"]
    assert check["blamed_rules"] == ["DRAFT-0001"]
    assert check["outcome"] == {"auth": "NONE"}


def test_draft_violates_inv_auth_02_at_daily_threshold_plus_one():
    check = check_auth_invariant([REG_01, REG_02, DRAFT_0001], INV_02)
    assert check["status"] == "VIOLATED"
    cx = check["counterexample"]
    assert cx["daily_total_after"] == 20_000_001
    assert cx["amount"] == 1
    assert cx["sender_account_age_days"] == 366
    assert cx["receiver_is_familiar"] is True
    assert check["blamed_rules"] == ["DRAFT-0001"]


def test_counterexample_values_are_ints_not_floats():
    check = check_auth_invariant([REG_01, REG_02, DRAFT_0001], INV_01)
    for name, value in check["counterexample"].items():
        assert type(value) in (int, bool), name


def test_fixed_draft_passes_both_invariants():
    report = verify_rules([REG_01, REG_02, DRAFT_0001_FIXED])
    assert report["verdict"] == "PASS"
    assert [c["status"] for c in report["checks"]] == ["HOLDS", "HOLDS"]


def test_missing_regulatory_rule_is_reported_without_blame():
    check = check_auth_invariant([REG_02], INV_01)
    assert check["status"] == "VIOLATED"
    assert check["blamed_rules"] == []


def test_unknown_is_never_pass():
    assert solver_status(z3.unknown) == "UNKNOWN"
    assert solver_status(z3.sat) == "VIOLATED"
    assert solver_status(z3.unsat) == "HOLDS"


def test_run_spike_shape():
    result = run_spike()
    assert set(result["scenarios"]) == {"seed", "draft", "fixed"}
    assert result["scenarios"]["draft"]["verdict"] == "FAIL"
    assert isinstance(result["ms"], int)


def test_spike_endpoint():
    res = TestClient(app).get("/spike/z3")
    assert res.status_code == 200
    body = res.json()
    draft_checks = body["scenarios"]["draft"]["checks"]
    assert draft_checks[0]["counterexample"]["amount"] == 10_000_001
    assert draft_checks[1]["counterexample"]["daily_total_after"] == 20_000_001
    assert body["scenarios"]["fixed"]["verdict"] == "PASS"
