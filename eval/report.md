# Báo cáo ablation (docs/08)

- Tập: `test` · 30 case tổng hợp do đội tự viết, gold viết trước khi chạy model.
- Model: `không có (chưa cấu hình LLM)` · prompt `compile.v1` · 1 lần chạy cho cấu hình có LLM.
- Thời điểm chạy: 2026-11-27T02:10:12+00:00. Không phải dữ liệu vận hành thật; không suy rộng ra tổn thất thật.

**Chưa chạy:** B — LLM thuần (tự đánh giá, tự sửa), C — RingForge (LLM + Z3 + LLM sửa có kiểm chứng lại), D — RingForge, sửa tất định — thiếu `LLM_API_KEY`. Không có số liệu nào cho các cấu hình này.

**Đọc bảng cho đúng:** G dùng gold DSL và chính bộ kiểm chứng Z3; vi phạm gold được đối chiếu với bộ kiểm chứng khi viết fixture (`tests/test_eval_fixtures.py`), nên 100% của G **không phải** bằng chứng độc lập về độ đúng của Z3 — nó cho thấy trên CÙNG luật, backtest (A) bỏ sót gì. Đóng góp của AI chỉ đo được ở B/C/D (cần LLM).

## Phát hiện lỗi

| Cấu hình | Precision | Recall | Case khớp đúng toàn bộ |
|---|---|---|---|
| A — Backtest-only (gold DSL, không Z3) | 62% | 53% | 33% |
| G — Gold DSL + Z3 + sửa tất định (không AI) | 100% | 100% | 100% |

Recall theo mã lỗi:

| Cấu hình | INV-AUTH-01 | INV-AUTH-02 | INV-CX-01 | VC-03 | VC-05 | VC-06 |
|---|---|---|---|---|---|---|
| A | 57% (4/7) | 88% (7/8) | 100% (1/1) | 100% (4/4) | 0% (0/2) | 0% (0/8) |
| G | 100% (7/7) | 100% (8/8) | 100% (1/1) | 100% (4/4) | 100% (2/2) | 100% (8/8) |

## Sửa luật (case có tiêu chí sửa)

| Cấu hình | Thành công | Độ giữ ý định TB (hạng 1) | Mở rộng phạm vi | Dùng tham số khi cần |
|---|---|---|---|---|
| G — Gold DSL + Z3 + sửa tất định (không AI) | 100% (8 case) | 100% | 0% | 100% |

Độ giữ ý định không đo được (luật gốc không khớp giao dịch nào ngoài vùng vi phạm trong dữ liệu): T-14 — không tính vào trung bình, không tính là trượt.

## Độ trễ (ms)

| Cấu hình | Phát hiện p50/p95 | Biên dịch p50/p95 | Sửa p50/p95 |
|---|---|---|---|
| A | 11 / 13 | — | — |
| G | 70 / 202 | — | 314 / 330 |

## Case sai

- A · T-02 (CLEAN): thừa VC-03
- A · T-04 (CLEAN): thừa VC-03
- A · T-05 (CLEAN): thừa VC-03
- A · T-06 (CLEAN): thừa VC-03
- A · T-07 (CLEAN): thừa VC-03
- A · T-09 (REG_BYPASS): thiếu VC-06
- A · T-10 (REG_BYPASS): thiếu INV-AUTH-01
- A · T-11 (REG_BYPASS): thiếu VC-06
- A · T-12 (REG_BYPASS): thiếu VC-06
- A · T-13 (REG_BYPASS): thiếu VC-06
- A · T-14 (REG_BYPASS): thiếu INV-AUTH-01, INV-AUTH-02; thừa VC-03
- A · T-15 (REG_BYPASS): thiếu INV-AUTH-01, VC-06
- A · T-20 (REDUNDANT): thiếu VC-05
- A · T-21 (REDUNDANT): thiếu VC-05
- A · T-22 (CONFLICT): thiếu VC-06; thừa VC-03
- A · T-23 (CONFLICT): thiếu VC-06
- A · T-24 (AMBIGUOUS): thừa VC-03
- A · T-28 (INJECTION): thiếu VC-06
- A · T-29 (INJECTION): thừa VC-03
- A · T-30 (INJECTION): thừa VC-03
