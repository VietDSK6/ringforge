import os
import tempfile
from pathlib import Path

# DB riêng cho test (SQLite tạm) — đặt trước khi import app để settings đọc được.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp(prefix='rf-test-')) / 'test.sqlite3'}"
os.environ["RINGFORGE_NO_DOTENV"] = "1"  # test không bao giờ đọc .env thật → không gọi LLM thật, không đụng DB thật
os.environ.pop("LLM_API_KEY", None)

import pytest  # noqa: E402

from app.data.generate import generate  # noqa: E402


@pytest.fixture(scope="session")
def seed_df():
    """Bộ dữ liệu tổng hợp sinh trong bộ nhớ (seed cố định), dùng chung cho mọi test."""
    return generate()
