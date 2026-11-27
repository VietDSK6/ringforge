from __future__ import annotations

from contextlib import asynccontextmanager

import z3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.client import get_client
from app.ai.tasks import seed_cache_size
from app.api import errors, ratelimit
from app.api.approvals import router as approvals_router
from app.api.io import router as io_router
from app.api.pack import router as pack_router
from app.api.sessions import router as sessions_router
from app.api.verify import router as verify_router
from app.config import settings
from app.store import repo
from app.store.db import session_factory


API_DESCRIPTION = """
CI/CD cho chính sách rủi ro: kiểm chứng hình thức (Z3) và backtest tài chính cho bộ luật chống gian lận.
**Dữ liệu 100% tổng hợp, không phải dữ liệu MoMo.** Tiền là số nguyên VNĐ.

### Thử nhanh không cần đăng nhập

```bash
API=https://<địa-chỉ-api>   # hoặc http://localhost:8000

# 1) Kiểm chứng bộ luật seed + một luật miễn trừ của bạn → FAIL kèm phản ví dụ 10.000.001 đ
curl -s -X POST "$API/verify" -H 'Content-Type: application/json' -d '{
  "include_seed_rules": true,
  "rules": [{"id": "MY-01", "name": "Fast-path khách thân thiết", "kind": "FRICTION", "status": "CANDIDATE",
             "when": {"all": [{"field": "sender_account_age_days", "op": ">", "value": 365},
                              {"field": "receiver_is_familiar", "op": "==", "value": true}]},
             "then": {"exempt_auth": true}}]
}'

# 2) Backtest luật chặn khoản nạn nhân → mule: L_net (đ) và chênh lệch so với bộ luật seed
curl -s -X POST "$API/backtest" -H 'Content-Type: application/json' -d '{
  "rules": [{"id": "FR-05", "name": "Tài khoản nhận mới gom tiền", "kind": "FRAUD", "status": "CANDIDATE",
             "when": {"all": [{"field": "receiver_account_age_days", "op": "<", "value": 14},
                              {"field": "receiver_distinct_senders_60m", "op": ">=", "value": 2},
                              {"field": "channel", "op": "==", "value": "P2P"}]},
             "then": {"decision": "HOLD", "hold_seconds": 120}}]
}'

# 3) Danh mục trường dùng được trong luật
curl -s "$API/catalog"
```

Muốn lưu trạng thái (Policy Pack, change set, audit): `POST /sessions` để tạo phiên sandbox, rồi dùng các endpoint `/sessions/{sid}/…`.
Giới hạn: 60 yêu cầu/phút/IP, body tối đa 64 KB.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    with session_factory()() as db:  # tạo bảng nếu chưa có + dọn phiên quá 3 ngày (docs/06 mục 3)
        repo.cleanup_stale_sessions(db)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="RingForge API",
    version="0.1.0",
    description=API_DESCRIPTION,
)

ratelimit.install(app, ratelimit.RateLimiter(settings.rate_limit_per_min))
# errors.install trước CORS: middleware thêm sau nằm ngoài cùng, nên lỗi 413 vẫn có header CORS.
errors.install(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(verify_router)
app.include_router(sessions_router)
app.include_router(pack_router)
app.include_router(approvals_router)
app.include_router(io_router)


# HEAD để dịch vụ ping giữ ấm (UptimeRobot) không nhận 405 → báo "down" sai.
@app.head("/health", include_in_schema=False)
@app.get("/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "z3_version": z3.get_version_string(),
        "app_env": settings.app_env,
        "llm": "ready" if get_client().available else "fallback",
        "ai_cache_entries": seed_cache_size(),  # câu mẫu có kết quả AI đã lưu (chế độ dự phòng)
    }
