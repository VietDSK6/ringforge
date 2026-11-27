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


# ---------- VC-05 luật thừa, VC-06 xung đột miễn trừ (P1) ----------


def _effect(r: dict[str, Any]) -> tuple[int, int, bool, int]:
    t = r["then"]
    dec = DEC[t["decision"]] if "decision" in t else 0
    auth = AUTH[t["auth"]] if "auth" in t else 0
    hold = t.get("hold_seconds", 0) if t.get("decision") == "HOLD" else 0
    return dec, auth, bool(t.get("exempt_auth")), hold


def _covers(s: tuple[int, int, bool, int], r: tuple[int, int, bool, int]) -> bool:
    """Hiệu ứng của s bao trùm r: bỏ r không đổi kết quả ở đâu cả khi s cũng khớp."""
    return s[0] >= r[0] and s[1] >= r[1] and (not r[2] or s[2]) and s[3] >= r[3]


def check_redundant(
    rules: list[dict[str, Any]], pack: dict[str, Any], ctx: z3.Context, v: dict[str, z3.ExprRef], timeout_ms: int,
    dead: set[str] | None = None,
) -> list[dict[str, Any]]:
    """VC-05 (docs/03 mục 3): r thừa so với s nếu r ⊆ s và hiệu ứng của s bao trùm r; chỉ xét cùng kind hoặc s pháp lý.
    Luật chết (VC-03) nằm trong mọi luật một cách tầm thường → không báo thừa, tránh nhiễu cạnh lỗi ERROR."""
    active = [r for r in rules if r["status"] in ACTIVE_STATUSES and r["id"] not in (dead or set())]
    dom = domain(v, ctx)
    whens = {r["id"]: enc(r["when"], v, pack["params"], ctx) for r in active}
    findings, flagged = [], set()
    # Xét từ luật thêm sau về trước: khi hai luật trùng nhau, luật mới (thường là ứng viên) mới là luật thừa.
    for r in reversed(active):
        for s in active:
            if r is s or s["id"] in flagged or not (r["kind"] == s["kind"] or s["kind"] == "REGULATORY"):
                continue
            if not _covers(_effect(s), _effect(r)):
                continue
            sol = _new_solver(ctx, timeout_ms)
            sol.add(dom, whens[r["id"]], z3.Not(whens[s["id"]]))
            if _check(sol) != "unsat":
                continue  # sat: r không nằm trong s; unknown: không kết luận → không báo
            flagged.add(r["id"])
            findings.append({
                "code": "VC-05", "severity": "WARN", "status": "REDUNDANT", "redundant": r["id"], "covered_by": s["id"],
                "message_vi": f"Luật {r['id']} thừa: mọi giao dịch nó khớp đều đã được {s['id']} xử lý ở mức bằng hoặc chặt hơn.",
            })
            break
    order = {r["id"]: i for i, r in enumerate(active)}
    return sorted(findings, key=lambda f: order[f["redundant"]])


def check_exemption_conflicts(
    rules: list[dict[str, Any]], pack: dict[str, Any], ctx: z3.Context, v: dict[str, z3.ExprRef], timeout_ms: int,
    vc04: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """VC-06: luật miễn trừ r chồng lấn luật s yêu cầu xác thực ≥ OTP → miễn trừ thắng ở vùng chồng lấn.
    Bỏ qua cặp (r, luật pháp lý) khi r đã bị VC-04 quy lỗi — lỗi đó đã được báo ở mức ERROR."""
    active = [r for r in rules if r["status"] in ACTIVE_STATUSES]
    already = {b for f in vc04 for b in f.get("blamed_rules", [])}
    dom = domain(v, ctx)
    findings = []
    for r in (x for x in active if x["then"].get("exempt_auth")):
        for s in active:
            if s is r or AUTH.get(s["then"].get("auth", "NONE"), 0) < AUTH["OTP"]:
                continue
            if s["kind"] == "REGULATORY" and r["id"] in already:
                continue
            hard = z3.And(dom, enc(r["when"], v, pack["params"], ctx), enc(s["when"], v, pack["params"], ctx))
            sol = _new_solver(ctx, timeout_ms)
            sol.add(hard)
            if _check(sol) != "sat":
                continue
            m = readable_model(ctx, v, hard, timeout_ms) or sol.model()
            level = LEVEL_VI[s["then"]["auth"]]
            findings.append({
                "code": "VC-06", "severity": "WARN", "status": "CONFLICT", "rule_id": r["id"], "conflicts_with": s["id"],
                "message_vi": (
                    f"Luật {r['id']} miễn xác thực cả những giao dịch mà {s['id']} yêu cầu {level}: "
                    f"miễn trừ thắng, nên {s['id']} mất tác dụng ở vùng chồng lấn."
                ),
                "counterexample": model_to_tx(m, v),
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
    findings = check_dead_rules(rules, pack, ctx, v, timeout_ms)
    dead = {f["rule_id"] for f in findings if f.get("status") == "DEAD"}
    vc04 = check_invariants(rules, pack, ctx, v, timeout_ms)
    findings += vc04
    findings += check_redundant(rules, pack, ctx, v, timeout_ms, dead)
    findings += check_exemption_conflicts(rules, pack, ctx, v, timeout_ms, vc04)
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
