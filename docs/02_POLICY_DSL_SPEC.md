# 02 — Đặc tả RingForge Policy DSL

Phiên bản DSL: `rf-dsl/0.1`. Định dạng: JSON. Một nguồn sự thật duy nhất: schema Pydantic trong `services/api/app/dsl/schema.py`; JSON Schema xuất từ Pydantic dùng cho structured output của LLM.

Nguyên tắc: DSL phải **vừa chạy được trên dữ liệu (pandas)** vừa **mã hóa được sang Z3**. Vì vậy chỉ dùng số nguyên, boolean, enum hữu hạn; không regex, không chuỗi tự do, không số thực.

---

## 1. Danh mục trường (Field Catalog)

Tất cả đặc trưng được tính **chỉ từ giao dịch xảy ra trước** giao dịch hiện tại, trừ `daily_total_after` (gồm cả giao dịch hiện tại). Xem `04` mục 3.

| Trường | Kiểu | Miền | Ý nghĩa |
|---|---|---|---|
| `amount` | int (VND) | 1 … 500.000.000 | Số tiền giao dịch |
| `channel` | enum | P2P, MERCHANT_QR, TOPUP, WITHDRAW, BILL | Kênh |
| `hour` | int | 0 … 23 | Giờ địa phương |
| `daily_total_after` | int (VND) | 1 … 2.000.000.000 | Tổng chi trong ngày của người gửi, gồm giao dịch này |
| `is_new_device` | bool | | Thiết bị mới trong 7 ngày |
| `sender_account_age_days` | int | 0 … 3650 | Tuổi tài khoản gửi |
| `sender_dormant_days` | int | 0 … 3650 | Số ngày không hoạt động ngay trước giao dịch |
| `sender_kyc_level` | enum | BASIC, FULL | Mức định danh |
| `sender_inbound_amount_60m` | int (VND) | 0 … 2.000.000.000 | Tiền nhận vào trong 60 phút trước |
| `sender_distinct_inbound_60m` | int | 0 … 500 | Số người gửi khác nhau vào tài khoản này trong 60 phút |
| `sender_outbound_ratio_60m_pct` | int (%) | 0 … 1000 | (Tiền chuyển ra 60 phút, gồm giao dịch này) / (tiền nhận vào 60 phút) × 100; = 0 nếu không có tiền vào |
| `sender_outbound_count_24h` | int | 0 … 1000 | Số giao dịch chi trong 24h trước |
| `receiver_account_age_days` | int | 0 … 3650 | Tuổi tài khoản nhận |
| `receiver_is_verified_merchant` | bool | | Người nhận là merchant đã xác minh |
| `receiver_is_familiar` | bool | | Người gửi đã chuyển cho người nhận này ≥ 3 lần trong 90 ngày trước |
| `receiver_inbound_count_30m` | int | 0 … 5000 | Số giao dịch nhận của người nhận trong 30 phút |
| `receiver_distinct_senders_30m` | int | 0 … 5000 | Số người gửi khác nhau vào người nhận trong 30 phút |

### Ràng buộc miền phụ thuộc (domain constraints, dùng trong Z3)
Để phản ví dụ **khả thi trên thực tế**:
- `daily_total_after >= amount`
- `sender_dormant_days <= sender_account_age_days`
- `receiver_distinct_senders_30m <= receiver_inbound_count_30m`
- `sender_inbound_amount_60m == 0 ⇒ sender_distinct_inbound_60m == 0 ∧ sender_outbound_ratio_60m_pct == 0`
- `sender_distinct_inbound_60m >= 1 ⇒ sender_inbound_amount_60m >= 1`
- `receiver_is_verified_merchant ⇒ receiver_account_age_days >= 30` (giả định của generator)
- `channel == TOPUP ⇒ receiver_is_verified_merchant == false` (giả định)

Ràng buộc nào thêm vào Z3 thì **generator cũng phải tuân thủ**; có test kiểm tra.

---

## 2. Ngữ pháp điều kiện

```jsonc
Condition :=
    { "all": [Condition, ...] }          // AND, ≥ 1 phần tử
  | { "any": [Condition, ...] }          // OR, ≥ 1 phần tử
  | { "not": Condition }
  | { "field": FieldName, "op": CmpOp, "value": Value }
  | { "field": FieldName, "op": "between", "value": [Value, Value] }   // bao gồm hai đầu
  | { "field": FieldName, "op": "in" | "not_in", "value": [EnumValue, ...] }
  | { "const": true | false }

CmpOp := ">" | ">=" | "<" | "<=" | "==" | "!="
Value := integer | boolean | EnumValue | { "param": ParamName }
```

Quy tắc validator:
- `value` của trường int phải là integer hoặc `{param}` trỏ tới tham số int. **Không chấp nhận chuỗi** như "10tr", "10.000.000".
- Trường bool chỉ dùng `==`/`!=` với true/false.
- Trường enum chỉ dùng `==`, `!=`, `in`, `not_in` với giá trị hợp lệ.
- `between`: a ≤ b, cả hai cùng kiểu.
- Độ sâu tối đa 6, tối đa 20 điều kiện lá mỗi luật (tránh nổ Z3 và UI).

---

## 3. Hành động và ngữ nghĩa quyết định

```jsonc
Action := {
  "decision": "ALLOW" | "MONITOR" | "HOLD" | "BLOCK",   // tùy chọn
  "auth": "NONE" | "OTP" | "BIOMETRIC",                  // tùy chọn: yêu cầu xác thực tối thiểu
  "exempt_auth": true | false,                           // tùy chọn, mặc định false
  "hold_seconds": 60..180                                // bắt buộc khi decision = HOLD
}
```

| Quyết định | Tầng | Ý nghĩa |
|---|---|---|
| ALLOW | — | Cho qua |
| MONITOR | 1 | Cho qua, gắn cờ giám sát ngầm |
| HOLD | 2 | Khoảng dừng 60–180 s + bước xác minh độc lập; người dùng có nút hủy/hoãn nổi bật |
| BLOCK | 3 | Chặn, chuyển người duyệt, có thể cô lập cụm |

Thứ tự: `ALLOW < MONITOR < HOLD < BLOCK`; `NONE < OTP < BIOMETRIC`. `NONE` nghĩa là chỉ dùng xác thực mặc định (PIN/mật khẩu), không thêm bước.

### Ngữ nghĩa cho một giao dịch t với bộ luật R (tất định, dùng chung cho interpreter và Z3)
```
M = { r ∈ R : r.status ∈ {ACTIVE, CANDIDATE} ∧ r.when(t) }
decision(t) = max({ r.then.decision : r ∈ M, có decision } ∪ {ALLOW})
auth_req(t) = max({ r.then.auth : r ∈ M, có auth } ∪ {NONE})
exempt(t)   = ∃ r ∈ M : r.then.exempt_auth = true
auth(t)     = exempt(t) ? NONE : auth_req(t)
```

**Vì sao miễn trừ ghi đè cả luật pháp lý?** Vì đó là cách các "fast-path"/whitelist thường được cài trong thực tế và cũng là nguồn lỗi. Engine không cấm người dùng viết luật miễn trừ; **invariant** của Policy Pack mới là thứ bảo đảm an toàn, và Z3 kiểm tra nó. Đây là tâm điểm của Demo 1.

`HOLD` cần `hold_seconds`; nếu nhiều luật HOLD cùng khớp, lấy `max(hold_seconds)`.

---

## 4. Cấu trúc luật

```jsonc
Rule := {
  "id": "FR-01",                       // duy nhất trong workspace; luật mới: "DRAFT-xxxx"
  "version": 1,
  "name": "Tài khoản mới gom-tẩu nhanh",
  "description": "…",                  // mô tả do người hoặc AI viết, không dùng để chạy
  "kind": "FRAUD" | "FRICTION" | "REGULATORY",
  "status": "ACTIVE" | "CANDIDATE" | "SHADOW" | "RETIRED",
  "locked": false,                     // true với luật REGULATORY trong seed: không sửa qua UI
  "when": Condition,
  "then": Action,
  "assumptions": ["'ban đêm' = 0–5 giờ"],  // từ bước biên dịch, người dùng đã xác nhận
  "provenance": { "created_by": "human" | "ai_compile" | "ai_repair" | "det_repair",
                  "parent": "FR-01@v1" | null, "ai_call_id": "…" | null }
}
```

---

## 5. Policy Pack

```jsonc
PolicyPack := {
  "id": "VN-PAYMENTS-SIM",
  "version": "2026.11-sim.1",
  "disclaimer": "Giả lập phục vụ thử nghiệm, không phải diễn giải pháp lý chính thức.",
  "params": {
    "biometric_per_tx_threshold": { "value": 10000000, "unit": "VND",
        "source": "QĐ 2345/QĐ-NHNN — đối chiếu văn bản gốc về 'trên' hay 'từ'" },
    "biometric_daily_threshold":  { "value": 20000000, "unit": "VND", "source": "QĐ 2345/QĐ-NHNN" },
    "small_merchant_payment_max": { "value": 2000000,  "unit": "VND", "source": "Chính sách nội bộ giả lập" },
    "hold_min_seconds":           { "value": 60, "unit": "s", "source": "Chính sách nội bộ giả lập" },
    "hold_max_seconds":           { "value": 180, "unit": "s", "source": "Chính sách nội bộ giả lập" }
  },
  "invariants": [Invariant, ...]
}

Invariant :=
  { "id": "INV-AUTH-01", "type": "AUTH_AT_LEAST", "level": "BIOMETRIC",
    "when": { "field": "amount", "op": ">", "value": { "param": "biometric_per_tx_threshold" } },
    "source": "QĐ 2345/QĐ-NHNN", "severity": "HARD" }
| { "id": "INV-AUTH-02", "type": "AUTH_AT_LEAST", "level": "BIOMETRIC",
    "when": { "field": "daily_total_after", "op": ">", "value": { "param": "biometric_daily_threshold" } },
    "source": "QĐ 2345/QĐ-NHNN", "severity": "HARD" }
| { "id": "INV-CX-01", "type": "DECISION_AT_MOST", "level": "MONITOR",
    "when": { "all": [
        { "field": "receiver_is_verified_merchant", "op": "==", "value": true },
        { "field": "channel", "op": "==", "value": "MERCHANT_QR" },
        { "field": "amount", "op": "<=", "value": { "param": "small_merchant_payment_max" } } ] },
    "source": "Chính sách trải nghiệm khách hàng giả lập", "severity": "HARD" }
```

Loại invariant MVP:
- `AUTH_AT_LEAST(level)`: với mọi t thỏa `when`, `auth(t) ≥ level`.
- `DECISION_AT_MOST(level)`: với mọi t thỏa `when`, `decision(t) ≤ level`. Đây là dạng "trần chặn nhầm" **có thể chứng minh**: không luật nào được giữ/chặn thanh toán nhỏ cho merchant đã xác minh. Còn *tỷ lệ* chặn nhầm thì do backtest đo.
- (P2) `DECISION_AT_LEAST(level)`.

Luật REGULATORY trong seed hiện thực các invariant (ví dụ `REG-01: amount > {param} → auth BIOMETRIC`). Invariant là **đặc tả**; luật là **hiện thực**. Z3 kiểm tra hiện thực thỏa đặc tả.

---

## 6. Bộ luật seed (gợi ý, sinh trong `data/seed/rules.json`)

| ID | Kind | Khi | Thì | Ghi chú demo |
|---|---|---|---|---|
| REG-01 | REGULATORY, locked | `amount > {biometric_per_tx_threshold}` | auth BIOMETRIC | |
| REG-02 | REGULATORY, locked | `daily_total_after > {biometric_daily_threshold}` | auth BIOMETRIC | |
| FR-01 | FRAUD | tuổi gửi < 14 ∧ distinct_inbound_60m ≥ 3 ∧ outbound_ratio ≥ 80 ∧ channel ∈ {P2P, WITHDRAW} | HOLD 120 s | Mule; Demo 3 có biến thể |
| FR-02 | FRAUD | dormant ≥ 90 ∧ is_new_device ∧ hour ∈ [0,5] ∧ channel ∈ {P2P, WITHDRAW} | HOLD 180 s + auth BIOMETRIC | Chiếm tài khoản. Giới hạn kênh (chốt 26/11) để seed không vi phạm INV-CX-01 (HOLD thanh toán QR nhỏ cho merchant đã xác minh) |
| FR-03 | FRAUD | amount ≥ 5.000.000 ∧ receiver_age < 7 ∧ ¬familiar ∧ hour ∈ [22,23] ∪ [0,5] | MONITOR | |
| FR-04 | FRAUD | receiver_distinct_senders_30m ≥ 30 ∧ ¬receiver_is_verified_merchant | HOLD 60 s | Fan-in; có thể bắt nhầm flash-sale nếu merchant chưa xác minh |
| FX-01 | FRICTION | verified_merchant ∧ MERCHANT_QR ∧ amount ≤ {small_merchant_payment_max} | ALLOW | Giảm ma sát |
| LG-07 | FRAUD (legacy) | amount > 9.000.000 ∧ amount < 10.000.000 ∧ hour ∈ [0,5] | MONITOR | **Viết cứng 10.000.000** → Demo 2 lộ ra |
| LG-09 | FRAUD (legacy) | tuổi gửi < 7 ∧ distinct_inbound_60m ≥ 5 ∧ outbound_ratio ≥ 90 ∧ channel == P2P | HOLD 60 s | **Thừa**: bị FR-01 bao trùm (VC-05) |

---

## 7. Hiển thị luật bằng câu tiếng Việt (tất định)

Hàm `render_vi(rule)` duyệt AST, dùng nhãn trường trong catalog:
- `amount > {biometric_per_tx_threshold}` → "số tiền **lớn hơn ngưỡng sinh trắc học/lần (hiện 10.000.000 đ)**"
- `all` → nối "VÀ", `any` → "HOẶC", có ngoặc khi lồng.
- Hành động: "THÌ giữ 120 giây để xác minh · yêu cầu sinh trắc học · **miễn xác thực bổ sung**" (miễn trừ in đỏ).

Không dùng LLM cho phần này để câu hiển thị luôn đúng với AST.

---

## 8. Ví dụ đầy đủ: luật Demo 1 sau biên dịch

```json
{
  "id": "DRAFT-0001", "version": 1,
  "name": "Fast-path khách thân thiết",
  "kind": "FRICTION", "status": "CANDIDATE", "locked": false,
  "when": { "all": [
    { "field": "sender_account_age_days", "op": ">", "value": 365 },
    { "field": "receiver_is_familiar", "op": "==", "value": true }
  ]},
  "then": { "exempt_auth": true },
  "assumptions": ["'trên 1 năm' = tuổi tài khoản > 365 ngày",
                  "'người nhận quen' = đã chuyển ≥ 3 lần trong 90 ngày (trường receiver_is_familiar)"],
  "provenance": { "created_by": "ai_compile", "parent": null, "ai_call_id": "call_…" }
}
```

Bản sửa mong đợi (một trong các ứng viên):
```json
"when": { "all": [
  { "field": "sender_account_age_days", "op": ">", "value": 365 },
  { "field": "receiver_is_familiar", "op": "==", "value": true },
  { "field": "amount", "op": "<=", "value": { "param": "biometric_per_tx_threshold" } },
  { "field": "daily_total_after", "op": "<=", "value": { "param": "biometric_daily_threshold" } }
]}
```
