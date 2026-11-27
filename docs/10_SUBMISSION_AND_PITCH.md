# 10 — Hồ sơ nộp bài, slide, video, README, câu hỏi

## 1. Checklist nộp bài (theo đề chính thức)

Nộp qua Google Form của BTC: https://docs.google.com/forms/d/e/1FAIpQLSc0C4Zcc_ILiL-DEC-S5nYjgwH29vYtT9J-qAIMGe3DMcJH8A/viewform
Mở form sớm (ngày 02/12) để biết trước các trường cần điền, giới hạn dung lượng file và có cần đăng nhập Google không.

| Thành phần (đề) | Yêu cầu | Kiểm tra |
|---|---|---|
| **Sản phẩm** | Hướng dẫn sử dụng **tối đa 1 trang A4, PDF**, chứa link để giám khảo dùng trực tuyến ngay; kèm tài khoản thử nếu cần đăng nhập | RingForge không cần đăng nhập → ghi rõ "không cần tài khoản". Link mở được ở chế độ ẩn danh; uptime monitor bật đến hết 11/12 |
| **Mã nguồn** | **.zip toàn bộ mã nguồn**; README khai: cách chạy, công nghệ, **tài sản có sẵn, thư viện mã nguồn mở, công cụ AI đã dùng** | Không có `.env`, key; README đủ mục 4 bên dưới |
| **Tài liệu mô tả** | **Slide tối đa 10 trang, PDF**; nêu rõ **vấn đề và giải pháp**; dùng cho chung kết và **không được sửa sau khi nộp** | Duyệt kỹ trước khi nộp, vì không sửa được để pitch |
| **Video** | **Tối đa 3 phút, MP4**; quay **sản phẩm đang chạy thật**; phần quá 3 phút không được xem | Đặt độ dài 2:50 để an toàn; quay trên link production |

Đề yêu cầu sản phẩm là "**sử dụng được trực tuyến, không chỉ là bản trình diễn hay bản mẫu thử**". Hình thức có thể là ứng dụng, **dịch vụ API** hoặc công cụ. RingForge nên thể hiện cả hai: web app và API công khai có tài liệu (FR-S9).

Thể lệ (theo context đội đã đọc): một bài hợp lệ mỗi đội, bản nộp cuối trước hạn; không sửa bài/sản phẩm sau hạn; không dùng lại sản phẩm làm trước cuộc thi cho chính bài toán; khai báo tài sản có sẵn, OSS, công cụ AI, nguồn dữ liệu.

## 2. Dàn ý slide (10 trang)

1. **Tiêu đề + một câu**: "RingForge — kiểm chứng luật chống gian lận trước khi bật." Chủ đề: An ninh mạng (chính) · Chống lừa đảo · Trợ lý AI. Người dùng: đội vận hành rủi ro tại ví điện tử/ngân hàng số (đề yêu cầu nêu rõ đối tượng). Tên đội.
2. **Vấn đề**: mỗi luật mới có thể phá luật cũ hoặc phá quy định. Ví dụ một dòng: luật "fast-path khách thân thiết" vô tình bỏ sinh trắc học với giao dịch > 10 triệu (QĐ 2345). Backtest chỉ thấy lỗi đã từng xảy ra.
3. **Hiện trạng và khoảng trống**: công cụ hiện có (viết luật bằng lời + backtest + shadow: Sardine, SEON, Oscilar). Thiếu: chứng minh "**không tồn tại**" giao dịch vi phạm. Tiền lệ: SMT cho chính sách truy cập đám mây. RingForge mang tư tưởng đó sang luật rủi ro thanh toán.
4. **Cơ chế**: sơ đồ 5 bước (Biên dịch → Kiểm chứng → Backtest → Sửa → Duyệt). Ranh giới AI/tất định trong một bảng nhỏ.
5. **Demo 1** (ảnh chụp): câu fast-path → phản ví dụ 10.000.001 đ (dữ liệu cũng có giao dịch như vậy) → **phần 2**: câu "Thanh toán QR cho merchant đã xác minh thì miễn xác thực thêm" → khung "Chạy thử trên dữ liệu: 0 giao dịch, bỏ sót / Z3: tìm ra thanh toán QR 10.000.001 đ" → bản sửa đã kiểm chứng.
6. **Demo 2 + 3** (2 ảnh): quy định đổi → luật nào gãy; bảng L_net giữa các phương án.
7. **AI impact — ablation**: bảng A/B/C/D với số thật trên 30 case; một câu kết luận trung thực.
8. **An toàn & tin cậy**: LLM không tính tiền, không tự bật luật; mọi đề xuất kiểm chứng lại; invariant là cổng cứng; audit; giới hạn của Z3 (nói thẳng).
9. **Tác động & mở rộng** — bám đúng câu chữ của đề: "AI thay đổi cách đội ngũ fintech làm việc, và **qua đó** thay đổi cách con người thanh toán và tự bảo vệ mình". Vẽ chuỗi: đội rủi ro (luật được chứng minh trước khi bật) → người dùng ví (xác thực bắt buộc không bị vô hiệu hóa, ít bị chặn nhầm, gian lận bị giữ trước khi tiền đi). Mở rộng sang tín dụng, AML, bảo hiểm; mô hình B2B. Ghi rõ đây là tiềm năng, chưa đo trên dữ liệu thật.
10. **Hạn chế & bước tiếp**: dữ liệu tổng hợp; một giao dịch đơn lẻ (chưa mô hình chuỗi); Policy Pack giả lập; chưa biết công cụ nội bộ MoMo; 1–2 ví dụ thất bại từ ablation. Kế hoạch tiếp theo.

Thiết kế: ít chữ, mỗi trang một ý, ảnh chụp sản phẩm thật. Không slide kiến trúc chi tiết.

## 3. Kịch bản video 3 phút

| Thời gian | Hình | Lời |
|---|---|---|
| 0:00–0:15 | Landing | "Mỗi luật chống gian lận mới có thể vô tình phá một yêu cầu bắt buộc. RingForge bắt lỗi đó trước khi luật được bật." |
| 0:15–1:15 | Demo 1 (dùng nút "Xem demo 60 giây") | Gõ câu fast-path → luật + giả định → Kiểm chứng → phản ví dụ 10.000.001 đ → phần 2: câu QR merchant → "dữ liệu cũ 0 giao dịch, chỉ Z3 bắt được" → Sửa bằng AI → bản sửa đã kiểm chứng, % giữ ý định, L_net |
| 1:15–1:50 | Demo 2 | Đổi ngưỡng 10 → 5 triệu → luật viết cứng bị báo, luật dùng tham số tự đúng, ma sát tăng N giao dịch |
| 1:50–2:25 | Demo 3 | So 3 phương án luật mule; kéo thanh trượt; flash-sale lộ chặn nhầm |
| 2:25–2:45 | Review + audit | Nút duyệt bị khóa khi FAIL; duyệt bản sửa; audit ghi AI và người |
| 2:45–3:00 | Bảng ablation + link | "Dữ liệu tổng hợp; số đo trên 30 case; thử tại [link]." |

Quay trên production, độ phân giải 1080p, không cắt ghép làm sai kết quả thật. Phụ đề tiếng Việt.

## 4. README (mẫu mục lục)

1. Giới thiệu một đoạn + link sản phẩm + link video.
2. Tính năng và 3 demo.
3. Kiến trúc (sơ đồ ngắn) và ranh giới AI/tất định.
4. Cách chạy local: yêu cầu (Python 3.11, Node 20), `cp .env.example .env`, lệnh sinh dữ liệu, chạy API, chạy web, chạy test, chạy ablation.
5. Biến môi trường (không có giá trị thật).
6. Công nghệ và **thư viện mã nguồn mở kèm license**.
7. **Dữ liệu**: 100% tổng hợp do đội sinh bằng `app/data/generate.py`, seed cố định; không dữ liệu cá nhân; Policy Pack là giả lập có dẫn nguồn văn bản.
8. **Công cụ AI**: model dùng trong sản phẩm (tên, nhà cung cấp); công cụ AI hỗ trợ phát triển (ví dụ trợ lý lập trình) — khai trung thực.
9. **Tài sản có sẵn**: template, component library nếu dùng.
10. Kết quả đánh giá (link `eval/report.md`) và hạn chế.
11. Thành viên và đóng góp.

## 5. Câu hỏi giám khảo có thể hỏi — chuẩn bị trả lời

| Câu hỏi | Hướng trả lời |
|---|---|
| "SEON/Sardine đã có AI viết luật rồi?" | Đúng, và RingForge cũng có. Khác biệt là chứng minh hình thức "không tồn tại vi phạm" + phản ví dụ, bắt lỗi ở vùng dữ liệu chưa từng có. Chỉ vào ca "0 giao dịch trong dữ liệu". |
| "Z3 có chứng minh hệ thống an toàn không?" | Không. Chỉ chứng minh các invariant đã viết, trên mô hình một giao dịch. Tỷ lệ chặn nhầm do backtest đo. |
| "Nếu repair tất định làm được thì AI để làm gì?" | Trả lời bằng số ablation. AI ở biên dịch tiếng Việt, nêu giả định, giữ ý định, dùng tham số. |
| "Luật thật của chúng tôi phức tạp hơn" | DSL là tập con có thể kiểm chứng; mở rộng sang điều kiện chuỗi thời gian là bước tiếp. Hỏi lại họ dạng luật thật để học. |
| "Policy Pack có đúng QĐ 2345 không?" | Là giả lập có dẫn nguồn; đã ghi rõ điểm "trên/từ 10 triệu" cần đối chiếu; hệ thống thiết kế để chuyên gia pháp chế sửa tham số. |
| "Ai trả tiền cho sản phẩm này?" | B2B: ví, ngân hàng, fintech; giá trị là tránh sự cố tuân thủ và tổn thất do thay đổi luật. Chưa có khách hàng — đây là giả thuyết. |
| "Dữ liệu giả thì tin sao được?" | Không tuyên bố hiệu quả thực tế; giá trị chứng minh được là cơ chế. Kiểm chứng hình thức không phụ thuộc dữ liệu. |

## 6. Email câu hỏi gửi BTC (gửi trước 27/11 23:59:59)

> Gửi BTC MoMo Tech Contest 2026,
> Đội chúng em xin hỏi một số điểm:
> 1. Sản phẩm của đội là công cụ cho đội vận hành rủi ro, chạy trên dữ liệu giao dịch tổng hợp và quy định giả lập (có dẫn nguồn), giám khảo có thể tự nhập luật và gọi API thật. Cách làm này có được coi là "sản phẩm dùng được" thay vì "bản trình diễn" không?
> 2. Đội có cần duy trì sản phẩm online đến ngày chung kết 11/12 không, hay chỉ đến hết vòng chấm sơ khảo?
> 3. Đội có được dùng API LLM thương mại không? Tài nguyên AWS/Kiro cấp cho đội (nếu có) có hạn mức và thời hạn thế nào?
> 4. Trường hợp sự cố hạ tầng (máy chủ ngừng) sau hạn nộp, đội có được khởi động lại dịch vụ mà không thay đổi mã nguồn không?
> 5. Việc nhắc tên MoMo hoặc mô phỏng quy trình nghiệp vụ của ví điện tử trong sản phẩm có bị hạn chế không?
> 6. Ranh giới giữa sử dụng thư viện/template mã nguồn mở và "sản phẩm đã phát triển trước cuộc thi" là gì?
> Chúng em cảm ơn.

## 7. Câu hỏi phỏng vấn người làm risk/fraud (15 phút, không dẫn dắt)

1. Kể lần gần nhất anh/chị thêm hoặc sửa một luật rủi ro: từ ý tưởng đến lúc bật mất bao lâu, qua những bước nào?
2. Trước khi bật, anh/chị kiểm tra luật bằng cách nào?
3. Đã bao giờ một luật mới gây sự cố (chặn nhầm hàng loạt, lọt gian lận, sai quy định) chưa? Phát hiện ra bằng cách nào?
4. Khi quy định của NHNN thay đổi, đội xác định luật nào bị ảnh hưởng ra sao?
5. Ai duyệt luật? Người duyệt cần thấy gì để yên tâm ký?
6. Phần nào trong quy trình tốn thời gian hoặc khiến anh/chị lo nhất?

Ghi chép nguyên văn ý chính; xin phép trước khi trích dẫn (ẩn danh) lên slide. Không trích tên công ty nếu chưa được đồng ý.

## 8. Hướng dẫn 1 trang A4 (bố cục)
- Link sản phẩm (to) · không cần tài khoản · trình duyệt khuyến nghị.
- 3 khối, mỗi khối 3 bước có ảnh nhỏ: Demo 1, 2, 3.
- Khối 4 "Dùng như công cụ thật": dán bộ luật JSON của anh/chị để kiểm chứng; link tài liệu API (`/docs`) kèm một lệnh `curl` mẫu.
- Mẹo: "Thử sửa câu luật theo ý anh/chị; nút Reset để về ban đầu."
- Ghi chú: dữ liệu tổng hợp; nếu AI tạm thời không khả dụng, hệ thống dùng kết quả đã lưu cho câu mẫu.
- Liên hệ trưởng nhóm (email đội).
