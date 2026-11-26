"""Kiểm chứng hình thức: VC-03 (luật chết), VC-04 (vi phạm invariant) — docs/03 mục 3.

Quy tắc an toàn: solver trả unknown (ví dụ hết thời gian) → status "UNKNOWN", không bao giờ coi là đạt.
"""

from __future__ import annotations

import time
from typing import Any

import z3

from app.dsl.catalog import AUTH, AUTH_LEVELS, DEC, DECISIONS
from app.dsl.render_vi import render_condition
from app.verify.encoder import ACTIVE_STATUSES, domain, enc, make_vars, model_to_tx, outcome
from app.verify.optimize import readable_model

TIMEOUT_MS = 5_000
DEAD_CHECK_STATUSES = ("ACTIVE", "CANDIDATE", "SHADOW")

LEVEL_VI = {"NONE": "xác thực mặc định", "OTP": "OTP", "BIOMETRIC": "sinh trắc học"}
DECISION_VI = {"ALLOW": "cho qua", "MONITOR": "giám sát", "HOLD": "giữ lại", "BLOCK": "chặn"}


def solver_status(result: z3.CheckSatResult) -> str:
    if result == z3.sat:
        return "sat"
    if result == z3.unsat:
        return "unsat"
    return "unknown"


def _check(solver: z3.Solver, *assumptions: z3.BoolRef) -> str:
    """Điểm duy nhất gọi solver.check — test có thể thay để giả lập timeout."""
    return solver_status(solver.check(*assumptions))


def _new_solver(ctx: z3.Context, timeout_ms: int) -> z3.Solver:
    s = z3.Solver(ctx=ctx)
    s.set("timeout", timeout_ms)
    return s


# ---------- VC-03 ----------


def check_dead_rules(
    rules: list[dict[str, Any]], pack: dict[str, Any], ctx: z3.Context, v: dict[str, z3.ExprRef], timeout_ms: int
) -> list[dict[str, Any]]:
    params = pack["params"]
    dom = domain(v, ctx)
    findings = []
    for r in rules:
        if r["status"] not in DEAD_CHECK_STATUSES:
            continue
        parts = r["when"]["all"] if "all" in r["when"] else [r["when"]]
        s = _new_solver(ctx, timeout_ms)
        s.set("core.minimize", True)
        s.add(dom)
        trackers = [z3.Bool(f"__part_{i}", ctx) for i in range(len(parts))]
        for p, part in zip(trackers, parts):
            s.add(z3.Implies(p, enc(part, v, params, ctx)))
        status = _check(s, *trackers)
        if status == "sat":
            continue
        if status == "unknown":
            findings.append({
                "code": "VC-03", "severity": "ERROR", "status": "UNKNOWN", "rule_id": r["id"],
                "message_vi": f"Không kết luận được luật {r['id']} có khả năng kích hoạt hay không (quá {timeout_ms} ms).",
            })
            continue
        core = {str(c) for c in s.unsat_core()}
        conflict = [render_condition(part, pack) for p, part in zip(trackers, parts) if str(p) in core]
        findings.append({
            "code": "VC-03", "severity": "ERROR", "status": "DEAD", "rule_id": r["id"],
            "message_vi": f"Luật {r['id']} không bao giờ kích hoạt: các điều kiện mâu thuẫn với nhau hoặc với miền giá trị.",
            "conflicting_conditions_vi": conflict,
        })
    return findings


# ---------- VC-04 ----------


def _violation(inv: dict[str, Any], dec: z3.ArithRef, auth: z3.ArithRef) -> z3.BoolRef:
    if inv["type"] == "AUTH_AT_LEAST":
        return auth < AUTH[inv["level"]]
    return dec > DEC[inv["level"]]


def _blame(
    inv: dict[str, Any], rules: list[dict[str, Any]], m: z3.ModelRef, v: dict[str, z3.ExprRef], params: dict[str, Any], ctx: z3.Context
) -> list[str]:
    blamed = []
    for r in rules:
        if r["status"] not in ACTIVE_STATUSES:
            continue
        if not z3.is_true(m.eval(enc(r["when"], v, params, ctx), model_completion=True)):
            continue
        t = r["then"]
        if inv["type"] == "AUTH_AT_LEAST" and t.get("exempt_auth"):
            blamed.append(r["id"])
        if inv["type"] == "DECISION_AT_MOST" and "decision" in t and DEC[t["decision"]] > DEC[inv["level"]]:
            blamed.append(r["id"])
    return blamed


def check_invariants(
    rules: list[dict[str, Any]], pack: dict[str, Any], ctx: z3.Context, v: dict[str, z3.ExprRef], timeout_ms: int
) -> list[dict[str, Any]]:
    params = pack["params"]
    dom = domain(v, ctx)
    dec, auth, _ = outcome(rules, v, params, ctx)
    findings = []
    for inv in pack["invariants"]:
        when = enc(inv["when"], v, params, ctx)
        hard = z3.And(dom, when, _violation(inv, dec, auth))
        s = _new_solver(ctx, timeout_ms)
        s.add(hard)
        status = _check(s)
        if status == "unsat":
            continue
        base = {"code": "VC-04", "severity": "ERROR", "invariant": inv["id"]}
        if status == "unknown":
            findings.append(base | {
                "status": "UNKNOWN",
                "message_vi": f"Không kết luận được {inv['id']} trong {timeout_ms} ms; không coi là đạt.",
            })
            continue
        m = readable_model(ctx, v, hard, timeout_ms) or s.model()
        blamed = _blame(inv, rules, m, v, params, ctx)
        got_dec = DECISIONS[m.eval(dec, model_completion=True).as_long()]
        got_auth = AUTH_LEVELS[m.eval(auth, model_completion=True).as_long()]
        scope = render_condition(inv["when"], pack)
        if inv["type"] == "AUTH_AT_LEAST":
            msg = f"Vi phạm {inv['id']}: có giao dịch ({scope}) đi qua mà không cần {LEVEL_VI[inv['level']]}"
            msg += f" do luật miễn trừ {', '.join(blamed)}." if blamed else ": không luật nào hiện thực yêu cầu này."
        else:
            msg = f"Vi phạm {inv['id']}: có giao dịch ({scope}) bị {DECISION_VI[got_dec]}, vượt mức tối đa {DECISION_VI[inv['level']]}"
            msg += f" do luật {', '.join(blamed)}." if blamed else "."
        findings.append(base | {
            "status": "VIOLATED",
            "message_vi": msg,
            "blamed_rules": blamed,
            "counterexample": model_to_tx(m, v),
            "outcome": {"decision": got_dec, "auth": got_auth},
        })
    return findings


# ---------- Tổng hợp ----------


def verdict_of(findings: list[dict[str, Any]]) -> str:
    if any(f["severity"] == "ERROR" and f.get("status") != "UNKNOWN" for f in findings):
        return "FAIL"
    if any(f.get("status") == "UNKNOWN" for f in findings):
        return "UNKNOWN"
    if any(f["severity"] == "WARN" for f in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def verify_rules(rules: list[dict[str, Any]], pack: dict[str, Any], timeout_ms: int = TIMEOUT_MS) -> dict[str, Any]:
    """Báo cáo kiểm chứng cho bộ luật đã qua VC-01 (dict chuẩn hóa) và Policy Pack."""
    started = time.perf_counter_ns()
    ctx = z3.Context()
    v = make_vars(ctx)
    findings = check_dead_rules(rules, pack, ctx, v, timeout_ms) + check_invariants(rules, pack, ctx, v, timeout_ms)
    return {
        "verdict": verdict_of(findings),
        "ms": (time.perf_counter_ns() - started) // 1_000_000,
        "checked": {
            "rules": [r["id"] for r in rules if r["status"] in DEAD_CHECK_STATUSES],
            "invariants": [inv["id"] for inv in pack["invariants"]],
            "pack_version": pack["version"],
        },
        "checks": findings,
    }
