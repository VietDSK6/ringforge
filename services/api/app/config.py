"""Cấu hình đọc từ biến môi trường. Xem services/api/.env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: list[str]


def load_settings() -> Settings:
    return Settings(
        app_env=os.environ.get("APP_ENV", "dev"),
        cors_origins=_split_csv(os.environ.get("CORS_ORIGINS", "http://localhost:3000")),
    )


settings = load_settings()
