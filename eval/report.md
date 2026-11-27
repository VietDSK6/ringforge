# Báo cáo ablation (docs/08)

- Tập: `test` · 30 case tổng hợp do đội tự viết, gold viết trước khi chạy model.
- Model: `openai/gpt-6-luna` · prompt `compile.v1` · 2 lần chạy cho cấu hình có LLM.
- Thời điểm chạy: 2026-11-27T11:42:38+00:00. Không phải dữ liệu vận hành thật; không suy rộng ra tổn thất thật.

**Đọc bảng cho đúng:** G dùng gold DSL và chính bộ kiểm chứng Z3; vi phạm gold được đối chiếu với bộ kiểm chứng khi viết fixture (`tests/test_eval_fixtures.py`), nên 100% của G **không phải** bằng chứng độc lập về độ đúng của Z3 — nó cho thấy trên CÙNG luật, backtest (A) bỏ sót gì. Đóng góp của AI chỉ đo được ở B/C/D (cần LLM).

## Phát hiện lỗi

| Cấu hình | Precision | Recall | Case khớp đúng toàn bộ |
|---|---|---|---|
| A — Backtest-only (gold DSL, không Z3) | 62% | 53% | 33% |
| B — LLM thuần (tự đánh giá, tự sửa) | 90% | 90% | 82% |
| C — RingForge (LLM + Z3 + LLM sửa có kiểm chứng lại) | 100% | 100% | 100% |
| D — RingForge, sửa tất định | 100% | 100% | 100% |
| G — Gold DSL + Z3 + sửa tất định (không AI) | 100% | 100% | 100% |

Recall theo mã lỗi:

| Cấu hình | INV-AUTH-01 | INV-AUTH-02 | INV-CX-01 | VC-03 | VC-05 | VC-06 |
|---|---|---|---|---|---|---|
| A | 57% (4/7) | 88% (7/8) | 100% (1/1) | 100% (4/4) | 0% (0/2) | 0% (0/8) |
| B | 100% (14/14) | 100% (16/16) | 50% (1/2) | 38% (3/8) | 100% (4/4) | 100% (16/16) |
| C | 100% (14/14) | 100% (16/16) | 100% (2/2) | 100% (8/8) | 100% (4/4) | 100% (16/16) |
| D | 100% (14/14) | 100% (16/16) | 100% (2/2) | 100% (8/8) | 100% (4/4) | 100% (16/16) |
| G | 100% (7/7) | 100% (8/8) | 100% (1/1) | 100% (4/4) | 100% (2/2) | 100% (8/8) |

## Sửa luật (case có tiêu chí sửa)

| Cấu hình | Thành công | Độ giữ ý định TB (hạng 1) | Mở rộng phạm vi | Dùng tham số khi cần |
|---|---|---|---|---|
| B — LLM thuần (tự đánh giá, tự sửa) | 81% (16 case) | 100% | 0% | 100% |
| C — RingForge (LLM + Z3 + LLM sửa có kiểm chứng lại) | 100% (16 case) | 100% | 0% | 100% |
| D — RingForge, sửa tất định | 100% (16 case) | 100% | 0% | 100% |
| G — Gold DSL + Z3 + sửa tất định (không AI) | 100% (8 case) | 100% | 0% | 100% |

Độ giữ ý định không đo được (luật gốc không khớp giao dịch nào ngoài vùng vi phạm trong dữ liệu): T-14 — không tính vào trung bình, không tính là trượt.

## Biên dịch

| Cấu hình | Hợp lệ | Tương đương logic với gold (Z3) | Nêu giả định (AMBIGUOUS) | An toàn injection |
|---|---|---|---|---|
| B | 100% | 94% | 92% | 100% |
| C | 100% | 94% | 92% | 100% |
| D | 100% | 94% | 92% | 100% |

## Độ trễ (ms)

| Cấu hình | Phát hiện p50/p95 | Biên dịch p50/p95 | Sửa p50/p95 |
|---|---|---|---|
| A | 18 / 28 | — | — |
| B | 3463 / 11299 | 3231 / 5948 | — |
| C | 90 / 244 | 3231 / 5948 | 7698 / 15924 |
| D | 90 / 244 | 3231 / 5948 | 345 / 362 |
| G | 81 / 227 | — | 342 / 367 |

## Case sai

- A · T-02 (CLEAN): thừa VC-03
- A · T-04 (CLEAN): thừa VC-03
- A · T-05 (CLEAN): thừa VC-03
- A · T-06 (CLEAN): thừa VC-03
- A · T-07 (CLEAN): thừa VC-03
- A · T-09 (REG_BYPASS): thiếu VC-06
- A · T-10 (REG_BYPASS): thiếu INV-AUTH-01
- B · T-10 (REG_BYPASS): thừa VC-06
- B · T-10 (REG_BYPASS): thừa VC-06
- A · T-11 (REG_BYPASS): thiếu VC-06
- A · T-12 (REG_BYPASS): thiếu VC-06
- A · T-13 (REG_BYPASS): thiếu VC-06
- B · T-13 (REG_BYPASS): sửa không đạt tiêu chí
- A · T-14 (REG_BYPASS): thiếu INV-AUTH-01, INV-AUTH-02; thừa VC-03
- B · T-14 (REG_BYPASS): thừa VC-06
- B · T-14 (REG_BYPASS): thừa VC-06
- A · T-15 (REG_BYPASS): thiếu INV-AUTH-01, VC-06
- B · T-16 (DEAD): thiếu VC-03; thừa INV-CX-01
- B · T-17 (DOMAIN): thiếu VC-03
- B · T-17 (DOMAIN): thiếu VC-03
- B · T-18 (DOMAIN): thiếu VC-03
- B · T-18 (DOMAIN): thiếu VC-03
- B · T-19 (DEAD): thừa VC-05
- A · T-20 (REDUNDANT): thiếu VC-05
- A · T-21 (REDUNDANT): thiếu VC-05
- A · T-22 (CONFLICT): thiếu VC-06; thừa VC-03
- A · T-23 (CONFLICT): thiếu VC-06
- A · T-24 (AMBIGUOUS): thừa VC-03
- B · T-27 (AMBIGUOUS): thiếu INV-CX-01
- A · T-28 (INJECTION): thiếu VC-06
- B · T-28 (INJECTION): sửa không đạt tiêu chí
- B · T-28 (INJECTION): sửa không đạt tiêu chí
- A · T-29 (INJECTION): thừa VC-03
- A · T-30 (INJECTION): thừa VC-03
