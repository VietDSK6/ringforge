# 04 — Dữ liệu tổng hợp và Backtest tài chính

Module: `services/api/app/data/` (generator, features) và `services/api/app/backtest/`.

## 1. Nguyên tắc
- 100% dữ liệu tổng hợp, không PII, seed cố định (`SEED = 20261203`).
- Sinh **một lần** khi build (`python -m app.data.generate`), lưu `data/seed/transactions.parquet` (~20.000 dòng, vài MB), load vào bộ nhớ khi API khởi động.
- Mọi ràng buộc miền ở `02` mục 1 phải đúng trên dữ liệu (test).
- Nhãn (`label`, `scenario`) **không** nằm trong catalog trường của DSL.
- PaySim: không dùng trong MVP (D2). Nếu sau này dùng, ghi license trong README và quy đổi rõ ràng.

## 2. Thực thể và quy mô [GL]

| Thực thể | Số lượng | Ghi chú |
|---|---|---|
| Người dùng cá nhân | 3.000 | Tuổi tài khoản phân phối lệch, đa số > 180 ngày |
| Merchant | 150 | 120 đã xác minh, 30 chưa |
| Tài khoản mule | 24 | Tuổi 1–13 ngày, KYC BASIC |
| Tài khoản bị chiếm | 6 | Ngủ đông ≥ 90 ngày |
| Thời gian | 7 ngày | Ngày 1–6: dữ liệu backtest; ngày 7: "ngày phát lại" cho shadow mode |
| Giao dịch | ~20.000 | Tỷ lệ gian lận ~1–2% theo số giao dịch |

## 3. Bảng giao dịch

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `tx_id` | str | |
| `ts` | int (epoch s) | Múi giờ VN khi tính `hour` |
| `sender_id`, `receiver_id` | str | ID tổng hợp, không giống số điện thoại thật |
| `amount` | int VND | |
| `channel` | str enum | |
| `is_new_device` | bool | |
| `sender_kyc_level` | str enum | |
| `label` | enum | `LEGIT`, `APP_VICTIM` (nạn nhân chuyển cho kẻ gian — **mang tổn thất**), `MULE_LAYER` (mule chuyển tiếp), `ATO` (tài khoản bị chiếm chuyển đi — **mang tổn thất**) |
| `scenario` | enum | `S0_NORMAL`, `S1_MULE`, `S2_ATO`, `S3_FLASH_SALE`, `S4_FAMILIAR_HIGH` |
| + các cột đặc trưng trong catalog | | Tính ở bước features |

**Chỉ `APP_VICTIM` và `ATO` mang giá trị tổn thất** để tránh đếm trùng cùng một đồng tiền qua nhiều lớp mule. `MULE_LAYER` báo cáo riêng như "dòng tiền mule bị chặn".

### Tính đặc trưng chống leakage
Sắp xếp theo `ts` (và `tx_id` khi trùng). Với mỗi giao dịch i:
- Cửa sổ thời gian dùng giao dịch có `ts < ts_i` và `ts >= ts_i - W` (không gồm i), **trừ** `daily_total_after` = tổng chi của người gửi từ 00:00 cùng ngày đến **và gồm** i, và `sender_outbound_ratio_60m_pct` gồm cả `amount_i` ở tử số.
- `receiver_is_familiar`: đếm giao dịch sender→receiver trong 90 ngày trước, **không gồm i**. Vì chỉ có 7 ngày dữ liệu, generator sinh thêm cột "lịch sử trước kỳ" `prior_pair_count` cho các cặp quen (gia đình, tiền nhà) rồi cộng vào.
- `sender_dormant_days`: số ngày từ giao dịch gần nhất trước i (có cột lịch sử `last_active_before_window`).

Hiện thực bằng pandas `groupby` + `rolling` theo thời gian, hoặc vòng lặp numpy (20.000 dòng: vài giây, chạy một lần lúc build).

**Leakage checker (P1):** mỗi trường trong catalog có thuộc tính `available_at_decision: true`; validator từ chối luật dùng trường không có thuộc tính này. Với MVP, mọi trường catalog đều thỏa; checker để chống ai đó (hoặc LLM) thêm trường kiểu `label`.

## 4. Kịch bản sinh dữ liệu

### S0 — Bình thường
- Chuyển khoản P2P giữa bạn bè, gia đình: 50.000–5.000.000 đ, đỉnh 11–13h và 19–22h.
- Thanh toán QR merchant: 20.000–2.000.000 đ.
- Hóa đơn, nạp ví.
- Một ít giao dịch lớn hợp lệ (mua xe, học phí) 10–50 triệu, có BIOMETRIC theo REG.

### S1 — Mạng mule rải lệnh (gian lận)
- 6 "chiến dịch". Mỗi chiến dịch: 8–15 nạn nhân chuyển 3–9.500.000 đ (`APP_VICTIM`) vào 3–5 mule lớp 1 trong 19h–23h.
- Mule lớp 1 chuyển tiếp trong 5–20 phút sang mule lớp 2 (`MULE_LAYER`), **mỗi lệnh ≤ 9.900.000 đ và tổng ngày ≤ 19.900.000 đ** (né cả hai ngưỡng sinh trắc học).
- Mule lớp 2 rút (`WITHDRAW`).
- Biến thể để Demo 3 có khác biệt: một nửa chiến dịch chuyển ra trong 15 phút, nửa còn lại 25–50 phút; một số chèn 1–2 thanh toán QR nhỏ để hạ tỷ lệ chuyển ra.

### S2 — Chiếm tài khoản ngủ đông (gian lận)
- 6 tài khoản ngủ đông 90–400 ngày, thiết bị mới, 0–4h, chuyển 3–5 lệnh 4–9.800.000 đ cho tài khoản lạ (`ATO`).

### S3 — Flash-sale hợp lệ (bẫy sạch)
- 3 merchant (2 **chưa** xác minh, 1 đã xác minh) nhận 40–120 thanh toán QR 50.000–500.000 đ trong 30 phút.
- Mục đích: FR-04 (fan-in, loại trừ merchant đã xác minh) bắt nhầm 2 merchant chưa xác minh → hiện trong Demo 3.

### S4 — Khách thân thiết chuyển lớn (hợp lệ)
- 200 cặp người gửi lâu năm → người nhận quen (tiền nhà, gửi bố mẹ), mỗi cặp 1–2 giao dịch/tuần; 60% dưới 10 triệu, 40% từ 10–30 triệu.
- Mục đích: Demo 1 grounding: luật fast-path miễn sinh trắc học sẽ chạm X giao dịch > 10 triệu.
- **Chủ ý:** không sinh giao dịch nào đúng 10.000.000 đ, để cho thấy ca "backtest không bắt được, Z3 bắt được" ở mốc ngưỡng (xem `03` mục 4). Ghi rõ điều này trong tài liệu kỹ thuật cho minh bạch.

## 5. Interpreter

`interpret(rules, df, params) -> DataFrame[decision:int8, auth:int8, hold_seconds:int16, matched:list]`

- Biên dịch mỗi `Condition` thành mặt nạ boolean numpy theo đệ quy (giống hệt `enc` ở `03`).
- `decision = max` trên các mảng; `auth` tương tự; `exempt` = OR các mặt nạ của luật miễn trừ; `auth = where(exempt, 0, auth)`.
- Không `eval`, không sinh code; chỉ duyệt AST.
- Hiệu năng: 20.000 dòng × 15 luật: < 100 ms.

## 6. Công thức tài chính (số nguyên)

Ký hiệu: tiền VNĐ là int; tỷ lệ là basis points (bp, 10.000 = 100%). Chỉ áp cho dữ liệu ngày 1–6 (ngày 7 dành cho shadow).

### Giả định có thanh trượt [GL — không phải số thật]
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `hold_stop_bp` | 5.000 | Xác suất một giao dịch gian lận bị HOLD được nạn nhân hủy |
| `monitor_stop_bp` | 0 | MONITOR không ngăn tiền |
| `c_review_block` | 30.000 đ | Chi phí người duyệt mỗi giao dịch hợp lệ bị BLOCK |
| `c_review_hold` | 0 đ | HOLD tự xử lý bằng xác minh |
| `churn_hold_bp` | 500 | Tỷ lệ khách thật bỏ giao dịch khi bị HOLD |
| `churn_block_bp` | 3.000 | Tỷ lệ khách thật bỏ khi bị BLOCK |
| `margin_bp` | 50 | Doanh thu/lợi nhuận mất trên mỗi đồng giao dịch bị bỏ |

Tất cả hiển thị kèm nhãn "giả định — chỉnh được". Không trích nguồn cho các số này vì không có.

### Tính toán
```
Loss_tx = {APP_VICTIM, ATO}
prevented = Σ_{i∈Loss, dec=BLOCK} amount_i
          + floor( Σ_{i∈Loss, dec=HOLD} amount_i × hold_stop_bp / 10000 )
FN_loss   = Σ_{i∈Loss} amount_i − prevented

Legit = {LEGIT}
review_cost = count(Legit ∧ dec=BLOCK) × c_review_block + count(Legit ∧ dec=HOLD) × c_review_hold
churn_loss  = floor( Σ_{Legit ∧ dec=HOLD} amount_i × churn_hold_bp × margin_bp / 10^8 )
            + floor( Σ_{Legit ∧ dec=BLOCK} amount_i × churn_block_bp × margin_bp / 10^8 )

L_net = FN_loss + review_cost + churn_loss
```
Làm tròn: floor trên tổng từng nhóm (không theo từng giao dịch), ghi rõ trong UI tooltip. Dùng `int` Python (không tràn).

### Chỉ số báo cáo kèm (không cộng vào L_net)
- `compliance_exposure`: số giao dịch và tổng tiền có `inv.when` đúng nhưng `auth < BIOMETRIC` (theo từng invariant). **Phương án có exposure > 0 bị gắn nhãn "không hợp lệ"**, không xếp hạng theo L_net (D4).
- `friction_biometric`: số giao dịch hợp lệ phải BIOMETRIC.
- `fp_count_hold`, `fp_count_block`, `fp_rate` theo kịch bản.
- `mule_flow_stopped`: tổng tiền `MULE_LAYER` bị HOLD/BLOCK.
- Recall theo số tiền và theo số giao dịch, theo kịch bản.

## 7. Backtest API

`POST /sessions/{sid}/backtest` với `variants: [{name, rule_changes: [...]}]` → mỗi variant: bộ luật = ACTIVE áp `rule_changes` (thêm/thay/bỏ) → kết quả như trên + `delta` so với baseline (bộ ACTIVE hiện tại).

## 8. Kiểm thử bắt buộc
1. Ràng buộc miền đúng trên mọi dòng dữ liệu.
2. Không giao dịch nào `amount == 10_000_000` (chủ ý, xem S4) — test để không vô tình đổi.
3. Bộ luật seed: `compliance_exposure == 0`.
4. Đặc trưng: test tay 5 giao dịch dựng sẵn (ví dụ mule nhận 3 lần rồi chuyển) cho ra đúng giá trị cửa sổ.
5. L_net: test với dữ liệu 10 dòng tính tay.
6. Tái lập: chạy generator 2 lần cùng seed → hash parquet giống nhau.
