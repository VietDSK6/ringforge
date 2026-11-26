"""Sinh data/seed/transactions.parquet (docs/04). Chạy: python -m app.data.generate [--out PATH]

Tất định theo SEED = 20261203: chạy lại cho cùng file (test so sánh hash).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.data.features import DAY, compute_features
from app.data.loader import TX_FILE, seed_path
from app.data.scenarios import SEED, START, build_world
from app.dsl.catalog import FIELD_NAMES

META_COLS = ["tx_id", "ts", "day", "sender_id", "receiver_id", "label", "scenario"]


def generate(seed: int = SEED) -> pd.DataFrame:
    w = build_world(seed)
    raw = pd.DataFrame(w.txs).sort_values(["ts", "seq"], kind="stable").reset_index(drop=True)
    raw["tx_id"] = [f"T{i:06d}" for i in range(len(raw))]
    df = compute_features(raw.drop(columns=["seq"]), w.accounts, w.prior_pairs)
    df["day"] = (df["ts"] - START) // DAY + 1
    df = df[META_COLS + list(FIELD_NAMES)]
    for c in ("ts", "day") + tuple(f for f in FIELD_NAMES if df[f].dtype.kind == "i"):
        df[c] = df[c].astype("int64")
    return df


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow", compression="zstd")


def summary(df: pd.DataFrame) -> str:
    lines = [f"{len(df):,} giao dịch, {df['sender_id'].nunique():,} người gửi"]
    lines.append(df.groupby(["scenario", "label"]).size().to_string())
    fraud = df["label"].isin(["APP_VICTIM", "ATO", "MULE_LAYER"]).mean()
    lines.append(f"Tỷ lệ gian lận theo số giao dịch: {fraud * 10_000:.0f} bp")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh dữ liệu giao dịch tổng hợp RingForge")
    ap.add_argument("--out", type=Path, default=seed_path(TX_FILE))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    df = generate(args.seed)
    write_parquet(df, args.out)
    print(f"Đã ghi {args.out}")
    print(summary(df))


if __name__ == "__main__":
    main()
