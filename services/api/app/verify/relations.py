"""Quan hệ logic giữa hai điều kiện, kiểm bằng Z3 trong miền (docs/08 semantic_equiv, docs/05 scope_ok)."""

from __future__ import annotations

from typing import Any

import z3

from app.verify.checks import TIMEOUT_MS, solver_status
from app.verify.encoder import domain, enc, make_vars


def _unsat(build, params: dict[str, Any], timeout_ms: int) -> str:
    ctx = z3.Context()
    v = make_vars(ctx)
    s = z3.Solver(ctx=ctx)
    s.set("timeout", timeout_ms)
    s.add(domain(v, ctx), build(v, ctx))
    return {"unsat": "YES", "sat": "NO"}.get(solver_status(s.check()), "UNKNOWN")


def implies(a: dict[str, Any], b: dict[str, Any], params: dict[str, Any], timeout_ms: int = TIMEOUT_MS) -> str:
    """a ⇒ b trên mọi giao dịch trong miền? "YES" | "NO" | "UNKNOWN"."""
    return _unsat(lambda v, ctx: z3.And(enc(a, v, params, ctx), z3.Not(enc(b, v, params, ctx))), params, timeout_ms)


def equivalent(a: dict[str, Any], b: dict[str, Any], params: dict[str, Any], timeout_ms: int = TIMEOUT_MS) -> str:
    """a ⇔ b trên mọi giao dịch trong miền? "YES" | "NO" | "UNKNOWN"."""
    return _unsat(lambda v, ctx: enc(a, v, params, ctx) != enc(b, v, params, ctx), params, timeout_ms)
