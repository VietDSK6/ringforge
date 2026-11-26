"""Spike T0.5 — mã hóa tối thiểu REG-01/REG-02 + luật miễn trừ sang Z3 và tìm phản ví dụ.

Theo hình dạng mã hóa ở docs/03 mục 2 (chỉ phần auth) để T1.4 nhấc lên `app/verify/encoder.py`.
Phạm vi: 4 trường của catalog (docs/02 mục 1), một Policy Pack rút gọn, invariant AUTH_AT_LEAST.

Quy tắc giữ ở đây và trong bản thật:
- Mọi giá trị tiền là int VNĐ; không có float.
- Solver trả unknown (ví dụ hết thời gian) → "UNKNOWN", không bao giờ coi là PASS.
- Mỗi lần kiểm chứng dùng `z3.Context()` riêng để an toàn khi FastAPI chạy song song nhiều request.
"""

from __future__ import annotations

import time
from typing import Any

import z3

AUTH = {"NONE": 0, "OTP": 1, "BIOMETRIC": 2}
AUTH_NAME = {v: k for k, v in AUTH.items()}
TIMEOUT_MS = 5_000

# Catalog con: tên → (kiểu, min, max). Miền lấy đúng docs/02 mục 1.
FIELDS: dict[str, tuple[str, int | None, int | None]] = {
    "amount": ("int", 1, 500_000_000),
    "daily_total_after": ("int", 1, 2_000_000_000),
    "sender_account_age_days": ("int", 0, 3650),
    "receiver_is_familiar": ("bool", None, None),
}

PARAMS: dict[str, dict[str, Any]] = {
    "biometric_per_tx_threshold": {"value": 10_000_000, "unit": "VND"},
    "biometric_daily_threshold": {"value": 20_000_000, "unit": "VND"},
}

INVARIANTS: list[dict[str, Any]] = [
    {
        "id": "INV-AUTH-01",
        "type": "AUTH_AT_LEAST",
        "level": "BIOMETRIC",
        "when": {"field": "amount", "op": ">", "value": {"param": "biometric_per_tx_threshold"}},
    },
    {
        "id": "INV-AUTH-02",
        "type": "AUTH_AT_LEAST",
        "level": "BIOMETRIC",
        "when": {"field": "daily_total_after", "op": ">", "value": {"param": "biometric_daily_threshold"}},
    },
]

# Thứ tự tối thiểu hóa (lexicographic) để phản ví dụ nằm sát mốc, dễ đọc (docs/03 mục 3).
MINIMIZE_ORDER: dict[str, list[str]] = {
    "INV-AUTH-01": ["amount", "daily_total_after", "sender_account_age_days"],
    "INV-AUTH-02": ["daily_total_after", "amount", "sender_account_age_days"],
}

REG_01: dict[str, Any] = {
    "id": "REG-01",
    "kind": "REGULATORY",
    "status": "ACTIVE",
    "when": {"field": "amount", "op": ">", "value": {"param": "biometric_per_tx_threshold"}},
    "then": {"auth": "BIOMETRIC"},
}
REG_02: dict[str, Any] = {
    "id": "REG-02",
    "kind": "REGULATORY",
    "status": "ACTIVE",
    "when": {"field": "daily_total_after", "op": ">", "value": {"param": "biometric_daily_threshold"}},
    "then": {"auth": "BIOMETRIC"},
}
# Luật Demo 1 (docs/02 mục 8): miễn xác thực cho khách lâu năm chuyển cho người nhận quen.
DRAFT_0001: dict[str, Any] = {
    "id": "DRAFT-0001",
    "kind": "FRICTION",
    "status": "CANDIDATE",
    "when": {
        "all": [
            {"field": "sender_account_age_days", "op": ">", "value": 365},
            {"field": "receiver_is_familiar", "op": "==", "value": True},
        ]
    },
    "then": {"exempt_auth": True},
}
# Bản sửa mong đợi (docs/02 mục 8): giới hạn miễn trừ dưới cả hai ngưỡng sinh trắc học.
DRAFT_0001_FIXED: dict[str, Any] = {
    **DRAFT_0001,
    "when": {
        "all": [
            {"field": "sender_account_age_days", "op": ">", "value": 365},
            {"field": "receiver_is_familiar", "op": "==", "value": True},
            {"field": "amount", "op": "<=", "value": {"param": "biometric_per_tx_threshold"}},
            {"field": "daily_total_after", "op": "<=", "value": {"param": "biometric_daily_threshold"}},
        ]
    },
}

SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "seed": [REG_01, REG_02],
    "draft": [REG_01, REG_02, DRAFT_0001],
    "fixed": [REG_01, REG_02, DRAFT_0001_FIXED],
}


def make_vars(ctx: z3.Context) -> dict[str, z3.ExprRef]:
    return {
        name: z3.Bool(name, ctx) if typ == "bool" else z3.Int(name, ctx)
        for name, (typ, _, _) in FIELDS.items()
    }


def domain(v: dict[str, z3.ExprRef]) -> z3.BoolRef:
    cs: list[z3.BoolRef] = []
    for name, (typ, lo, hi) in FIELDS.items():
        if typ == "int":
            cs += [v[name] >= lo, v[name] <= hi]
    cs.append(v["daily_total_after"] >= v["amount"])
    return z3.And(cs)


def _resolve(value: Any, params: dict[str, dict[str, Any]], ctx: z3.Context) -> z3.ExprRef:
    if isinstance(value, dict) and "param" in value:
        return z3.IntVal(params[value["param"]]["value"], ctx)
    if isinstance(value, bool):  # kiểm bool trước vì bool là lớp con của int
        return z3.BoolVal(value, ctx)
    if isinstance(value, int):
        return z3.IntVal(value, ctx)
    raise ValueError(f"Giá trị không hỗ trợ trong spike: {value!r}")


def enc(c: dict[str, Any], v: dict[str, z3.ExprRef], params: dict[str, dict[str, Any]], ctx: z3.Context) -> z3.BoolRef:
    if "all" in c:
        return z3.And([enc(x, v, params, ctx) for x in c["all"]])
    if "any" in c:
        return z3.Or([enc(x, v, params, ctx) for x in c["any"]])
    if "not" in c:
        return z3.Not(enc(c["not"], v, params, ctx))
    if "const" in c:
        return z3.BoolVal(c["const"], ctx)
    x, op = v[c["field"]], c["op"]
    if op == "between":
        a, b = (_resolve(val, params, ctx) for val in c["value"])
        return z3.And(x >= a, x <= b)
    y = _resolve(c["value"], params, ctx)
    if op == "==":
        return x == y
    if op == "!=":
        return x != y
    if op == ">":
        return x > y
    if op == ">=":
        return x >= y
    if op == "<":
        return x < y
    if op == "<=":
        return x <= y
    raise ValueError(f"Toán tử chưa hỗ trợ trong spike: {op}")


def auth_outcome(
    rules: list[dict[str, Any]], v: dict[str, z3.ExprRef], params: dict[str, dict[str, Any]], ctx: z3.Context
) -> z3.ArithRef:
    """auth(t) theo lattice docs/02 mục 3: max các auth khớp, trừ khi có luật miễn trừ khớp."""
    auth: z3.ArithRef = z3.IntVal(AUTH["NONE"], ctx)
    exempt: z3.BoolRef = z3.BoolVal(False, ctx)
    for r in rules:
        if r["status"] not in ("ACTIVE", "CANDIDATE"):
            continue
        w = enc(r["when"], v, params, ctx)
        then = r["then"]
        if "auth" in then:
            a = AUTH[then["auth"]]
            auth = z3.If(z3.And(w, auth < a), z3.IntVal(a, ctx), auth)
        if then.get("exempt_auth"):
            exempt = z3.Or(exempt, w)
    return z3.If(exempt, z3.IntVal(AUTH["NONE"], ctx), auth)


def solver_status(result: z3.CheckSatResult) -> str:
    """sat → có phản ví dụ; unsat → invariant đúng; còn lại (unknown/timeout) → UNKNOWN, không bao giờ PASS."""
    if result == z3.sat:
        return "VIOLATED"
    if result == z3.unsat:
        return "HOLDS"
    return "UNKNOWN"


def _to_py(val: z3.ExprRef) -> int | bool:
    if z3.is_true(val):
        return True
    if z3.is_false(val):
        return False
    return val.as_long()


def check_auth_invariant(
    rules: list[dict[str, Any]],
    inv: dict[str, Any],
    params: dict[str, dict[str, Any]] = PARAMS,
    timeout_ms: int = TIMEOUT_MS,
) -> dict[str, Any]:
    """VC-04 cho AUTH_AT_LEAST: sat?(domain ∧ inv.when ∧ auth(t) < level), tối thiểu hóa để ra phản ví dụ sát mốc."""
    ctx = z3.Context()
    v = make_vars(ctx)
    auth = auth_outcome(rules, v, params, ctx)

    opt = z3.Optimize(ctx=ctx)
    opt.set("timeout", timeout_ms)
    opt.add(domain(v), enc(inv["when"], v, params, ctx), auth < AUTH[inv["level"]])
    for name in MINIMIZE_ORDER.get(inv["id"], []):
        opt.minimize(v[name])

    status = solver_status(opt.check())
    check: dict[str, Any] = {"code": "VC-04", "invariant": inv["id"], "status": status}

    if status == "HOLDS":
        check["message_vi"] = f"Mọi giao dịch thuộc phạm vi {inv['id']} đều phải xác thực {inv['level']}."
    elif status == "UNKNOWN":
        check["message_vi"] = f"Không kết luận được trong {timeout_ms} ms; không coi là đạt."
    else:
        m = opt.model()
        cx = {name: _to_py(m.eval(v[name], model_completion=True)) for name in FIELDS}
        blamed = [
            r["id"]
            for r in rules
            if r["then"].get("exempt_auth") and z3.is_true(m.eval(enc(r["when"], v, params, ctx), model_completion=True))
        ]
        check["counterexample"] = cx
        check["outcome"] = {"auth": AUTH_NAME[m.eval(auth, model_completion=True).as_long()]}
        check["blamed_rules"] = blamed
        check["message_vi"] = (
            f"Có giao dịch thuộc phạm vi {inv['id']} đi qua mà không cần xác thực {inv['level']}"
            + (f" do luật miễn trừ {', '.join(blamed)}." if blamed else ": thiếu luật hiện thực invariant.")
        )
    return check


def verify_rules(rules: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [check_auth_invariant(rules, inv) for inv in INVARIANTS]
    statuses = {c["status"] for c in checks}
    if "VIOLATED" in statuses:
        verdict = "FAIL"
    elif "UNKNOWN" in statuses:
        verdict = "UNKNOWN"
    else:
        verdict = "PASS"
    return {"verdict": verdict, "rule_ids": [r["id"] for r in rules], "checks": checks}


def run_spike() -> dict[str, Any]:
    started = time.perf_counter_ns()
    scenarios = {name: verify_rules(rules) for name, rules in SCENARIOS.items()}
    ms = (time.perf_counter_ns() - started) // 1_000_000
    return {
        "params": {name: p["value"] for name, p in PARAMS.items()},
        "scenarios": scenarios,
        "ms": ms,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_spike(), ensure_ascii=False, indent=2))
