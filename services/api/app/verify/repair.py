"""Đánh giá và xếp hạng bản sửa (docs/05 mục 4, bước 2–7) — hoàn toàn tất định, áp cho cả bản AI và bản tất định.

Với mỗi ứng viên: kiểm chứng lại toàn bộ bộ luật (thay luật gốc), backtest, độ giữ ý định (coverage_bp),
phạm vi (candidate ⇒ original, bằng Z3). Xếp hạng: qua cổng invariant → scope_ok → coverage cao → L_net thấp → ít lá.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.backtest.interpreter import condition_mask
from app.backtest.metrics import BACKTEST_DAYS, Assumptions, delta, run_backtest
from app.dsl.render_vi import render_condition, render_rule
from app.verify.checks import verify_rules
from app.verify.relations import implies


def replace_rule(base: list[dict[str, Any]], original_id: str, new_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in base:
        if r["id"] == original_id:
            out.extend(new_rules)
        else:
            out.append(r)
    if not any(r["id"] == original_id for r in base):
        out.extend(new_rules)
    return out


def count_leaves(c: dict[str, Any]) -> int:
    if "all" in c or "any" in c:
        return sum(count_leaves(x) for x in c.get("all", c.get("any", [])))
    if "not" in c:
        return count_leaves(c["not"])
    return 1


def _top_parts(c: dict[str, Any]) -> list[dict[str, Any]]:
    return list(c["all"]) if "all" in c else [c]


def condition_diff(original: dict[str, Any], candidate: dict[str, Any], pack: dict[str, Any]) -> dict[str, list[str]]:
    """Diff mức điều kiện con trên cùng (dòng thêm/bớt) để UI hiển thị."""
    a, b = _top_parts(original), _top_parts(candidate)
    return {
        "added_vi": [render_condition(x, pack) for x in b if x not in a],
        "removed_vi": [render_condition(x, pack) for x in a if x not in b],
    }


def coverage_bp(
    original: dict[str, Any], candidates: list[dict[str, Any]], violated_whens: list[dict[str, Any]], df: pd.DataFrame, params: dict[str, Any]
) -> int | None:
    """Tỷ lệ giao dịch luật gốc khớp NGOÀI vùng vi phạm mà bản sửa vẫn khớp (docs/05 mục 4.4)."""
    orig = condition_mask(original["when"], df, params)
    viol = np.zeros(len(df), dtype=bool)
    for w in violated_whens:
        viol |= condition_mask(w, df, params)
    base = orig & ~viol
    cand = np.zeros(len(df), dtype=bool)
    for c in candidates:
        cand |= condition_mask(c["when"], df, params)
    n = int(base.sum())
    return int((base & cand).sum()) * 10_000 // n if n else None


def evaluate(
    cand_rules: list[dict[str, Any]],
    original: dict[str, Any],
    base_rules: list[dict[str, Any]],
    pack: dict[str, Any],
    df: pd.DataFrame,
    violated_invariants: list[str],
    baseline: dict[str, Any],
    assumptions: Assumptions | None = None,
) -> dict[str, Any]:
    rules = replace_rule(base_rules, original["id"], cand_rules)
    report = verify_rules(rules, pack)
    passes = report["verdict"] in ("PASS", "PASS_WITH_WARNINGS")
    whens = [c["when"] for c in cand_rules]
    union = whens[0] if len(whens) == 1 else {"any": whens}
    scope = implies(union, original["when"], pack["params"])
    invs = {i["id"]: i for i in pack["invariants"]}
    part = df[df["day"].isin(BACKTEST_DAYS)]
    cov = coverage_bp(original, cand_rules, [invs[i]["when"] for i in violated_invariants if i in invs], part, pack["params"])
    bt = run_backtest(rules, df, pack, assumptions)
    return {
        "rules": [r | {"render": render_rule(r, pack)} for r in cand_rules],
        "verdict": report["verdict"],
        "passes": passes,
        "remaining_checks": report["checks"],
        "scope_ok": scope == "YES",
        "scope": scope,
        "coverage_bp": cov,
        "l_net": bt["l_net"],
        "valid_backtest": bt["valid"],
        "delta": delta(bt, baseline),
        "leaves": sum(count_leaves(c["when"]) for c in cand_rules),
        "diff": condition_diff(original["when"], cand_rules[0]["when"], pack),
    }


def rank_key(c: dict[str, Any]) -> tuple:
    cov = c["coverage_bp"] if c["coverage_bp"] is not None else -1
    return (not c["passes"], not c["scope_ok"], -cov, c["l_net"], c["leaves"])
