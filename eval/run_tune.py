"""Đo task T1 (biên dịch) trên fixture với LLM thật — DoD T2.3: ≥ 8/10 câu tune hợp lệ schema.

Chạy từ gốc repo (cần LLM_API_KEY, LLM_MODEL; tùy chọn LLM_MODEL_FALLBACK):
    services/api/.venv/bin/python eval/run_tune.py [--split tune] [--out eval/tune_report.md]

Đo: schema_valid (lần 1 / sau retry), status đúng, tương đương logic với gold bằng Z3 (docs/08 semantic_equiv),
nêu giả định cho cụm mơ hồ. Không chỉnh prompt dựa trên tập test (docs/05 mục 8).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.ai.client import LLMError, get_client  # noqa: E402
from app.ai.schemas import compile_schema  # noqa: E402
from app.ai.tasks import COMPILE_VERSION, _evaluate, build_system_prompt, build_user_message  # noqa: E402
from app.data.loader import seed_pack, seed_rules  # noqa: E402
from app.verify.relations import equivalent  # noqa: E402


def load_cases(split: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "eval" / "fixtures" / split).glob("*.json"))]


def run_case(case: dict, client, pack: dict, rules: list[dict]) -> dict:
    system = build_system_prompt(pack, rules)
    schema = compile_schema(list(pack["params"]))
    row = {"id": case["id"], "category": case["category"]}
    errors: list[str] = []
    started = time.perf_counter_ns()
    out = rule = None
    for attempt in (1, 2):
        try:
            res = client.complete_json(system, build_user_message(case["requirement_vi"], errors or None), schema, "rf_compile")
        except LLMError as e:
            row |= {"error": f"{e.code}: {e}"}
            break
        out, rule, errors = _evaluate(res.data, pack, "DRAFT-0001", "eval")
        row[f"schema_valid_{attempt}"] = out is not None
        row[f"semantic_valid_{attempt}"] = out is not None and not errors
        if out is not None and not errors:
            break
    row["latency_ms"] = (time.perf_counter_ns() - started) // 1_000_000
    row["schema_valid"] = bool(row.get("schema_valid_1") or row.get("schema_valid_2"))
    row["final_valid"] = bool(row.get("semantic_valid_1") or row.get("semantic_valid_2"))
    row["status"] = out.status if out else None
    row["status_ok"] = row["status"] == case["gold_status"]
    gold = case["gold_rule"]
    if gold and rule:
        same_when = equivalent(rule["when"], gold["when"], pack["params"]) == "YES"
        row["semantic_equiv"] = same_when and rule["then"] == gold["then"] | {"exempt_auth": gold["then"].get("exempt_auth", False)}
    if case["gold_assumptions"] and out:
        said = " ".join(a.phrase.lower() + " " + a.interpretation.lower() for a in out.assumptions)
        row["assumption_recall"] = sum(p.lower() in said for p in case["gold_assumptions"]) / len(case["gold_assumptions"])
    row["errors"] = errors
    return row


def report(rows: list[dict], model: str, split: str) -> str:
    n = len(rows)
    count = lambda k: sum(1 for r in rows if r.get(k))  # noqa: E731
    eq = [r for r in rows if "semantic_equiv" in r]
    lines = [
        f"# Kết quả biên dịch — tập `{split}`",
        "",
        f"Model: `{model}` · prompt `{COMPILE_VERSION}` · {n} case · dữ liệu tổng hợp do đội tự viết.",
        "",
        f"- Hợp lệ schema (lần 1): **{count('schema_valid_1')}/{n}**",
        f"- Hợp lệ schema (sau retry): **{count('schema_valid')}/{n}** — DoD T2.3 cần ≥ 8/10",
        f"- Qua VC-01 sau retry: **{count('final_valid')}/{n}**",
        f"- Status đúng: **{count('status_ok')}/{n}**",
        f"- Tương đương logic với gold (Z3): **{sum(1 for r in eq if r['semantic_equiv'])}/{len(eq)}**",
        "",
        "| Case | Nhóm | Status | Schema | VC-01 | Tương đương | Giả định | ms | Lỗi |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['status']} | {'✅' if r['schema_valid'] else '❌'} | "
            f"{'✅' if r['final_valid'] else '❌'} | {r.get('semantic_equiv', '—')} | {r.get('assumption_recall', '—')} | "
            f"{r['latency_ms']} | {'; '.join(r['errors'])[:120] or r.get('error', '')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="tune", choices=["tune", "test"])
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "tune_report.md")
    args = ap.parse_args()
    client = get_client()
    if not client.available:
        print("Chưa cấu hình LLM_API_KEY/LLM_MODEL — không chạy được.", file=sys.stderr)
        return 2
    pack, rules = seed_pack(), seed_rules()
    rows = [run_case(c, client, pack, rules) for c in load_cases(args.split)]
    args.out.write_text(report(rows, client.model, args.split), encoding="utf-8")
    args.out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in rows if r["schema_valid"])
    print(f"Hợp lệ schema: {ok}/{len(rows)} → {args.out}")
    return 0 if ok >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
