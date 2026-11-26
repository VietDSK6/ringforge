"""Mã hóa Policy DSL sang Z3 (docs/03 mục 2) — mô hình một giao dịch với 17 biến của catalog.

Phải cho cùng decision/auth với interpreter (app/backtest/interpreter.py) — property test T1.5.
Sửa một bên thì sửa bên kia (CLAUDE.md quy tắc 3). Mỗi lần kiểm chứng dùng z3.Context riêng (an toàn đa luồng).
"""

from __future__ import annotations

from typing import Any

import z3

from app.dsl.catalog import AUTH, CATALOG, DEC, DOMAIN_CONSTRAINTS, FIELDS

ACTIVE_STATUSES = ("ACTIVE", "CANDIDATE")
ENUM_INDEX: dict[str, dict[str, int]] = {f.name: {v: i for i, v in enumerate(f.values)} for f in FIELDS if f.type == "enum"}


def make_vars(ctx: z3.Context) -> dict[str, z3.ExprRef]:
    """bool → Bool; int và enum (chỉ số) → Int."""
    return {f.name: z3.Bool(f.name, ctx) if f.type == "bool" else z3.Int(f.name, ctx) for f in FIELDS}


def _resolve(value: Any, params: dict[str, Any], field: str, ctx: z3.Context) -> z3.ExprRef:
    if isinstance(value, dict) and "param" in value:
        return z3.IntVal(params[value["param"]]["value"], ctx)
    if CATALOG[field].type == "enum":
        return z3.IntVal(ENUM_INDEX[field][value], ctx)
    if isinstance(value, bool):
        return z3.BoolVal(value, ctx)
    return z3.IntVal(value, ctx)


def enc(c: dict[str, Any], v: dict[str, z3.ExprRef], params: dict[str, Any], ctx: z3.Context) -> z3.BoolRef:
    if "all" in c:
        return z3.And([enc(x, v, params, ctx) for x in c["all"]] + [z3.BoolVal(True, ctx)])
    if "any" in c:
        return z3.Or([enc(x, v, params, ctx) for x in c["any"]] + [z3.BoolVal(False, ctx)])
    if "not" in c:
        return z3.Not(enc(c["not"], v, params, ctx))
    if "const" in c:
        return z3.BoolVal(bool(c["const"]), ctx)
    name, op, value = c["field"], c["op"], c["value"]
    x = v[name]
    if op == "between":
        lo, hi = (_resolve(val, params, name, ctx) for val in value)
        return z3.And(x >= lo, x <= hi)
    if op in ("in", "not_in"):
        e = z3.Or([x == _resolve(val, params, name, ctx) for val in value] + [z3.BoolVal(False, ctx)])
        return e if op == "in" else z3.Not(e)
    y = _resolve(value, params, name, ctx)
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
    raise ValueError(f"Toán tử không hỗ trợ: {op}")


def domain(v: dict[str, z3.ExprRef], ctx: z3.Context) -> z3.BoolRef:
    """Miền từng trường + ràng buộc phụ thuộc (docs/02 mục 1) — cùng nguồn DOMAIN_CONSTRAINTS với interpreter."""
    cs: list[z3.BoolRef] = []
    for f in FIELDS:
        if f.type != "bool":
            cs += [v[f.name] >= f.lo, v[f.name] <= f.hi]
    for c in DOMAIN_CONSTRAINTS:
        if c[0] == "ge":
            cs.append(v[c[1]] >= v[c[2]])
        else:
            cs.append(z3.Implies(enc(c[1], v, {}, ctx), enc(c[2], v, {}, ctx)))
    return z3.And(cs)


def outcome(
    rules: list[dict[str, Any]], v: dict[str, z3.ExprRef], params: dict[str, Any], ctx: z3.Context
) -> tuple[z3.ArithRef, z3.ArithRef, z3.BoolRef]:
    """(decision, auth, exempt) theo lattice lấy max; miễn trừ đưa auth về NONE (docs/02 mục 3)."""
    dec: z3.ArithRef = z3.IntVal(DEC["ALLOW"], ctx)
    auth: z3.ArithRef = z3.IntVal(AUTH["NONE"], ctx)
    exempt: z3.BoolRef = z3.BoolVal(False, ctx)
    for r in rules:
        if r["status"] not in ACTIVE_STATUSES:
            continue
        w = enc(r["when"], v, params, ctx)
        t = r["then"]
        if "decision" in t:
            d = DEC[t["decision"]]
            dec = z3.If(z3.And(w, dec < d), z3.IntVal(d, ctx), dec)
        if "auth" in t:
            a = AUTH[t["auth"]]
            auth = z3.If(z3.And(w, auth < a), z3.IntVal(a, ctx), auth)
        if t.get("exempt_auth"):
            exempt = z3.Or(exempt, w)
    return dec, z3.If(exempt, z3.IntVal(AUTH["NONE"], ctx), auth), exempt


def model_to_tx(m: z3.ModelRef, v: dict[str, z3.ExprRef]) -> dict[str, Any]:
    """Model Z3 → giao dịch dạng dict (enum trả về tên, tiền là int)."""
    tx: dict[str, Any] = {}
    for f in FIELDS:
        val = m.eval(v[f.name], model_completion=True)
        if f.type == "bool":
            tx[f.name] = z3.is_true(val)
        elif f.type == "enum":
            tx[f.name] = f.values[val.as_long()]
        else:
            tx[f.name] = val.as_long()
    return tx


def tx_to_substitution(tx: dict[str, Any], v: dict[str, z3.ExprRef], ctx: z3.Context) -> list[tuple[z3.ExprRef, z3.ExprRef]]:
    """Giao dịch cụ thể → cặp (biến, hằng) để z3.substitute (dùng cho property test)."""
    pairs = []
    for f in FIELDS:
        val = tx[f.name]
        if f.type == "bool":
            pairs.append((v[f.name], z3.BoolVal(bool(val), ctx)))
        elif f.type == "enum":
            pairs.append((v[f.name], z3.IntVal(ENUM_INDEX[f.name][val], ctx)))
        else:
            pairs.append((v[f.name], z3.IntVal(int(val), ctx)))
    return pairs
