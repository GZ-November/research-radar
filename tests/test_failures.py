import pytest
import httpx

from radar.config import Settings
from radar.llm.provider import ProviderLLMClient
from radar.schemas import EvidenceSpan


def test_unconfigured_llm_fails_explicitly():
    settings = Settings(
        _env_file=None, llm_api_key=None, llm_model=None, llm_base_url=None
    )
    with pytest.raises(RuntimeError, match="llm_not_configured"):
        ProviderLLMClient(settings).generate_structured(
            stage="failure_injection", prompt="no call", response_model=EvidenceSpan
        )


def test_deepseek_uses_json_object_and_embeds_schema():
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_base_url="https://api.deepseek.com",
    )

    payload = ProviderLLMClient(settings).build_payload(
        stage="impact_assessment",
        prompt="Evaluate only the supplied evidence.",
        response_model=EvidenceSpan,
    )

    assert payload["model"] == "deepseek-v4-pro"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert payload["max_tokens"] == 4096
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "system"
    assert "JSON Schema" in payload["messages"][0]["content"]
    assert "quote" in payload["messages"][0]["content"]
    assert payload["messages"][1]["content"] == "Evaluate only the supplied evidence."


def test_generic_provider_keeps_strict_json_schema():
    settings = Settings(
        _env_file=None,
        llm_provider="openai_compatible",
        llm_api_key="test-key",
        llm_model="test-model",
        llm_base_url="https://example.test/v1",
    )

    payload = ProviderLLMClient(settings).build_payload(
        stage="evidence", prompt="Return evidence.", response_model=EvidenceSpan
    )

    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_provider_retries_transient_503(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_base_url="https://api.deepseek.com",
        llm_max_retries=1,
        llm_retry_backoff_seconds=0,
    )
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        if len(calls) == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"quote":"exact","locator":"p:1"}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    monkeypatch.setattr("radar.llm.provider.httpx.post", fake_post)
    client = ProviderLLMClient(settings)
    result = client.generate_structured(
        stage="evidence", prompt="Return evidence.", response_model=EvidenceSpan
    )

    assert result.quote == "exact"
    assert len(calls) == 2
    assert client.last_receipt["attempts"] == 2


def _retry_test_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_base_url="https://api.deepseek.com",
        llm_max_retries=2,
        llm_retry_backoff_seconds=0,
        **overrides,
    )


def test_provider_does_not_retry_schema_validation_errors(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": '{"unexpected": true}'}}]},
        )

    monkeypatch.setattr("radar.llm.provider.httpx.post", fake_post)
    client = ProviderLLMClient(_retry_test_settings())
    with pytest.raises(RuntimeError, match="llm_provider_failed:evidence"):
        client.generate_structured(
            stage="evidence", prompt="Return evidence.", response_model=EvidenceSpan
        )
    assert len(calls) == 1


def test_provider_does_not_retry_client_errors_other_than_429(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        return httpx.Response(400, request=request)

    monkeypatch.setattr("radar.llm.provider.httpx.post", fake_post)
    client = ProviderLLMClient(_retry_test_settings())
    with pytest.raises(RuntimeError, match="llm_provider_failed:evidence"):
        client.generate_structured(
            stage="evidence", prompt="Return evidence.", response_model=EvidenceSpan
        )
    assert len(calls) == 1
