"""Lớp gọi model (docs/05 mục 1): complete_json(system, user, json_schema) → dict.

Provider chọn qua env LLM_PROVIDER: "openai" (Responses API) hoặc "openrouter" (Chat Completions, endpoint tương thích
OpenAI, cùng SDK). Không tool calling, không đưa secret vào prompt.
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
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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
    base_url: str | None = None

    def __init__(self, api_key: str, model: str, fallback: str = ""):
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, base_url=self.base_url, max_retries=0, timeout=TIMEOUT_S)
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


class OpenRouterClient(OpenAIClient):
    """OpenRouter qua Chat Completions + response_format json_schema strict.

    provider.require_parameters=True: OpenRouter chỉ định tuyến tới nhà cung cấp hỗ trợ đủ tham số (structured output),
    không âm thầm bỏ schema. Model đặt theo id của OpenRouter, ví dụ "openai/gpt-6-luna".
    """

    base_url = OPENROUTER_BASE_URL

    def _call(self, model: str, system: str, user: str, schema: dict[str, Any], schema_name: str) -> LLMResult:
        started = time.perf_counter_ns()
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
            extra_body={"provider": {"require_parameters": True}},
            timeout=TIMEOUT_S,
        )
        latency = (time.perf_counter_ns() - started) // 1_000_000
        if not resp.choices:
            raise LLMError("LLM_BAD_OUTPUT", "OpenRouter không trả về lựa chọn nào.")
        choice = resp.choices[0]
        msg = choice.message
        if getattr(msg, "refusal", None):
            raise LLMError("LLM_REFUSED", msg.refusal)
        if choice.finish_reason == "content_filter":
            raise LLMError("LLM_REFUSED", "Model từ chối trả lời (bộ lọc nội dung).")
        if choice.finish_reason == "length":
            raise LLMError("LLM_BAD_OUTPUT", "Output bị cắt ngang (hết max_tokens).")
        try:
            data = json.loads(msg.content or "")
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMError("LLM_BAD_OUTPUT", f"Output không phải JSON: {e}") from e
        if not isinstance(data, dict):
            raise LLMError("LLM_BAD_OUTPUT", "Output JSON không phải object.")
        usage = resp.usage
        return LLMResult(
            data=data,
            model=resp.model or model,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency,
            attempts=[model],
        )


PROVIDERS: dict[str, type[OpenAIClient]] = {"openai": OpenAIClient, "openrouter": OpenRouterClient}


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    s = settings
    cls = PROVIDERS.get(s.llm_provider)
    if cls is None:
        return UnavailableClient(f"LLM_PROVIDER '{s.llm_provider}' chưa được hỗ trợ (openai, openrouter).")
    if not s.llm_api_key or not s.llm_model:
        return UnavailableClient("Chưa cấu hình LLM_API_KEY/LLM_MODEL.")
    return cls(s.llm_api_key, s.llm_model, s.llm_model_fallback)
