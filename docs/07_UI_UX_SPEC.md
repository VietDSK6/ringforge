# 07 — Đặc tả UI/UX

Ngôn ngữ giao diện: tiếng Việt. Định dạng tiền `10.000.000 đ` (Intl `vi-VN`). Mục tiêu: giám khảo hiểu giá trị trong 2 phút mà không đọc tài liệu.

## 1. Nguyên tắc
- **Một câu chuyện mỗi màn hình**: luật → kiểm chứng → sửa → so sánh → duyệt.
- **Bằng chứng trước, kết luận sau**: phản ví dụ là một giao dịch cụ thể, kèm "trong dữ liệu có bao nhiêu".
- **Phân biệt rõ nguồn**: biểu tượng/nhãn cho nội dung do AI đề xuất, do người viết, do hệ thống tính. Số liệu luôn là "do hệ thống tính".
- **Không chặn người dùng bằng thông báo dài**; dùng badge và tooltip.
- Banner cố định trên cùng: "Sandbox · Dữ liệu tổng hợp · Không phải dữ liệu MoMo".

## 2. Bản đồ màn hình

```
/                     Landing: một câu giá trị + nút "Vào sandbox" + 3 thẻ demo
/s/[sid]/policies     Workspace: danh sách luật + trạng thái kiểm chứng toàn bộ + nút "Thêm luật bằng lời"
/s/[sid]/studio       Rule Studio: nhập tiếng Việt → luật → giả định → Kiểm chứng
/s/[sid]/verify/[id]  Báo cáo kiểm chứng + Sửa bằng AI
/s/[sid]/compare      So sánh phương án (backtest + thanh trượt)
/s/[sid]/pack         Policy Pack + phân tích tác động
/s/[sid]/review       Change set, phê duyệt, shadow, audit
```

Điều hướng: thanh bên trái (desktop) / tab dưới (mobile). Nút "Reset sandbox" ở menu.

## 3. Màn hình chi tiết

### 3.1 Landing
- Tiêu đề: "RingForge — kiểm chứng luật chống gian lận trước khi bật"
- Phụ đề: "Viết luật bằng tiếng Việt. Hệ thống chứng minh luật không phá quy định, tính tổn thất bằng VNĐ, và đề xuất bản sửa đã kiểm chứng."
- Nút chính: **Vào sandbox** (tạo phiên, chuyển tới guided tour).
- 3 thẻ: "Bắt lỗi chuyên viên bỏ sót" · "Quy định thay đổi" · "Chọn luật ít tổn thất nhất". Mỗi thẻ mở thẳng màn hình tương ứng với đầu vào điền sẵn.

### 3.2 Workspace
- Bảng luật: ID, tên, câu tiếng Việt rút gọn, loại (Pháp lý/Gian lận/Ma sát), trạng thái, khóa 🔒 với luật pháp lý.
- Thanh trạng thái toàn bộ: "Bộ luật đang chạy: ✅ Qua 3 invariant · ⚠ 1 luật thừa (LG-09)".
- Nút "Thêm luật bằng lời".

### 3.3 Rule Studio (Demo 1)
Bố cục 2 cột:
- **Trái:** textarea (placeholder là câu Demo 1), nút "Biên dịch". Bên dưới: 3 gợi ý câu khác để giám khảo bấm thử (ví dụ "Tài khoản mới dưới 7 ngày nhận tiền từ 5 người trong 1 giờ rồi chuyển đi gần hết thì giữ lại 2 phút").
- **Phải:** thẻ luật:
  - Câu tiếng Việt từ AST, phần "miễn xác thực" tô đỏ.
  - Danh sách **giả định** dạng chip có thể sửa ("người nhận quen = ≥ 3 lần/90 ngày").
  - `unsupported_parts` nếu có (vàng).
  - Tab JSON.
  - Nút chính **Kiểm chứng** (to, nổi).
- Trạng thái đang chạy: "AI đang biên dịch…" → "Đang kiểm chứng 3 invariant…" (hiển thị từng bước, tạo cảm giác pipeline thật).

### 3.4 Báo cáo kiểm chứng
- Badge lớn: ❌ **Không đạt** / ✅ Đạt / ⚠ Đạt có cảnh báo / ❔ Không kết luận được.
- Mỗi lỗi một thẻ:
  - Tiêu đề: "Vi phạm INV-AUTH-01 — sinh trắc học cho giao dịch trên ngưỡng/lần" + nguồn "QĐ 2345/QĐ-NHNN (giả lập)".
  - **Thẻ phản ví dụ**: trông như một giao dịch trong app (số tiền to, người gửi "tài khoản 366 ngày", người nhận "quen", giờ 10:00) → kết quả "Cho qua · không sinh trắc học" gạch đỏ.
  - Dòng grounding: "Trong 6 ngày dữ liệu: **X giao dịch · Y đ**" hoặc nổi bật "**0 giao dịch — backtest sẽ không phát hiện lỗi này**".
  - Luật gây lỗi: DRAFT-0001 (link).
- Nút **Sửa bằng AI**.
- Danh sách candidate:
  - Mỗi candidate: chiến lược, diff (dòng thêm xanh), badge "Đã kiểm chứng ✅", độ giữ ý định (%), L_net, Δ ma sát, nhãn nguồn "AI" hoặc "Tất định".
  - Dòng nhỏ: "2 đề xuất khác của AI bị loại vì không qua kiểm chứng" (bấm xem lý do).
  - Nút "Chọn bản này → tạo change set".

### 3.5 So sánh phương án (Demo 3)
- Luật gốc (chốt 27/11): luật mới FR-05 phía người nhận — giữ/chặn khoản chuyển cá nhân vào tài khoản nhận mới mở đang gom tiền từ nhiều người (nạn nhân → mule lớp 1), vì L_net chỉ tính tổn thất trên APP_VICTIM/ATO còn FR-01 chỉ chạm giao dịch MULE_LAYER. 2–4 biến thể điền sẵn: cửa sổ 15/30/60 phút, HOLD/BLOCK, có/không xét tuổi tài khoản nhận; giám khảo sửa được ngưỡng.
- Bảng: L_net · lọt gian lận · chặn nhầm (HOLD/BLOCK) · chi phí duyệt · mất do khách bỏ · exposure tuân thủ · nhãn "không hợp lệ" nếu exposure > 0. Hàng tốt nhất in đậm.
- Biểu đồ cột chồng (Recharts) thành phần L_net theo phương án.
- Bảng phân rã theo kịch bản (mule, chiếm tài khoản, flash-sale, khách thân thiết).
- Panel thanh trượt giả định (có tag "giả định — không phải số thật"): hiệu quả khoảng dừng, chi phí duyệt, tỷ lệ bỏ giao dịch, biên lợi nhuận. Kéo → tính lại (debounce 300 ms).

### 3.6 Policy Pack (Demo 2)
- Bảng tham số: tên, giá trị, nguồn, nút sửa. Bảng invariant: mã, mô tả tiếng Việt, nguồn.
- Sửa `biometric_per_tx_threshold` → nút **Phân tích tác động** → danh sách:
  - Luật tự thích ứng (tham chiếu tham số) ✅.
  - Luật **không còn tương thích** ❌ kèm phản ví dụ (ví dụ LG-07 viết cứng 10.000.000).
  - Thay đổi ma sát: "+N giao dịch hợp lệ phải sinh trắc học (trên dữ liệu 6 ngày)".
- Nút "Sửa bằng AI các luật bị ảnh hưởng" (P1) và "Áp dụng pack mới".
- (P1) Ô "Dán mô tả quy định mới" → AI đề xuất patch → hiển thị diff → xác nhận.

### 3.7 Review
- Change set: danh sách thay đổi, kết quả kiểm chứng, tóm tắt backtest, tóm tắt AI (P1, có nhãn).
- Hai nút theo vai: "Phê duyệt" / "Từ chối" + ô lý do. Nút phê duyệt **vô hiệu** khi kiểm chứng FAIL, tooltip giải thích.
- Sau phê duyệt: "Chạy shadow trên ngày 7" (P1) → bảng khác biệt.
- Timeline audit: người/AI/hệ thống, thời gian, hành động, phiên bản model.

## 4. Guided tour
- Overlay 4–5 bước cho mỗi demo (thư viện nhẹ hoặc tự viết): chỉ vào ô nhập → nút Biên dịch → nút Kiểm chứng → thẻ phản ví dụ → nút Sửa bằng AI.
- Luôn có "Bỏ qua hướng dẫn".
- Mỗi bước 1 câu ≤ 15 từ.

## 5. Trạng thái lỗi và dự phòng
| Tình huống | Hiển thị |
|---|---|
| LLM lỗi/hết lượt | Banner vàng "AI tạm thời không khả dụng — đang dùng kết quả đã lưu cho câu mẫu; sửa luật bằng JSON hoặc dùng sửa tất định" |
| Câu nhập không phải luật | "Mình chưa hiểu đây là luật rủi ro. Thử: …" + 2 gợi ý |
| Cần làm rõ | Hiện câu hỏi + chip giả định để chọn |
| Z3 timeout | Badge ❔ "Không kết luận được trong 5 giây — không coi là đạt" |
| API ngủ/chậm | Skeleton + "Đang khởi động máy chủ…" (lẽ ra không xảy ra nếu NFR-2 đạt) |

## 6. Thành phần dùng lại
`RuleSentence`, `AssumptionChips`, `VerdictBadge`, `CounterexampleCard`, `GroundingLine`, `CandidateCard`, `DiffView`, `MetricTable`, `LnetStackedBar`, `AssumptionSliders`, `SourceTag (AI/Người/Hệ thống/Tất định)`, `SandboxBanner`.

## 7. Mobile
Một cột; thẻ phản ví dụ và badge kết luận giữ nguyên; bảng so sánh cuộn ngang; thanh trượt dạng sheet.
