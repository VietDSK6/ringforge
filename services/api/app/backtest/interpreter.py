"""Interpreter pandas/numpy cho Policy DSL (docs/04 mục 5, ngữ nghĩa lattice docs/02 mục 3).

Phải cho cùng decision/auth với encoder Z3 (app/verify/encoder.py) trên mọi giao dịch — property test T1.5.
Sửa một bên thì sửa bên kia (CLAUDE.md quy tắc 3). Chỉ duyệt AST, không eval.
"""

from __future__ import annotations

import operator
from typing import Any

import numpy as np
import pandas as pd

from app.dsl.catalog import AUTH, DEC, DOMAIN_CONSTRAINTS

ACTIVE_STATUSES = ("ACTIVE", "CANDIDATE")

_CMP = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne}


def _resolve(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, dict) and "param" in value:
        return params[value["param"]]["value"]
    return value


def condition_mask(c: dict[str, Any], df: pd.DataFrame, params: dict[str, Any]) -> np.ndarray:
    n = len(df)
    if "all" in c:
        return np.logical_and.reduce([condition_mask(x, df, params) for x in c["all"]] + [np.ones(n, dtype=bool)])
    if "any" in c:
        return np.logical_or.reduce([condition_mask(x, df, params) for x in c["any"]] + [np.zeros(n, dtype=bool)])
    if "not" in c:
        return ~condition_mask(c["not"], df, params)
    if "const" in c:
        return np.full(n, bool(c["const"]))
    col = df[c["field"]].to_numpy()
    op, value = c["op"], c["value"]
    if op == "between":
        lo, hi = (_resolve(v, params) for v in value)
        return (col >= lo) & (col <= hi)
    if op in ("in", "not_in"):
        m = np.isin(col, list(value))
        return m if op == "in" else ~m
    return np.asarray(_CMP[op](col, _resolve(value, params)), dtype=bool)


def domain_mask(df: pd.DataFrame) -> np.ndarray:
    """Dòng nào thỏa mọi ràng buộc miền phụ thuộc (docs/02 mục 1). Miền từng trường kiểm riêng."""
    m = np.ones(len(df), dtype=bool)
    for c in DOMAIN_CONSTRAINTS:
        if c[0] == "ge":
            m &= df[c[1]].to_numpy() >= df[c[2]].to_numpy()
        else:
            m &= ~condition_mask(c[1], df, {}) | condition_mask(c[2], df, {})
    return m


def interpret(
    rules: list[dict[str, Any]],
    df: pd.DataFrame,
    params: dict[str, Any],
    with_matched: bool = True,
) -> pd.DataFrame:
    """decision/auth theo lattice lấy max; miễn trừ đưa auth về NONE; hold_seconds = max các luật HOLD khớp."""
    n = len(df)
    dec = np.zeros(n, dtype=np.int8)
    auth = np.zeros(n, dtype=np.int8)
    hold = np.zeros(n, dtype=np.int16)
    exempt = np.zeros(n, dtype=bool)
    ids: list[str] = []
    masks: list[np.ndarray] = []

    for r in rules:
        if r["status"] not in ACTIVE_STATUSES:
            continue
        m = condition_mask(r["when"], df, params)
        t = r["then"]
        if "decision" in t:
            dec = np.where(m, np.maximum(dec, DEC[t["decision"]]), dec).astype(np.int8)
            if t["decision"] == "HOLD":
                hold = np.where(m, np.maximum(hold, t["hold_seconds"]), hold).astype(np.int16)
        if "auth" in t:
            auth = np.where(m, np.maximum(auth, AUTH[t["auth"]]), auth).astype(np.int8)
        if t.get("exempt_auth"):
            exempt |= m
        ids.append(r["id"])
        masks.append(m)

    auth = np.where(exempt, AUTH["NONE"], auth).astype(np.int8)
    hold = np.where(dec == DEC["HOLD"], hold, 0).astype(np.int16)
    out = pd.DataFrame({"decision": dec, "auth": auth, "hold_seconds": hold, "exempt": exempt}, index=df.index)
    if with_matched:
        if masks:
            mat = np.column_stack(masks)
            out["matched"] = [[ids[j] for j in np.flatnonzero(row)] for row in mat]
        else:
            out["matched"] = [[] for _ in range(n)]
    return out
