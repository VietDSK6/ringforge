from __future__ import annotations

import z3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.spike_z3 import run_spike

app = FastAPI(title="RingForge API", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# HEAD để dịch vụ ping giữ ấm (UptimeRobot) không nhận 405 → báo "down" sai.
@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "z3_version": z3.get_version_string(),
        "app_env": settings.app_env,
    }


@app.get("/spike/z3")
def spike_z3() -> dict:
    """Spike T0.5: REG-01/02 + luật miễn trừ DRAFT-0001 (lỗi) và bản sửa. Thay bằng /verify ở T1.6."""
    return run_spike()
