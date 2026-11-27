"""Tính đặc trưng chống leakage cho bảng giao dịch (docs/04 mục 3).

Duyệt giao dịch theo (ts, tx_id). Cửa sổ thời gian chỉ dùng giao dịch có ts_i − W ≤ ts < ts_i (không gồm i),
trừ `daily_total_after` (từ 00:00 giờ VN cùng ngày đến và gồm i) và tử số của `sender_outbound_ratio_60m_pct`
(gồm amount_i). Mọi phép tính tiền là int Python.

Quy ước [GL]: "hoạt động" cho `sender_dormant_days` là giao dịch CHI của tài khoản (nhận tiền không tính,
vì tài khoản bị chiếm vẫn có thể nhận tiền mà chủ không hề dùng).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from app.dsl.catalog import CATALOG, FIELD_NAMES

DAY = 86_400
VN_OFFSET = 7 * 3600
W_SENDER = 3600  # 60 phút
W_RECEIVER = (900, 1800, 3600)  # 15, 30, 60 phút
W_24H = DAY


@dataclass
class Account:
    id: str
    created_ts: int
    kyc: str = "FULL"
    verified_merchant: bool = False
    last_active_ts: int | None = None  # giao dịch chi gần nhất trước kỳ dữ liệu; None = chưa từng chi
    device_changes: list[int] = field(default_factory=list)  # thời điểm bắt đầu dùng thiết bị mới

    def is_new_device(self, ts: int) -> bool:
        """Thiết bị mới trong 7 ngày: tính từ lúc tạo tài khoản hoặc lúc đổi thiết bị."""
        return any(c <= ts < c + 7 * DAY for c in [self.created_ts, *self.device_changes])


def local_hour(ts: int) -> int:
    return ((ts + VN_OFFSET) // 3600) % 24


def local_day(ts: int) -> int:
    return (ts + VN_OFFSET) // DAY


def _clip(name: str, v: int) -> int:
    f = CATALOG[name]
    return min(max(v, f.lo), f.hi)


def compute_features(
    raw: pd.DataFrame,
    accounts: Mapping[str, Account],
    prior_pairs: Mapping[tuple[str, str], int],
) -> pd.DataFrame:
    """raw cần các cột: tx_id, ts, sender_id, receiver_id, amount, channel, is_new_device, sender_kyc_level.
    Trả về raw (đã sắp theo ts, tx_id) + các cột catalog theo đúng thứ tự catalog."""
    df = raw.sort_values(["ts", "tx_id"], kind="stable").reset_index(drop=True)

    out_hist: dict[str, deque[tuple[int, int]]] = defaultdict(deque)  # (ts, amount) giao dịch chi, giữ 24h
    in_hist: dict[str, deque[tuple[int, int, str]]] = defaultdict(deque)  # (ts, amount, sender), giữ 60 phút
    day_out: dict[str, tuple[int, int]] = {}  # account → (ngày VN, tổng chi)
    last_out: dict[str, int] = {a.id: (a.last_active_ts if a.last_active_ts is not None else a.created_ts) for a in accounts.values()}
    pair_count: dict[tuple[str, str], int] = defaultdict(int, prior_pairs)

    cols: dict[str, list] = {name: [] for name in FIELD_NAMES}
    for ts, s, r, amount, channel, new_dev, kyc in zip(
        df["ts"].tolist(),
        df["sender_id"].tolist(),
        df["receiver_id"].tolist(),
        df["amount"].tolist(),
        df["channel"].tolist(),
        df["is_new_device"].tolist(),
        df["sender_kyc_level"].tolist(),
    ):
        sa, ra = accounts[s], accounts[r]

        # Cắt bỏ phần cũ khỏi cửa sổ (ts tăng dần nên an toàn).
        oh = out_hist[s]
        while oh and oh[0][0] < ts - W_24H:
            oh.popleft()
        for acc in (s, r):
            ih = in_hist[acc]
            while ih and ih[0][0] < ts - W_SENDER:
                ih.popleft()

        # Người gửi: tiền vào 60 phút trước (không gồm giao dịch cùng giây với i).
        in_amt, in_senders = 0, set()
        for t, a, frm in in_hist[s]:
            if t < ts:
                in_amt += a
                in_senders.add(frm)
        out_amt_60 = sum(a for t, a in oh if ts - W_SENDER <= t < ts)
        out_cnt_24 = sum(1 for t, _ in oh if t < ts)
        ratio = (out_amt_60 + amount) * 100 // in_amt if in_amt > 0 else 0

        # Người nhận: nhận vào 15/30/60 phút trước (cửa sổ lồng nhau).
        r_cnt = dict.fromkeys(W_RECEIVER, 0)
        r_senders: dict[int, set[str]] = {w: set() for w in W_RECEIVER}
        for t, _, frm in in_hist[r]:
            for w in W_RECEIVER:
                if ts - w <= t < ts:
                    r_cnt[w] += 1
                    r_senders[w].add(frm)

        d = local_day(ts)
        prev_day, prev_sum = day_out.get(s, (d, 0))
        daily = (prev_sum if prev_day == d else 0) + amount

        cols["amount"].append(amount)
        cols["channel"].append(channel)
        cols["hour"].append(local_hour(ts))
        cols["daily_total_after"].append(_clip("daily_total_after", daily))
        cols["is_new_device"].append(bool(new_dev))
        cols["sender_account_age_days"].append(_clip("sender_account_age_days", (ts - sa.created_ts) // DAY))
        cols["sender_dormant_days"].append(_clip("sender_dormant_days", (ts - last_out[s]) // DAY))
        cols["sender_kyc_level"].append(kyc)
        cols["sender_inbound_amount_60m"].append(_clip("sender_inbound_amount_60m", in_amt))
        cols["sender_distinct_inbound_60m"].append(_clip("sender_distinct_inbound_60m", len(in_senders)))
        cols["sender_outbound_ratio_60m_pct"].append(_clip("sender_outbound_ratio_60m_pct", ratio))
        cols["sender_outbound_count_24h"].append(_clip("sender_outbound_count_24h", out_cnt_24))
        cols["receiver_account_age_days"].append(_clip("receiver_account_age_days", (ts - ra.created_ts) // DAY))
        cols["receiver_is_verified_merchant"].append(ra.verified_merchant)
        cols["receiver_is_familiar"].append(pair_count[(s, r)] >= 3)
        for w, tag in zip(W_RECEIVER, ("15m", "30m", "60m")):
            cols[f"receiver_inbound_count_{tag}"].append(_clip(f"receiver_inbound_count_{tag}", r_cnt[w]))
            cols[f"receiver_distinct_senders_{tag}"].append(_clip(f"receiver_distinct_senders_{tag}", len(r_senders[w])))

        # Cập nhật trạng thái SAU khi tính (chống leakage).
        oh.append((ts, amount))
        in_hist[r].append((ts, amount, s))
        day_out[s] = (d, daily)
        last_out[s] = ts
        pair_count[(s, r)] += 1

    base = df.drop(columns=[c for c in FIELD_NAMES if c in df.columns])
    return pd.concat([base, pd.DataFrame(cols)], axis=1)
