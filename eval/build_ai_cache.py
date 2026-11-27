"""Ghi sẵn kết quả AI cho các câu mẫu của guided tour vào data/seed/ai_cache.json (docs/05 mục 1, T5.3).

Khi API LLM lỗi / hết hạn mức / chưa có key, câu mẫu vẫn chạy bằng kết quả đã lưu (UI gắn nhãn "kết quả đã lưu").
Chỉ ghi output do LLM thật trả về và đã qua JSON Schema + validator VC-01 — không bao giờ viết tay output AI.

Chạy từ gốc repo khi có LLM_API_KEY, LLM_MODEL:
    services/api/.venv/bin/python eval/build_ai_cache.py
Khóa cache phụ thuộc phiên bản prompt, Policy Pack seed và bộ luật seed → đổi một trong ba thì chạy lại.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.ai.client import LLMError, get_client  # noqa: E402
from app.ai.schemas import compile_schema  # noqa: E402
from app.ai.tasks import AI_CACHE_FILE, COMPILE_VERSION, _evaluate, build_system_prompt, build_user_message, cache_key  # noqa: E402
from app.data.loader import seed_pack, seed_path, seed_rules  # noqa: E402

# Phải trùng từng chữ với DEMO1 và SUGGESTIONS trong apps/web/components/StudioView.tsx (có test kiểm).
SAMPLES = [
    "Để giảm phiền hà cho khách thân thiết: tài khoản trên 1 năm, chuyển cho người nhận quen thì không cần xác thực thêm.",
    "Tài khoản mới dưới 7 ngày nhận tiền từ 5 người trong 1 giờ rồi chuyển đi gần hết thì giữ lại 2 phút.",
    "Chuyển tiền từ 5 triệu trở lên lúc nửa đêm cho tài khoản nhận mới mở dưới 3 ngày thì gắn cờ giám sát.",
    "Thanh toán QR cho merchant đã xác minh dưới 500 nghìn thì miễn xác thực thêm.",
]


def build_cache(client, samples: list[str] = SAMPLES) -> tuple[dict, list[str]]:
    """Gọi LLM cho từng câu mẫu (tối đa 2 lần như pipeline thật) → (cache, câu không ghi được)."""
    pack, rules = seed_pack(), seed_rules()
    system = build_system_prompt(pack, rules)
    schema = compile_schema(list(pack["params"]))
    cache: dict = {}
    failed: list[str] = []
    for text in samples:
        errors: list[str] = []
        saved = False
        for _ in (1, 2):
            try:
                res = client.complete_json(system, build_user_message(text, errors or None), schema, "rf_compile")
            except LLMError:
                break
            out, _rule, errors = _evaluate(res.data, pack, "DRAFT-0001", "cache")
            if out is not None and not errors:
                cache[cache_key(text, pack, rules)] = res.data
                saved = True
                break
        if not saved:
            failed.append(text)
    cache["_meta"] = {"task": "compile", "prompt_version": COMPILE_VERSION, "pack_version": pack["version"],
                      "model": getattr(client, "model", "?"), "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                      "samples": len(samples) - len(failed)}
    return cache, failed


def main() -> int:
    client = get_client()
    if not client.available:
        print("Chưa có LLM_API_KEY/LLM_MODEL — không ghi cache (không bao giờ viết tay output AI).")
        return 1
    cache, failed = build_cache(client)
    out = seed_path(AI_CACHE_FILE)
    out.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Đã ghi {cache['_meta']['samples']}/{len(SAMPLES)} câu mẫu vào {out.relative_to(ROOT)}.")
    for text in failed:
        print(f"  ✗ không ghi được: {text}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
