# CLAUDE.md — RingForge

Dự án thi MoMo Tech Contest 2026. **Hạn nộp: 03/12/2026 23:59:59 (GMT+7)** — mục tiêu nộp trước 20:00. Sau hạn không được sửa mã nguồn hay sản phẩm đã deploy.

## Sản phẩm trong một đoạn
RingForge là "CI/CD cho chính sách rủi ro" dành cho đội vận hành chống gian lận ở ví điện tử/ngân hàng số. Người dùng viết luật bằng tiếng Việt → LLM biên dịch thành Policy DSL (JSON) → Z3 kiểm chứng invariant (ví dụ xác thực sinh trắc học bắt buộc theo QĐ 2345) và trả phản ví dụ → backtest trên dữ liệu tổng hợp tính tổn thất ròng (VNĐ) → LLM đề xuất sửa, mọi bản sửa được kiểm chứng lại → người duyệt, audit log.

## Nguồn sự thật
Đọc tài liệu trong `docs/` trước khi làm bất kỳ phần nào; **không tự đổi đặc tả**. Nếu đặc tả mâu thuẫn hoặc thiếu, hỏi lại thay vì đoán.
- `docs/01_PRD.md` — yêu cầu (FR-xx, NFR-xx), 3 demo, ưu tiên P0/P1/P2
- `docs/02_POLICY_DSL_SPEC.md` — catalog trường, ngữ pháp, ngữ nghĩa lattice, Policy Pack, luật seed
- `docs/03_VERIFICATION_SPEC.md` — VC-01..07, mã hóa Z3, grounding, repair tất định
- `docs/04_DATA_AND_BACKTEST_SPEC.md` — generator, features chống leakage, công thức L_net
- `docs/05_AI_SPEC.md` — tác vụ LLM, schema output, guardrail, cache
- `docs/06_ARCHITECTURE_API.md` — cấu trúc repo, data model, API, deploy, bảo mật
- `docs/07_UI_UX_SPEC.md` — màn hình, copy tiếng Việt
- `docs/08_EVALUATION_PLAN.md` — fixture, ablation A/B/C/D
- `docs/09_IMPLEMENTATION_PLAN.md` — task theo ngày (T0.x … T6.x), DoD, điểm cắt scope

## Stack
- `services/api`: Python 3.11, FastAPI, Pydantic v2, z3-solver, pandas, numpy, pyarrow, pytest. Docker.
- `apps/web`: Next.js (App Router) + TypeScript + Tailwind + Recharts. Type API sinh từ OpenAPI.
- DB: Postgres (Supabase/Neon). Deploy: API trên Render/Railway (Docker), web trên Vercel.

## Quy tắc không được vi phạm
1. **Tiền là `int` VNĐ; tỷ lệ là basis points (int).** Không dùng float trong mọi phép tính tiền.
2. **LLM không bao giờ** tính tiền, đếm giao dịch, kết luận PASS/FAIL, tự bật luật, sửa Policy Pack mà không có xác nhận của người dùng, hay sinh code để chạy. Output LLM luôn qua JSON Schema + validator ngữ nghĩa.
3. **Interpreter (pandas) và encoder Z3 phải cho cùng kết quả** — luôn giữ property test xanh (`03` mục 6.1). Sửa một bên thì sửa bên kia.
4. Không `eval`/`exec` trên DSL hay output LLM; chỉ duyệt AST.
5. Z3 timeout → `UNKNOWN`, không bao giờ coi là PASS.
6. Không commit secret. Key chỉ ở `.env` (đã gitignore); cập nhật `.env.example` khi thêm biến.
7. Dữ liệu 100% tổng hợp, seed cố định; không thêm PII hay dữ liệu thật.
8. Không thêm trường nhãn (`label`, `scenario`) vào catalog DSL.
9. Giao diện và thông báo lỗi bằng tiếng Việt; định dạng tiền `vi-VN`.

## Cách làm việc
- Làm theo task ID trong `docs/09_IMPLEMENTATION_PLAN.md`; một task = một hoặc vài commit nhỏ, message dạng `T1.4: z3 encoder + VC-03/VC-04`.
- **P0 trước.** Không làm P1/P2 khi P0 của ngày chưa đạt DoD.
- Viết test cùng lúc với code cho: validator, encoder, interpreter, metrics, features. Chạy `pytest` trước khi báo xong.
- Ưu tiên đơn giản: không multi-agent, không thêm framework/thư viện nếu không cần; nếu thêm, ghi vào README mục OSS kèm license.
- Khi một task trễ, đề xuất điểm cắt theo `09` mục 4 thay vì làm vội.
- Cuối mỗi task: nêu ngắn đã làm gì, test nào chạy, còn gì dở.

## Lệnh (cập nhật khi repo có)
```bash
# API (máy dev không có sẵn Python 3.11 → dùng uv để khớp image python:3.11-slim)
cd services/api && uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt         # runtime pin ở requirements.txt; dev thêm pytest, httpx
pytest -q
uvicorn app.main:app --reload --port 8000      # http://localhost:8000/docs
python -m app.data.generate                    # (Ngày 1) sinh data/seed/transactions.parquet
docker build -t ringforge-api . && docker run --rm -p 8000:8000 ringforge-api

# Web
cd apps/web && npm install && npm run dev      # http://localhost:3000
npm run lint && npm run build
```

## Ghi chú cho README nộp bài
Ghi lại mọi công cụ AI dùng khi phát triển (Claude Code…) và model dùng trong sản phẩm; thể lệ yêu cầu khai báo tài sản có sẵn, thư viện mã nguồn mở, công cụ AI.
