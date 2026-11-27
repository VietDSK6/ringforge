"""Task T1 — biên dịch tiếng Việt → Policy DSL (docs/05 mục 3). LLM đề xuất, code tất định quyết định.

Pipeline: cache → LLM (JSON Schema strict) → Pydantic → validator VC-01 → nếu lỗi gọi lại 1 lần kèm danh sách lỗi.
Server tự điền id/version/status/provenance. Mọi lần gọi ghi vào ai_calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import LLMClient, LLMError
from app.ai.schemas import CompileOutput, compile_schema, strip_nulls
from app.data.loader import seed_path
from app.dsl.catalog import FIELDS
from app.dsl.render_vi import PARAM_LABELS_VI, render_rule
from app.dsl.validator import check_rule
from app.store import repo
from app.store.models import AICallRow, new_id

PROMPT_DIR = Path(__file__).parent / "prompts"
COMPILE_VERSION = "compile.v1"
MAX_TEXT = 1000
AI_CACHE_FILE = "ai_cache.json"


@lru_cache(maxsize=4)
def _prompt_files(version: str) -> tuple[str, list[dict[str, Any]]]:
    template = (PROMPT_DIR / f"{version}.md").read_text(encoding="utf-8")
    examples = json.loads((PROMPT_DIR / f"{version}.examples.json").read_text(encoding="utf-8"))
    return template, examples


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _catalog_brief() -> list[dict[str, Any]]:
    out = []
    for f in FIELDS:
        d: dict[str, Any] = {"name": f.name, "type": f.type, "label_vi": f.label_vi}
        if f.type == "int":
            d |= {"min": f.lo, "max": f.hi, "unit": f.unit}
        elif f.type == "enum":
            d["values"] = {v: f.value_labels_vi[v] for v in f.values}
        out.append(d)
    return out


def build_system_prompt(pack: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    template, examples = _prompt_files(COMPILE_VERSION)
    params = [
        {"name": k, "value": p["value"], "unit": p["unit"], "label_vi": PARAM_LABELS_VI.get(k, k)}
        for k, p in pack["params"].items()
    ]
    summary = "\n".join(f"- {r['id']}: {render_rule(r, pack)['sentence_vi']}" for r in rules if r["status"] != "RETIRED")
    shots = "\n\n".join(
        f"Yêu cầu: {ex['requirement']}\nOutput: {json.dumps(ex['output'], ensure_ascii=False)}" for ex in examples
    )
    return (
        template.replace("{{CATALOG}}", json.dumps(_catalog_brief(), ensure_ascii=False))
        .replace("{{PARAMS}}", json.dumps(params, ensure_ascii=False))
        .replace("{{RULES}}", summary or "(trống)")
        .replace("{{EXAMPLES}}", shots)
    )


def build_user_message(text: str, errors: list[str] | None = None) -> str:
    # Chống thoát khỏi khối dữ liệu: vô hiệu hóa mọi thẻ user_requirement người dùng tự gõ.
    safe = re.sub(r"</?\s*user_requirement\s*>", "[thẻ đã bị loại bỏ]", text, flags=re.IGNORECASE)
    msg = f"<user_requirement>{safe}</user_requirement>"
    if errors:
        msg += "\n\nOutput trước bị bộ kiểm tra từ chối vì các lỗi sau. Hãy sửa và trả lại JSON đúng:\n" + "\n".join(f"- {e}" for e in errors)
    return msg


def cache_key(text: str, pack: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    return repo.stable_hash({
        "task": "compile",
        "prompt_version": COMPILE_VERSION,
        "text": normalize_text(text).lower(),
        "pack_version": pack["version"],
        "ruleset": repo.stable_hash(rules),
    })


@lru_cache(maxsize=1)
def _seed_cache() -> dict[str, Any]:
    """Kết quả ghi sẵn cho câu mẫu của guided tour (docs/05 mục 1) — sinh bằng scripts ghi cache khi có key."""
    p = seed_path(AI_CACHE_FILE)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def seed_cache_size() -> int:
    return sum(1 for k in _seed_cache() if not k.startswith("_"))


def lookup_cache(db: Session, key: str) -> dict[str, Any] | None:
    seeded = _seed_cache().get(key)
    if seeded is not None:
        return seeded
    row = db.scalars(
        select(AICallRow)
        .where(AICallRow.task == "compile", AICallRow.input_hash == key, AICallRow.semantic_valid.is_(True))
        .order_by(AICallRow.created_at.desc())
    ).first()
    return row.output if row else None


@dataclass
class CompileResult:
    status: str  # OK | NEEDS_CLARIFICATION | OUT_OF_SCOPE | INVALID
    rule: dict[str, Any] | None = None
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)
    unsupported_parts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str = "ai"  # ai | cache
    model: str = ""
    ai_call_id: str | None = None

    def to_dict(self, pack: dict[str, Any]) -> dict[str, Any]:
        d = self.__dict__.copy()
        if self.rule is not None:
            d["rule"] = self.rule | {"render": render_rule(self.rule, pack)}
        return d


def _to_rule(out: CompileOutput, rule_id: str, call_id: str) -> dict[str, Any]:
    r = out.rule
    assert r is not None
    return {
        "id": rule_id,
        "version": 1,
        "name": r.name[:200] or "Luật mới",
        "description": r.description,
        "kind": r.kind,
        "status": "CANDIDATE",
        "locked": False,
        "when": strip_nulls(r.when),
        "then": strip_nulls(r.then),
        "assumptions": [f"'{a.phrase}' = {a.interpretation}" for a in out.assumptions],
        "provenance": {"created_by": "ai_compile", "parent": None, "ai_call_id": call_id},
    }


def _evaluate(data: dict[str, Any], pack: dict[str, Any], rule_id: str, call_id: str) -> tuple[CompileOutput | None, dict[str, Any] | None, list[str]]:
    """Kiểm output LLM: schema (Pydantic) rồi ngữ nghĩa (VC-01). Trả (output, luật hợp lệ, lỗi)."""
    try:
        out = CompileOutput.model_validate(data)
    except ValidationError as e:
        return None, None, [f"Sai schema tại {'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:10]]
    if out.status != "OK":
        return out, None, []
    if out.rule is None:
        return out, None, ["status = OK nhưng rule = null."]
    rule, issues = check_rule(_to_rule(out, rule_id, call_id), pack)
    return out, rule, [i.message_vi for i in issues]


def compile_requirement(
    db: Session,
    sid: str,
    text: str,
    pack: dict[str, Any],
    rules: list[dict[str, Any]],
    client: LLMClient,
    use_cache: bool = True,
) -> CompileResult:
    key = cache_key(text, pack, rules)
    rule_id = repo.next_draft_id(db, sid)

    if use_cache and (cached := lookup_cache(db, key)) is not None:
        call_id = repo.add_ai_call(
            db, sid, task="compile", model="cache", prompt_version=COMPILE_VERSION, prompt_hash="", input_hash=key,
            output=cached, schema_valid=True, semantic_valid=True, from_cache=True,
        )
        out, rule, errors = _evaluate(cached, pack, rule_id, call_id)
        if out is not None and not errors:
            return CompileResult(out.status, rule, [a.model_dump() for a in out.assumptions], out.clarifying_questions,
                                 out.unsupported_parts, source="cache", model="cache", ai_call_id=call_id)

    system = build_system_prompt(pack, rules)
    prompt_hash = repo.stable_hash(system)
    schema = compile_schema(list(pack["params"]))
    errors: list[str] = []
    for _attempt in range(2):
        call_id = new_id()
        try:
            res = client.complete_json(system, build_user_message(text, errors or None), schema, "rf_compile")
        except LLMError as e:
            repo.add_ai_call(db, sid, id=call_id, task="compile", model=client.model, prompt_version=COMPILE_VERSION,
                             prompt_hash=prompt_hash, input_hash=key, error=f"{e.code}: {e}")
            db.commit()
            raise
        out, rule, errors = _evaluate(res.data, pack, rule_id, call_id)
        repo.add_ai_call(
            db, sid, id=call_id, task="compile", model=res.model, prompt_version=COMPILE_VERSION, prompt_hash=prompt_hash,
            input_hash=key, output=res.data, schema_valid=out is not None, semantic_valid=out is not None and not errors,
            tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms,
            error="; ".join(errors)[:2000] if errors else None,
        )
        if out is not None and not errors:
            return CompileResult(out.status, rule, [a.model_dump() for a in out.assumptions], out.clarifying_questions,
                                 out.unsupported_parts, model=res.model, ai_call_id=call_id)
    return CompileResult("INVALID", errors=errors, model=client.model, ai_call_id=call_id)
