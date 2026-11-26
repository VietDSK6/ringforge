"""Lớp gọi model (docs/05 mục 1): complete_json(system, user, json_schema) → dict.

Provider chọn qua env LLM_PROVIDER (hiện hỗ trợ "openai"). Không tool calling, không đưa secret vào prompt.
Timeout 25 s; lỗi mạng/5xx/timeout → thử lại 1 lần với model dự phòng.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from app.config import settings

TIMEOUT_S = 25


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # LLM_UNAVAILABLE | LLM_BAD_OUTPUT | LLM_REFUSED


@dataclass
class LLMResult:
    data: dict[str, Any]
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    attempts: list[str] = field(default_factory=list)


class LLMClient(Protocol):
    available: bool
    model: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any], schema_name: str) -> LLMResult: ...


class UnavailableClient:
    """Không có key/model: mọi lời gọi báo LLM_UNAVAILABLE → UI dùng kết quả đã lưu hoặc sửa tất định."""

    available = False
    model = ""

    def __init__(self, reason: str):
        self.reason = reason

    def complete_json(self, system: str, user: str, schema: dict[str, Any], schema_name: str) -> LLMResult:
        raise LLMError("LLM_UNAVAILABLE", self.reason)


class OpenAIClient:
    available = True

    def __init__(self, api_key: str, model: str, fallback: str = ""):
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, max_retries=0, timeout=TIMEOUT_S)
        self.model = model
        self.fallback = fallback

    def _call(self, model: str, system: str, user: str, schema: dict[str, Any], schema_name: str) -> LLMResult:
        started = time.perf_counter_ns()
        resp = self._client.responses.create(
            model=model,
            instructions=system,
            input=[{"role": "user", "content": user}],
            text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
            store=False,
            timeout=TIMEOUT_S,
        )
        latency = (time.perf_counter_ns() - started) // 1_000_000
        for item in resp.output or []:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", "") == "refusal":
                    raise LLMError("LLM_REFUSED", getattr(part, "refusal", "") or "Model từ chối trả lời.")
        if resp.status == "incomplete":
            raise LLMError("LLM_BAD_OUTPUT", f"Output bị cắt ngang: {resp.incomplete_details}")
        try:
            data = json.loads(resp.output_text)
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMError("LLM_BAD_OUTPUT", f"Output không phải JSON: {e}") from e
        usage = resp.usage
        return LLMResult(
            data=data,
            model=resp.model or model,
            tokens_in=getattr(usage, "input_tokens", 0) or 0,
            tokens_out=getattr(usage, "output_tokens", 0) or 0,
            latency_ms=latency,
            attempts=[model],
        )

    def complete_json(self, system: str, user: str, schema: dict[str, Any], schema_name: str) -> LLMResult:
        o = self._openai
        transient = (o.APIConnectionError, o.APITimeoutError, o.InternalServerError, o.RateLimitError)
        try:
            return self._call(self.model, system, user, schema, schema_name)
        except transient as e:
            if not self.fallback:
                raise LLMError("LLM_UNAVAILABLE", f"Lỗi gọi model: {type(e).__name__}") from e
            try:
                res = self._call(self.fallback, system, user, schema, schema_name)
                res.attempts = [self.model, self.fallback]
                return res
            except transient as e2:
                raise LLMError("LLM_UNAVAILABLE", f"Lỗi gọi model dự phòng: {type(e2).__name__}") from e2
        except o.APIStatusError as e:  # 4xx: key sai, model không tồn tại, schema không hợp lệ…
            raise LLMError("LLM_UNAVAILABLE", f"API trả lỗi {e.status_code}") from e


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    s = settings
    if s.llm_provider != "openai":
        return UnavailableClient(f"LLM_PROVIDER '{s.llm_provider}' chưa được hỗ trợ.")
    if not s.llm_api_key or not s.llm_model:
        return UnavailableClient("Chưa cấu hình LLM_API_KEY/LLM_MODEL.")
    return OpenAIClient(s.llm_api_key, s.llm_model, s.llm_model_fallback)
