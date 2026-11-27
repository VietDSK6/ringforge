# RingForge

**Kiểm chứng luật chống gian lận trước khi bật.** RingForge là "CI/CD cho chính sách rủi ro" dành cho đội vận hành chống gian lận ở ví điện tử/ngân hàng số: viết luật bằng tiếng Việt → AI biên dịch thành Policy DSL (JSON) → Z3 chứng minh bộ luật không phá các yêu cầu bắt buộc (ví dụ xác thực sinh trắc học theo QĐ 2345) hoặc đưa ra **một giao dịch cụ thể làm phản ví dụ** → backtest trên dữ liệu tổng hợp tính tổn thất ròng bằng VNĐ → đề xuất bản sửa, mọi bản sửa được kiểm chứng lại → người duyệt ký, có audit log.

> RingForge không phát hiện kẻ gian. RingForge phát hiện sai sót trong các chính sách được tạo ra để ngăn kẻ gian.

- **Sản phẩm:** _(link production — điền sau khi deploy)_ · không cần tài khoản.
- **API công khai:** `<API>/docs` (Swagger, có ví dụ `curl`) · **Video:** _(điền khi có)_
- Dự thi MoMo Tech Contest 2026. **Toàn bộ dữ liệu là dữ liệu tổng hợp**, không có dữ liệu thật hay PII; Policy Pack là bản giả lập có dẫn nguồn, không phải diễn giải pháp lý chính thức. Đặc tả chi tiết ở [`docs/`](docs/00_README.md).

## Tính năng và 3 demo

| Demo | Thao tác | Hệ thống chỉ ra |
|---|---|---|
| **1 — Lỗi chuyên viên bỏ sót** (Rule Studio) | Gõ "khách thân thiết… thì không cần xác thực thêm" | Luật miễn trừ phá INV-AUTH-01/02; phản ví dụ **10.000.001 đ**; số giao dịch/số tiền trong dữ liệu rơi vào vùng lỗi; bản sửa tham chiếu tham số, đã kiểm chứng lại |
| **2 — Quy định thay đổi** (Policy Pack) | Hạ ngưỡng sinh trắc học/lần 10 → 5 triệu (giả lập) | LG-07 viết cứng 10.000.000 bị báo không còn tương thích kèm nhân chứng; REG-01 tự thích ứng; +85 giao dịch thật phải sinh trắc học; semantic diff (VC-07) |
| **3 — Chọn luật ít tổn thất nhất** (So sánh) | So 4 phương án luật chặn khoản nạn nhân → mule: cửa sổ 15/30/60 phút, giữ hay chặn | Bảng L_net, lọt gian lận, chặn nhầm; biểu đồ thành phần; phân rã kịch bản; kéo thanh trượt giả định thì thứ hạng đổi; chỉ phương án qua cổng invariant được xếp hạng |

Ngoài 3 demo — dùng như công cụ thật:
- **Nhập/xuất JSON** bộ luật + Policy Pack (màn Bộ luật), kiểm chứng ngay sau khi nhập.
- **Change set + phê duyệt** (màn Duyệt): kiểm chứng lại lúc duyệt, nút phê duyệt khóa khi FAIL; **shadow** trên ngày 7 (ngày không dùng cho backtest); tóm tắt cho người duyệt (AI viết lời, mọi con số được đối chiếu với số liệu hệ thống); **audit** ghi người, AI (model, phiên bản prompt, hash prompt), hệ thống.
- **API công khai không cần phiên:** `POST /verify`, `POST /backtest`, `GET /catalog`; giới hạn 60 yêu cầu/phút/IP.
- Guided tour cho cả 3 demo; chế độ dự phòng khi AI không khả dụng (kiểm chứng, sửa tất định, backtest, duyệt không cần AI).

## Kiến trúc

```
apps/web/  Next.js (App Router) + TypeScript + Tailwind + Recharts ──HTTPS/JSON──► services/api/  FastAPI
                                                                                  ├─ dsl/       schema, validator VC-01, câu tiếng Việt từ AST
                                                                                  ├─ verify/    Z3: VC-03…VC-07, phản ví dụ, grounding, sửa tất định, tác động pack
                                                                                  ├─ backtest/  interpreter pandas, L_net số nguyên, shadow
                                                                                  ├─ ai/        LLM: biên dịch, đề xuất sửa, tóm tắt (JSON Schema strict)
                                                                                  └─ store/     SQLite/Postgres: phiên, luật, pack, change set, ai_calls, audit
```

**Ranh giới AI / tất định**

| AI (LLM) được làm | Chỉ code tất định làm |
|---|---|
| Biên dịch tiếng Việt → DSL, nêu giả định cho cụm mơ hồ | Kết luận đạt/không đạt (Z3), phản ví dụ |
| Đề xuất bản sửa (tối đa 3) | Kiểm chứng lại, backtest, xếp hạng mọi bản sửa; bản không qua bị loại, có ghi lý do |
| Viết lời tóm tắt cho người duyệt | Mọi con số: tiền (int VNĐ), số giao dịch, tỷ lệ (basis points) |
| — | Bật luật, sửa Policy Pack (chỉ khi người dùng xác nhận) |

Output AI luôn qua JSON Schema + validator ngữ nghĩa; không `eval`/`exec`; nội dung người dùng đặt trong khối dữ liệu riêng (chống prompt injection). Interpreter pandas và encoder Z3 cho cùng kết quả trên 5.000 giao dịch (property test).

## Chạy local

Yêu cầu: Python 3.11 (khuyến nghị [uv](https://docs.astral.sh/uv/)), Node.js ≥ 20.

```bash
# API — http://localhost:8000/docs
cd services/api
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
python -m app.data.generate        # sinh data/seed/transactions.parquet (tất định, seed 20261203)
pytest -q
uvicorn app.main:app --reload --port 8000
```

```bash
# Web — http://localhost:3000
cd apps/web
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install && npm run dev
npm run lint && npm run build
```

```bash
# API bằng Docker (giống môi trường deploy) — chạy từ GỐC REPO vì image cần data/seed/
docker build -f services/api/Dockerfile -t ringforge-api .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=http://localhost:3000 ringforge-api
```

Có LLM key (đặt trong `.env`, đã gitignore):

```bash
# Đo biên dịch trên 10 câu tune → eval/tune_report.md
services/api/.venv/bin/python eval/run_tune.py
```

```bash
# Ghi sẵn kết quả AI cho câu mẫu (chế độ dự phòng) → data/seed/ai_cache.json
services/api/.venv/bin/python eval/build_ai_cache.py
```

```bash
# Ablation A/G/B/C/D trên 30 case test → eval/report.md, eval/results.json (không có key: chỉ chạy A, G)
services/api/.venv/bin/python eval/run_ablation.py --configs A,G,B,C,D --split test --runs 2
```

## Biến môi trường

Xem [`.env.example`](.env.example) (đầy đủ), `services/api/.env.example`, `apps/web/.env.example`. Không bao giờ commit giá trị thật.

| Biến | Ý nghĩa |
|---|---|
| `APP_ENV` | `dev` · `staging` · `production` |
| `CORS_ORIGINS` | Origin web được gọi API, phân tách bằng dấu phẩy, không dùng `*` |
| `DATABASE_URL` | Postgres (Neon/Supabase). Trống = SQLite trong thư mục tạm (mất khi khởi động lại) |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODEL_FALLBACK` | LLM phía server (hiện hỗ trợ OpenAI, Structured Outputs) |
| `LLM_DAILY_CALL_CAP`, `LLM_SESSION_DAILY_CAP` | Hạn mức gọi LLM toàn hệ thống / mỗi phiên mỗi ngày (mặc định 500 / 40) |
| `RATE_LIMIT_PER_MIN` | Giới hạn yêu cầu/phút/IP (mặc định 60; 0 = tắt) |
| `NEXT_PUBLIC_API_URL` | URL API cho web (nhúng lúc build) |

Không có key LLM, sản phẩm vẫn chạy: biên dịch bằng AI báo không khả dụng (câu mẫu dùng kết quả đã lưu nếu có), mọi phần kiểm chứng, sửa tất định, backtest, duyệt vẫn hoạt động.

## Dùng API

```bash
API=http://localhost:8000
# Danh mục 21 trường của Policy DSL, toán tử, nhãn tiếng Việt
curl -s "$API/catalog"
```

```bash
# Kiểm chứng luật Demo 1 + bộ luật seed → FAIL kèm phản ví dụ amount = 10.000.001
curl -s -X POST "$API/verify" -H 'Content-Type: application/json' -d '{
  "include_seed_rules": true,
  "rules": [{"id": "DRAFT-0001", "name": "Fast-path khách thân thiết", "kind": "FRICTION", "status": "CANDIDATE",
             "when": {"all": [{"field": "sender_account_age_days", "op": ">", "value": 365},
                              {"field": "receiver_is_familiar", "op": "==", "value": true}]},
             "then": {"exempt_auth": true}}]
}'
```

```bash
# Backtest một luật mới: L_net (đ) và chênh lệch so với bộ luật seed
curl -s -X POST "$API/backtest" -H 'Content-Type: application/json' -d '{
  "rules": [{"id": "FR-05", "name": "Tài khoản nhận mới gom tiền", "kind": "FRAUD", "status": "CANDIDATE",
             "when": {"all": [{"field": "receiver_account_age_days", "op": "<", "value": 14},
                              {"field": "receiver_distinct_senders_60m", "op": ">=", "value": 2},
                              {"field": "channel", "op": "==", "value": "P2P"}]},
             "then": {"decision": "HOLD", "hold_seconds": 120}}]
}'
```

`verdict`: `PASS` · `PASS_WITH_WARNINGS` · `FAIL` · `UNKNOWN` (Z3 hết thời gian — **không bao giờ coi là đạt**). Muốn lưu trạng thái (Policy Pack, change set, audit): `POST /sessions` rồi dùng `/sessions/{sid}/…`.

## Dữ liệu

- **100% tổng hợp** do đội sinh bằng [`services/api/app/data/generate.py`](services/api/app/data/generate.py), seed cố định `20261203`, ~19.700 giao dịch 7 ngày: giao dịch bình thường, mạng mule rải lệnh, chiếm tài khoản ngủ đông, flash-sale hợp lệ, khách thân thiết chuyển lớn. Ngày 1–6 cho backtest, ngày 7 cho shadow.
- Đặc trưng tính chống leakage (chỉ từ giao dịch trước đó). Chủ ý không có giao dịch nào đúng 10.000.000 đ để minh họa lỗi mà backtest không bắt được nhưng Z3 bắt được.
- Không dữ liệu cá nhân; ID tổng hợp. Policy Pack là **giả lập có dẫn nguồn** (QĐ 2345/QĐ-NHNN) — điểm "trên"/"từ" 10 triệu cần đối chiếu văn bản gốc.

## Đánh giá

[`eval/report.md`](eval/report.md): 30 case test tổng hợp do đội tự viết (gold viết trước khi chạy model), 10 case tune tách riêng.

- **Đã chạy (không cần AI):** trên cùng các luật gold, chỉ backtest (cấu hình A) đạt recall 53% — bỏ sót INV-AUTH-01 ở 3/7 case vì dữ liệu không có giao dịch vùng đó, không phát hiện được luật thừa/xung đột miễn trừ, báo nhầm "luật chết" với luật hiếm. Cấu hình G (gold + Z3) khớp 100%, nhưng đó **không phải** bằng chứng độc lập vì gold được đối chiếu với bộ kiểm chứng khi viết fixture.
- **Chưa chạy:** B (LLM thuần), C (RingForge), D (RingForge sửa tất định) — cần LLM key. Chưa có số nào về đóng góp của AI; sẽ cập nhật khi chạy.

## Hạn chế

- Dữ liệu tổng hợp; không tuyên bố hiệu quả trên dữ liệu thật hay "giảm X% tổn thất".
- Z3 chứng minh trên mô hình **một giao dịch** với các invariant đã viết; không chứng minh tỷ lệ chặn nhầm (do backtest đo), không kiểm hành vi chuỗi giao dịch theo thời gian, không bảo đảm invariant phản ánh đúng luật pháp.
- DSL là tập con có thể kiểm chứng (số nguyên, boolean, enum hữu hạn); chưa có điều kiện chuỗi thời gian tùy ý.
- Không RBAC: vai "người đề xuất"/"người duyệt" chỉ mô phỏng.

## Deploy

Thứ tự: deploy API → lấy URL API → deploy web với URL đó → lấy domain web → cập nhật `CORS_ORIGINS` của API.

### API trên Render (Docker)

Nhanh nhất: **New → Blueprint** → chọn repo; Render đọc [`render.yaml`](render.yaml) (Docker, build context gốc repo, `/health`, build filter) và hỏi các biến bí mật (`CORS_ORIGINS`, `DATABASE_URL`, `LLM_*`). Hoặc tạo tay:

1. **New → Web Service** → chọn repo GitHub.
2. **Language/Runtime**: Docker · **Root Directory**: để trống (gốc repo) · **Dockerfile Path**: `./services/api/Dockerfile` · **Docker Build Context Directory**: `.` — image cần `data/seed/` ở gốc repo. **Build Filters → Included Paths**: `services/api/**`, `data/seed/**`.
3. **Instance type**: gói trả phí thấp nhất, **không sleep** (docs/06 mục 5). Nếu dùng Free: service ngủ sau 15 phút không có request → monitor UptimeRobot gọi `https://<service>.onrender.com/health` mỗi 5 phút (`/health` nhận cả GET và HEAD), giữ đến hết 11/12. Free có 750 giờ/tháng mỗi workspace: chỉ đủ **một** service chạy 24/7.
4. **Health Check Path**: `/health`.
5. **Environment**: `APP_ENV` = `production`; `CORS_ORIGINS` = `https://<project>.vercel.app`; `DATABASE_URL` = chuỗi kết nối Postgres (Neon/Supabase — không đặt thì phiên sandbox mất khi service khởi động lại); `LLM_*` nếu có key. Không cần đặt `PORT`.
6. Kiểm tra: `curl https://<service>.onrender.com/health` và các lệnh ở mục "Dùng API".

### Web trên Vercel

1. **Add New → Project** → chọn repo · **Root Directory**: `apps/web` · Framework: Next.js.
2. **Environment Variables**: `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com` (không có `/` cuối). Đổi giá trị thì phải **Redeploy**.
3. Lấy domain Vercel → cập nhật `CORS_ORIGINS` trên Render → mở web, phải thấy **"API ok"**.

## Công cụ AI

- **Dùng khi phát triển:** **Claude Code** (Anthropic, model Claude Opus 5.5) hỗ trợ dựng khung, viết mã, test và tài liệu theo đặc tả trong `docs/`; prompt các phiên làm việc lưu ở [`KICKOFF_PROMPTS.md`](KICKOFF_PROMPTS.md). Mọi thay đổi do đội đọc lại và chịu trách nhiệm.
- **Dùng trong sản phẩm:** OpenAI qua Responses API với Structured Outputs (JSON Schema strict); model đặt bằng `LLM_MODEL`/`LLM_MODEL_FALLBACK`, sẽ chốt sau khi chạy `eval/run_tune.py` và ghi lại tại đây. Prompt có phiên bản: `compile.v1`, `repair.v1`, `summary.v1` (`services/api/app/ai/prompts/`).

## Tài sản có sẵn

Không dùng template hay thư viện component UI có sẵn. Khung ban đầu của web tạo bằng `create-next-app` (Next.js). Bảng màu biểu đồ dùng bảng màu phân loại mặc định của hướng dẫn trực quan hóa dữ liệu, đã kiểm độ tương phản và mù màu.

## Thư viện mã nguồn mở

| Thư viện | Dùng cho | License |
|---|---|---|
| FastAPI | API HTTP | MIT |
| Uvicorn | ASGI server | BSD-3-Clause |
| Pydantic | Schema, validate | MIT |
| z3-solver | Kiểm chứng hình thức (SMT) | MIT |
| pandas | Backtest | BSD-3-Clause |
| NumPy | Tính toán mảng | BSD-3-Clause |
| PyArrow | Đọc/ghi Parquet | Apache-2.0 |
| SQLAlchemy | Truy cập CSDL (SQLite/Postgres) | MIT |
| psycopg 3 | Driver Postgres | LGPL-3.0 |
| OpenAI Python SDK | Gọi LLM | Apache-2.0 |
| python-dotenv | Đọc `.env` | BSD-3-Clause |
| pytest, HTTPX | Kiểm thử | MIT, BSD-3-Clause |
| Next.js, React | Giao diện | MIT |
| Tailwind CSS | Style | MIT |
| Recharts | Biểu đồ so sánh L_net (Demo 3) | MIT |

## Thành viên

_(Điền tên, vai trò và phần đóng góp thực tế của từng thành viên — docs/09 mục 5 yêu cầu ghi trung thực.)_
