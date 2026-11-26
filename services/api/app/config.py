"""Cấu hình đọc từ biến môi trường. Xem services/api/.env.example và .env.example ở gốc repo."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_seed_dir() -> Path:
    # Local: services/api/app/config.py → gốc repo là parents[3]. Trong Docker đặt SEED_DIR=/srv/data/seed.
    parents = Path(__file__).resolve().parents
    return parents[3] / "data" / "seed" if len(parents) > 3 else Path("data/seed")


def normalize_db_url(url: str) -> str:
    """Rỗng → SQLite trong thư mục tạm. postgres:// (Supabase/Neon/Render) → driver psycopg của SQLAlchemy."""
    if not url:
        return f"sqlite:///{Path(tempfile.gettempdir()) / 'ringforge.sqlite3'}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw.isdigit() else default


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: list[str]
    seed_dir: Path
    database_url: str
    llm_provider: str
    llm_api_key: str
    llm_model: str
    llm_model_fallback: str
    llm_daily_call_cap: int
    llm_session_daily_cap: int


def load_settings() -> Settings:
    return Settings(
        app_env=os.environ.get("APP_ENV", "dev"),
        cors_origins=_split_csv(os.environ.get("CORS_ORIGINS", "http://localhost:3000")),
        seed_dir=Path(os.environ["SEED_DIR"]) if os.environ.get("SEED_DIR") else _default_seed_dir(),
        database_url=normalize_db_url(os.environ.get("DATABASE_URL", "").strip()),
        llm_provider=os.environ.get("LLM_PROVIDER", "openai").strip().lower(),
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        llm_model=os.environ.get("LLM_MODEL", "").strip(),
        llm_model_fallback=os.environ.get("LLM_MODEL_FALLBACK", "").strip(),
        llm_daily_call_cap=_int_env("LLM_DAILY_CALL_CAP", 500),
        llm_session_daily_cap=_int_env("LLM_SESSION_DAILY_CAP", 40),
    )


settings = load_settings()
