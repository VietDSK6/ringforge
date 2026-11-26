# 03 — Đặc tả kiểm chứng hình thức

Module: `services/api/app/verify/`. Thư viện: `z3-solver` (Python). Mọi kiểm tra chạy trên **mô hình một giao dịch đơn lẻ** với các trường trong catalog và ràng buộc miền ở `02` mục 1.

## 0. Phạm vi trung thực (ghi y như vậy trong slide và README)

Z3 chứng minh được: với **mọi** giao dịch thỏa ràng buộc miền đã mô hình hóa, bộ luật có thỏa các invariant đã viết hay không; nếu không, đưa ra một giao dịch cụ thể làm phản ví dụ.

Z3 **không** chứng minh được:
- Tỷ lệ chặn nhầm, hiệu quả chống gian lận (do backtest đo).
- Đúng đắn của đặc trưng đầu vào (`daily_total_after` tính sai thì kết luận cũng sai).
- Hành vi qua nhiều giao dịch theo thời gian (MVP chỉ mô hình một giao dịch; các đặc trưng cửa sổ thời gian là biến đầu vào).
- Rằng invariant phản ánh đúng quy định pháp luật (đó là việc của người viết Policy Pack).

---

## 1. Danh sách phép kiểm tra

| Mã | Tên | Mức | Đầu ra | Ưu tiên |
|---|---|---|---|---|
| VC-01 | Schema & kiểu | ERROR | Danh sách lỗi validator | P0 (Pydantic, không cần Z3) |
| VC-02 | Ngoài miền | WARN | Lá điều kiện luôn đúng/luôn sai do miền | P1 |
| VC-03 | Luật chết | ERROR | Luật không bao giờ khớp | P0 |
| VC-04 | Vi phạm invariant | ERROR (HARD) | Phản ví dụ + luật gây ra + grounding | P0 |
| VC-05 | Luật thừa | WARN | Cặp (luật thừa, luật bao trùm) | P1 |
| VC-06 | Xung đột miễn trừ | WARN | Cặp luật + giao dịch nhân chứng | P1 |
| VC-07 | Semantic diff | INFO | Vùng có kết quả khác giữa hai phiên bản + nhân chứng + grounding | P1 |

Kết quả tổng: `PASS` (không ERROR) · `PASS_WITH_WARNINGS` · `FAIL`. Change set có ERROR **không thể phê duyệt**.

---

## 2. Mã hóa sang Z3

```python
from z3 import Int, Bool, And, Or, Not, If, BoolVal, IntVal, Solver, sat

DEC  = {"ALLOW": 0, "MONITOR": 1, "HOLD": 2, "BLOCK": 3}
AUTH = {"NONE": 0, "OTP": 1, "BIOMETRIC": 2}
ENUM = {"channel": ["P2P","MERCHANT_QR","TOPUP","WITHDRAW","BILL"],
        "sender_kyc_level": ["BASIC","FULL"]}

def make_vars(catalog):
    v = {}
    for f in catalog:
        v[f.name] = Bool(f.name) if f.type == "bool" else Int(f.name)  # enum → Int (chỉ số)
    return v

def domain(v, catalog):
    cs = []
    for f in catalog:
        if f.type in ("int", "enum"):
            lo, hi = f.lo, f.hi          # enum: 0 .. len-1
            cs += [v[f.name] >= lo, v[f.name] <= hi]
    cs += [v["daily_total_after"] >= v["amount"],
           v["sender_dormant_days"] <= v["sender_account_age_days"],
           v["receiver_distinct_senders_30m"] <= v["receiver_inbound_count_30m"],
           # … các ràng buộc còn lại ở 02 mục 1
          ]
    return And(cs)

def resolve(value, params, field):
    if isinstance(value, dict) and "param" in value:
        return IntVal(params[value["param"]]["value"])
    if field.type == "enum":
        return IntVal(ENUM[field.name].index(value))
    if isinstance(value, bool):
        return BoolVal(value)
    return IntVal(value)

def enc(c, v, params, cat):
    if "all" in c:   return And([enc(x, v, params, cat) for x in c["all"]])
    if "any" in c:   return Or([enc(x, v, params, cat) for x in c["any"]])
    if "not" in c:   return Not(enc(c["not"], v, params, cat))
    if "const" in c: return BoolVal(c["const"])
    f = cat[c["field"]]; x = v[f.name]; op = c["op"]
    if op == "between":
        a, b = (resolve(val, params, f) for val in c["value"]); return And(x >= a, x <= b)
    if op in ("in", "not_in"):
        e = Or([x == resolve(val, params, f) for val in c["value"]])
        return e if op == "in" else Not(e)
    y = resolve(c["value"], params, f)
    return {">": x > y, ">=": x >= y, "<": x < y, "<=": x <= y, "==": x == y, "!=": x != y}[op]

def outcome(rules, v, params, cat):
    dec, auth, exempt = IntVal(0), IntVal(0), BoolVal(False)
    for r in rules:
        w = enc(r.when, v, params, cat); t = r.then
        if t.decision: d = DEC[t.decision]; dec  = If(And(w, dec  < d), IntVal(d), dec)
        if t.auth:     a = AUTH[t.auth];    auth = If(And(w, auth < a), IntVal(a), auth)
        if t.exempt_auth: exempt = Or(exempt, w)
    return dec, If(exempt, IntVal(0), auth)
```

Ghi chú hiện thực:
- `rules` gồm luật `ACTIVE` + `CANDIDATE` trong change set (luật `SHADOW` kiểm riêng khi chạy shadow).
- Đặt `timeout` cho solver 5.000 ms; quá thời gian → kết quả `UNKNOWN` (hiển thị "không kết luận được", **không** coi là PASS).
- Mỗi phép kiểm tra dùng `Solver()` mới hoặc `push/pop`.

---

## 3. Từng phép kiểm tra

### VC-03 Luật chết
`sat?( domain ∧ when_r )`. `unsat` → ERROR "Luật không bao giờ kích hoạt". Kèm giải thích: thử bỏ từng lá điều kiện để tìm tập lá mâu thuẫn tối thiểu (dùng `unsat_core` với assumption literal cho mỗi lá).

### VC-04 Vi phạm invariant
Với invariant `AUTH_AT_LEAST(L)`:
```
sat?( domain ∧ enc(inv.when) ∧ auth(t) < AUTH[L] )
```
Với `DECISION_AT_MOST(L)`:
```
sat?( domain ∧ enc(inv.when) ∧ decision(t) > DEC[L] )
```
`sat` → lấy model làm phản ví dụ.

**Quy kết luật gây lỗi (blame):** từ model, đánh giá `when_r` của từng luật; luật gây lỗi là:
- với AUTH: các luật khớp có `exempt_auth`; nếu không có, là "thiếu luật hiện thực" (invariant không được luật nào hiện thực).
- với DECISION: các luật khớp có `decision > L`.

**Phản ví dụ dễ đọc:** dùng `Optimize` để đẩy nhân chứng về gần mốc: tối thiểu hóa `amount` (và các trường tiền khác) với trọng số; trường không liên quan đặt giá trị "trung tính" mặc định (ví dụ `hour = 10`, `is_new_device = false`) bằng soft constraint. Kết quả ví dụ: `amount = 10.000.001`, tuổi 366 ngày, người nhận quen.

### VC-05 Luật thừa
Luật r thừa so với s nếu:
```
unsat?( domain ∧ when_r ∧ ¬when_s )                     // r ⊆ s
∧ s.decision ≥ r.decision ∧ s.auth ≥ r.auth ∧ (r.exempt_auth ⇒ s.exempt_auth) ∧ (s.hold_seconds ≥ r.hold_seconds)
```
Chỉ xét cặp cùng `kind` hoặc s là REGULATORY. Số cặp ~n² với n ≈ 10–15: ổn.

### VC-06 Xung đột miễn trừ
Cặp (r có `exempt_auth`, s có `auth ≥ OTP`): `sat?( domain ∧ when_r ∧ when_s )` → WARN kèm nhân chứng. (VC-04 bắt trường hợp xung đột chạm invariant; VC-06 báo cả trường hợp không chạm invariant nhưng có thể ngoài ý muốn.)

### VC-07 Semantic diff
Hai bộ luật R_old, R_new:
```
sat?( domain ∧ (dec_old ≠ dec_new ∨ auth_old ≠ auth_new) )
```
Lặp: lấy nhân chứng, phân loại kiểu khác (ví dụ "tăng HOLD", "mất BIOMETRIC"), thêm ràng buộc loại trừ kiểu đó, tìm tiếp; tối đa 5 nhân chứng. Kèm grounding bằng chạy backtest hai bộ luật và đếm giao dịch khác kết quả.

### VC-02 Ngoài miền
Với mỗi lá điều kiện `ℓ`: `unsat?(domain ∧ ℓ)` → lá luôn sai; `unsat?(domain ∧ ¬ℓ)` → lá luôn đúng. Ví dụ `amount > 600.000.000` → luôn sai.

---

## 4. Grounding: từ phản ví dụ về dữ liệu

Phản ví dụ là một điểm; giám khảo cần biết **vùng đó lớn cỡ nào trong dữ liệu**.

Vùng vi phạm (với AUTH):
```
region = inv.when ∧ (OR các when_r của luật exempt bị blame)
```
Đây là một `Condition` DSL hợp lệ → chạy interpreter trên tập giao dịch → trả `count`, `sum_amount`, phân rã theo `scenario` và `label`. Hiển thị: "Trong dữ liệu tổng hợp 7 ngày: X giao dịch, tổng Y đ lẽ ra phải xác thực sinh trắc học nhưng sẽ được miễn."

Nếu `count = 0`: hiển thị rõ "Backtest **không** bắt được lỗi này vì dữ liệu quá khứ chưa có giao dịch nào như vậy; kiểm chứng hình thức thì bắt được." Đây là thông điệp mạnh nhất của sản phẩm; nên có ít nhất một ca như vậy trong demo (ví dụ lỗi ngay mốc 10.000.000–10.000.001 đ).

---

## 5. Repair tất định (baseline + dự phòng)

Với vi phạm AUTH do luật r miễn trừ:
```
r'.when = r.when ∧ ¬inv.when          // với mọi invariant AUTH bị vi phạm bởi r
```
Ví dụ: thêm `¬(amount > {param})` = `amount <= {param}`. Đơn giản hóa phủ định một lá so sánh thành toán tử ngược. Sau đó **kiểm chứng lại**.

Với vi phạm DECISION do luật r: `r'.when = r.when ∧ ¬inv.when`.

Repair tất định luôn đúng về mặt invariant (nếu không tạo luật chết) nhưng có thể vụng: không tham chiếu tham số khi invariant viết bằng số cứng, không xử lý ý định, không tối ưu L_net. Đây chính là baseline D trong ablation.

---

## 6. Kiểm thử bắt buộc cho module này

1. **Đồng nhất interpreter ↔ Z3 (NFR-5):** với 5.000 giao dịch (2.000 từ dữ liệu + 3.000 sinh ngẫu nhiên trong miền), tính `decision/auth` bằng pandas interpreter và bằng Z3 (`substitute` giá trị rồi `simplify`) → phải trùng 100%. Chạy trong CI/pytest.
2. Mỗi luật seed: VC-03 PASS.
3. Bộ luật seed ban đầu: VC-04 PASS (seed phải sạch), VC-05 phát hiện LG-09 thừa.
4. Thêm DRAFT Demo 1 → VC-04 FAIL INV-AUTH-01 và INV-AUTH-02; phản ví dụ có `amount = 10.000.001` sau Optimize.
5. Đổi tham số 10.000.000 → 5.000.000 → LG-07 bị VC-07/VC-02 phát hiện thay đổi ngữ nghĩa so với ý định (xem `04` Demo 2).
6. Timeout → `UNKNOWN`, không phải PASS.

---

## 7. Hiệu năng

Bộ luật ~10–15 luật, ~17 biến, chủ yếu ràng buộc tuyến tính: mỗi truy vấn thường < 100 ms. Tổng cho VC-03 + VC-04 + VC-05: mục tiêu < 3 s. Nếu chậm: cache theo hash (bộ luật + pack); chạy VC-05 bất đồng bộ.
