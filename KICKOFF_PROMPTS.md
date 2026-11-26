# Prompt mở đầu cho Claude Code

Mẹo chung:
- Mỗi ngày mở một phiên mới; `CLAUDE.md` tự được nạp.
- Với task lớn, bật **plan mode** trước (Shift+Tab) để xem kế hoạch rồi mới cho viết code.
- Việc Claude Code không làm thay bạn được: tạo tài khoản Render/Vercel/Supabase, nhập API key, bấm deploy lần đầu trên web dashboard.

---

## Phiên 1 — tối 26/11 (Ngày 0: T0.3 → T0.5)

```
Đọc CLAUDE.md và docs/00_README.md, docs/06_ARCHITECTURE_API.md, docs/09_IMPLEMENTATION_PLAN.md (phần Ngày 0).

Làm các task T0.3, T0.4 (phần code), T0.5:

1. Dựng monorepo theo cấu trúc ở docs/06 mục 2 (chỉ tạo phần cần cho hôm nay):
   - services/api: FastAPI với GET /health trả {status, z3_version, app_env}; CORS đọc từ env CORS_ORIGINS;
     requirements.txt; Dockerfile (python:3.11-slim, chạy uvicorn trên ${PORT:-8000}); .dockerignore.
   - apps/web: Next.js App Router + TypeScript + Tailwind (dùng create-next-app), trang chủ gọi
     NEXT_PUBLIC_API_URL/health và hiển thị kết quả.
   - .gitignore, .env.example (gốc và từng app), README.md ngắn.
2. Spike Z3 (T0.5): services/api/app/spike_z3.py mã hóa tối thiểu theo docs/03:
   các biến amount, daily_total_after, sender_account_age_days, receiver_is_familiar; ràng buộc miền;
   REG-01, REG-02 (auth BIOMETRIC theo tham số 10.000.000 và 20.000.000); luật DRAFT miễn xác thực
   cho tuổi > 365 ngày và người nhận quen. Kiểm INV-AUTH-01 và INV-AUTH-02 bằng Optimize
   (minimize amount/daily_total rồi tuổi). Kỳ vọng phản ví dụ amount = 10000001 và daily_total_after = 20000001.
   Thêm bản luật đã sửa (giới hạn amount <= ngưỡng và daily_total_after <= ngưỡng) → kỳ vọng cả hai unsat.
   Endpoint GET /spike/z3 trả kết quả. Viết tests/test_spike_z3.py khẳng định các kỳ vọng trên.
3. Chạy pytest, chạy uvicorn và gọi thử /health, /spike/z3. Build thử Docker image nếu máy có Docker.
4. Viết hướng dẫn deploy ngắn trong README: Render (Root Directory services/api, Docker, env APP_ENV,
   CORS_ORIGINS) và Vercel (Root Directory apps/web, env NEXT_PUBLIC_API_URL).

Không làm gì ngoài Ngày 0. Commit theo task ID.
```

Sau phiên này **bạn tự làm**: tạo repo GitHub, push, tạo service trên Render và project trên Vercel, đặt env, kiểm tra web gọi được API qua link public. Đo thời gian cold start và RAM của API.

---

## Phiên 2 — 27/11 (Ngày 1: T1.1 → T1.6)

```
Đọc CLAUDE.md, docs/02, docs/03, docs/04, docs/09 (Ngày 1). Bật plan mode và trình bày kế hoạch trước.

Làm T1.1 → T1.6 theo đúng DoD:
- T1.1 app/dsl: catalog.py (17 trường, miền, nhãn tiếng Việt), schema.py (Pydantic theo docs/02),
  validator.py (VC-01), render_vi.py; data/seed/rules.json + policy_pack.json theo docs/02 mục 5–6.
- T1.2 app/data: generate.py, scenarios.py (S0–S4), features.py (chống leakage), xuất parquet, seed 20261203.
- T1.3 app/backtest/interpreter.py theo lattice docs/02 mục 3.
- T1.4 app/verify/encoder.py + checks.py (VC-03, VC-04) + optimize.py (phản ví dụ dễ đọc).
- T1.5 property test interpreter ≡ Z3 trên 5.000 mẫu.
- T1.6 GET /catalog, POST /verify.
Viết test theo docs/03 mục 6 và docs/04 mục 8. Báo lại test nào xanh, cái gì còn dở.
```

---

## Mẫu prompt cho các ngày sau

```
Đọc CLAUDE.md và docs/09 (Ngày N), cùng các file spec liên quan: <liệt kê>.
Trạng thái hiện tại: <task nào xong, link staging, lỗi đang gặp>.
Làm <T?.?> → <T?.?> theo DoD. P0 trước. Nếu ước lượng không kịp trong ngày, đề xuất điểm cắt theo docs/09 mục 4.
Chạy test trước khi báo xong.
```

## Prompt rà soát cuối ngày

```
Rà soát những gì đã làm hôm nay so với DoD trong docs/09 và các quy tắc trong CLAUDE.md:
tiền có dùng float ở đâu không, LLM có chạm vào số liệu không, property test interpreter ≡ Z3 còn xanh không,
có secret nào trong git không. Liệt kê vấn đề, chưa sửa.
```
