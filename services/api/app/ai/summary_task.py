"""Task T4 — tóm tắt cho người duyệt (docs/05 mục 6, P1).

AI chỉ viết lời từ số liệu hệ thống đã tính. Kiểm tra tất định: MỌI con số trong câu tóm tắt phải xuất hiện trong dữ liệu
đầu vào (sau khi chuẩn hóa dấu chấm/phẩy); vi phạm → bỏ bản AI, dùng mẫu tất định. Đây là bảo đảm G5 "không con số nào
do LLM bịa". Không có AI (thiếu key, hết lượt, lỗi) → luôn có mẫu tất định.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.ai.client import LLMClient, LLMError
from app.ai.schemas import _obj
from app.ai.tasks import PROMPT_DIR
from app.store import repo
from app.store.models import new_id

SUMMARY_VERSION = "summary.v1"
OP_VI = {"add": "thêm", "replace": "sửa", "retire": "ngừng"}
VERDICT_VI = {"PASS": "đạt", "PASS_WITH_WARNINGS": "đạt có cảnh báo", "FAIL": "không đạt", "UNKNOWN": "không kết luận được"}
# Mã luật/invariant chứa chữ số (FR-05, INV-AUTH-01, VC-04) không phải "con số" → bỏ trước khi kiểm.
CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b")
NUM_RE = re.compile(r"\d[\d.,]*\d|\d")


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def build_facts(cs: dict[str, Any]) -> dict[str, Any]:
    """Số liệu gọn (đã định dạng vi-VN) cho AI và cho mẫu tất định."""
    s = cs["summary"]
    v, bt, diff = s["verify"], s["backtest"], s["semantic_diff"]
    b0, b1 = bt["before"], bt["after"]
    facts: dict[str, Any] = {
        "thay_doi": [f"{OP_VI[i['op']]} {i['rule_id']}" for i in cs["items"]],
        "ket_luan_kiem_chung": VERDICT_VI.get(v["verdict"], v["verdict"]),
        "loi": [c["message_vi"] for c in v["checks"] if c["severity"] == "ERROR"][:4],
        "canh_bao": [c["message_vi"] for c in v["checks"] if c["severity"] == "WARN"][:3],
        "so_ngay_du_lieu": fmt(len(bt["days"])),
        "ton_that_rong_truoc_d": fmt(b0["l_net"]),
        "ton_that_rong_sau_d": fmt(b1["l_net"]),
        "chenh_lech_ton_that_rong_d": fmt(abs(bt["delta"]["l_net"])),
        "ton_that_rong_giam": bt["delta"]["l_net"] < 0,
        "giao_dich_that_bi_giu_chan_truoc": fmt(b0["fp_hold"] + b0["fp_block"]),
        "giao_dich_that_bi_giu_chan_sau": fmt(b1["fp_hold"] + b1["fp_block"]),
        "giao_dich_that_phai_sinh_trac_truoc": fmt(b0["friction_biometric"]),
        "giao_dich_that_phai_sinh_trac_sau": fmt(b1["friction_biometric"]),
        "giao_dich_pham_invariant_tren_du_lieu": fmt(sum(e["count"] for e in b1["compliance_exposure"])),
        "semantic_diff": diff["message_vi"],
    }
    sh = s.get("shadow")
    if sh:
        facts |= {
            "shadow_giao_dich_doi_ket_qua": fmt(sh["changed"]["tx_count"]),
            "shadow_tong_giao_dich_ngay_7": fmt(sh["n_tx"]),
            "shadow_gian_lan_bi_giu_them": fmt(sh["fraud_newly_stopped"]),
            "shadow_giao_dich_that_bi_giu_them": fmt(sh["legit_newly_stopped"]),
        }
    return facts


def _normalize(num: str) -> str:
    return num.replace(".", "").replace(",", "").lstrip("0") or "0"


def allowed_numbers(facts: dict[str, Any]) -> set[str]:
    text = CODE_RE.sub(" ", json.dumps(facts, ensure_ascii=False))
    return {_normalize(n) for n in NUM_RE.findall(text)}


def invented_numbers(summary: str, facts: dict[str, Any]) -> list[str]:
    """Các con số trong câu tóm tắt KHÔNG có trong dữ liệu đầu vào (rỗng = đạt)."""
    ok = allowed_numbers(facts)
    return [n for n in NUM_RE.findall(CODE_RE.sub(" ", summary)) if _normalize(n) not in ok]


def template_summary(f: dict[str, Any]) -> str:
    """Mẫu tất định — luôn đúng số, dùng khi không có AI hoặc bản AI bị loại."""
    parts = [f"Change set {', '.join(f['thay_doi'])}; kiểm chứng {f['ket_luan_kiem_chung']}."]
    if f["loi"]:
        parts.append(f"Còn lỗi: {f['loi'][0]} Change set này không phê duyệt được cho đến khi sửa.")
    before, after, diff = f["ton_that_rong_truoc_d"], f["ton_that_rong_sau_d"], f["chenh_lech_ton_that_rong_d"]
    days = f"Trên {f['so_ngay_du_lieu']} ngày dữ liệu tổng hợp"
    if diff == "0":
        parts.append(f"{days}, tổn thất ròng không đổi ({before} đ).")
    else:
        trend = "giảm" if f["ton_that_rong_giam"] else "tăng"
        parts.append(f"{days}, tổn thất ròng {trend} {diff} đ: {before} đ → {after} đ.")
    parts.append(
        f"Giao dịch thật bị giữ/chặn: {f['giao_dich_that_bi_giu_chan_truoc']} → {f['giao_dich_that_bi_giu_chan_sau']}; "
        f"phải sinh trắc học: {f['giao_dich_that_phai_sinh_trac_truoc']} → {f['giao_dich_that_phai_sinh_trac_sau']}."
    )
    if "shadow_giao_dich_doi_ket_qua" in f:
        parts.append(
            f"Shadow ngày 7: {f['shadow_giao_dich_doi_ket_qua']}/{f['shadow_tong_giao_dich_ngay_7']} giao dịch đổi kết quả, "
            f"giữ thêm {f['shadow_gian_lan_bi_giu_them']} giao dịch gian lận và {f['shadow_giao_dich_that_bi_giu_them']} giao dịch thật."
        )
    if f["canh_bao"]:
        parts.append(f"Cần xem: {f['canh_bao'][0]}")
    return " ".join(parts)


@lru_cache(maxsize=1)
def _system() -> str:
    return (PROMPT_DIR / f"{SUMMARY_VERSION}.md").read_text(encoding="utf-8")


def summary_schema() -> dict[str, Any]:
    return _obj({"summary_vi": {"type": "string"}, "numbers_used": {"type": "array", "items": {"type": "string"}}})


def summarize_change_set(db: Session, sid: str, cs: dict[str, Any], client: LLMClient | None) -> dict[str, Any]:
    """→ {summary_vi, source: ai|template, ...}. client None = không gọi AI."""
    facts = build_facts(cs)
    fallback = {"summary_vi": template_summary(facts), "source": "template", "facts": facts}
    if client is None or not client.available:
        return fallback | {"ai": "unavailable"}
    system = _system()
    user = "<facts>" + json.dumps(facts, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e") + "</facts>"
    call_id = new_id()
    common = dict(id=call_id, task="summary", prompt_version=SUMMARY_VERSION, prompt_hash=repo.stable_hash(system),
                  input_hash=repo.stable_hash(facts))
    try:
        res = client.complete_json(system, user, summary_schema(), "rf_summary")
    except LLMError as e:
        repo.add_ai_call(db, sid, model=client.model, error=f"{e.code}: {e}", **common)
        return fallback | {"ai": "error"}
    text = str(res.data.get("summary_vi", "")).strip()
    bad = invented_numbers(text, facts)
    repo.add_ai_call(db, sid, model=res.model, output=res.data, schema_valid=bool(text), semantic_valid=bool(text) and not bad,
                     tokens_in=res.tokens_in, tokens_out=res.tokens_out, latency_ms=res.latency_ms,
                     error=f"Số không có trong dữ liệu: {bad}" if bad else None, **common)
    repo.audit(db, sid, "ai", "changeset.summary", {"ai_call_id": call_id, "change_set_id": cs["id"], "accepted": not bad and bool(text)})
    if not text or bad:
        return fallback | {"ai": "rejected", "rejected_numbers": bad}
    return {"summary_vi": text, "source": "ai", "ai": "used", "ai_call_id": call_id, "model": res.model, "facts": facts}
