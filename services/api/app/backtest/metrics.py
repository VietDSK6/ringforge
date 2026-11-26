"""Backtest tài chính (docs/04 mục 6) — toàn bộ là số nguyên: tiền VNĐ int, tỷ lệ basis points (10.000 = 100%).

Làm tròn: floor trên TỔNG từng nhóm, không theo từng giao dịch. Chỉ dùng dữ liệu ngày 1–6 (ngày 7 dành cho shadow).
Chỉ APP_VICTIM và ATO mang tổn thất; MULE_LAYER báo riêng là "dòng tiền mule bị chặn".
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.backtest.interpreter import condition_mask, interpret
from app.dsl.catalog import AUTH, DEC

BACKTEST_DAYS = (1, 2, 3, 4, 5, 6)
LOSS_LABELS = ("APP_VICTIM", "ATO")
SCENARIO_VI = {
    "S0_NORMAL": "Giao dịch bình thường",
    "S1_MULE": "Mạng mule",
    "S2_ATO": "Chiếm tài khoản",
    "S3_FLASH_SALE": "Flash-sale hợp lệ",
    "S4_FAMILIAR_HIGH": "Khách thân thiết chuyển lớn",
}


class Assumptions(BaseModel):
    """Giả định có thanh trượt [GL — không phải số thật], docs/04 mục 6."""

    model_config = ConfigDict(extra="forbid")
    hold_stop_bp: StrictInt = Field(5_000, ge=0, le=10_000, description="Xác suất giao dịch gian lận bị HOLD được nạn nhân hủy")
    monitor_stop_bp: StrictInt = Field(0, ge=0, le=10_000, description="MONITOR mặc định không ngăn tiền")
    c_review_block: StrictInt = Field(30_000, ge=0, le=10_000_000, description="Chi phí duyệt mỗi giao dịch hợp lệ bị BLOCK (đ)")
    c_review_hold: StrictInt = Field(0, ge=0, le=10_000_000, description="Chi phí duyệt mỗi giao dịch hợp lệ bị HOLD (đ)")
    churn_hold_bp: StrictInt = Field(500, ge=0, le=10_000, description="Tỷ lệ khách thật bỏ giao dịch khi bị HOLD")
    churn_block_bp: StrictInt = Field(3_000, ge=0, le=10_000, description="Tỷ lệ khách thật bỏ giao dịch khi bị BLOCK")
    margin_bp: StrictInt = Field(50, ge=0, le=10_000, description="Lợi nhuận mất trên mỗi đồng giao dịch bị bỏ")


def _sum(amounts: pd.Series, mask: np.ndarray) -> int:
    return int(amounts[mask].sum())


def _count(mask: np.ndarray) -> int:
    return int(np.count_nonzero(mask))


def _bp(num: int, den: int) -> int | None:
    return num * 10_000 // den if den else None


def _money_block(amount: pd.Series, label: pd.Series, dec: np.ndarray, a: Assumptions) -> dict[str, int | None]:
    """Các thành phần L_net cho một tập giao dịch (toàn bộ hoặc một kịch bản)."""
    loss = label.isin(LOSS_LABELS).to_numpy()
    legit = (label == "LEGIT").to_numpy()
    mule = (label == "MULE_LAYER").to_numpy()
    block, hold, monitor = dec == DEC["BLOCK"], dec == DEC["HOLD"], dec == DEC["MONITOR"]

    loss_total = _sum(amount, loss)
    prevented = (
        _sum(amount, loss & block)
        + _sum(amount, loss & hold) * a.hold_stop_bp // 10_000
        + _sum(amount, loss & monitor) * a.monitor_stop_bp // 10_000
    )
    fn_loss = loss_total - prevented
    fp_hold, fp_block = _count(legit & hold), _count(legit & block)
    review_cost = fp_block * a.c_review_block + fp_hold * a.c_review_hold
    churn_loss = (
        _sum(amount, legit & hold) * a.churn_hold_bp * a.margin_bp // 100_000_000
        + _sum(amount, legit & block) * a.churn_block_bp * a.margin_bp // 100_000_000
    )
    stopped = hold | block
    return {
        "l_net": fn_loss + review_cost + churn_loss,
        "fn_loss": fn_loss,
        "review_cost": review_cost,
        "churn_loss": churn_loss,
        "loss_total": loss_total,
        "prevented": prevented,
        "loss_count": _count(loss),
        "loss_stopped_count": _count(loss & stopped),
        "recall_amount_bp": _bp(prevented, loss_total),
        "recall_count_bp": _bp(_count(loss & stopped), _count(loss)),
        "legit_count": _count(legit),
        "fp_hold": fp_hold,
        "fp_block": fp_block,
        "fp_rate_bp": _bp(fp_hold + fp_block, _count(legit)),
        "mule_flow_stopped": _sum(amount, mule & stopped),
        "mule_flow_total": _sum(amount, mule),
    }


def compute_metrics(
    df: pd.DataFrame, out: pd.DataFrame, pack: dict[str, Any], assumptions: Assumptions
) -> dict[str, Any]:
    """df: giao dịch (đã lọc ngày); out: kết quả interpret cùng index."""
    dec = out["decision"].to_numpy()
    auth = out["auth"].to_numpy()
    legit = (df["label"] == "LEGIT").to_numpy()
    summary = _money_block(df["amount"], df["label"], dec, assumptions)

    exposure = []
    for inv in pack["invariants"]:
        scope = condition_mask(inv["when"], df, pack["params"])
        bad = scope & (auth < AUTH[inv["level"]] if inv["type"] == "AUTH_AT_LEAST" else dec > DEC[inv["level"]])
        exposure.append({"invariant": inv["id"], "count": _count(bad), "amount_sum": _sum(df["amount"], bad)})

    by_scenario = {}
    for sc in sorted(df["scenario"].unique()):
        m = (df["scenario"] == sc).to_numpy()
        block = _money_block(df["amount"][m], df["label"][m], dec[m], assumptions)
        by_scenario[sc] = {"label_vi": SCENARIO_VI.get(sc, sc), "count": _count(m), **block}

    return {
        **summary,
        "friction_biometric": _count(legit & (auth == AUTH["BIOMETRIC"])),
        "friction_otp": _count(legit & (auth == AUTH["OTP"])),
        "compliance_exposure": exposure,
        "valid": all(e["count"] == 0 for e in exposure),
        "by_scenario": by_scenario,
        "n_tx": len(df),
    }


def run_backtest(
    rules: list[dict[str, Any]],
    df: pd.DataFrame,
    pack: dict[str, Any],
    assumptions: Assumptions | None = None,
    days: tuple[int, ...] = BACKTEST_DAYS,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    a = assumptions or Assumptions()
    part = df[df["day"].isin(days)]
    out = interpret(rules, part, pack["params"], with_matched=False)
    result = compute_metrics(part, out, pack, a)
    result["days"] = list(days)
    result["assumptions"] = a.model_dump()
    result["ms"] = (time.perf_counter_ns() - started) // 1_000_000
    return result


DELTA_KEYS = ("l_net", "fn_loss", "review_cost", "churn_loss", "prevented", "fp_hold", "fp_block",
              "friction_biometric", "mule_flow_stopped")


def delta(result: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    """Chênh lệch so với bộ luật đang chạy (âm = giảm)."""
    return {k: result[k] - baseline[k] for k in DELTA_KEYS}
