# RingForge — Bộ tài liệu triển khai

**AI Safety Compiler for Financial Risk Policies**
Phiên bản tài liệu: 1.0 · Ngày: 26/11/2026 · Dựa trên bản chốt RingForge v3 của đội

---

## ⚠️ Ba việc sống còn trong 24 giờ tới (làm trước khi code)

1. ~~Đăng ký đội~~ **Đã đăng ký (26/11).** Còn lại: kiểm tra email xác nhận của BTC trong 24 giờ (cả thư mục spam); chưa có thì email techday@mservice.com.vn trước 23:59:59 ngày 27/11. Nhớ: chung kết 11/12 tại TP.HCM cần đủ thành viên.
2. **Gửi câu hỏi cho BTC** (techday@mservice.com.vn) trước 23:59:59 ngày 27/11. Danh sách ở `10_SUBMISSION_AND_PITCH.md` mục 6. Tên ba chủ đề đã có trong đề chính thức; câu hỏi quan trọng nhất còn lại là **dữ liệu tổng hợp có được chấp nhận** và **khởi động lại máy chủ sau hạn nộp** khi có sự cố.
3. **Deploy "hello world" cả web lẫn API ngay tối 26/11.** Rủi ro deploy Z3 + FastAPI phải lộ ra ở ngày đầu, không phải ngày cuối.

---

## Danh sách tài liệu

| File | Nội dung | Dùng khi |
|---|---|---|
| `01_PRD.md` | Bài toán, người dùng, phạm vi, yêu cầu chức năng có mã ID, NFR, demo, rủi ro | Đọc đầu tiên; mọi tranh cãi về scope quay về đây |
| `02_POLICY_DSL_SPEC.md` | Ngữ pháp DSL, danh mục trường, ngữ nghĩa quyết định, Policy Pack | Viết schema, interpreter, prompt |
| `03_VERIFICATION_SPEC.md` | Các phép kiểm chứng, mã hóa Z3, phản ví dụ, giới hạn | Viết module verify |
| `04_DATA_AND_BACKTEST_SPEC.md` | Bộ sinh dữ liệu, kịch bản, đặc trưng chống leakage, công thức L_net | Viết generator và backtester |
| `05_AI_SPEC.md` | Các tác vụ LLM, schema output, prompt khung, guardrail, fallback | Viết module AI |
| `06_ARCHITECTURE_API.md` | Kiến trúc, cấu trúc repo, data model, API, deploy, bảo mật | Dựng dự án |
| `07_UI_UX_SPEC.md` | Màn hình, luồng, guided tour, copy tiếng Việt | Viết frontend |
| `08_EVALUATION_PLAN.md` | Fixture, ablation A/B/C/D, chỉ số, cách báo cáo trung thực | Ngày 01/12 |
| `09_IMPLEMENTATION_PLAN.md` | Lịch làm việc từng ngày cho một người, task có ước lượng, điểm cắt scope, việc giao thành viên 2 | Hằng ngày |
| `10_SUBMISSION_AND_PITCH.md` | Checklist nộp bài, dàn ý slide 10 trang, kịch bản video 3 phút, README mẫu, câu hỏi BTC | 02–03/12 |

Thứ tự đọc khi bắt đầu code: 01 → 02 → 03 → 04 → 06 → 09. Các file còn lại đọc khi tới phần việc tương ứng.

---

## Quyết định kỹ thuật đã chốt (decision log)

| # | Quyết định | Lý do | Xem lại nếu |
|---|---|---|---|
| D1 | Backend **Python FastAPI**, frontend **Next.js** | `z3-solver` bản Python ổn định nhất; pandas/numpy cho backtest | Deploy Python thất bại trong spike tối 26/11 |
| D2 | **Bộ sinh dữ liệu tự viết** là nguồn chính; PaySim **tắt mặc định** | Kiểm soát nhãn, khớp ràng buộc VN (10 tr/lần, 20 tr/ngày); PaySim là tiền tệ và phân phối châu Phi, ghép tốn công | Còn dư thời gian sau 01/12 |
| D3 | Ngữ nghĩa quyết định theo **lattice lấy max**, có cờ `exempt_auth` | Đơn giản, mã hóa Z3 dễ, và tái hiện đúng loại lỗi thật: "luật ưu tiên/miễn trừ" vô hiệu hóa xác thực bắt buộc | — |
| D4 | **Invariant pháp lý là cổng cứng**; L_net chỉ tối ưu giữa các phương án đã qua cổng | Vi phạm quy định không phải đánh đổi tiền | — |
| D5 | LLM **không** tính tiền, **không** tự bật luật, **không** sinh code chạy | An toàn và giải trình | — |
| D6 | Mỗi giám khảo có **sandbox riêng** (clone từ seed) + nút Reset | Giám khảo không phá dữ liệu của nhau | — |
| D7 | Có **chế độ dự phòng**: kết quả LLM cho đầu vào mẫu được cache sẵn; có repair tất định khi LLM lỗi | Demo không chết khi API LLM lỗi hoặc hết hạn mức | — |
| D8 | Đồ thị Cytoscape là **P2** | Bản v3 đặt graph thành tính năng phụ | — |
| D9 | Tiền là **số nguyên VNĐ**; xác suất là **basis points** (0–10.000) | Không có float trong tính tiền | — |
| D10 | Các tham số pháp lý nằm trong **Policy Pack có phiên bản**, luật tham chiếu tham số, không viết cứng số | Thích ứng khi quy định đổi | — |

---

## Quy ước

- **[V]** đã xác minh có nguồn · **[H]** giả thuyết cần kiểm chứng · **[GL]** số liệu giả lập hoặc giả định mặc định cho demo.
- **P0** bắt buộc cho bài nộp · **P1** nên có · **P2** chỉ làm nếu dư thời gian.
- Mọi số liệu "kết quả" chỉ được viết vào slide sau khi chạy thật trên fixture, ghi rõ là dữ liệu tổng hợp.
