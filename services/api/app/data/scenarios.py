"""Thực thể và kịch bản S0–S4 cho dữ liệu tổng hợp (docs/04 mục 2, 4). Mọi số lượng/phân phối là [GL].

Tiền luôn là int (lấy từ lưới số nguyên, không làm tròn số thực). Không có PII: ID tổng hợp dạng U00001, M001…

Diễn giải [GL] ghi lại cho minh bạch:
- Mule (S1): mỗi chiến dịch 3 mule lớp 1 + 1 mule lớp 2 (6 × 4 = 24 mule). "Chèn thanh toán QR nhỏ để hạ tỷ lệ
  chuyển ra" hiện thực là: ở 2 chiến dịch, mule lớp 1 giữ lại 15–30% tiền và tiêu 1–2 khoản QR nhỏ.
- Chiến dịch mule ở ngày 1, 2, 3, 5, 6, 7; chiếm tài khoản ở ngày 1, 2, 4, 5, 6, 7 — ngày 7 (phát lại/shadow) có gian lận.
- TOPUP = nạp tiền điện thoại cho nhà mạng (T01–T03, không phải merchant đã xác minh); BILL trả cho đơn vị
  thu hộ đã xác minh (B01–B06); WITHDRAW rút về tài khoản ngân hàng hệ thống (K01–K08).
- S4 và mọi kịch bản: KHÔNG sinh giao dịch nào đúng 10.000.000 đ (ca "backtest không bắt được, Z3 bắt được").
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import numpy as np

from app.data.features import DAY, Account, local_day, local_hour

SEED = 20261203
START = int(datetime(2026, 11, 17, tzinfo=timezone(timedelta(hours=7))).timestamp())  # 00:00 giờ VN
DAYS = 7
END = START + DAYS * DAY

N_USERS = 3000
N_MERCHANTS, N_VERIFIED = 150, 120
MULE_CAMPAIGN_DAYS = (1, 2, 3, 5, 6, 7)
ATO_DAYS = (1, 2, 4, 5, 6, 7)
TX_CAP, DAY_CAP = 9_900_000, 19_900_000  # mule né cả hai ngưỡng sinh trắc học

# Trọng số giờ trong ngày cho giao dịch thường: đỉnh 11–13h và 19–22h.
HOUR_W = np.array(
    [0.3, 0.2, 0.15, 0.1, 0.1, 0.2, 0.6, 1.0, 1.2, 1.3, 1.5, 2.6, 3.0, 2.4, 1.5, 1.4, 1.5, 1.8, 2.2, 2.8, 3.0, 2.8, 2.0, 1.0]
)
HOUR_P = HOUR_W / HOUR_W.sum()


class World:
    def __init__(self, seed: int = SEED):
        self.rng = np.random.default_rng(seed)
        self.accounts: dict[str, Account] = {}
        self.prior_pairs: dict[tuple[str, str], int] = {}
        self.txs: list[dict[str, Any]] = []
        self.day_out: dict[tuple[str, int], int] = defaultdict(int)
        self.users: list[str] = []
        self.merchants: list[str] = []
        self.merchant_p: np.ndarray = np.array([])
        self.friends: dict[str, list[str]] = {}

    # ---------- tiện ích ngẫu nhiên (tiền luôn là int) ----------

    def ri(self, lo: int, hi: int) -> int:
        """Số nguyên đều trong [lo, hi]."""
        return int(self.rng.integers(lo, hi + 1))

    def money(self, lo: int, hi: int, step: int) -> int:
        """Tiền đều trên lưới bội số step trong [lo, hi]."""
        return step * self.ri(-(-lo // step), hi // step)

    def money_log(self, lo: int, hi: int, step: int) -> int:
        """Tiền lệch về số nhỏ (xác suất ∝ 1/k) trên lưới bội số step."""
        k0, k1 = -(-lo // step), hi // step
        return step * (k0 + int(self.rng.choice(k1 - k0 + 1, p=_inv_weights(k0, k1))))

    def pick(self, items: list[str]) -> str:
        return items[int(self.rng.integers(len(items)))]

    def ts_in_day(self, day: int, hour: int | None = None) -> int:
        h = int(self.rng.choice(24, p=HOUR_P)) if hour is None else hour
        return START + (day - 1) * DAY + h * 3600 + self.ri(0, 3599)

    # ---------- thực thể & giao dịch ----------

    def add_account(self, acc: Account) -> Account:
        self.accounts[acc.id] = acc
        return acc

    def add_tx(self, ts: int, sender: str, receiver: str, amount: int, channel: str, label: str, scenario: str) -> bool:
        if not START <= ts < END:
            return False
        assert amount != 10_000_000 and amount >= 1
        acc = self.accounts[sender]
        self.txs.append(
            {
                "seq": len(self.txs),
                "ts": ts,
                "sender_id": sender,
                "receiver_id": receiver,
                "amount": int(amount),
                "channel": channel,
                "is_new_device": acc.is_new_device(ts),
                "sender_kyc_level": acc.kyc,
                "label": label,
                "scenario": scenario,
            }
        )
        self.day_out[(sender, local_day(ts))] += amount
        return True


@lru_cache(maxsize=64)
def _inv_weights(k0: int, k1: int) -> np.ndarray:
    w = 1.0 / np.arange(k0, k1 + 1)
    return w / w.sum()


# ---------- thực thể ----------


def build_entities(w: World) -> None:
    rng = w.rng
    for i in range(N_USERS):
        if rng.random() < 0.85:
            age = min(180 + int(rng.gamma(2.0, 400.0)), 3600)
        else:
            age = w.ri(14, 179)
        created = START - age * DAY - w.ri(0, DAY - 1)
        dormant = w.ri(10, 60) if rng.random() < 0.05 else w.ri(0, 3)
        last_active = max(created, START - dormant * DAY - w.ri(0, DAY - 1))
        acc = Account(f"U{i:05d}", created, "FULL" if rng.random() < 0.85 else "BASIC", False, last_active)
        if rng.random() < 0.03:
            acc.device_changes.append(START + w.ri(0, DAYS * DAY - 1))
        w.add_account(acc)
        w.users.append(acc.id)

    for i in range(N_MERCHANTS):
        verified = i < N_VERIFIED
        age = w.ri(30, 2500) if verified else w.ri(5, 1500)
        w.add_account(Account(f"M{i + 1:03d}", START - age * DAY - w.ri(0, DAY - 1), "FULL", verified))
        w.merchants.append(f"M{i + 1:03d}")
    pop = 1.0 / np.arange(1, N_MERCHANTS + 1) ** 0.8
    w.merchant_p = pop / pop.sum()

    for i in range(1, 4):
        w.add_account(Account(f"T{i:02d}", START - 3650 * DAY, "FULL", False))  # nhà mạng
    for i in range(1, 7):
        w.add_account(Account(f"B{i:02d}", START - 3000 * DAY, "FULL", True))  # đơn vị thu hộ
    for i in range(1, 9):
        w.add_account(Account(f"K{i:02d}", START - 3650 * DAY, "FULL", False))  # ngân hàng

    # Bạn bè: 5 người/user; 2 người thân (đã chuyển ≥ 3 lần trong 90 ngày trước kỳ).
    for u in w.users:
        fr = [w.users[int(j)] for j in rng.choice(N_USERS, 6, replace=False) if w.users[int(j)] != u][:5]
        w.friends[u] = fr
        for k, f in enumerate(fr):
            prior = w.ri(3, 12) if k < 2 else w.ri(0, 2)
            if prior:
                w.prior_pairs[(u, f)] = prior


# ---------- S0: bình thường ----------


def scenario_normal(w: World) -> None:
    rng = w.rng
    channels = ["P2P", "MERCHANT_QR", "BILL", "TOPUP", "WITHDRAW"]
    ch_p = [0.38, 0.37, 0.08, 0.10, 0.07]
    rates = rng.gamma(2.0, 0.45, size=N_USERS)
    billers = [f"B{i:02d}" for i in range(1, 7)]
    telcos = [f"T{i:02d}" for i in range(1, 4)]
    banks = [f"K{i:02d}" for i in range(1, 9)]
    for ui, u in enumerate(w.users):
        for day in range(1, DAYS + 1):
            for _ in range(int(rng.poisson(rates[ui]))):
                ts = w.ts_in_day(day)
                if rng.random() < 0.004:  # giao dịch lớn hợp lệ: mua xe, học phí
                    if rng.random() < 0.6:
                        seller = w.pick(w.users)
                        if seller != u:
                            w.add_tx(ts, u, seller, w.money(10_100_000, 50_000_000, 100_000), "P2P", "LEGIT", "S0_NORMAL")
                    else:
                        w.add_tx(ts, u, w.pick(billers), w.money(10_100_000, 50_000_000, 100_000), "BILL", "LEGIT", "S0_NORMAL")
                    continue
                ch = channels[int(rng.choice(5, p=ch_p))]
                if ch == "P2P":
                    to = w.pick(w.friends[u]) if rng.random() < 0.85 else w.pick(w.users)
                    if to == u:
                        continue
                    w.add_tx(ts, u, to, w.money_log(50_000, 5_000_000, 10_000), ch, "LEGIT", "S0_NORMAL")
                elif ch == "MERCHANT_QR":
                    m = w.merchants[int(rng.choice(N_MERCHANTS, p=w.merchant_p))]
                    w.add_tx(ts, u, m, w.money_log(20_000, 2_000_000, 1_000), ch, "LEGIT", "S0_NORMAL")
                elif ch == "BILL":
                    w.add_tx(ts, u, w.pick(billers), w.money_log(100_000, 3_000_000, 1_000), ch, "LEGIT", "S0_NORMAL")
                elif ch == "TOPUP":
                    amt = [10_000, 20_000, 50_000, 100_000, 200_000, 500_000][int(rng.integers(6))]
                    w.add_tx(ts, u, w.pick(telcos), amt, ch, "LEGIT", "S0_NORMAL")
                else:
                    w.add_tx(ts, u, w.pick(banks), w.money_log(200_000, 5_000_000, 50_000), ch, "LEGIT", "S0_NORMAL")


# ---------- S1: mạng mule ----------


def _drain(
    w: World,
    acc: str,
    inflows: list[tuple[int, int]],
    delay: tuple[int, int],
    to_fn,
    channel: str,
    share_bp: int = 10_000,
) -> list[tuple[int, int]]:
    """Mule chuyển tiếp tiền nhận được: mỗi lệnh ≤ 9,9 tr, tổng chi/ngày ≤ 19,9 tr; hết hạn mức thì sang tối hôm sau."""
    emitted: list[tuple[int, int]] = []
    by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for ts, a in sorted(inflows):
        by_day[local_day(ts)].append((ts, a))
    pending, t = 0, START
    for d in sorted(by_day):
        batch = by_day[d]
        pending += sum(a for _, a in batch) * share_bp // 10_000
        t = max(t, batch[-1][0]) + w.ri(*delay)
        while pending > 0 and t < END:
            room = DAY_CAP - w.day_out[(acc, local_day(t))]
            chunk = min(pending, w.money(3_000_000, TX_CAP, 10_000), room)
            if chunk < 500_000 and chunk < pending:
                # hết hạn mức ngày → tiếp tục 19:00–20:59 tối hôm sau
                t = START + (local_day(t) - local_day(START) + 1) * DAY + w.ri(19 * 3600, 21 * 3600 - 1)
                continue
            to = to_fn()
            if w.add_tx(t, acc, to, chunk, channel, "MULE_LAYER", "S1_MULE"):
                emitted.append((t, chunk))
            pending -= chunk
            t += w.ri(120, 480)
    return emitted


def scenario_mule(w: World) -> None:
    rng = w.rng
    banks = [f"K{i:02d}" for i in range(1, 9)]
    mule_n = 0
    for c, day in enumerate(MULE_CAMPAIGN_DAYS):
        day_start = START + (day - 1) * DAY
        mules = []
        for _ in range(4):
            age = w.ri(1, 11)
            created = day_start - age * DAY - w.ri(0, DAY - 1)
            w.add_account(Account(f"U{N_USERS + 6 + mule_n:05d}", created, "BASIC", False, None))
            mules.append(f"U{N_USERS + 6 + mule_n:05d}")
            mule_n += 1
        l1, l2 = mules[:3], mules[3]
        fast = c % 2 == 0  # nửa chiến dịch chuyển ra trong 15 phút, nửa còn lại 25–50 phút
        keep_some = c in (1, 4)

        victims = [w.users[int(i)] for i in rng.choice(N_USERS, w.ri(8, 15), replace=False)]
        base = day_start + w.ri(19 * 3600, 21 * 3600 - 1)
        inflows: dict[str, list[tuple[int, int]]] = {m: [] for m in l1}
        bursts = {m: base + j * w.ri(600, 1800) for j, m in enumerate(l1)}
        for k, v in enumerate(victims):
            m = l1[k % 3]
            ts = bursts[m] + w.ri(0, 2400)
            amt = w.money(3_000_000, 9_500_000, 10_000)
            if w.add_tx(ts, v, m, amt, "P2P", "APP_VICTIM", "S1_MULE"):
                inflows[m].append((ts, amt))

        to_l2: list[tuple[int, int]] = []
        for m in l1:
            if not inflows[m]:
                continue
            delay = (300, 900) if fast else (1500, 3000)
            share = 10_000
            if keep_some:
                share = w.ri(7_000, 8_500)
                last_in = max(t for t, _ in inflows[m])
                for _ in range(w.ri(1, 2)):
                    shop = w.merchants[int(rng.choice(N_MERCHANTS, p=w.merchant_p))]
                    w.add_tx(last_in + w.ri(60, delay[0] - 60), m, shop, w.money(50_000, 300_000, 1_000), "MERCHANT_QR", "MULE_LAYER", "S1_MULE")
            to_l2 += _drain(w, m, inflows[m], delay, lambda: l2, "P2P", share)
        _drain(w, l2, to_l2, (600, 2400), lambda: w.pick(banks), "WITHDRAW")


# ---------- S2: chiếm tài khoản ngủ đông ----------


def scenario_ato(w: World) -> None:
    drops = []
    for i in range(6):
        drop = f"U{N_USERS + 30 + i:05d}"
        w.add_account(Account(drop, START - w.ri(2, 60) * DAY, "BASIC", False, None))
        drops.append(drop)
    for i, day in enumerate(ATO_DAYS):
        dormant = w.ri(90, 400)
        last_active = START - dormant * DAY - w.ri(0, DAY - 1)
        acc = w.add_account(Account(f"U{N_USERS + i:05d}", last_active - w.ri(100, 1500) * DAY, "FULL", False, last_active))
        t = START + (day - 1) * DAY + w.ri(0, 3 * 3600 - 1)
        acc.device_changes.append(t - w.ri(60, 600))
        targets = [drops[i], drops[(i + 1) % 6]][: w.ri(1, 2)]
        for k in range(w.ri(3, 5)):
            if local_hour(t) > 4:
                break
            w.add_tx(t, acc.id, targets[k % len(targets)], w.money(4_000_000, 9_800_000, 10_000), "P2P", "ATO", "S2_ATO")
            t += w.ri(180, 1200)


# ---------- S3: flash-sale hợp lệ ----------


def scenario_flash_sale(w: World) -> None:
    # 2 merchant CHƯA xác minh + 1 đã xác minh (FR-04 bắt nhầm 2 merchant đầu).
    events = [("M121", 2, 12), ("M122", 4, 20), ("M050", 6, 12)]
    for merchant, day, hour in events:
        t0 = START + (day - 1) * DAY + hour * 3600 + w.ri(0, 1799)
        n = w.ri(40, 120)
        for j in w.rng.choice(N_USERS, n, replace=False):
            w.add_tx(t0 + w.ri(0, 1799), w.users[int(j)], merchant, w.money(50_000, 500_000, 1_000), "MERCHANT_QR", "LEGIT", "S3_FLASH_SALE")


# ---------- S4: khách thân thiết chuyển lớn ----------


def scenario_familiar_high(w: World) -> None:
    rng = w.rng
    long_users = [u for u in w.users if START - w.accounts[u].created_ts > 365 * DAY]
    senders = [long_users[int(i)] for i in rng.choice(len(long_users), 200, replace=False)]
    for s in senders:
        r = w.pick(w.users)
        while r == s:
            r = w.pick(w.users)
        w.prior_pairs[(s, r)] = w.ri(3, 20)
        for day in sorted(int(d) for d in rng.choice(np.arange(1, DAYS + 1), w.ri(1, 2), replace=False)):
            if rng.random() < 0.6:
                amt = w.money(1_000_000, 9_990_000, 10_000)
            else:
                amt = w.money(10_010_000, 30_000_000, 10_000)
            w.add_tx(w.ts_in_day(day, w.ri(8, 21)), s, r, amt, "P2P", "LEGIT", "S4_FAMILIAR_HIGH")


def build_world(seed: int = SEED) -> World:
    w = World(seed)
    build_entities(w)
    scenario_normal(w)
    scenario_mule(w)
    scenario_ato(w)
    scenario_flash_sale(w)
    scenario_familiar_high(w)
    return w
