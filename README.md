# RingForge

**CI/CD cho chính sách rủi ro** dành cho đội vận hành chống gian lận ở ví điện tử/ngân hàng số. Người dùng viết luật bằng tiếng Việt → LLM biên dịch thành Policy DSL (JSON) → Z3 kiểm chứng các invariant pháp lý (ví dụ xác thực sinh trắc học bắt buộc) và trả phản ví dụ → backtest trên dữ liệu tổng hợp tính tổn thất ròng (VNĐ) → đề xuất sửa đã được kiểm chứng lại → người duyệt, có audit log.

Dự án dự thi MoMo Tech Contest 2026. Toàn bộ dữ liệu là **dữ liệu tổng hợp**, không có dữ liệu thật hay PII. Đặc tả chi tiết ở [`docs/`](docs/00_README.md).

## Cấu trúc

```
apps/web/        Next.js (App Router) + TypeScript + Tailwind — giao diện
services/api/    FastAPI + Pydantic + z3-solver + pandas — DSL, kiểm chứng, backtest
docs/            Bộ tài liệu đặc tả (nguồn sự thật)
```

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
```

Biến môi trường: xem [`.env.example`](.env.example) (đầy đủ), `services/api/.env.example`, `apps/web/.env.example`.

```bash
# API bằng Docker (giống môi trường deploy) — chạy từ GỐC REPO vì image cần data/seed/
docker build -f services/api/Dockerfile -t ringforge-api .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=http://localhost:3000 ringforge-api
```

## Dùng API

Tài liệu tương tác (OpenAPI, có ví dụ): `<API>/docs`. Mọi số tiền là số nguyên VNĐ.

```bash
# Danh mục trường của Policy DSL (17 trường, toán tử, nhãn tiếng Việt)
curl -s http://localhost:8000/catalog
```

```bash
# Kiểm chứng: luật Demo 1 + toàn bộ luật seed đang chạy → FAIL kèm phản ví dụ amount = 10.000.001
curl -s -X POST http://localhost:8000/verify -H 'Content-Type: application/json' -d '{
  "include_seed_rules": true,
  "rules": [{
    "id": "DRAFT-0001", "name": "Fast-path khách thân thiết", "kind": "FRICTION", "status": "CANDIDATE",
    "when": {"all": [
      {"field": "sender_account_age_days", "op": ">", "value": 365},
      {"field": "receiver_is_familiar", "op": "==", "value": true}
    ]},
    "then": {"exempt_auth": true}
  }]
}'
```

`/verify` nhận `rules` (tối đa 50 luật), `include_seed_rules` (gộp luật seed; luật gửi lên cùng `id` thay luật seed) và `policy_pack` (bỏ trống = Policy Pack seed). Kết quả: `verdict` (`PASS` · `PASS_WITH_WARNINGS` · `FAIL` · `UNKNOWN` khi Z3 hết thời gian — không bao giờ coi là đạt), `checks` (VC-01 lỗi cú pháp/kiểu, VC-03 luật chết, VC-04 vi phạm invariant kèm phản ví dụ và luật gây lỗi), `rules_vi` (câu tiếng Việt của từng luật).

## Deploy

Thứ tự: deploy API → lấy URL API → deploy web với URL đó → lấy domain web → cập nhật `CORS_ORIGINS` của API.

### API trên Render (Docker)

1. **New → Web Service** → chọn repo GitHub.
2. **Language/Runtime**: Docker · **Root Directory**: để trống (gốc repo) · **Dockerfile Path**: `./services/api/Dockerfile` · **Docker Build Context Directory**: `.` — image cần `data/seed/` ở gốc repo. **Build Filters → Included Paths**: `services/api/**`, `data/seed/**` để sửa web không làm API deploy lại.
3. **Instance type**: gói trả phí thấp nhất, **không sleep** (docs/06 mục 5). Nếu dùng Free: service ngủ sau 15 phút không có request (thức lại mất khoảng 1 phút) → tạo monitor UptimeRobot HTTP(s) gọi `https://<service>.onrender.com/health` mỗi 5 phút (`/health` nhận cả GET và HEAD), giữ đến hết 11/12. Free có 750 giờ/tháng cho mỗi workspace: chỉ đủ cho **một** service chạy 24/7.
4. **Health Check Path**: `/health`.
5. **Environment**:
   - `APP_ENV` = `staging` (bản nộp: `production`)
   - `CORS_ORIGINS` = `https://<project>.vercel.app` (nhiều origin phân tách bằng dấu phẩy, ví dụ thêm `http://localhost:3000` khi cần gọi từ máy local; không dùng `*`)
   - Không cần đặt `PORT`: Render tự cấp, container đọc `${PORT:-8000}`.
6. Deploy xong kiểm tra: `curl https://<service>.onrender.com/health` và lệnh `/verify` ở mục "Dùng API" (đổi `localhost:8000` thành URL Render).

### Web trên Vercel

1. **Add New → Project** → chọn repo.
2. **Root Directory**: `apps/web` · Framework: Next.js (tự nhận).
3. **Environment Variables**: `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com` (không có `/` cuối).
4. Deploy. Biến `NEXT_PUBLIC_*` được nhúng vào bundle **lúc build**: đổi giá trị thì phải **Redeploy**.
5. Lấy domain Vercel → quay lại Render cập nhật `CORS_ORIGINS` → mở web, phải thấy **"API ok"**.

### Đo sau khi deploy (ghi lại cho quyết định D1)

| Chỉ số | Cách đo | Local (Docker, 26/11) | Render |
|---|---|---|---|
| Kích thước image | `docker images` / log build Render | 579 MB (arm64), 584 MB (amd64) | |
| RAM nhàn rỗi | `docker stats` / Render Metrics | ~59 MiB | |
| Thời gian sẵn sàng | container start → `/health` 200 | ~1 s | |
| Cold start | dòng "phản hồi sau … ms" trên trang chủ sau khi service nghỉ | — | |
| `/verify` Demo 1 | trường `ms` trong response | (đo sau) | |

## Công cụ AI dùng khi phát triển

- **Claude Code** (Anthropic, model Claude Opus 5.5): hỗ trợ dựng khung dự án, viết mã và test theo đặc tả trong `docs/`. Các prompt phiên làm việc lưu ở [`KICKOFF_PROMPTS.md`](KICKOFF_PROMPTS.md).
- Model LLM dùng trong sản phẩm: sẽ ghi khi tích hợp (Ngày 2).

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
| pytest, HTTPX | Kiểm thử | MIT, BSD-3-Clause |
| Next.js, React | Giao diện | MIT |
| Tailwind CSS | Style | MIT |

Danh sách sẽ được cập nhật khi thêm thư viện.
