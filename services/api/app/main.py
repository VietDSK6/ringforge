from __future__ import annotations

import z3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import errors
from app.api.verify import router as verify_router
from app.config import settings

app = FastAPI(
    title="RingForge API",
    version="0.1.0",
    description="CI/CD cho chính sách rủi ro: kiểm chứng hình thức bộ luật chống gian lận (dữ liệu tổng hợp).",
)

# errors.install trước CORS: middleware thêm sau nằm ngoài cùng, nên lỗi 413 vẫn có header CORS.
errors.install(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(verify_router)


# HEAD để dịch vụ ping giữ ấm (UptimeRobot) không nhận 405 → báo "down" sai.
@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "z3_version": z3.get_version_string(),
        "app_env": settings.app_env,
    }
