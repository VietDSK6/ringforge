"""VC-01 — kiểm schema & kiểu cho luật và Policy Pack (docs/02 mục 2, docs/03 mục 1).

Hai tầng: Pydantic (cấu trúc, kiểu, khóa lạ) → kiểm ngữ nghĩa theo catalog và Policy Pack.
Trả về dict chuẩn hóa (dùng cho interpreter/Z3) hoặc danh sách lỗi tiếng Việt. Không bao giờ eval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.dsl.catalog import AUTH_LEVELS, CATALOG, DECISIONS, MAX_DEPTH, MAX_LEAVES, OPS_BY_TYPE
from app.dsl.schema import COND_TAGS, PolicyPack, Rule, to_plain

HOLD_MIN_DEFAULT, HOLD_MAX_DEFAULT = 60, 180


@dataclass(frozen=True)
class Issue:
    message_vi: str
    path: str = ""
    rule_id: str | None = None
    code: str = "VC-01"
    severity: str = "ERROR"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "severity": self.severity, "message_vi": self.message_vi}
        if self.rule_id:
            d["rule_id"] = self.rule_id
        if self.path:
            d["path"] = self.path
        return d


# ---------- Lỗi Pydantic → tiếng Việt ----------

_PYD_MSG = {
    "missing": "thiếu khóa bắt buộc",
    "extra_forbidden": "khóa không được phép",
    "int_type": "phải là số nguyên",
    "int_parsing": "phải là số nguyên",
    "bool_type": "phải là true/false",
    "string_type": "phải là chuỗi",
    "too_short": "không được rỗng",
    "too_long": "quá dài",
    "string_too_short": "không được rỗng",
    "string_too_long": "quá dài",
    "string_pattern_mismatch": "sai định dạng (ví dụ hợp lệ: FR-01, DRAFT-0001)",
    "greater_than_equal": "giá trị quá nhỏ",
    "union_tag_not_found": "điều kiện không hợp lệ",
    "union_tag_invalid": "điều kiện không hợp lệ",
    "model_type": "phải là object JSON",
    "dict_type": "phải là object JSON",
    "list_type": "phải là danh sách",
}


def _clean_loc(loc: tuple[Any, ...]) -> str:
    parts: list[str] = []
    for p in loc:
        if isinstance(p, int):
            parts.append(f"[{p}]")
            continue
        if p in COND_TAGS or p in ("bool", "int", "str", "ParamRef") or "[" in str(p):
            continue  # tag của union / nhánh union, không phải khóa JSON
        parts.append(("." if parts else "") + str(p))
    return "".join(parts)


def _pydantic_issues(err: ValidationError, rule_id: str | None, prefix: str = "") -> list[Issue]:
    by_path: dict[str, list[dict[str, Any]]] = {}
    for e in err.errors():
        path = _clean_loc(e["loc"])
        by_path.setdefault(path, []).append(e)
    issues = []
    for path, errs in by_path.items():
        full = f"{prefix}{path}" if prefix else path
        if len(errs) > 1 and path.endswith("value"):
            msg = "kiểu giá trị không hợp lệ: dùng số nguyên, true/false, giá trị enum hoặc {\"param\": tên}; không dùng số thực"
        else:
            e = errs[0]
            if e["type"] == "literal_error":
                msg = f"giá trị không hợp lệ, cho phép: {e.get('ctx', {}).get('expected', '')}"
            else:
                msg = _PYD_MSG.get(e["type"], e["msg"])
        issues.append(Issue(f"Sai cấu trúc tại '{full or '(gốc)'}': {msg}.", full, rule_id))
    return issues


# ---------- Kiểm ngữ nghĩa điều kiện ----------


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class _CondChecker:
    def __init__(self, params: dict[str, Any], rule_id: str | None, issues: list[Issue]):
        self.params = params
        self.rule_id = rule_id
        self.issues = issues
        self.leaves = 0
        self.max_depth = 0

    def err(self, path: str, msg: str) -> None:
        self.issues.append(Issue(msg, path, self.rule_id))

    def resolve_int(self, v: Any, path: str, label: str) -> int | None:
        if isinstance(v, dict):
            name = v.get("param")
            p = self.params.get(name)
            if p is None:
                self.err(path, f"Tham số không tồn tại trong Policy Pack: '{name}'.")
                return None
            return p["value"]
        if _is_int(v):
            return v
        if isinstance(v, str):
            self.err(path, f"Giá trị của '{label}' phải là số nguyên hoặc tham số Policy Pack, không dùng chuỗi như '{v}'.")
        else:
            self.err(path, f"Giá trị của '{label}' phải là số nguyên hoặc tham số Policy Pack.")
        return None

    def check(self, c: dict[str, Any], path: str, depth: int) -> None:
        self.max_depth = max(self.max_depth, depth)
        if "all" in c or "any" in c:
            key = "all" if "all" in c else "any"
            for i, sub in enumerate(c[key]):
                self.check(sub, f"{path}.{key}[{i}]", depth + 1)
            return
        if "not" in c:
            self.check(c["not"], f"{path}.not", depth + 1)
            return
        if "const" in c:
            self.leaves += 1
            return
        self.leaves += 1
        self.leaf(c, path)

    def leaf(self, c: dict[str, Any], path: str) -> None:
        name, op, value = c["field"], c["op"], c["value"]
        f = CATALOG.get(name)
        if f is None:
            self.err(f"{path}.field", f"Trường không có trong danh mục: '{name}'.")
            return
        if not f.available_at_decision:
            self.err(f"{path}.field", f"Trường '{f.label_vi}' không có sẵn lúc ra quyết định.")
            return
        if op not in OPS_BY_TYPE[f.type]:
            allowed = ", ".join(OPS_BY_TYPE[f.type])
            self.err(f"{path}.op", f"Toán tử '{op}' không dùng được với '{f.label_vi}' (cho phép: {allowed}).")
            return
        vpath = f"{path}.value"
        if op == "between":
            if not isinstance(value, list) or len(value) != 2:
                self.err(vpath, f"'between' cần đúng 2 giá trị [từ, đến] cho '{f.label_vi}'.")
                return
            a = self.resolve_int(value[0], f"{vpath}[0]", f.label_vi)
            b = self.resolve_int(value[1], f"{vpath}[1]", f.label_vi)
            if a is not None and b is not None and a > b:
                self.err(vpath, f"'between' của '{f.label_vi}' cần giá trị đầu ≤ giá trị cuối ({a} > {b}).")
            return
        if op in ("in", "not_in"):
            if not isinstance(value, list) or not value:
                self.err(vpath, f"'{op}' cần danh sách giá trị không rỗng cho '{f.label_vi}'.")
                return
            for i, v in enumerate(value):
                if not isinstance(v, str) or v not in f.values:
                    self.err(f"{vpath}[{i}]", f"Giá trị '{v}' không hợp lệ cho '{f.label_vi}' (cho phép: {', '.join(f.values)}).")
            return
        if isinstance(value, list):
            self.err(vpath, f"Toán tử '{op}' cần một giá trị, không phải danh sách.")
            return
        if f.type == "int":
            self.resolve_int(value, vpath, f.label_vi)
        elif f.type == "bool":
            if not isinstance(value, bool):
                self.err(vpath, f"'{f.label_vi}' chỉ so sánh với true/false.")
        elif not isinstance(value, str) or value not in f.values:
            self.err(vpath, f"Giá trị '{value}' không hợp lệ cho '{f.label_vi}' (cho phép: {', '.join(f.values)}).")


def check_condition(cond: dict[str, Any], params: dict[str, Any], path: str, rule_id: str | None) -> list[Issue]:
    issues: list[Issue] = []
    ch = _CondChecker(params, rule_id, issues)
    ch.check(cond, path, 1)
    if ch.max_depth > MAX_DEPTH:
        issues.append(Issue(f"Điều kiện lồng quá sâu ({ch.max_depth} > {MAX_DEPTH} tầng).", path, rule_id))
    if ch.leaves > MAX_LEAVES:
        issues.append(Issue(f"Quá nhiều điều kiện lá ({ch.leaves} > {MAX_LEAVES}).", path, rule_id))
    return issues


def _hold_bounds(params: dict[str, Any]) -> tuple[int, int]:
    lo = params.get("hold_min_seconds", {}).get("value", HOLD_MIN_DEFAULT)
    hi = params.get("hold_max_seconds", {}).get("value", HOLD_MAX_DEFAULT)
    return lo, hi


# ---------- API công khai ----------


def check_pack(raw: Any) -> tuple[dict[str, Any] | None, list[Issue]]:
    try:
        pack = to_plain(PolicyPack.model_validate(raw))
    except ValidationError as e:
        return None, _pydantic_issues(e, None, "policy_pack.")
    issues: list[Issue] = []
    seen: set[str] = set()
    for i, inv in enumerate(pack["invariants"]):
        path = f"policy_pack.invariants[{i}]"
        if inv["id"] in seen:
            issues.append(Issue(f"Trùng mã invariant '{inv['id']}'.", path))
        seen.add(inv["id"])
        levels = AUTH_LEVELS if inv["type"] == "AUTH_AT_LEAST" else DECISIONS
        if inv["level"] not in levels:
            issues.append(Issue(f"Mức '{inv['level']}' không hợp lệ cho {inv['type']} (cho phép: {', '.join(levels)}).", f"{path}.level"))
        issues += check_condition(inv["when"], pack["params"], f"{path}.when", None)
    return (None if issues else pack), issues


def check_rule(raw: Any, pack: dict[str, Any], index: int | None = None) -> tuple[dict[str, Any] | None, list[Issue]]:
    rule_id = raw.get("id") if isinstance(raw, dict) and isinstance(raw.get("id"), str) else None
    prefix = f"rules[{index}]." if index is not None else ""
    try:
        rule = to_plain(Rule.model_validate(raw))
    except ValidationError as e:
        return None, _pydantic_issues(e, rule_id, prefix)
    params = pack["params"]
    issues = check_condition(rule["when"], params, f"{prefix}when", rule_id)
    then = rule["then"]
    lo, hi = _hold_bounds(params)
    hold = then.get("hold_seconds")
    if then.get("decision") == "HOLD" and hold is None:
        issues.append(Issue(f"Quyết định HOLD cần 'hold_seconds' ({lo}–{hi} giây).", f"{prefix}then.hold_seconds", rule_id))
    if hold is not None and not lo <= hold <= hi:
        issues.append(Issue(f"'hold_seconds' phải trong khoảng {lo}–{hi} giây (đang là {hold}).", f"{prefix}then.hold_seconds", rule_id))
    return (None if issues else rule), issues


def check_rules(raws: list[Any], pack: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Issue]]:
    """Kiểm cả bộ luật. Chỉ trả danh sách luật khi không có lỗi nào."""
    rules: list[dict[str, Any]] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for i, raw in enumerate(raws):
        rule, errs = check_rule(raw, pack, i)
        issues += errs
        if rule is not None:
            if rule["id"] in seen:
                issues.append(Issue(f"Trùng mã luật '{rule['id']}' trong bộ luật.", f"rules[{i}].id", rule["id"]))
            seen.add(rule["id"])
            rules.append(rule)
    return (rules if not issues else []), issues
