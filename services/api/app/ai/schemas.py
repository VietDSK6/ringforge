"""JSON Schema cho output LLM (structured output, chế độ strict) + model Pydantic để kiểm lại phía server.

Viết tay để hợp tập con JSON Schema của chế độ strict: mọi object có additionalProperties=false và liệt kê
đủ `required`; trường tùy chọn biểu diễn bằng null. Tên trường và tham số bị giới hạn bằng enum theo catalog/pack.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dsl.catalog import AUTH_LEVELS, DECISIONS, FIELD_NAMES

LEAF_OPS = [">", ">=", "<", "<=", "==", "!=", "between", "in", "not_in"]


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def condition_defs(param_names: list[str]) -> dict[str, Any]:
    return {
        "Condition": {"anyOf": [{"$ref": f"#/$defs/{n}"} for n in ("AllCond", "AnyCond", "NotCond", "ConstCond", "LeafCond")]},
        "AllCond": _obj({"all": {"type": "array", "items": {"$ref": "#/$defs/Condition"}}}),
        "AnyCond": _obj({"any": {"type": "array", "items": {"$ref": "#/$defs/Condition"}}}),
        "NotCond": _obj({"not": {"$ref": "#/$defs/Condition"}}),
        "ConstCond": _obj({"const": {"type": "boolean"}}),
        "LeafCond": _obj({
            "field": {"type": "string", "enum": list(FIELD_NAMES)},
            "op": {"type": "string", "enum": LEAF_OPS},
            "value": {"$ref": "#/$defs/Value"},
        }),
        "ParamRef": _obj({"param": {"type": "string", "enum": param_names}}),
        "Scalar": {"anyOf": [{"type": "integer"}, {"type": "boolean"}, {"type": "string"}, {"$ref": "#/$defs/ParamRef"}]},
        "Value": {"anyOf": [{"$ref": "#/$defs/Scalar"}, {"type": "array", "items": {"$ref": "#/$defs/Scalar"}}]},
        "Action": _obj({
            "decision": {"type": ["string", "null"], "enum": [*DECISIONS, None]},
            "auth": {"type": ["string", "null"], "enum": [*AUTH_LEVELS, None]},
            "exempt_auth": {"type": "boolean"},
            "hold_seconds": {"type": ["integer", "null"]},
        }),
        "RuleOut": _obj({
            "name": {"type": "string"},
            "description": {"type": "string"},
            "kind": {"type": "string", "enum": ["FRAUD", "FRICTION", "REGULATORY"]},
            "when": {"$ref": "#/$defs/Condition"},
            "then": {"$ref": "#/$defs/Action"},
        }),
    }


def compile_schema(param_names: list[str]) -> dict[str, Any]:
    """Output của task T1 (docs/05 mục 3)."""
    root = _obj({
        "status": {"type": "string", "enum": ["OK", "NEEDS_CLARIFICATION", "OUT_OF_SCOPE"]},
        "rule": {"anyOf": [{"$ref": "#/$defs/RuleOut"}, {"type": "null"}]},
        "assumptions": {"type": "array", "items": _obj({
            "phrase": {"type": "string"},
            "interpretation": {"type": "string"},
            "editable": {"type": "boolean"},
        })},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "unsupported_parts": {"type": "array", "items": {"type": "string"}},
    })
    return root | {"$defs": condition_defs(param_names)}


REPAIR_STRATEGIES = ["NARROW_SCOPE", "CHANGE_ACTION", "SPLIT_RULE", "OTHER"]


def repair_schema(param_names: list[str]) -> dict[str, Any]:
    """Output của task T2 (docs/05 mục 4)."""
    candidate = _obj({
        "strategy": {"type": "string", "enum": REPAIR_STRATEGIES},
        "rules": {"type": "array", "items": {"$ref": "#/$defs/RuleOut"}},
        "rationale": {"type": "string"},
        "intent_preserved": {"type": "string"},
        "intent_lost": {"type": "string"},
    })
    return _obj({"candidates": {"type": "array", "items": candidate}}) | {"$defs": condition_defs(param_names)}


# ---------- kiểm lại phía server (không tin output LLM) ----------


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Assumption(_M):
    phrase: str = Field(max_length=200)
    interpretation: str = Field(max_length=300)
    editable: bool = True


class RuleOut(_M):
    name: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    kind: Literal["FRAUD", "FRICTION", "REGULATORY"]
    when: dict[str, Any]
    then: dict[str, Any]


class CompileOutput(_M):
    status: Literal["OK", "NEEDS_CLARIFICATION", "OUT_OF_SCOPE"]
    rule: RuleOut | None
    assumptions: list[Assumption] = Field(default_factory=list, max_length=20)
    clarifying_questions: list[str] = Field(default_factory=list, max_length=10)
    unsupported_parts: list[str] = Field(default_factory=list, max_length=10)


class RepairCandidate(_M):
    strategy: Literal["NARROW_SCOPE", "CHANGE_ACTION", "SPLIT_RULE", "OTHER"]
    rules: list[RuleOut] = Field(min_length=1, max_length=2)
    rationale: str = Field(max_length=1000)
    intent_preserved: str = Field(default="", max_length=500)
    intent_lost: str = Field(default="", max_length=500)


class RepairOutput(_M):
    candidates: list[RepairCandidate] = Field(max_length=5)


def strip_nulls(obj: Any) -> Any:
    """Bỏ khóa có giá trị null (cách strict mode biểu diễn trường tùy chọn) trước khi đưa vào validator DSL."""
    if isinstance(obj, dict):
        return {k: strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_nulls(v) for v in obj]
    return obj
