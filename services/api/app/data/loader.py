"""Nạp dữ liệu seed (luật, Policy Pack, giao dịch) từ settings.seed_dir."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings

RULES_FILE = "rules.json"
PACK_FILE = "policy_pack.json"
TX_FILE = "transactions.parquet"


def seed_path(name: str, seed_dir: Path | None = None) -> Path:
    return (seed_dir or settings.seed_dir) / name


def load_seed_rules_raw(seed_dir: Path | None = None) -> list[dict[str, Any]]:
    return json.loads(seed_path(RULES_FILE, seed_dir).read_text(encoding="utf-8"))


def load_seed_pack_raw(seed_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(seed_path(PACK_FILE, seed_dir).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def seed_pack() -> dict[str, Any]:
    """Policy Pack seed đã qua VC-01 (dạng dict chuẩn hóa)."""
    from app.dsl.validator import check_pack

    pack, issues = check_pack(load_seed_pack_raw())
    if pack is None:
        raise RuntimeError(f"Policy Pack seed không hợp lệ: {[i.message_vi for i in issues]}")
    return pack


@lru_cache(maxsize=1)
def seed_rules() -> list[dict[str, Any]]:
    """Bộ luật seed đã qua VC-01 (dạng dict chuẩn hóa)."""
    from app.dsl.validator import check_rules

    rules, issues = check_rules(load_seed_rules_raw(), seed_pack())
    if issues:
        raise RuntimeError(f"Luật seed không hợp lệ: {[i.message_vi for i in issues]}")
    return rules
