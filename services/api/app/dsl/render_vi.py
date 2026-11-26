"""Hiển thị luật thành câu tiếng Việt, tất định, duyệt AST (docs/02 mục 7). Không dùng LLM."""

from __future__ import annotations

from typing import Any

from app.dsl.catalog import CATALOG, Field

PARAM_LABELS_VI = {
    "biometric_per_tx_threshold": "ngưỡng sinh trắc học/lần",
    "biometric_daily_threshold": "ngưỡng sinh trắc học/ngày",
    "small_merchant_payment_max": "mức thanh toán merchant nhỏ",
    "hold_min_seconds": "thời gian giữ tối thiểu",
    "hold_max_seconds": "thời gian giữ tối đa",
}

_OP_VI = {">": "lớn hơn", ">=": "từ", "<": "nhỏ hơn", "<=": "không quá", "==": "bằng", "!=": "khác"}

DECISION_VI = {
    "ALLOW": "cho qua",
    "MONITOR": "cho qua và gắn cờ giám sát",
    "HOLD": "giữ {s} giây để xác minh",
    "BLOCK": "chặn và chuyển người duyệt",
}
AUTH_VI = {"NONE": "không yêu cầu xác thực thêm", "OTP": "yêu cầu OTP", "BIOMETRIC": "yêu cầu sinh trắc học"}
EXEMPT_VI = "miễn xác thực bổ sung"


def format_vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " đ"


def _format_int(f: Field, n: int) -> str:
    if f.unit == "VND":
        return format_vnd(n)
    num = f"{n:,}".replace(",", ".")
    if f.unit == "giờ":
        return f"{n}h"
    if f.unit == "%":
        return f"{num}%"
    return f"{num} {f.unit}".strip()


def _value(f: Field, v: Any, pack: dict[str, Any] | None) -> str:
    if isinstance(v, dict) and "param" in v:
        name = v["param"]
        label = PARAM_LABELS_VI.get(name, name)
        p = (pack or {}).get("params", {}).get(name)
        return f"{label} (hiện {_format_int(f, p['value'])})" if p else label
    if f.type == "enum":
        return f.value_labels_vi.get(v, str(v))
    return _format_int(f, v)


def _leaf(c: dict[str, Any], pack: dict[str, Any] | None) -> str:
    f = CATALOG[c["field"]]
    op, v = c["op"], c["value"]
    if f.type == "bool":
        truthy = (v is True) == (op == "==")
        return f.label_vi if truthy else (f.label_false_vi or f"không phải {f.label_vi}")
    if op == "between":
        return f"{f.label_vi} từ {_value(f, v[0], pack)} đến {_value(f, v[1], pack)}"
    if op in ("in", "not_in"):
        items = " hoặc ".join(_value(f, x, pack) for x in v)
        return f"{f.label_vi} {'là' if op == 'in' else 'không phải'} {items}"
    if f.type == "enum":
        return f"{f.label_vi} {'là' if op == '==' else 'không phải'} {_value(f, v, pack)}"
    if op == ">=":
        return f"{f.label_vi} từ {_value(f, v, pack)} trở lên"
    return f"{f.label_vi} {_OP_VI[op]} {_value(f, v, pack)}"


def render_condition(c: dict[str, Any], pack: dict[str, Any] | None = None, nested: bool = False) -> str:
    if "all" in c or "any" in c:
        key, joiner = ("all", " VÀ ") if "all" in c else ("any", " HOẶC ")
        parts = [render_condition(x, pack, nested=True) for x in c[key]]
        text = joiner.join(parts)
        return f"({text})" if nested and len(parts) > 1 else text
    if "not" in c:
        return f"KHÔNG ({render_condition(c['not'], pack)})"
    if "const" in c:
        return "luôn đúng" if c["const"] else "luôn sai"
    return _leaf(c, pack)


def render_action(then: dict[str, Any]) -> str:
    parts = []
    d = then.get("decision")
    if d:
        parts.append(DECISION_VI[d].format(s=then.get("hold_seconds", "")))
    if then.get("auth"):
        parts.append(AUTH_VI[then["auth"]])
    if then.get("exempt_auth"):
        parts.append(EXEMPT_VI)
    return " · ".join(parts) if parts else "không làm gì"


def render_rule(rule: dict[str, Any], pack: dict[str, Any] | None = None) -> dict[str, Any]:
    """Câu hiển thị + cờ để UI tô đỏ phần miễn trừ."""
    when = render_condition(rule["when"], pack)
    then = render_action(rule["then"])
    return {
        "when_vi": when,
        "then_vi": then,
        "sentence_vi": f"NẾU {when} THÌ {then}",
        "has_exemption": bool(rule["then"].get("exempt_auth")),
    }
