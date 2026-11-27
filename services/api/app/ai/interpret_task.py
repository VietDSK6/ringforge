"""Task T3 — diễn giải mô tả quy định mới → đề xuất bản vá Policy Pack (docs/05 mục 5, FR-P4, P1).

AI chỉ ĐỀ XUẤT. Bản vá qua JSON Schema strict → Pydantic → apply_patch + VC-01 của Policy Pack; lỗi thì gọi lại 1 lần
kèm danh sách lỗi; vẫn lỗi thì báo người dùng, không đoán. Không bao giờ tự áp dụng: người dùng xem phân tích tác động
rồi bấm áp dụng (POST /pack/apply).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.ai.client import LLMClient, LLMError
from app.ai.schemas import _obj, condition_defs, strip_nulls
from app.ai.tasks import PROMPT_DIR, _catalog_brief
from app.dsl.catalog import AUTH_LEVELS, DECISIONS
from app.dsl.render_vi import PARAM_LABELS_VI, describe_invariant
from app.store import repo
from app.store.models import new_id
from app.verify.impact import PatchOp, apply_patch

INTERPRET_VERSION = "interpret.v1"
MAX_TEXT = 1000
_PATCH = TypeAdapter(list[PatchOp])


@lru_cache(maxsize=2)
def _template(version: str) -> str:
    return (PROMPT_DIR / f"{version}.md").read_text(encoding="utf-8")


def build_system(pack: dict[str, Any]) -> str:
    params = [{"name": k, "label_vi": PARAM_LABELS_VI.get(k, k), "value": p["value"], "unit": p["unit"], "source": p["source"]}
              for k, p in pack["params"].items()]
    invs = [{"id": i["id"], "type": i["type"], "level": i["level"], "when": i["when"], "mo_ta": describe_invariant(i, pack)}
            for i in pack["invariants"]]
    return (_template(INTERPRET_VERSION)
            .replace("{{CATALOG}}", json.dumps(_catalog_brief(), ensure_ascii=False))
            .replace("{{PARAMS}}", json.dumps(params, ensure_ascii=False))
            .replace("{{INVARIANTS}}", json.dumps(invs, ensure_ascii=False)))


def build_user(text: str, errors: list[str] | None = None) -> str:
    safe = re.sub(r"</?\s*regulation_text\s*>", "[thẻ đã bị loại bỏ]", text, flags=re.IGNORECASE)
    msg = f"<regulation_text>{safe}</regulation_text>"
    if errors:
        msg += "\n\nBản vá trước bị bộ kiểm tra từ chối vì:\n" + "\n".join(f"- {e}" for e in errors) + "\nHãy sửa và trả lại JSON đúng."
    return msg


def interpret_schema(pack: dict[str, Any]) -> dict[str, Any]:
    defs = condition_defs(list(pack["params"]))
    defs["InvariantOut"] = _obj({
        "id": {"type": "string"},
        "type": {"type": "string", "enum": ["AUTH_AT_LEAST", "DECISION_AT_MOST"]},
        "level": {"type": "string", "enum": [*AUTH_LEVELS, *DECISIONS]},
        "when": {"$ref": "#/$defs/Condition"},
        "source": {"type": "string"},
    })
    op = _obj({
        "op": {"type": "string", "enum": ["set_param", "add_invariant"]},
        "param": {"type": ["string", "null"], "enum": [*pack["params"], None]},
        "value": {"type": ["integer", "null"]},
        "invariant": {"anyOf": [{"$ref": "#/$defs/InvariantOut"}, {"type": "null"}]},
    })
    root = _obj({
        "out_of_scope": {"type": "boolean"},
        "patch": {"type": "array", "items": op},
        "effective_date": {"type": ["string", "null"]},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    })
    return root | {"$defs": defs}


def _evaluate(data: dict[str, Any], pack: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """→ (bản vá chuẩn hóa, thay đổi, pack mới, lỗi)."""
    raw = []
    for item in data.get("patch") or []:
        item = strip_nulls(item)
        if item.get("op") == "set_param":
            raw.append({"op": "set_param", "param": item.get("param"), "value": item.get("value"), "source": "Theo văn bản quy định người dùng dán (AI đề xuất, người dùng xác nhận khi áp dụng)"})
        elif item.get("op") == "add_invariant":
            raw.append({"op": "add_invariant", "invariant": (item.get("invariant") or {}) | {"severity": "HARD"}})
    try:
        ops = _PATCH.validate_python(raw)
    except ValidationError as e:
        return [], [], None, [f"Sai cấu trúc bản vá: {x['msg']} tại {'.'.join(map(str, x['loc']))}" for x in e.errors()[:5]]
    if not ops:
        return [], [], None, ["Bản vá rỗng."]
    new, issues, changes = apply_patch(pack, ops)
    errors = [i.message_vi for i in issues]
    if new is not None and not changes:
        errors.append("Bản vá không thay đổi gì so với Policy Pack hiện hành.")
    return [o.model_dump(exclude_none=True) for o in ops], changes, new, errors


def interpret_regulation(db: Session, sid: str, text: str, pack: dict[str, Any], client: LLMClient) -> dict[str, Any]:
    system = build_system(pack)
    schema = interpret_schema(pack)
    errors: list[str] = []
    result: dict[str, Any] = {}
    for _ in range(2):
        call_id = new_id()
        common = dict(id=call_id, task="interpret", prompt_version=INTERPRET_VERSION, prompt_hash=repo.stable_hash(system),
                      input_hash=repo.stable_hash({"text": text, "pack": pack["version"]}))
        try:
            res = client.complete_json(system, build_user(text, errors or None), schema, "rf_interpret")
        except LLMError as e:
            repo.add_ai_call(db, sid, model=client.model, error=f"{e.code}: {e}", **common)
            raise
        data = res.data
        if data.get("out_of_scope"):
            repo.add_ai_call(db, sid, model=res.model, output=data, schema_valid=True, semantic_valid=True,
                             tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, **common)
            result = {"status": "OUT_OF_SCOPE", "patch": [], "changes": [], "uncertainties": data.get("uncertainties") or []}
            break
        patch, changes, new, errors = _evaluate(data, pack)
        repo.add_ai_call(db, sid, model=res.model, output=data, schema_valid=True, semantic_valid=not errors,
                         tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms,
                         error="; ".join(errors)[:2000] if errors else None, **common)
        result = {
            "status": "INVALID" if errors else "OK",
            "patch": patch if not errors else [],
            "changes": changes if not errors else [],
            "errors": errors,
            "pack_after_version": new["version"] if new and not errors else None,
            "effective_date": data.get("effective_date"),
            "uncertainties": data.get("uncertainties") or [],
        }
        if not errors:
            break
    result |= {"ai_call_id": call_id, "model": getattr(client, "model", None), "prompt_version": INTERPRET_VERSION}
    for c in result.get("changes", []):
        if c["op"] == "add_invariant":
            inv = next(o["invariant"] for o in result["patch"] if o["op"] == "add_invariant" and o["invariant"]["id"] == c["invariant_id"])
            c["description_vi"] = describe_invariant(inv, pack)
    return result
