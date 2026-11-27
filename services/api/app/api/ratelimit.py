"""Giới hạn tần suất gọi API theo IP (FR-S9, docs/06 mục 6): mặc định 60 yêu cầu/phút, cửa sổ trượt trong RAM.

Không thêm thư viện (slowapi) vì chỉ có một tiến trình uvicorn; đủ để chặn gọi dồn từ một máy.
/health (ping giữ ấm), tài liệu API và preflight CORS không bị tính.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.errors import error_body

EXEMPT_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")
WINDOW_S = 60


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """(được phép?, số giây nên chờ). per_minute <= 0 nghĩa là tắt giới hạn."""
        if self.per_minute <= 0:
            return True, 0
        t = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= t - WINDOW_S:
                q.popleft()
            if len(q) >= self.per_minute:
                return False, max(1, int(q[0] + WINDOW_S - t) + 1)
            q.append(t)
            return True, 0


def client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()  # Render/Vercel đặt IP thật ở đầu danh sách
    return request.client.host if request.client else "unknown"


def install(app: FastAPI, limiter: RateLimiter) -> None:
    app.state.rate_limiter = limiter

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path.startswith(EXEMPT_PATHS):
            return await call_next(request)
        ok, retry = app.state.rate_limiter.allow(client_key(request))
        if not ok:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry)},
                content=error_body("RATE_LIMITED", f"Gọi API quá nhanh. Thử lại sau {retry} giây.", {"retry_after_s": retry}),
            )
        return await call_next(request)
