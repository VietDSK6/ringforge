"""Schema Pydantic của Policy DSL rf-dsl/0.1 (docs/02) — nguồn sự thật cho cấu trúc JSON.

Pydantic chỉ kiểm cấu trúc và kiểu (không float, không khóa lạ). Ràng buộc theo catalog/Policy Pack
(trường có tồn tại, toán tử hợp kiểu, tham số có thật, độ sâu…) nằm ở `validator.py`.
Engine (interpreter, Z3) nhận dạng dict chuẩn hóa: `to_plain(model)`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    Tag,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ParamRef(_Strict):
    param: StrictStr = Field(min_length=1, max_length=64)


Scalar = Union[StrictBool, StrictInt, StrictStr, ParamRef]


class AllCond(_Strict):
    all_: list[Condition] = Field(alias="all", min_length=1)


class AnyCond(_Strict):
    any_: list[Condition] = Field(alias="any", min_length=1)


class NotCond(_Strict):
    not_: Condition = Field(alias="not")


class ConstCond(_Strict):
    const: StrictBool


class LeafCond(_Strict):
    field: StrictStr = Field(min_length=1, max_length=64)
    op: Literal[">", ">=", "<", "<=", "==", "!=", "between", "in", "not_in"]
    value: Union[Scalar, list[Scalar]]


# Tên tag có tiền tố "c_" để lọc khỏi đường dẫn lỗi (không trùng khóa "all"/"any"/"not" thật).
COND_TAGS = ("c_all", "c_any", "c_not", "c_const", "c_leaf")


def _cond_tag(v: Any) -> str | None:
    if isinstance(v, dict):
        for key in ("all", "any", "not", "const"):
            if key in v:
                return f"c_{key}"
        return "c_leaf"
    for cls, tag in ((AllCond, "c_all"), (AnyCond, "c_any"), (NotCond, "c_not"), (ConstCond, "c_const"), (LeafCond, "c_leaf")):
        if isinstance(v, cls):
            return tag
    return None


Condition = Annotated[
    Union[
        Annotated[AllCond, Tag("c_all")],
        Annotated[AnyCond, Tag("c_any")],
        Annotated[NotCond, Tag("c_not")],
        Annotated[ConstCond, Tag("c_const")],
        Annotated[LeafCond, Tag("c_leaf")],
    ],
    Discriminator(_cond_tag),
]

for _m in (AllCond, AnyCond, NotCond):
    _m.model_rebuild()

Decision = Literal["ALLOW", "MONITOR", "HOLD", "BLOCK"]
AuthLevel = Literal["NONE", "OTP", "BIOMETRIC"]


class Action(_Strict):
    decision: Decision | None = None
    auth: AuthLevel | None = None
    exempt_auth: StrictBool = False
    hold_seconds: StrictInt | None = None


class Provenance(_Strict):
    created_by: Literal["human", "ai_compile", "ai_repair", "det_repair"] = "human"
    parent: StrictStr | None = None
    ai_call_id: StrictStr | None = None


class Rule(_Strict):
    id: StrictStr = Field(pattern=r"^[A-Z][A-Z0-9]*-[A-Za-z0-9]+$", max_length=32)
    version: StrictInt = Field(default=1, ge=1)
    name: StrictStr = Field(min_length=1, max_length=200)
    description: StrictStr = Field(default="", max_length=2000)
    kind: Literal["FRAUD", "FRICTION", "REGULATORY"]
    status: Literal["ACTIVE", "CANDIDATE", "SHADOW", "RETIRED"]
    locked: StrictBool = False
    when: Condition
    then: Action
    assumptions: list[Annotated[StrictStr, Field(max_length=500)]] = Field(default_factory=list, max_length=20)
    provenance: Provenance = Field(default_factory=Provenance)


class Param(_Strict):
    value: StrictInt
    unit: StrictStr
    source: StrictStr = ""


class Invariant(_Strict):
    id: StrictStr = Field(min_length=1, max_length=64)
    type: Literal["AUTH_AT_LEAST", "DECISION_AT_MOST"]
    level: StrictStr
    when: Condition
    source: StrictStr = ""
    severity: Literal["HARD"] = "HARD"


class PolicyPack(_Strict):
    id: StrictStr
    version: StrictStr
    disclaimer: StrictStr = ""
    params: dict[str, Param]
    invariants: list[Invariant]


def to_plain(model: BaseModel) -> dict[str, Any]:
    """Dạng dict chuẩn hóa (khóa JSON gốc, bỏ giá trị None) mà interpreter và encoder dùng."""
    return model.model_dump(by_alias=True, exclude_none=True)
