# Dàn slide nộp bài (10 trang, PDF) — bản nháp

Theo docs/10 mục 2. Slide **không sửa được sau khi nộp** và dùng lại cho chung kết. Mỗi trang một ý, ít chữ, ảnh chụp sản phẩm thật.

Quy ước: mọi con số dưới đây do hệ thống tính trên dữ liệu tổng hợp (seed 20261203), đã chạy lại ngày 27/11; trước khi xuất PDF chạy lại lệnh ở cột "Nguồn" để chắc số không đổi. Mục đánh dấu **[CHỜ]** chưa có dữ liệu — không được điền số ước lượng.

Ảnh chụp: chụp trên link production, khổ 16:9, trình duyệt sáng (light), cửa sổ ~1440 px; tắt tour hướng dẫn (bấm "Bỏ qua hướng dẫn") trước khi chụp.

---

## 1. Tiêu đề

- **Chữ:** RingForge — kiểm chứng luật chống gian lận trước khi bật.
  Dòng phụ: Chủ đề An ninh mạng (chính) · Chống lừa đảo · Trợ lý AI. Người dùng: đội vận hành rủi ro ở ví điện tử / ngân hàng số. Tên đội **[CHỜ]**.
- **Hình:** ảnh Landing (tiêu đề + 3 thẻ demo).
- **Nói:** "Mỗi luật chống gian lận mới có thể vô tình tắt một lớp bảo vệ bắt buộc. RingForge bắt lỗi đó trước khi luật được bật."

## 2. Vấn đề

- **Chữ:** Một luật "fast-path cho khách thân thiết" — tài khoản trên 1 năm, chuyển cho người quen thì không cần xác thực thêm — vô tình bỏ sinh trắc học với giao dịch trên 10 triệu (QĐ 2345, giả lập).
  Backtest chỉ thấy lỗi **đã từng xảy ra** trong dữ liệu.
- **Số:** trên 6 ngày dữ liệu tổng hợp, luật này cho **90 giao dịch · 1.820.410.000 đ** đi qua mà không sinh trắc học (INV-AUTH-01) và **55 giao dịch · 1.259.000.000 đ** vượt ngưỡng ngày (INV-AUTH-02), trong đó **2 giao dịch của tài khoản bị chiếm**.
  Nguồn: `POST /verify` với luật Demo 1 + `include_seed_rules`.
- **Hình:** thẻ phản ví dụ 10.000.001 đ (Rule Studio sau khi Kiểm chứng).
- **Nói:** "Ở luật này dữ liệu có giao dịch trong vùng lỗi nên backtest cũng thấy. Nhưng với luật 'thanh toán QR cho merchant đã xác minh thì miễn xác thực', dữ liệu có **0 giao dịch** trong vùng vi phạm INV-AUTH-01 — backtest im lặng, Z3 vẫn chỉ ra giao dịch 10.000.001 đ." (Nguồn: `POST /verify` với luật đó + `include_seed_rules`.)

## 3. Hiện trạng và khoảng trống

- **Chữ:** Công cụ hiện có: viết luật bằng lời + backtest + shadow (Sardine, SEON, Oscilar).
  Thiếu: chứng minh **không tồn tại** giao dịch vi phạm, và chỉ ra giao dịch cụ thể khi có.
  Tiền lệ: SMT cho chính sách truy cập đám mây (AWS Zelkova, Cedar) — RingForge mang ý tưởng đó sang luật rủi ro thanh toán. Không tuyên bố "đầu tiên".
- **Hình:** bảng 2 cột "Backtest trả lời" / "Kiểm chứng hình thức trả lời".
- **Lưu ý:** kiểm lại link nguồn [V cần kiểm link] trong docs/01 mục 2.4 trước khi đưa tên sản phẩm lên slide.

## 4. Cơ chế

- **Chữ:** 5 bước: Biên dịch (AI) → Kiểm chứng (Z3) → Backtest (VNĐ) → Sửa (AI + tất định, kiểm chứng lại) → Duyệt (audit).
  Bảng ranh giới: AI biên dịch, nêu giả định, đề xuất sửa, viết lời tóm tắt · Code tất định: kết luận đạt/không đạt, mọi con số, bật luật.
- **Hình:** sơ đồ 5 ô một hàng (vẽ tay trên slide, không chụp).
- **Nói:** "AI đề xuất, code tất định quyết định. Không con số nào trên màn hình do AI đặt ra."

## 5. Demo 1 — lỗi chuyên viên bỏ sót

- **Hình (3 ảnh nhỏ, trái → phải):** câu tiếng Việt + luật biên dịch (có giả định) → báo cáo Không đạt + phản ví dụ 10.000.001 đ + dòng grounding → bản sửa đã kiểm chứng lại (độ giữ ý định 100%, dùng tham số ngưỡng).
- **Số:** bản sửa tất định giữ 100% giao dịch luật gốc nhắm tới ngoài vùng vi phạm; Δ L_net = 0 (luật miễn trừ không đổi tổn thất); thêm điều kiện "không quá ngưỡng sinh trắc học/lần và /ngày" bằng tham số.
  Nguồn: `POST /sessions/{sid}/repair` với luật Demo 1.
- **Nói:** "Giám khảo có thể đổi câu: 'trên 2 năm', 'người nhận là người thân' — kết quả vẫn đúng logic."
- **Ảnh phụ (nếu còn chỗ):** dòng "0 giao dịch trong N ngày dữ liệu — backtest sẽ không phát hiện" của luật QR merchant — thông điệp mạnh nhất (docs/03 mục 4).

## 6. Demo 2 + 3

- **Trái — Quy định đổi:** hạ ngưỡng 10 → 5 triệu (giả lập) → LG-07 viết cứng 10.000.000 bị báo không còn tương thích (nhân chứng 9.000.001 đ lúc 05:00); REG-01 tham chiếu tham số tự đúng; **+85 giao dịch thật** phải sinh trắc học; semantic diff: 186 giao dịch đổi kết quả trên 6 ngày. Nguồn: `POST /sessions/{sid}/pack/impact`.
- **Phải — Chọn luật:** luật chặn khoản nạn nhân → mule; cửa sổ 15/30/60 phút bắt **9/20/23** khoản nạn nhân; L_net: hiện hành 445.252.695 đ → giữ 60 phút 369.852.695 đ → chặn mọi tuổi tài khoản 294.547.465 đ (chặn nhầm 3 giao dịch thật). Đặt hiệu quả khoảng dừng = 100% thì "giữ 60 phút" lên hạng 1. Nguồn: màn So sánh / `POST /sessions/{sid}/backtest`.
- **Hình:** ảnh thẻ LG-07 + ảnh bảng/biểu đồ So sánh.

## 7. AI impact — ablation

- **Chữ:** bảng A/B/C/D trên 30 case tổng hợp (gold viết trước khi chạy model).
- **Đã có:** A (chỉ backtest, gold DSL): recall 53%, precision 62%; bỏ sót INV-AUTH-01 ở 3/7 case vì dữ liệu không có giao dịch vùng đó, không phát hiện luật thừa / xung đột miễn trừ.
  G (gold + Z3) khớp 100% — **ghi rõ** đây không phải bằng chứng độc lập vì gold được đối chiếu với bộ kiểm chứng.
- **[CHỜ]** B (LLM thuần), C (RingForge), D (sửa tất định): cần `LLM_API_KEY`, chạy `eval/run_ablation.py --configs A,G,B,C,D --runs 2`. Một câu kết luận trung thực theo số thật, kể cả khi D ≈ C.
- Nguồn: `eval/report.md`.

## 8. An toàn và tin cậy

- **Chữ:** LLM không tính tiền, không kết luận đạt/không đạt, không tự bật luật hay sửa Policy Pack; mọi đề xuất được kiểm chứng lại; tóm tắt AI bị loại nếu có con số không có trong dữ liệu; invariant là cổng cứng (không phê duyệt được change set FAIL); audit ghi model, phiên bản prompt, hash prompt.
  Giới hạn của Z3 (nói thẳng): mô hình một giao dịch, chỉ chứng minh các invariant đã viết, không đo tỷ lệ chặn nhầm.
- **Số:** interpreter pandas ≡ encoder Z3 trên 5.000 giao dịch (property test); 252 test tự động.
- **Hình:** ảnh màn Duyệt: nút phê duyệt bị khóa + timeline audit.

## 9. Tác động và mở rộng

- **Chữ — bám câu chữ của đề:** AI thay đổi cách **đội ngũ fintech** làm việc (luật được chứng minh trước khi bật) → **qua đó** người dùng ví: xác thực bắt buộc không bị vô hiệu hóa, ít bị chặn nhầm, gian lận bị giữ trước khi tiền đi.
  Mở rộng: tín dụng, AML, bảo hiểm; mô hình B2B. Ghi rõ là tiềm năng, chưa đo trên dữ liệu thật.
- **Hình:** chuỗi 3 ô: Đội rủi ro → Bộ luật đã chứng minh → Người dùng ví.

## 10. Hạn chế và bước tiếp

- **Chữ:** dữ liệu tổng hợp; mô hình một giao dịch (chưa điều kiện chuỗi thời gian); Policy Pack giả lập (đối chiếu "trên"/"từ" 10 triệu); chưa biết công cụ nội bộ MoMo; 1–2 case thất bại từ ablation **[CHỜ]**.
  Bước tiếp: điều kiện chuỗi thời gian; nhập luật từ hệ thống thật; phỏng vấn người làm risk/fraud (docs/10 mục 7) **[CHỜ nếu có]**.
- **Hình:** không cần; có thể đặt link sản phẩm + QR.

---

## Việc cần làm trước khi xuất PDF

1. Deploy, lấy link production; chụp ảnh theo từng slide.
2. Có key: chạy ablation đủ A/G/B/C/D (2 lần), điền slide 7 và case thất bại slide 10.
3. Điền tên đội, thành viên; kiểm link nguồn slide 3.
4. Chạy lại các lệnh ở cột "Nguồn" để xác nhận số; đối chiếu với `eval/report.md`.
5. Xuất PDF ≤ 10 trang; đọc lại toàn bộ vì không sửa được sau khi nộp.
