"""OpenAI-compatible structured JSON adapter with explicit errors."""

import json
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from radar.config import Settings, get_settings


ResponseT = TypeVar("ResponseT", bound=BaseModel)


class ProviderLLMClient:
    transient_statuses = {429, 500, 502, 503, 504}

    def __init__(
        self,
        settings: Settings | None = None,
        timeout_seconds: float | None = None,
    ):
        self.settings = settings or get_settings()
        self.timeout_seconds = timeout_seconds or self.settings.llm_timeout_seconds
        self.last_receipt: dict = {}

    def generate_structured(
        self, *, stage: str, prompt: str, response_model: type[ResponseT]
    ) -> ResponseT:
        if not all([self.settings.llm_api_key, self.settings.llm_model, self.settings.llm_base_url]):
            raise RuntimeError("llm_not_configured")
        payload = self.build_payload(stage=stage, prompt=prompt, response_model=response_model)
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            started = time.perf_counter()
            try:
                response = httpx.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                self.last_receipt = {
                    "raw_response": content,
                    "usage": {
                        **usage,
                        # OpenAI-compatible usage, falling back to Ollama-style
                        # eval counters when the endpoint reports those instead.
                        "prompt_tokens": int(
                            usage.get(
                                "prompt_tokens", body.get("prompt_eval_count", 0)
                            )
                            or 0
                        ),
                        "completion_tokens": int(
                            usage.get("completion_tokens", body.get("eval_count", 0))
                            or 0
                        ),
                    },
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "attempts": attempt + 1,
                }
                return response_model.model_validate(json.loads(content))
            except httpx.HTTPStatusError as exc:
                last_error = exc
                # 4xx other than 429 is a request/schema problem: retrying
                # the same prompt cannot fix it.
                retryable = exc.response.status_code in self.transient_statuses
            except httpx.HTTPError as exc:
                # Timeouts and transport-level network failures are transient.
                last_error = exc
                retryable = True
            except (ValidationError, KeyError, TypeError, ValueError) as exc:
                # The response does not match the schema; fail fast instead
                # of burning retries on an unfixable prompt/schema mismatch.
                last_error = exc
                retryable = False
            if not retryable or attempt >= self.settings.llm_max_retries:
                break
            time.sleep(self.settings.llm_retry_backoff_seconds * (2**attempt))
        raise RuntimeError(f"llm_provider_failed:{stage}: {last_error}") from last_error

    def build_payload(
        self, *, stage: str, prompt: str, response_model: type[ResponseT]
    ) -> dict:
        """Build a provider-specific Chat Completions request without sending it."""

        schema = response_model.model_json_schema()
        provider = (self.settings.llm_provider or "").strip().lower()
        if provider.startswith("deepseek"):
            properties = ", ".join(schema.get("properties", {}).keys())
            system_prompt = (
                "Return exactly one valid JSON object and no Markdown. "
                "The JSON object must validate against the supplied JSON Schema. "
                f"Required top-level JSON keys: {properties}.\n"
                f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"
            )
            return {
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                # DeepSeek JSON Output supports json_object rather than
                # OpenAI's json_schema response format.
                "response_format": {"type": "json_object"},
                "thinking": {"type": self.settings.llm_thinking},
                "reasoning_effort": self.settings.llm_reasoning_effort,
                "max_tokens": self.settings.llm_max_tokens,
                "stream": False,
            }

        payload = {
            "model": self.settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": stage,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
        }
        return payload
