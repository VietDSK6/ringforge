"""Danh mục trường của Policy DSL (docs/02 mục 1) — nguồn duy nhất cho validator, interpreter, Z3, generator, UI.

Không bao giờ thêm trường nhãn (`label`, `scenario`) vào đây (CLAUDE.md quy tắc 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DSL_VERSION = "rf-dsl/0.1"

FieldType = Literal["int", "bool", "enum"]

DECISIONS: tuple[str, ...] = ("ALLOW", "MONITOR", "HOLD", "BLOCK")
AUTH_LEVELS: tuple[str, ...] = ("NONE", "OTP", "BIOMETRIC")
DEC = {name: i for i, name in enumerate(DECISIONS)}
AUTH = {name: i for i, name in enumerate(AUTH_LEVELS)}

CMP_OPS: tuple[str, ...] = (">", ">=", "<", "<=", "==", "!=")
OPS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "int": CMP_OPS + ("between",),
    "bool": ("==", "!="),
    "enum": ("==", "!=", "in", "not_in"),
}

MAX_DEPTH = 6
MAX_LEAVES = 20


@dataclass(frozen=True)
class Field:
    name: str
    type: FieldType
    label_vi: str
    lo: int = 0
    hi: int = 0
    unit: str = ""  # "VND" | "ngày" | "giờ" | "%" | ""
    values: tuple[str, ...] = ()  # enum
    value_labels_vi: dict[str, str] = field(default_factory=dict)  # enum
    label_false_vi: str = ""  # bool: cách đọc khi == false
    available_at_decision: bool = True  # chống leakage (docs/04 mục 3)

    def __post_init__(self) -> None:
        if self.type == "enum":
            object.__setattr__(self, "lo", 0)
            object.__setattr__(self, "hi", len(self.values) - 1)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "label_vi": self.label_vi,
            "ops": list(OPS_BY_TYPE[self.type]),
            "available_at_decision": self.available_at_decision,
        }
        if self.type == "int":
            d |= {"min": self.lo, "max": self.hi, "unit": self.unit}
        elif self.type == "enum":
            d |= {"values": list(self.values), "value_labels_vi": dict(self.value_labels_vi)}
        else:
            d |= {"label_false_vi": self.label_false_vi}
        return d


CHANNELS = ("P2P", "MERCHANT_QR", "TOPUP", "WITHDRAW", "BILL")
KYC_LEVELS = ("BASIC", "FULL")

FIELDS: tuple[Field, ...] = (
    Field("amount", "int", "số tiền", 1, 500_000_000, "VND"),
    Field(
        "channel",
        "enum",
        "kênh",
        values=CHANNELS,
        value_labels_vi={
            "P2P": "chuyển tiền cá nhân",
            "MERCHANT_QR": "thanh toán QR",
            "TOPUP": "nạp tiền điện thoại",
            "WITHDRAW": "rút tiền",
            "BILL": "thanh toán hóa đơn",
        },
    ),
    Field("hour", "int", "giờ giao dịch", 0, 23, "giờ"),
    Field("daily_total_after", "int", "tổng chi trong ngày (gồm giao dịch này)", 1, 2_000_000_000, "VND"),
    Field("is_new_device", "bool", "dùng thiết bị mới (trong 7 ngày)", label_false_vi="không dùng thiết bị mới"),
    Field("sender_account_age_days", "int", "tuổi tài khoản gửi", 0, 3650, "ngày"),
    Field("sender_dormant_days", "int", "số ngày tài khoản gửi không hoạt động", 0, 3650, "ngày"),
    Field(
        "sender_kyc_level",
        "enum",
        "mức định danh người gửi",
        values=KYC_LEVELS,
        value_labels_vi={"BASIC": "định danh cơ bản", "FULL": "định danh đầy đủ"},
    ),
    Field("sender_inbound_amount_60m", "int", "tiền nhận vào trong 60 phút trước", 0, 2_000_000_000, "VND"),
    Field("sender_distinct_inbound_60m", "int", "số người khác nhau chuyển vào trong 60 phút", 0, 500),
    Field("sender_outbound_ratio_60m_pct", "int", "tỷ lệ chuyển ra/nhận vào trong 60 phút", 0, 1000, "%"),
    Field("sender_outbound_count_24h", "int", "số giao dịch chi trong 24 giờ trước", 0, 1000),
    Field("receiver_account_age_days", "int", "tuổi tài khoản nhận", 0, 3650, "ngày"),
    Field(
        "receiver_is_verified_merchant",
        "bool",
        "người nhận là merchant đã xác minh",
        label_false_vi="người nhận không phải merchant đã xác minh",
    ),
    Field("receiver_is_familiar", "bool", "người nhận quen", label_false_vi="người nhận không quen"),
    Field("receiver_inbound_count_30m", "int", "số giao dịch người nhận nhận vào trong 30 phút", 0, 5000),
    Field("receiver_distinct_senders_30m", "int", "số người khác nhau chuyển cho người nhận trong 30 phút", 0, 5000),
)

CATALOG: dict[str, Field] = {f.name: f for f in FIELDS}
FIELD_NAMES: tuple[str, ...] = tuple(CATALOG)

# Ràng buộc miền phụ thuộc (docs/02 mục 1). Dùng chung cho Z3 (encoder) và dữ liệu (interpreter/generator test),
# nên viết bằng chính ngữ pháp Condition của DSL để hai bên dịch cùng một cách.
#   ("ge", a, b)             : a >= b (so sánh hai trường)
#   ("implies", cond, cond)  : cond_a ⇒ cond_b
DOMAIN_CONSTRAINTS: tuple[tuple[Any, ...], ...] = (
    ("ge", "daily_total_after", "amount"),
    ("ge", "sender_account_age_days", "sender_dormant_days"),
    ("ge", "receiver_inbound_count_30m", "receiver_distinct_senders_30m"),
    (
        "implies",
        {"field": "sender_inbound_amount_60m", "op": "==", "value": 0},
        {
            "all": [
                {"field": "sender_distinct_inbound_60m", "op": "==", "value": 0},
                {"field": "sender_outbound_ratio_60m_pct", "op": "==", "value": 0},
            ]
        },
    ),
    (
        "implies",
        {"field": "sender_distinct_inbound_60m", "op": ">=", "value": 1},
        {"field": "sender_inbound_amount_60m", "op": ">=", "value": 1},
    ),
    (
        "implies",
        {"field": "receiver_is_verified_merchant", "op": "==", "value": True},
        {"field": "receiver_account_age_days", "op": ">=", "value": 30},
    ),
    (
        "implies",
        {"field": "channel", "op": "==", "value": "TOPUP"},
        {"field": "receiver_is_verified_merchant", "op": "==", "value": False},
    ),
)


def catalog_payload() -> dict[str, Any]:
    """Nội dung cho GET /catalog."""
    return {
        "dsl_version": DSL_VERSION,
        "fields": [f.to_dict() for f in FIELDS],
        "decisions": list(DECISIONS),
        "auth_levels": list(AUTH_LEVELS),
        "ops_by_type": {k: list(v) for k, v in OPS_BY_TYPE.items()},
        "limits": {"max_depth": MAX_DEPTH, "max_leaves": MAX_LEAVES},
    }
