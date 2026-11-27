"""Grounding (docs/03 mục 4): từ phản ví dụ (một điểm) về dữ liệu — vùng vi phạm lớn cỡ nào trong dữ liệu tổng hợp.

Vùng vi phạm = giao dịch thuộc phạm vi invariant mà bộ luật cho kết quả vi phạm (auth < mức / decision > mức).
Với vi phạm AUTH do luật miễn trừ, đây đúng là `inv.when ∧ (OR when của luật miễn trừ bị quy lỗi)` như đặc tả.
Mọi con số do code tính (interpreter pandas), không bao giờ do LLM. Dùng ngày 1–6 như backtest.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.backtest.interpreter import condition_mask, interpret
from app.backtest.metrics import BACKTEST_DAYS, SCENARIO_VI
from app.dsl.catalog import AUTH, DEC
from app.dsl.render_vi import format_vnd

LEVEL_VI = {"OTP": "xác thực OTP", "BIOMETRIC": "xác thực sinh trắc học"}


def region_condition(inv: dict[str, Any], blamed: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Vùng vi phạm dạng Condition DSL (đặc tả 03 mục 4) khi vi phạm AUTH do luật miễn trừ."""
    if inv["type"] != "AUTH_AT_LEAST" or not blamed:
        return None
    exempt = [r["when"] for r in blamed]
    return {"all": [inv["when"], exempt[0] if len(exempt) == 1 else {"any": exempt}]}


def violation_mask(inv: dict[str, Any], df: pd.DataFrame, out: pd.DataFrame, params: dict[str, Any]) -> np.ndarray:
    scope = condition_mask(inv["when"], df, params)
    if inv["type"] == "AUTH_AT_LEAST":
        return scope & (out["auth"].to_numpy() < AUTH[inv["level"]])
    return scope & (out["decision"].to_numpy() > DEC[inv["level"]])


def _summary(df: pd.DataFrame, mask: np.ndarray) -> dict[str, Any]:
    part = df[mask]
    by_scenario = {
        sc: {"label_vi": SCENARIO_VI.get(sc, sc), "count": int(len(g)), "amount_sum": int(g["amount"].sum())}
        for sc, g in part.groupby("scenario", sort=True)
    }
    by_label = {lb: int(n) for lb, n in part["label"].value_counts().sort_index().items()}
    return {"tx_count": int(len(part)), "amount_sum": int(part["amount"].sum()), "by_scenario": by_scenario, "by_label": by_label}


def note_vi(inv: dict[str, Any], tx_count: int, amount_sum: int, n_days: int) -> str:
    if tx_count == 0:
        return (
            "Dữ liệu quá khứ không có giao dịch nào trong vùng này: backtest sẽ KHÔNG phát hiện lỗi này, "
            "chỉ kiểm chứng hình thức bắt được."
        )
    what = (
        f"lẽ ra phải {LEVEL_VI.get(inv['level'], inv['level'])} nhưng sẽ không bị yêu cầu"
        if inv["type"] == "AUTH_AT_LEAST"
        else "bị giữ/chặn vượt mức cho phép"
    )
    return f"Trong {n_days} ngày dữ liệu tổng hợp: {tx_count:,} giao dịch · {format_vnd(amount_sum)} {what}.".replace(",", ".")


def ground_findings(
    findings: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    pack: dict[str, Any],
    df: pd.DataFrame,
    days: tuple[int, ...] = BACKTEST_DAYS,
) -> None:
    """Gắn `grounding` vào từng phát hiện VC-04 (sửa tại chỗ)."""
    vc04 = [f for f in findings if f.get("code") == "VC-04" and f.get("status") == "VIOLATED"]
    if not vc04:
        return
    part = df[df["day"].isin(days)]
    out = interpret(rules, part, pack["params"], with_matched=False)
    invs = {inv["id"]: inv for inv in pack["invariants"]}
    by_id = {r["id"]: r for r in rules}
    for f in vc04:
        inv = invs[f["invariant"]]
        g = _summary(part, violation_mask(inv, part, out, pack["params"]))
        g["days"] = list(days)
        g["note_vi"] = note_vi(inv, g["tx_count"], g["amount_sum"], len(days))
        region = region_condition(inv, [by_id[b] for b in f.get("blamed_rules", []) if b in by_id])
        if region is not None:
            g["region"] = region
        f["grounding"] = g
