"""Phản ví dụ dễ đọc (docs/03 mục 3): đẩy nhân chứng về sát mốc và về giá trị "trung tính".

Thứ tự ưu tiên (lexicographic): tối thiểu tiền (amount → daily_total_after → tiền vào 60 phút), rồi từng trường
còn lại gần giá trị trung tính nhất. Chỉ ảnh hưởng cách trình bày; kết luận sat/unsat do Solver quyết định.
"""

from __future__ import annotations

import z3

from app.dsl.catalog import CATALOG
from app.verify.encoder import ENUM_INDEX

MONEY_ORDER = ("amount", "daily_total_after", "sender_inbound_amount_60m")

# Giá trị trung tính [GL]: một giao dịch P2P ban ngày bình thường của tài khoản lâu năm.
NEUTRAL: dict[str, int | bool | str] = {
    "hour": 10,
    "channel": "P2P",
    "is_new_device": False,
    "sender_kyc_level": "FULL",
    "sender_account_age_days": 400,
    "sender_dormant_days": 0,
    "sender_distinct_inbound_60m": 0,
    "sender_outbound_ratio_60m_pct": 0,
    "sender_outbound_count_24h": 0,
    "receiver_account_age_days": 400,
    "receiver_is_verified_merchant": False,
    "receiver_is_familiar": False,
    "receiver_inbound_count_30m": 0,
    "receiver_distinct_senders_30m": 0,
}


def readable_model(
    ctx: z3.Context, v: dict[str, z3.ExprRef], hard: z3.BoolRef, timeout_ms: int
) -> z3.ModelRef | None:
    """Model đẹp nhất trong thời hạn; None nếu Optimize không kết luận kịp (khi đó dùng model của Solver)."""
    opt = z3.Optimize(ctx=ctx)
    opt.set("timeout", timeout_ms)
    opt.add(hard)
    for name in MONEY_ORDER:
        opt.minimize(v[name])
    for name, val in NEUTRAL.items():
        f, x = CATALOG[name], v[name]
        if f.type == "bool":
            opt.minimize(z3.If(x == z3.BoolVal(bool(val), ctx), z3.IntVal(0, ctx), z3.IntVal(1, ctx)))
        elif f.type == "enum":
            opt.minimize(z3.If(x == ENUM_INDEX[name][val], z3.IntVal(0, ctx), z3.IntVal(1, ctx)))
        else:
            n = z3.IntVal(int(val), ctx)
            opt.minimize(z3.If(x >= n, x - n, n - x))
    return opt.model() if opt.check() == z3.sat else None
