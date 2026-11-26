# 06 — Kiến trúc, dữ liệu, API, deploy

## 1. Sơ đồ

```
┌────────────────────────────┐        HTTPS/JSON        ┌───────────────────────────────────────────┐
│ apps/web — Next.js (Vercel)│ ───────────────────────► │ services/api — FastAPI (Docker)            │
│ App Router, TS, Tailwind   │                          │  ├─ dsl/       schema, validator, render_vi │
│ Recharts, (Cytoscape P2)   │ ◄─────────────────────── │  ├─ verify/    z3 encoder, VC-01..07        │
└────────────────────────────┘                          │  ├─ backtest/  interpreter, metrics         │
                                                        │  ├─ data/      generator, features          │
                                                        │  ├─ ai/        client, tasks, prompts, cache│
                                                        │  ├─ store/     Postgres (Supabase/Neon)     │
                                                        │  └─ api/       routes, rate limit           │
                                                        └───────────────┬───────────────────────────┘
                                                                        │
                                            ┌───────────────────────────┴──────────┐
                                            │ Postgres: sessions, rules, packs,     │
                                            │ runs, ai_calls, audit                 │
                                            │ Parquet giao dịch: load vào RAM       │
                                            │ LLM API (server-side key)             │
                                            └──────────────────────────────────────┘
```

Lý do tách web/API: Z3 + pandas chạy tốt nhất trên Python; web trên Vercel cho tốc độ dựng UI của bạn (TypeScript).
Phương án gọn hơn nếu deploy hai nơi gây rắc rối: build Next.js static export và cho FastAPI phục vụ file tĩnh (một container duy nhất). Quyết định ở spike tối 26/11.

## 2. Cấu trúc repo

```
ringforge/
├─ apps/web/
│  ├─ app/(routes)/            # page.tsx cho từng màn hình ở 07
│  ├─ components/              # RuleCard, RuleSentence, CounterexampleCard, VerdictBadge, MetricTable…
│  ├─ lib/api.ts               # client typed, sinh type từ OpenAPI (openapi-typescript)
│  └─ lib/format.ts            # định dạng VNĐ (Intl 'vi-VN'), nhãn tiếng Việt
├─ services/api/
│  ├─ app/main.py
│  ├─ app/config.py            # env, giới hạn
│  ├─ app/dsl/{catalog.py, schema.py, validator.py, render_vi.py}
│  ├─ app/verify/{encoder.py, checks.py, optimize.py, grounding.py, det_repair.py}
│  ├─ app/backtest/{interpreter.py, metrics.py, variants.py}
│  ├─ app/data/{generate.py, features.py, scenarios.py, loader.py}
│  ├─ app/ai/{client.py, tasks.py, cache.py, prompts/*.md}
│  ├─ app/store/{db.py, models.py, repo.py}
│  ├─ app/api/{sessions.py, rules.py, verify.py, backtest.py, repair.py, pack.py, approvals.py, audit.py}
│  ├─ tests/
│  └─ Dockerfile
├─ data/seed/{rules.json, policy_pack.json, transactions.parquet, ai_cache.json}
├─ eval/{fixtures/tune/*.json, fixtures/test/*.json, run_ablation.py, report.md}
├─ docs/                       # bộ tài liệu này
├─ README.md
└─ .env.example
```

## 3. Data model (Postgres)

```sql
create table sessions (
  id uuid primary key, created_at timestamptz default now(),
  last_seen_at timestamptz, llm_calls_today int default 0, label text);

create table policy_packs (
  id uuid primary key, session_id uuid references sessions on delete cascade,
  version text not null, body jsonb not null, created_at timestamptz default now(),
  is_current boolean default false);

create table rules (
  pk uuid primary key, session_id uuid references sessions on delete cascade,
  rule_id text not null, version int not null, body jsonb not null,
  status text not null check (status in ('ACTIVE','CANDIDATE','SHADOW','RETIRED')),
  created_at timestamptz default now(), unique (session_id, rule_id, version));

create table change_sets (
  id uuid primary key, session_id uuid references sessions on delete cascade,
  items jsonb not null,            -- [{op: add|replace|retire, rule_id, version}]
  pack_version text, state text check (state in ('DRAFT','VERIFIED','APPROVED','REJECTED','SHADOW','LIVE_SIM')),
  verify_run_id uuid, backtest_run_id uuid, note text, created_at timestamptz default now());

create table verify_runs  (id uuid primary key, session_id uuid, input_hash text, result jsonb, ms int, created_at timestamptz default now());
create table backtest_runs(id uuid primary key, session_id uuid, input_hash text, result jsonb, ms int, created_at timestamptz default now());

create table ai_calls (
  id uuid primary key, session_id uuid, task text, model text, prompt_version text,
  prompt_hash text, input_hash text, output jsonb, schema_valid bool, semantic_valid bool,
  tokens_in int, tokens_out int, latency_ms int, from_cache bool, created_at timestamptz default now());

create table audit_log (
  id bigserial primary key, session_id uuid, actor text,   -- 'user:proposer' | 'user:approver' | 'ai' | 'system'
  action text, ref jsonb, created_at timestamptz default now());
```

Dọn dẹp: xóa phiên không hoạt động > 3 ngày (cron đơn giản lúc khởi động hoặc endpoint nội bộ).

## 4. API (REST, JSON, tiền là int)

| Method | Path | Mô tả | P |
|---|---|---|---|
| GET | `/health` | Trạng thái, phiên bản, LLM sẵn sàng hay dự phòng | P0 |
| GET | `/catalog` | Trường, enum, hành động, nhãn tiếng Việt | P0 |
| POST | `/sessions` | Tạo sandbox từ seed → `{session_id}` | P0 |
| POST | `/sessions/{sid}/reset` | Về seed | P0 |
| GET | `/sessions/{sid}/rules` | Luật hiện hành + candidate | P0 |
| PUT | `/sessions/{sid}/rules/{rule_id}` | Lưu phiên bản mới (body DSL) | P1 |
| POST | `/sessions/{sid}/compile` | `{text}` → kết quả T1 + câu tiếng Việt | P0 |
| POST | `/sessions/{sid}/verify` | `{change_set}` hoặc `{rules}` → báo cáo VC | P0 |
| POST | `/sessions/{sid}/backtest` | `{variants, assumptions}` → chỉ số | P0 |
| POST | `/sessions/{sid}/repair` | `{rule, verify_run_id}` → candidates đã kiểm chứng + backtest | P0 |
| GET | `/sessions/{sid}/pack` | Policy Pack hiện hành | P0 |
| POST | `/sessions/{sid}/pack/impact` | `{patch}` → luật bị ảnh hưởng, phản ví dụ, thay đổi ma sát | P0 |
| POST | `/sessions/{sid}/pack/apply` | `{patch}` → pack phiên bản mới | P0 |
| POST | `/sessions/{sid}/pack/interpret` | `{text}` → T3 patch đề xuất | P1 |
| POST | `/sessions/{sid}/change-sets` | Tạo change set | P0 |
| POST | `/sessions/{sid}/change-sets/{id}/decision` | `{approve|reject, note, role}`; từ chối nếu verify FAIL | P0 |
| POST | `/sessions/{sid}/change-sets/{id}/shadow` | Chạy shadow trên ngày 7 | P1 |
| GET | `/sessions/{sid}/audit` | Nhật ký | P0 |
| POST | `/sessions/{sid}/summary` | T4 tóm tắt | P1 |

Lỗi trả `{error_code, message_vi, details}`. Mã: `VALIDATION_ERROR`, `LLM_UNAVAILABLE`, `LLM_QUOTA`, `VERIFY_TIMEOUT`, `NOT_FOUND`.

### Ví dụ response `/verify`
```jsonc
{
  "verdict": "FAIL",
  "ms": 412,
  "checks": [
    { "code": "VC-04", "severity": "ERROR", "invariant": "INV-AUTH-01",
      "message_vi": "Bộ luật cho phép giao dịch trên ngưỡng sinh trắc học/lần đi qua mà không cần sinh trắc học.",
      "blamed_rules": ["DRAFT-0001"],
      "counterexample": { "amount": 10000001, "channel": "P2P", "hour": 10,
                          "sender_account_age_days": 366, "receiver_is_familiar": true, "...": "..." },
      "outcome": { "decision": "ALLOW", "auth": "NONE" },
      "grounding": { "tx_count": 0, "amount_sum": 0, "by_scenario": {} ,
                     "note_vi": "Dữ liệu quá khứ không có giao dịch nào trong vùng này: backtest sẽ không phát hiện." } },
    { "code": "VC-04", "severity": "ERROR", "invariant": "INV-AUTH-02", "...": "..." },
    { "code": "VC-05", "severity": "WARN", "redundant": "LG-09", "covered_by": "FR-01" }
  ]
}
```
(Ví dụ minh họa cấu trúc; con số thật do hệ thống tính.)

## 5. Deploy

| Thành phần | Lựa chọn chính | Dự phòng |
|---|---|---|
| Web | Vercel (Hobby) | Cloudflare Pages / static export phục vụ từ API |
| API | Container trên Render (gói trả phí thấp nhất, **không sleep**) hoặc Railway/Fly.io | AWS App Runner nếu BTC cấp credit |
| DB | Supabase hoặc Neon Postgres | SQLite trên volume persistent |
| Giám sát | UptimeRobot ping `/health` 5 phút | — |

Lưu ý:
- Free tier có sleep làm giám khảo chờ cold start: tránh, hoặc ping giữ ấm. Kiểm tra chính sách tạm dừng project không hoạt động của nhà cung cấp DB và đặt ping đến hết 11/12.
- `z3-solver` cài từ pip trong Docker (`python:3.11-slim`); kiểm tra kích thước image và RAM (512 MB thường đủ cho dữ liệu này; đo trong spike).
- Biến môi trường: `DATABASE_URL`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODEL_FALLBACK`, `LLM_DAILY_CALL_CAP`, `CORS_ORIGINS`, `APP_ENV`.
- Gắn tag git `submission-2026-12-03` cho bản nộp; **không deploy gì sau 23:59:59 ngày 03/12** (thể lệ cấm sửa sản phẩm sau hạn), trừ khi BTC cho phép khắc phục sự cố hạ tầng — hỏi trước.

## 6. Bảo mật

- CORS chỉ cho domain web.
- Rate limit theo IP và phiên (`slowapi`): 60 req/phút; LLM theo `05`.
- Giới hạn kích thước body 64 KB; độ dài `text` 1.000 ký tự.
- Validator DSL chặn độ sâu/độ rộng (chống làm nổ Z3); timeout Z3.
- Không log nội dung nhạy cảm (không có PII thật; vẫn giữ thói quen).
- Quét secret trước khi zip: `gitleaks detect` hoặc `git grep -nE "(sk-|api_key|AKIA)"`.
- Header: CSP cơ bản trên web, `X-Content-Type-Options`.

## 7. Thư viện mã nguồn mở (khai trong README)
Next.js, React, Tailwind CSS, Recharts, (Cytoscape.js), FastAPI, Pydantic, Uvicorn, z3-solver, pandas, numpy, pyarrow, SQLAlchemy/psycopg, slowapi, pytest. Kiểm tra và ghi license từng thư viện khi viết README.
