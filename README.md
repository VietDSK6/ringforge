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
