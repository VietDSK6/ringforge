import pytest

from app.data.generate import generate


@pytest.fixture(scope="session")
def seed_df():
    """Bộ dữ liệu tổng hợp sinh trong bộ nhớ (seed cố định), dùng chung cho mọi test."""
    return generate()
