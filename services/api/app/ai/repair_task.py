"""Task T2 — AI đề xuất bản sửa (docs/05 mục 4). AI chỉ ĐỀ XUẤT; kiểm chứng lại, backtest, xếp hạng do code tất định.

Đầu vào cho AI: luật gốc (dữ liệu người dùng, đặt trong khối riêng), báo cáo kiểm chứng (invariant, phản ví dụ, blame),
quy mô ảnh hưởng chỉ để AI hiểu mức độ. Output qua JSON Schema strict → Pydantic → VC-01 cho từng luật.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.client import LLMClient, LLMError
from app.ai.schemas import RepairOutput, repair_schema, strip_nulls
from app.ai.tasks import PROMPT_DIR, _catalog_brief
from app.dsl.render_vi import PARAM_LABELS_VI, render_condition, render_rule
from app.dsl.validator import check_rule
from app.store import repo
from app.store.models import new_id

REPAIR_VERSION = "repair.v1"
MAX_CANDIDATES = 3


@lru_cache(maxsize=2)
def _template(version: str) -> str:
    return (PROMPT_DIR / f"{version}.md").read_text(encoding="utf-8")


def _data_json(obj: Any) -> str:
    """JSON cho khối dữ liệu; mã hóa '<' để nội dung người dùng không thể đóng khối/giả thẻ."""
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def build_repair_system(pack: dict[str, Any], version: str = REPAIR_VERSION) -> str:
    params = [{"name": k, "value": p["value"], "unit": p["unit"], "label_vi": PARAM_LABELS_VI.get(k, k)} for k, p in pack["params"].items()]
    invs = [
        {"id": i["id"], "type": i["type"], "level": i["level"], "when": i["when"], "when_vi": render_condition(i["when"], pack)}
        for i in pack["invariants"]
    ]
    return (
        _template(version)
        .replace("{{CATALOG}}", json.dumps(_catalog_brief(), ensure_ascii=False))
        .replace("{{PARAMS}}", json.dumps(params, ensure_ascii=False))
        .replace("{{INVARIANTS}}", json.dumps(invs, ensure_ascii=False))
    )


def build_repair_user(original: dict[str, Any], findings: list[dict[str, Any]], pack: dict[str, Any], feedback: list[str] | None = None) -> str:
    rule = {k: original.get(k) for k in ("name", "description", "kind", "when", "then", "assumptions")}
    rule["sentence_vi"] = render_rule(original, pack)["sentence_vi"]
    violations = [
        {
            "invariant": f["invariant"],
            "blamed_rules": f.get("blamed_rules", []),
            "counterexample": f.get("counterexample"),
            "outcome": f.get("outcome"),
            "affected_transactions": f.get("grounding", {}).get("tx_count"),
        }
        for f in findings
        if f.get("code") == "VC-04" and original["id"] in f.get("blamed_rules", [])
    ]
    msg = (
        f"<original_rule>{_data_json(rule)}</original_rule>\n"
        f"<verification>{_data_json(violations)}</verification>\n"
        "(affected_transactions chỉ để bạn hiểu mức độ; không nhắc lại con số.)"
    )
    if feedback:
        msg += "\n\nCác bản sửa trước đều bị bộ kiểm chứng loại vì:\n" + "\n".join(f"- {f}" for f in feedback) + "\nHãy đề xuất lại."
    return msg


def _to_rules(cand, original: dict[str, Any], call_id: str) -> list[dict[str, Any]]:
    out = []
    for i, r in enumerate(cand.rules):
        out.append({
            "id": original["id"] if i == 0 else f"{original['id']}B",
            "version": original.get("version", 1) + 1 if i == 0 else 1,
            "name": r.name[:200] or original["name"],
            "description": r.description,
            "kind": r.kind,
            "status": "CANDIDATE",
            "locked": False,
            "when": strip_nulls(r.when),
            "then": strip_nulls(r.then),
            "assumptions": list(original.get("assumptions", [])),
            "provenance": {"created_by": "ai_repair", "parent": f"{original['id']}@v{original.get('version', 1)}", "ai_call_id": call_id},
        })
    return out


def propose_repairs(
    db: Session,
    sid: str,
    original: dict[str, Any],
    findings: list[dict[str, Any]],
    pack: dict[str, Any],
    client: LLMClient,
    feedback: list[str] | None = None,
    version: str = REPAIR_VERSION,
    user: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Gọi AI một lần → (đề xuất qua VC-01, đề xuất bị loại kèm lý do). LLMError được ném tiếp cho caller.
    version/user cho phép dùng lại pipeline với prompt khác (ví dụ sửa luật không còn tương thích sau khi đổi Policy Pack)."""
    system = build_repair_system(pack, version)
    user = user if user is not None else build_repair_user(original, findings, pack, feedback)
    call_id = new_id()
    common = dict(id=call_id, task="repair", prompt_version=version, prompt_hash=repo.stable_hash(system),
                  input_hash=repo.stable_hash({"user": user, "pack": pack["version"]}))
    try:
        res = client.complete_json(system, user, repair_schema(list(pack["params"])), "rf_repair")
    except LLMError as e:
        repo.add_ai_call(db, sid, model=client.model, error=f"{e.code}: {e}", **common)
        repo.audit(db, sid, "ai", "rule.repair_propose", {"ai_call_id": call_id, "rule_id": original["id"], "error": e.code})
        raise
    try:
        out = RepairOutput.model_validate(res.data)
    except ValidationError as e:
        repo.add_ai_call(db, sid, model=res.model, output=res.data, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                         latency_ms=res.latency_ms, error=str(e)[:2000], **common)
        repo.audit(db, sid, "ai", "rule.repair_propose", {"ai_call_id": call_id, "rule_id": original["id"], "error": "SCHEMA_INVALID"})
        return [], [{"source": "ai", "strategy": "OTHER", "reason_vi": "AI trả về sai định dạng nên bị loại."}]

    proposals, rejected = [], []
    for cand in out.candidates[:MAX_CANDIDATES]:
        rules, errors = [], []
        for r in _to_rules(cand, original, call_id):
            clean, issues = check_rule(r, pack)
            errors += [i.message_vi for i in issues]
            if clean is not None:
                rules.append(clean)
        if errors:
            rejected.append({"source": "ai", "strategy": cand.strategy, "reason_vi": "Sai cú pháp/kiểu (VC-01): " + " ".join(errors[:3])})
            continue
        proposals.append({
            "source": "ai", "strategy": cand.strategy, "rationale_vi": cand.rationale,
            "intent_preserved_vi": cand.intent_preserved, "intent_lost_vi": cand.intent_lost,
            "rules": rules, "ai_call_id": call_id,
        })
    repo.add_ai_call(db, sid, model=res.model, output=res.data, schema_valid=True, semantic_valid=bool(proposals),
                     tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms, **common)
    repo.audit(db, sid, "ai", "rule.repair_propose", {
        "ai_call_id": call_id, "rule_id": original["id"], "model": res.model,
        "proposals": len(proposals), "rejected_vc01": len(rejected),
    })
    return proposals, rejected
