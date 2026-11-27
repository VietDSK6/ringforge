"""Repair tất định (docs/03 mục 5) — baseline D trong ablation và dự phòng khi LLM lỗi.

Với vi phạm do luật r: r'.when = r.when ∧ ¬inv.when (mọi invariant r bị quy lỗi). Phủ định một lá so sánh
được đơn giản hóa thành toán tử ngược, ví dụ ¬(amount > {param}) → amount <= {param}.
"""

from __future__ import annotations

import copy
from typing import Any

NEG_OP = {">": "<=", ">=": "<", "<": ">=", "<=": ">", "==": "!=", "!=": "==", "in": "not_in", "not_in": "in"}


def negate(c: dict[str, Any]) -> dict[str, Any]:
    if "not" in c:
        return copy.deepcopy(c["not"])
    if "const" in c:
        return {"const": not c["const"]}
    if "all" in c:
        return {"any": [negate(x) for x in c["all"]]}
    if "any" in c:
        return {"all": [negate(x) for x in c["any"]]}
    op = c["op"]
    if op in ("==", "!=") and isinstance(c["value"], bool):
        return {"field": c["field"], "op": "==", "value": (not c["value"]) if op == "==" else c["value"]}
    if op in NEG_OP:
        return {"field": c["field"], "op": NEG_OP[op], "value": copy.deepcopy(c["value"])}
    return {"not": copy.deepcopy(c)}  # between


def conjoin(base: dict[str, Any], extras: list[dict[str, Any]]) -> dict[str, Any]:
    parts = list(base["all"]) if "all" in base else [base]
    for e in extras:
        if e not in parts:
            parts.append(e)
    return {"all": copy.deepcopy(parts)}


def deterministic_repair(rule: dict[str, Any], findings: list[dict[str, Any]], pack: dict[str, Any]) -> dict[str, Any] | None:
    """Bản sửa tất định cho luật bị quy lỗi trong các phát hiện VC-04; None nếu luật không bị quy lỗi."""
    invs = {inv["id"]: inv for inv in pack["invariants"]}
    blamed = [f["invariant"] for f in findings if f.get("code") == "VC-04" and rule["id"] in f.get("blamed_rules", [])]
    if not blamed:
        return None
    extras = [negate(invs[i]["when"]) for i in dict.fromkeys(blamed)]
    fixed = copy.deepcopy(rule)
    fixed["when"] = conjoin(rule["when"], extras)
    fixed["version"] = rule.get("version", 1) + 1
    fixed["status"] = "CANDIDATE"
    fixed["provenance"] = {"created_by": "det_repair", "parent": f"{rule['id']}@v{rule.get('version', 1)}"}
    fixed.pop("render", None)
    return fixed
