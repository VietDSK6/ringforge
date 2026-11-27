# Kết quả biên dịch — tập `tune`

Model: `openai/gpt-6-luna` · prompt `compile.v1` · 10 case · dữ liệu tổng hợp do đội tự viết.

- Hợp lệ schema (lần 1): **10/10**
- Hợp lệ schema (sau retry): **10/10** — DoD T2.3 cần ≥ 8/10
- Qua VC-01 sau retry: **10/10**
- Status đúng: **10/10**
- Tương đương logic với gold (Z3): **8/9**

| Case | Nhóm | Status | Schema | VC-01 | Tương đương | Giả định | ms | Lỗi |
|---|---|---|---|---|---|---|---|---|
| TU-01 | CLEAN | OK | ✅ | ✅ | True | — | 3767 |  |
| TU-02 | CLEAN | OK | ✅ | ✅ | True | — | 2800 |  |
| TU-03 | REG_BYPASS | OK | ✅ | ✅ | True | — | 5184 |  |
| TU-04 | REG_BYPASS | OK | ✅ | ✅ | True | — | 2885 |  |
| TU-05 | DEAD | OK | ✅ | ✅ | True | — | 5036 |  |
| TU-06 | AMBIGUOUS | OK | ✅ | ✅ | False | 1.0 | 2907 |  |
| TU-07 | AMBIGUOUS | OK | ✅ | ✅ | True | 1.0 | 3150 |  |
| TU-08 | INJECTION | OK | ✅ | ✅ | True | — | 2395 |  |
| TU-09 | REDUNDANT | OK | ✅ | ✅ | True | — | 3610 |  |
| TU-10 | OUT_OF_SCOPE | OUT_OF_SCOPE | ✅ | ✅ | — | — | 2473 |  |
