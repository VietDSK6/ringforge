"""Cấu hình đọc từ biến môi trường. Xem services/api/.env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_seed_dir() -> Path:
    # Local: services/api/app/config.py → gốc repo là parents[3]. Trong Docker đặt SEED_DIR=/srv/data/seed.
    parents = Path(__file__).resolve().parents
    return parents[3] / "data" / "seed" if len(parents) > 3 else Path("data/seed")


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: list[str]
    seed_dir: Path


def load_settings() -> Settings:
    return Settings(
        app_env=os.environ.get("APP_ENV", "dev"),
        cors_origins=_split_csv(os.environ.get("CORS_ORIGINS", "http://localhost:3000")),
        seed_dir=Path(os.environ["SEED_DIR"]) if os.environ.get("SEED_DIR") else _default_seed_dir(),
    )


settings = load_settings()
