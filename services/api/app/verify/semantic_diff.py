"""VC-07 — semantic diff giữa hai phiên bản bộ luật (docs/03 mục 3, FR-V8). Mức INFO, không ảnh hưởng kết luận.

sat?( domain ∧ (dec_A ≠ dec_B ∨ auth_A ≠ auth_B) ). Lặp: lấy nhân chứng dễ đọc, phân loại kiểu khác
("Cho qua → Giữ lại", "xác thực mặc định → sinh trắc học"), loại trừ kiểu đó rồi tìm tiếp; tối đa 5 nhân chứng.
Hai phiên bản có thể khác bộ luật (change set) hoặc khác tham số Policy Pack (phân tích tác động Demo 2).
Grounding: chạy interpreter cả hai phiên bản trên dữ liệu ngày 1–6, đếm giao dịch đổi kết quả theo từng kiểu.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import z3

from app.backtest.interpreter import interpret
from app.backtest.metrics import BACKTEST_DAYS
from app.dsl.catalog import AUTH, AUTH_LEVELS, DEC, DECISIONS
from app.verify.checks import TIMEOUT_MS, solver_status
from app.verify.encoder import domain, make_vars, model_to_tx, outcome
from app.verify.grounding import summarize
from app.verify.optimize import readable_model

MAX_WITNESSES = 5

DEC_VI = {"ALLOW": "Cho qua", "MONITOR": "Giám sát", "HOLD": "Giữ lại", "BLOCK": "Chặn"}
AUTH_VI = {"NONE": "xác thực mặc định", "OTP": "OTP", "BIOMETRIC": "sinh trắc học"}


def _kind_label(kind: dict[str, Any]) -> str:
    parts = []
    if kind["decision"]:
        a, b = kind["decision"]
        parts.append(f"Quyết định: {DEC_VI[a]} → {DEC_VI[b]}")
    if kind["auth"]:
        a, b = kind["auth"]
        parts.append(f"Xác thực: {AUTH_VI[a]} → {AUTH_VI[b]}")
    return " · ".join(parts)


def _direction(kind: dict[str, Any]) -> str:
    ups = []
    if kind["decision"]:
        ups.append(DEC[kind["decision"][1]] > DEC[kind["decision"][0]])
    if kind["auth"]:
        ups.append(AUTH[kind["auth"][1]] > AUTH[kind["auth"][0]])
    return "stricter" if all(ups) else "looser" if not any(ups) else "mixed"


def _key(kind: dict[str, Any]) -> tuple:
    return (tuple(kind["decision"] or ()), tuple(kind["auth"] or ()))


def semantic_diff(
    rules_a: list[dict[str, Any]],
    params_a: dict[str, Any],
    rules_b: list[dict[str, Any]],
    params_b: dict[str, Any],
    df: pd.DataFrame | None = None,
    max_witnesses: int = MAX_WITNESSES,
    timeout_ms: int = TIMEOUT_MS,
) -> dict[str, Any]:
    """A = phiên bản trước, B = phiên bản sau."""
    ctx = z3.Context()
    v = make_vars(ctx)
    dom = domain(v, ctx)
    dec_a, auth_a, _ = outcome(rules_a, v, params_a, ctx)
    dec_b, auth_b, _ = outcome(rules_b, v, params_b, ctx)
    differ = z3.Or(dec_a != dec_b, auth_a != auth_b)

    diffs: list[dict[str, Any]] = []
    excluded: list[z3.BoolRef] = []
    status = "unsat"
    while len(diffs) < max_witnesses:
        hard = z3.And(dom, differ, *excluded)
        s = z3.Solver(ctx=ctx)
        s.set("timeout", timeout_ms)
        s.add(hard)
        status = solver_status(s.check())
        if status != "sat":
            break
        m = readable_model(ctx, v, hard, timeout_ms) or s.model()
        da, db, aa, ab = (m.eval(x, model_completion=True).as_long() for x in (dec_a, dec_b, auth_a, auth_b))
        kind = {
            "decision": [DECISIONS[da], DECISIONS[db]] if da != db else None,
            "auth": [AUTH_LEVELS[aa], AUTH_LEVELS[ab]] if aa != ab else None,
        }
        dec_part = z3.And(dec_a == da, dec_b == db) if da != db else dec_a == dec_b
        auth_part = z3.And(auth_a == aa, auth_b == ab) if aa != ab else auth_a == auth_b
        excluded.append(z3.Not(z3.And(dec_part, auth_part)))
        diffs.append(kind | {
            "label_vi": _kind_label(kind),
            "direction": _direction(kind),
            "before": {"decision": DECISIONS[da], "auth": AUTH_LEVELS[aa]},
            "after": {"decision": DECISIONS[db], "auth": AUTH_LEVELS[ab]},
            "counterexample": model_to_tx(m, v),
        })
    else:
        status = "sat"  # dừng vì đủ số nhân chứng tối đa → có thể còn kiểu khác chưa liệt kê

    result: dict[str, Any] = {
        "code": "VC-07",
        "severity": "INFO",
        "status": "UNKNOWN" if status == "unknown" else ("DIFFERENT" if diffs else "EQUIVALENT"),
        "complete": status == "unsat",
        "diffs": diffs,
    }
    if df is not None:
        _ground(result, rules_a, params_a, rules_b, params_b, df)
    result["message_vi"] = _message(result)
    return result


def _ground(result: dict[str, Any], rules_a, params_a, rules_b, params_b, df: pd.DataFrame) -> None:
    part = df[df["day"].isin(BACKTEST_DAYS)]
    oa = interpret(rules_a, part, params_a, with_matched=False)
    ob = interpret(rules_b, part, params_b, with_matched=False)
    da, db = oa["decision"].to_numpy(), ob["decision"].to_numpy()
    aa, ab = oa["auth"].to_numpy(), ob["auth"].to_numpy()
    changed = (da != db) | (aa != ab)
    g = summarize(part, changed)
    g["days"] = list(BACKTEST_DAYS)
    result["grounding"] = g
    seen = set()
    for d in result["diffs"]:
        mask = changed.copy()
        mask &= (da == DEC[d["decision"][0]]) & (db == DEC[d["decision"][1]]) if d["decision"] else (da == db)
        mask &= (aa == AUTH[d["auth"][0]]) & (ab == AUTH[d["auth"][1]]) if d["auth"] else (aa == ab)
        d["data"] = summarize(part, mask)
        seen.add(_key(d))
    # Kiểu khác có trong dữ liệu nhưng chưa có nhân chứng (khi dừng ở MAX_WITNESSES).
    other = np.zeros(len(part), dtype=bool)
    for i in np.flatnonzero(changed):
        k = ((DECISIONS[da[i]], DECISIONS[db[i]]) if da[i] != db[i] else (), (AUTH_LEVELS[aa[i]], AUTH_LEVELS[ab[i]]) if aa[i] != ab[i] else ())
        if k not in seen:
            other[i] = True
    g["other_tx_count"] = int(other.sum())


def _message(r: dict[str, Any]) -> str:
    if r["status"] == "EQUIVALENT":
        return "Hai phiên bản cho cùng quyết định và mức xác thực trên MỌI giao dịch trong miền (chứng minh bằng Z3)."
    if r["status"] == "UNKNOWN" and not r["diffs"]:
        return "Không kết luận được hai phiên bản có tương đương hay không trong thời hạn."
    n = len(r["diffs"])
    msg = f"Hai phiên bản cho kết quả khác nhau ở {n}{'' if r['complete'] else '+'} kiểu giao dịch"
    g = r.get("grounding")
    if g is not None:
        days = len(g["days"])
        if g["tx_count"]:
            msg += f"; trong {days} ngày dữ liệu tổng hợp có {g['tx_count']:,} giao dịch đổi kết quả".replace(",", ".")
        else:
            msg += f"; dữ liệu {days} ngày không có giao dịch nào đổi kết quả — chỉ kiểm chứng hình thức thấy khác biệt"
    return msg + "."
