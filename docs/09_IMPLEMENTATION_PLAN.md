# 09 — Kế hoạch triển khai (một người làm, thành viên 2 vào sau)

Giả định: bạn làm khoảng **10–12 giờ/ngày** từ tối 26/11 đến 03/12. Nếu ít hơn, cắt theo mục 4 sớm hơn. Ước lượng là để lập kế hoạch, sai lệch ±30% là bình thường; quan trọng là **cuối mỗi ngày có link deploy chạy được**.

Ký hiệu: ⏱ ước lượng · ✅ Definition of Done (DoD).

---

## Ngày 0 — Thứ Tư 26/11 (tối, ~3 giờ)

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T0.1 | Soạn và gửi email câu hỏi BTC (`10` mục 6) | 20' | Đã gửi |
| T0.2 | Chốt thành viên 2, gom thông tin đăng ký | 20' | Có đủ thông tin; hẹn đăng ký sáng 27/11 |
| T0.3 | Repo monorepo; FastAPI `/health`; Next.js trang trắng gọi `/health` | 45' | Chạy local |
| T0.4 | **Spike deploy**: Docker API (có `pip install z3-solver pandas pyarrow`) lên Render/Railway; web lên Vercel | 60' | 2 URL public; web hiển thị "API ok" |
| T0.5 | **Spike Z3**: script 30 dòng mã hóa REG-01 + luật miễn trừ → in phản ví dụ | 30' | In ra `amount=10000001…` |

Nếu T0.4 thất bại quá 90': chuyển phương án một container (FastAPI phục vụ static export).

## Ngày 1 — Thứ Năm 27/11 (~11 giờ) · **HẠN ĐĂNG KÝ**

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T1.0 | ~~Đăng ký đội~~ (xong 26/11). Kiểm tra email xác nhận; chưa có thì liên hệ BTC trước 23:59:59 | 10' | Có email xác nhận |
| T1.1 | `catalog.py` + `schema.py` (Pydantic) + validator ngữ nghĩa + `render_vi` | 2h | Test: 9 luật seed parse/validate/render OK |
| T1.2 | Generator S0–S4 + features chống leakage + parquet | 3h | Test ràng buộc miền + tái lập seed + không có amount == 10.000.000 |
| T1.3 | Interpreter pandas + lattice | 1.5h | Test 10 dòng tính tay |
| T1.4 | Z3 encoder + VC-03 + VC-04 + Optimize phản ví dụ | 2h | Test `03` mục 6.2–6.4 |
| T1.5 | Property test interpreter ≡ Z3 | 1h | 5.000 mẫu trùng 100% |
| T1.6 | Endpoint `/catalog`, `/verify` (body = danh sách luật) deploy | 1h | curl staging trả báo cáo |

## Ngày 2 — Thứ Sáu 28/11 (~11 giờ)

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T2.1 | Metrics backtest + L_net + phân rã kịch bản + exposure | 2.5h | Test L_net tay; seed exposure = 0 |
| T2.2 | Seed `rules.json`, `policy_pack.json` theo `02` mục 5–6 | 1h | Seed verify PASS_WITH_WARNINGS (LG-09) |
| T2.3 | `LLMClient` + T1 compile + retry + log `ai_calls` | 3h | 10 câu tune: ≥ 8 hợp lệ schema |
| T2.4 | DB + sessions + rules versioning + reset | 2h | Tạo/reset phiên qua API |
| T2.5 | Web: Landing + Workspace + Rule Studio (gọi compile, hiển thị RuleSentence, giả định) | 2.5h | Trên staging: gõ câu → thấy luật |

**Mốc cuối ngày 2: vertical slice** — gõ câu Demo 1 → luật → bấm Kiểm chứng → thấy FAIL + phản ví dụ (UI thô cũng được).

## Ngày 3 — Thứ Bảy 29/11 (~11 giờ)

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T3.1 | Grounding (vùng vi phạm → count/sum/kịch bản) | 1.5h | Demo 1 hiện số thật hoặc "0 — backtest không bắt được" |
| T3.2 | Repair tất định (`03` mục 5) | 1h | Demo 1 có ≥ 1 candidate PASS không cần LLM |
| T3.3 | T2 repair LLM + kiểm chứng lại + backtest + coverage + scope + xếp hạng | 3h | Demo 1 có 2–3 candidate, có số bị loại |
| T3.4 | VC-05, VC-06 | 1.5h | LG-09 báo thừa |
| T3.5 | Web: Báo cáo kiểm chứng (VerdictBadge, CounterexampleCard, GroundingLine, CandidateCard, DiffView) | 3h | **Demo 1 hoàn chỉnh trên staging** |

## Ngày 4 — Chủ Nhật 30/11 (~11 giờ)

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T4.1 | `/pack`, `/pack/impact` (verify lại + ma sát trước/sau) , `/pack/apply` | 2h | Đổi 10tr→5tr: LG-07 bị báo |
| T4.2 | VC-07 semantic diff (dùng cho impact) | 1.5h | Có nhân chứng + đếm dữ liệu |
| T4.3 | Web: màn hình Policy Pack + tác động | 2h | **Demo 2 hoàn chỉnh** |
| T4.4 | `/backtest` variants + Web Compare (bảng, biểu đồ, thanh trượt) | 3h | **Demo 3 hoàn chỉnh** |
| T4.5 | Change set + phê duyệt (chặn khi FAIL) + audit + màn Review | 2h | Luồng duyệt chạy; audit có bản ghi AI |
| T4.6 | Nhập/xuất JSON bộ luật + Policy Pack (FR-S8); trang API `/docs` công khai có ví dụ, rate limit (FR-S9) | 1.5h | Dán bộ luật lạ → kiểm chứng được; `curl` từ máy khác gọi `/verify` thành công |

**Mốc cuối ngày 4: đủ 3 demo P0 trên staging.**

## Ngày 5 — Thứ Hai 01/12 (~11 giờ)

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T5.1 | Viết fixture 30 test + 10 tune (nếu chưa viết dần từ trước) | 3h | Gold đầy đủ |
| T5.2 | `run_ablation.py` A/B/C/D + `report.md` | 3h | Bảng số thật |
| T5.3 | Cache AI cho đầu vào mẫu + chế độ dự phòng + rate limit + quota | 2h | Tắt API key → 3 demo vẫn chạy với nhãn |
| T5.4 | Guided tour + trạng thái lỗi + banner | 2h | Người lạ làm xong Demo 1 không cần hỏi |
| T5.5 | (P1 nếu kịp) T3 diễn giải quy định, T4 tóm tắt, shadow ngày 7 | còn lại | — |

## Ngày 6 — Thứ Ba 02/12 · **FEATURE FREEZE 12:00**

| ID | Việc | ⏱ | ✅ DoD |
|---|---|---|---|
| T6.1 | Deploy production, monitor UptimeRobot | 1h | Ping xanh |
| T6.2 | QA: Chrome ẩn danh, Safari, điện thoại; mạng chậm; LLM tắt; 2 tab cùng lúc | 2.5h | Không lỗi chặn luồng |
| T6.3 | README đầy đủ (`10` mục 4) + `.env.example` | 1.5h | Người khác chạy được theo README |
| T6.4 | Hướng dẫn 1 trang A4 PDF | 1h | 1 trang, có link, không cần tài khoản |
| T6.5 | Slide 10 trang PDF | 3h | Theo `10` mục 2 |
| T6.6 | Quay + dựng video ≤ 3:00 MP4 | 2.5h | Quay sản phẩm thật trên link production |

## Ngày 7 — Thứ Tư 03/12 · **NỘP BÀI**

| Giờ | Việc |
|---|---|
| Sáng | Sửa lỗi nghiêm trọng duy nhất từ QA; không thêm tính năng |
| 15:00 | Đóng băng code, tag `submission-2026-12-03`, deploy lần cuối |
| 15:00–17:00 | Tạo ZIP từ tag (`git archive`), quét secret, kiểm tra file ZIP giải nén chạy được |
| 17:00–20:00 | Nộp đủ 5 thành phần; chụp màn hình xác nhận |
| 23:59:59 | Hạn chót — **không** để đến giờ này |

## 04/12–11/12
Theo dõi uptime; không sửa sản phẩm/mã nguồn đã nộp. Chuẩn bị pitch từ slide đã nộp; tập trả lời câu hỏi (`10` mục 5). Nếu vào Top 5 (công bố 08/12), cả đội có mặt tại TP.HCM ngày 11/12.

---

## 4. Điểm cắt scope (quyết định theo mốc, không cảm tính)

| Mốc | Nếu chưa đạt | Cắt |
|---|---|---|
| Cuối 27/11: verify chạy trên staging | Trễ ≥ ½ ngày | Bỏ VC-06, VC-07; Demo 2 dùng VC-04 lặp lại thay vì semantic diff |
| Cuối 28/11: vertical slice | Trễ | Bỏ DB: lưu phiên trong bộ nhớ + JSON file (chấp nhận mất phiên khi restart); bỏ versioning |
| Cuối 29/11: Demo 1 đầy đủ | Trễ | Bỏ LLM repair, chỉ giữ repair tất định + LLM viết lời giải thích; ablation D vs C bỏ |
| Cuối 30/11: 3 demo | Trễ | Demo 3 chỉ bảng, bỏ biểu đồ; bỏ Review/shadow, giữ audit log đơn giản |
| 01/12 12:00: ablation chưa chạy | Trễ | Giảm fixture còn 15 case, chỉ A và C |

**Không bao giờ cắt:** Demo 1 end-to-end trên link public · kiểm chứng Z3 thật · backtest L_net thật · chế độ dự phòng LLM · README + video quay sản phẩm thật.

---

## 5. Việc giao thành viên 2 khi tham gia (theo thứ tự giá trị)

1. **QA và vai giám khảo**: làm 3 demo như người lạ, ghi lại chỗ bối rối (30'/lần, lặp nhiều lần).
2. **Viết/rà gold fixture** (`08`): viết case nhóm AMBIGUOUS và INJECTION; rà chéo gold của bạn.
3. **Đọc văn bản gốc QĐ 2345** và hướng dẫn cho ví điện tử; xác nhận "trên"/"từ" 10 triệu; cập nhật Policy Pack source.
4. **Tìm 1–2 người làm risk/fraud** (cựu sinh viên, LinkedIn) để hỏi 15 phút theo câu hỏi ở `10` mục 7 → bằng chứng nỗi đau cho slide.
5. Slide và video (bạn duyệt nội dung).
6. Viết README phần OSS/license.

Ghi vào README phần đóng góp của từng thành viên một cách trung thực.

---

## 6. Thói quen hằng ngày
- Sáng: xem mốc ngày, chọn điểm cắt nếu trễ.
- Mỗi task xong: commit + deploy staging.
- Tối: chạy test + thử Demo 1 trên link public từ điện thoại.
- Dùng công cụ AI hỗ trợ code (ví dụ Claude Code, Kiro) thì ghi lại để khai trong README như thể lệ yêu cầu.
