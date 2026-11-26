# 01 — PRD: RingForge

**AI Safety Compiler for Financial Risk Policies**
Chủ sản phẩm: (tên trưởng nhóm) · Trạng thái: Chốt cho MVP · Ngày: 26/11/2026

---

## 1. Tóm tắt

RingForge là hệ thống "CI/CD cho chính sách quản trị rủi ro". Chuyên viên viết yêu cầu luật bằng tiếng Việt; AI biên dịch thành luật có cấu trúc (Policy DSL); bộ kiểm chứng hình thức (Z3) tìm xung đột và vi phạm ràng buộc pháp lý, kèm **phản ví dụ cụ thể**; backtest trên dữ liệu giao dịch tính **tổn thất tài chính ròng bằng VNĐ**; AI đề xuất bản sửa, mọi bản sửa được kiểm chứng lại trước khi hiện ra; con người phê duyệt, đưa vào shadow mode, có audit log.

> RingForge không phát hiện kẻ gian. RingForge phát hiện sai sót trong các chính sách được tạo ra để ngăn kẻ gian.

**Chủ đề (theo đề chính thức, một sản phẩm được thuộc nhiều chủ đề):**
- **An ninh mạng (chính).** Đề mô tả: "phát hiện, ngăn chặn và phản ứng với các mối đe dọa an ninh… ví dụ: hệ thống phát hiện lỗ hổng bảo mật, cảnh báo bất thường". RingForge là **bộ phát hiện lỗ hổng trong cấu hình chính sách bảo mật**: một luật miễn trừ sai là lỗ hổng vô hiệu hóa lớp xác thực bắt buộc; phản ví dụ chính là "proof-of-concept" của lỗ hổng.
- **Chống lừa đảo (phụ).** Đề nhấn mạnh giúp *người dùng* được bảo vệ *trước khi mất tiền*. Liên hệ gián tiếp: luật đúng và không bị vô hiệu hóa → giao dịch lừa đảo bị giữ (HOLD) trước khi tiền đi.
- **Trợ lý AI (phụ).** Trợ lý cho đội vận hành: hiểu yêu cầu bằng tiếng Việt và làm thay phần viết, kiểm tra, sửa luật.

**Khớp chủ đề cuộc thi:** đề yêu cầu tưởng tượng "AI thay đổi cách **đội ngũ fintech** làm việc, và **qua đó** thay đổi cách con người… thanh toán… và tự bảo vệ mình". RingForge đi đúng chuỗi này: đội rủi ro làm việc khác (luật được chứng minh trước khi bật) → người dùng ví ít bị chặn nhầm hơn, xác thực bắt buộc không bị vô hiệu hóa, gian lận bị giữ đúng lúc. Slide và video phải nói rõ vế "qua đó" này, không dừng ở công cụ nội bộ.

**Yêu cầu "sản phẩm dùng được, không chỉ là bản trình diễn hay bản mẫu thử":** xem FR-S8 đến FR-S10. Sandbox dữ liệu tổng hợp phải là **công cụ thật**: giám khảo viết luật bất kỳ, nhập bộ luật của mình, gọi API thật, chứ không chỉ bấm qua kịch bản dựng sẵn.

---

## 2. Bối cảnh và bài toán

### 2.1 Bối cảnh [V]
- QĐ 2345/QĐ-NHNN (hiệu lực 01/7/2024) yêu cầu xác thực sinh trắc học với giao dịch trên 10 triệu đồng/lần hoặc tổng trên 20 triệu đồng/ngày. Ví điện tử có hướng dẫn hạn mức nạp/rút riêng. **Phải đọc văn bản gốc**: các nguồn báo chí dùng lẫn "trên 10 triệu" và "từ 10 triệu", tức khác nhau ở đúng mốc 10.000.000 đ.
- MoMo công bố hệ thống phát hiện gần 29.000 giao dịch đáng ngờ mỗi ngày năm 2025 (số tự công bố, theo Thanh Niên 12/11/2026).
- Nền tảng chống gian lận thương mại (Sardine, SEON, Oscilar) đã có "viết luật bằng lời + backtest + shadow mode". Sardine viết rằng chạy backtest mất khoảng một giờ nhưng quyết định có tin kết quả hay không mất nhiều ngày (blog nhà cung cấp).

### 2.2 Bài toán [H]
Khi có thủ đoạn mới hoặc quy định mới, đội rủi ro phải thêm hoặc sửa luật. Mỗi thay đổi có thể:
1. Vô hiệu hóa một yêu cầu bắt buộc (ví dụ luật "fast-path cho khách thân thiết" bỏ qua sinh trắc học với giao dịch trên ngưỡng).
2. Không bao giờ kích hoạt (điều kiện mâu thuẫn, ngưỡng ngoài miền giá trị).
3. Thừa, bị luật khác bao trùm.
4. Xung đột với luật khác.
5. Làm tăng tổn thất: lọt gian lận hoặc chặn nhầm khách thật.

Backtest chỉ bắt được lỗi **có xuất hiện trong dữ liệu quá khứ**. Lỗi logic ở vùng hiếm (đúng mốc ngưỡng, tổ hợp điều kiện ít gặp) có thể lọt qua backtest. Kiểm chứng hình thức trả lời được câu hỏi "**có tồn tại** giao dịch nào vi phạm không", kể cả khi dữ liệu chưa từng có giao dịch đó.

### 2.3 Câu hỏi cốt lõi
Làm sao cập nhật chính sách chống gian lận nhanh mà không tạo ra rủi ro mới cho hệ thống thanh toán?

### 2.4 Tiền lệ và định vị trung thực
- [V cần kiểm link] AWS dùng SMT (Zelkova) để kiểm chứng chính sách truy cập IAM; ngôn ngữ chính sách Cedar được thiết kế để phân tích được. Open Policy Agent có kiểm thử policy-as-code.
- RingForge **áp dụng tư tưởng đó cho luật chống gian lận và xác thực giao dịch**, ghép với backtest tài chính và LLM biên dịch/sửa luật. Không tuyên bố world-first.
- Chưa biết MoMo có công cụ kiểm chứng hình thức nội bộ hay không; slide nói rõ đây là điều chưa biết.

---

## 3. Người dùng

| Persona | Mô tả | Việc cần làm | Nỗi lo |
|---|---|---|---|
| **Risk Policy Engineer** (chính) | Viết và bảo trì bộ luật rủi ro, xác thực | Thêm/sửa luật nhanh, chứng minh không phá quy định | Luật mới gây sự cố production, vi phạm NHNN |
| **Fraud Analyst L2** | Điều tra thủ đoạn, đề xuất luật | Mô tả thủ đoạn bằng lời, xem tác động bằng tiền | Không biết viết DSL; không biết luật mình đề xuất đụng luật nào |
| **Risk/Compliance Lead** (người duyệt) | Duyệt thay đổi | Hiểu nhanh rủi ro và lợi ích, có bằng chứng để ký | Ký vào thứ không hiểu; thiếu dấu vết kiểm toán |
| **Giám khảo** (người dùng thật của MVP) | Chuyên gia MoMo, có 2–5 phút | Tự gõ luật, thấy hệ thống bắt lỗi thật | Demo dựng sẵn, số liệu bịa |

---

## 4. Mục tiêu và phi mục tiêu

### Mục tiêu MVP
- G1. Giám khảo tự nhập một luật bằng tiếng Việt và trong **dưới 60 giây** thấy: luật dạng có cấu trúc, kết quả kiểm chứng, phản ví dụ cụ thể, số giao dịch/số tiền trong dữ liệu bị ảnh hưởng, và bản sửa đã được kiểm chứng lại.
- G2. Đổi một tham số quy định và thấy hệ thống chỉ ra chính xác luật nào không còn tương thích.
- G3. So sánh các luật ứng viên bằng L_net (VNĐ), có thanh trượt giả định chi phí.
- G4. Có bằng chứng ablation trên fixture tổng hợp cho phần đóng góp của AI.
- G5. Không có con số nào trên màn hình do LLM tự đặt ra.

### Phi mục tiêu
- Không chấm điểm rủi ro từng giao dịch theo thời gian thực, không thay hệ thống phát hiện gian lận.
- Không tích hợp API MoMo hay ngân hàng; không dữ liệu thật; không PII.
- Không tự động áp dụng luật hay quy định mới mà không có người duyệt.
- Không train mô hình ML; không multi-agent.
- Không RBAC, không quản trị người dùng nhiều vai trò (chỉ mô phỏng vai "người đề xuất" và "người duyệt").
- Không tư vấn pháp lý: Policy Pack là **giả lập có dẫn nguồn**, không phải diễn giải pháp luật chính thức.

---

## 5. Yêu cầu chức năng

Ưu tiên: P0 bắt buộc · P1 nên có · P2 nếu dư thời gian.

### 5.1 Biên dịch luật (AI Policy Compiler)
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-C1 | Nhập yêu cầu bằng tiếng Việt tự nhiên; trả về luật DSL hợp lệ theo schema | P0 |
| FR-C2 | Hiển thị luật dưới dạng **câu tiếng Việt sinh tất định từ AST** (không do LLM viết) và tab JSON | P0 |
| FR-C3 | Với khái niệm mơ hồ ("ban đêm", "khoản lớn", "khách thân thiết"), LLM phải nêu **giả định** rõ ràng để người dùng xác nhận hoặc sửa | P0 |
| FR-C4 | Validator ngữ nghĩa: trường tồn tại, đúng kiểu, giá trị enum hợp lệ, tiền là số nguyên VNĐ; lỗi thì gọi lại LLM tối đa 1 lần kèm thông báo lỗi; vẫn lỗi thì báo người dùng, không đoán | P0 |
| FR-C5 | Sửa luật trực tiếp trên JSON hoặc qua form đơn giản | P1 |
| FR-C6 | Biên dịch được nhiều luật từ một đoạn mô tả | P2 |

### 5.2 Kiểm chứng hình thức (Formal Verification)
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-V1 | VC-03: phát hiện luật không bao giờ kích hoạt | P0 |
| FR-V2 | VC-04: kiểm tra mọi invariant của Policy Pack trên **toàn bộ bộ luật** (luật mới + luật đang chạy); vi phạm thì trả phản ví dụ | P0 |
| FR-V3 | Phản ví dụ hiển thị như một giao dịch cụ thể, đọc được | P0 |
| FR-V4 | **Grounding**: đếm số giao dịch và tổng tiền trong dữ liệu rơi vào vùng vi phạm | P0 |
| FR-V5 | VC-02: cảnh báo điều kiện ngoài miền giá trị | P1 |
| FR-V6 | VC-05: phát hiện luật thừa | P1 |
| FR-V7 | VC-06: phát hiện xung đột miễn trừ/yêu cầu xác thực có vùng chồng lấn | P1 |
| FR-V8 | VC-07: semantic diff giữa hai phiên bản bộ luật (vùng giao dịch có kết quả khác nhau) | P1 |
| FR-V9 | Thời gian kiểm chứng toàn bộ bộ luật seed < 3 giây | P0 |

### 5.3 Backtest tài chính
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-B1 | Chạy bộ luật (đang chạy ± thay đổi) trên dữ liệu tổng hợp, ra quyết định từng giao dịch | P0 |
| FR-B2 | Tính L_net và các thành phần (lọt gian lận, chi phí duyệt, mất do khách bỏ) bằng số nguyên VNĐ | P0 |
| FR-B3 | Phân rã theo kịch bản (mule, chiếm tài khoản, flash-sale, khách thân thiết) | P0 |
| FR-B4 | Thanh trượt giả định: chi phí duyệt, tỷ lệ bỏ giao dịch, biên lợi nhuận, hiệu quả của khoảng dừng | P0 |
| FR-B5 | Chỉ số tuân thủ riêng: số giao dịch/số tiền lẽ ra phải sinh trắc học nhưng không | P0 |
| FR-B6 | So sánh 2–4 phương án cạnh nhau | P0 |
| FR-B7 | Thời gian backtest < 3 giây/phương án trên ~20.000 giao dịch | P0 |

### 5.4 Sửa luật bằng AI (AI Policy Repair)
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-R1 | Từ báo cáo vi phạm + phản ví dụ, LLM đề xuất tối đa 3 bản sửa kèm lý do | P0 |
| FR-R2 | **Mọi bản sửa được kiểm chứng lại và backtest** trước khi hiển thị; bản không qua kiểm chứng bị ẩn (có ghi số lượng bị loại) | P0 |
| FR-R3 | Xếp hạng bản sửa: qua cổng invariant → giữ ý định gốc (độ phủ) → L_net thấp | P0 |
| FR-R4 | Hiển thị diff giữa luật gốc và bản sửa | P0 |
| FR-R5 | **Repair tất định dự phòng** (thêm điều kiện loại trừ vùng vi phạm) khi LLM lỗi; đồng thời là baseline ablation | P0 |
| FR-R6 | Bản sửa ưu tiên tham chiếu tham số Policy Pack thay vì viết cứng số | P1 |

### 5.5 Policy Pack và phân tích tác động quy định
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-P1 | Xem Policy Pack: tham số, invariant, nguồn văn bản, phiên bản | P0 |
| FR-P2 | Sửa tham số → kiểm chứng lại toàn bộ → danh sách luật bị ảnh hưởng kèm phản ví dụ | P0 |
| FR-P3 | Thay đổi ma sát: số giao dịch hợp lệ phải xác thực thêm trước/sau | P1 |
| FR-P4 | Dán đoạn mô tả quy định mới → LLM đề xuất bản vá Policy Pack → người dùng xác nhận | P1 |
| FR-P5 | Sửa hàng loạt các luật bị ảnh hưởng | P2 |

### 5.6 Phê duyệt, shadow mode, audit
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-A1 | Gói thay đổi (change set) gồm: luật, kết quả kiểm chứng, kết quả backtest, ghi chú | P0 |
| FR-A2 | Phê duyệt hoặc từ chối có lý do; **không phê duyệt được** gói còn vi phạm invariant | P0 |
| FR-A3 | Audit log: ai/AI làm gì, lúc nào, phiên bản model, hash prompt | P0 |
| FR-A4 | Shadow mode mô phỏng: chạy song song bộ luật cũ và mới trên "ngày phát lại" (dữ liệu ngày cuối), hiển thị khác biệt | P1 |
| FR-A5 | Rollback về phiên bản trước | P2 |

### 5.7 Sandbox và trải nghiệm giám khảo
| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-S1 | Nút "Vào sandbox" tạo phiên riêng từ dữ liệu seed, không cần đăng ký | P0 |
| FR-S2 | Nút Reset về trạng thái seed | P0 |
| FR-S3 | Guided tour với 3 kịch bản demo, đầu vào điền sẵn nhưng **sửa được** | P0 |
| FR-S4 | Banner cố định: "Dữ liệu tổng hợp, không phải dữ liệu MoMo" | P0 |
| FR-S5 | Chế độ dự phòng khi LLM lỗi hoặc hết hạn mức: dùng kết quả cache cho đầu vào mẫu, có nhãn rõ | P0 |
| FR-S6 | Đồ thị cụm giao dịch cho từng kịch bản | P2 |
| FR-S7 | LLM red team sinh biến thể né luật | P2 (stretch) |
| FR-S8 | **Nhập/xuất bộ luật và Policy Pack dạng JSON** (dán hoặc tải file), kiểm chứng ngay bộ luật nhập vào | P0 |
| FR-S9 | **API công khai có tài liệu** (Swagger/OpenAPI của FastAPI) cho `/verify` và `/backtest`, có ví dụ `curl` trong hướng dẫn; rate limit | P0 |
| FR-S10 | Tải lên CSV giao dịch của người dùng (theo schema `04`) để backtest; xử lý trong phiên, không lưu lâu | P2 |

---

## 6. Yêu cầu phi chức năng

| ID | Yêu cầu |
|---|---|
| NFR-1 | Uptime liên tục từ lúc nộp đến hết 11/12/2026; có monitor ping 5 phút |
| NFR-2 | Không cold start làm giám khảo chờ > 10 giây (không dùng free tier có sleep, hoặc có keep-alive) |
| NFR-3 | Kiểm chứng < 3 s, backtest < 3 s/phương án, biên dịch LLM < 20 s (hiển thị tiến trình) |
| NFR-4 | Tiền: số nguyên VNĐ. Xác suất: basis points. Không float trong tính tiền |
| NFR-5 | Interpreter (backtest) và bộ mã hóa Z3 **cho cùng kết quả** trên mọi giao dịch mẫu (test tự động) |
| NFR-6 | API key chỉ ở server; không có trong repo hay file ZIP |
| NFR-7 | Giới hạn gọi LLM: theo phiên và theo ngày toàn hệ thống |
| NFR-8 | Responsive: đọc được trên điện thoại; trải nghiệm đầy đủ trên laptop |
| NFR-9 | Mọi output LLM qua schema validation; input người dùng là dữ liệu không tin cậy (chống prompt injection) |
| NFR-10 | Tái lập được: seed dữ liệu cố định, ghi phiên bản model và prompt |

---

## 7. Ba kịch bản demo (tiêu chí nghiệm thu)

### Demo 1 — "Lỗi mà chuyên viên bỏ sót"
- **Đầu vào mẫu (sửa được):** "Để giảm phiền hà cho khách thân thiết: tài khoản trên 1 năm, chuyển cho người nhận quen thì không cần xác thực thêm."
- **Kỳ vọng:**
  1. Biên dịch thành luật có `exempt_auth: true`, nêu giả định "người nhận quen = đã chuyển ≥ 3 lần trong 90 ngày".
  2. VC-04 báo vi phạm INV-AUTH-01, phản ví dụ: giao dịch 10.000.001 đ, tài khoản 400 ngày, người nhận quen → không bị yêu cầu sinh trắc học.
  3. Grounding: "X giao dịch / Y đ trong dữ liệu rơi vào vùng này" (số thật từ dữ liệu).
  4. Repair: bản sửa giới hạn miễn trừ dưới ngưỡng, tham chiếu tham số Policy Pack; qua kiểm chứng; L_net và ma sát hiển thị.
- **Nghiệm thu:** giám khảo đổi câu chữ (ví dụ "trên 2 năm", "người nhận là người thân") vẫn ra kết quả đúng logic.

### Demo 2 — "Quy định thay đổi"
- **Thao tác:** sửa `biometric_per_tx_threshold` từ 10.000.000 xuống 5.000.000 (ghi rõ: kịch bản giả lập).
- **Kỳ vọng:** luật nào viết cứng 10.000.000 bị báo không tương thích kèm phản ví dụ; luật tham chiếu tham số tự đúng; hiển thị số giao dịch hợp lệ phải xác thực thêm; AI đề xuất sửa; kiểm chứng lại xanh.

### Demo 3 — "Tối ưu tổn thất"
- **Thao tác:** chọn 2–4 phương án cho luật chống mule (cửa sổ 15/30/60 phút; HOLD hay BLOCK).
- **Kỳ vọng:** bảng L_net, lọt gian lận, chặn nhầm, phân rã theo kịch bản (flash-sale cho thấy chặn nhầm); kéo thanh trượt giả định thì thứ hạng có thể đổi; chỉ phương án qua cổng invariant được chọn.

---

## 8. Chỉ số thành công

### Cho bài thi
- Giám khảo hoàn thành Demo 1 trong ≤ 2 phút không cần hướng dẫn ngoài guided tour.
- 0 con số do LLM tạo xuất hiện như dữ liệu (kiểm bằng test).
- Bảng ablation thật trên fixture (xem `08_EVALUATION_PLAN.md`).

### Cho sản phẩm (giả thuyết dài hạn, không đưa như kết quả)
- Thời gian từ ý tưởng luật đến luật được duyệt.
- Số sự cố do thay đổi luật lọt lên production.
- Tổn thất ròng trước/sau.

---

## 9. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Không đăng ký kịp hoặc thiếu thành viên | **Chí mạng** | Đăng ký sáng 27/11 |
| AI impact bị coi là yếu (repair tất định làm được gần bằng) | Cao | Ablation trung thực; nhấn mạnh biên dịch tiếng Việt + giữ ý định + giả định có kiểm soát; P2 red team |
| Giám khảo: "SEON/Sardine có rồi" | Cao | Mở demo bằng phản ví dụ mà backtest không bắt được; bảng khác biệt trong slide |
| Một người làm, scope quá lớn | Cao | Điểm cắt scope ở `09` |
| Deploy Z3/Python lỗi | Trung bình | Spike tối 26/11; Docker |
| Diễn giải sai QĐ 2345 | Trung bình | Policy Pack ghi "giả lập có dẫn nguồn"; đọc văn bản gốc; toán tử mốc ngưỡng là tham số |
| API LLM lỗi hoặc hết tiền khi chấm | Trung bình | Cache + repair tất định + giới hạn lượt |
| Bị coi là "bản trình diễn/mẫu thử" (đề loại trừ rõ) | Cao | FR-S8, FR-S9: giám khảo nhập luật/bộ luật bất kỳ và gọi API thật; guided tour chỉ là lối vào, không phải toàn bộ sản phẩm; hướng dẫn 1 trang có mục "Thử với luật của anh/chị" |
| Giám khảo thấy sản phẩm chỉ phục vụ nội bộ, xa người dùng cuối | Trung bình | Slide/video nói rõ chuỗi "đội fintech → người dùng ví" theo đúng câu chữ của đề |

---

## 10. Giả định và câu hỏi mở

- Giả định: thể lệ cho phép dữ liệu tổng hợp và API LLM thương mại (hỏi BTC).
- Giả định: bộ luật thật ở ví điện tử có dạng điều kiện-hành động tương tự (chưa xác minh).
- Mở: MoMo có quy trình kiểm chứng luật nội bộ nào? (không cần biết để làm MVP; nêu là điều chưa biết)
- Mở: có thể nói chuyện 15 phút với 1–2 người làm risk/fraud ở ví hoặc ngân hàng không? Nếu có, đó là bằng chứng nỗi đau tốt nhất cho slide.
