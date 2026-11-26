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
# API bằng Docker (giống môi trường deploy)
cd services/api
docker build -t ringforge-api .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=http://localhost:3000 ringforge-api
```

## Deploy

Thứ tự: deploy API → lấy URL API → deploy web với URL đó → lấy domain web → cập nhật `CORS_ORIGINS` của API.

### API trên Render (Docker)

1. **New → Web Service** → chọn repo GitHub.
2. **Root Directory**: `services/api` · **Language/Runtime**: Docker (Render tự dùng `services/api/Dockerfile`).
3. **Instance type**: gói trả phí thấp nhất, **không sleep** (docs/06 mục 5). Free tier sleep sau một lúc không có request → giám khảo phải chờ cold start.
4. **Health Check Path**: `/health`.
5. **Environment**:
   - `APP_ENV` = `staging` (bản nộp: `production`)
   - `CORS_ORIGINS` = `https://<project>.vercel.app` (nhiều origin phân tách bằng dấu phẩy, ví dụ thêm `http://localhost:3000` khi cần gọi từ máy local; không dùng `*`)
   - Không cần đặt `PORT`: Render tự cấp, container đọc `${PORT:-8000}`.
6. Deploy xong kiểm tra: `curl https://<service>.onrender.com/health` và `/spike/z3`.

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
| `/spike/z3` | trường `ms` trong response | 22 ms | |

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
