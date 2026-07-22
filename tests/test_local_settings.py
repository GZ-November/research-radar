"""Local settings persistence: UI-written env file layering and masking."""

from radar.config import Settings, get_settings, mask_secret, save_local_settings


def test_save_writes_and_preserves_unrelated_lines(tmp_path):
    target = tmp_path / "settings.local.env"
    target.write_text("# 注释\nLLM_MODEL=old-model\nCROSSREF_MAILTO=a@b.c\n")
    save_local_settings(
        {"LLM_MODEL": "new-model", "LLM_API_KEY": "sk-secret1234"}, path=target
    )
    content = target.read_text(encoding="utf-8")
    assert "# 注释" in content
    assert "CROSSREF_MAILTO=a@b.c" in content
    assert "LLM_MODEL=new-model" in content
    assert "old-model" not in content
    assert "LLM_API_KEY=sk-secret1234" in content


def test_local_file_overrides_project_env(tmp_path):
    base = tmp_path / ".env"
    local = tmp_path / "settings.local.env"
    base.write_text("LLM_MODEL=base-model\nLLM_BASE_URL=https://api.base.example\n")
    save_local_settings({"LLM_MODEL": "local-model"}, path=local)
    settings = Settings(_env_file=(str(base), str(local)))
    assert settings.llm_model == "local-model"
    # Keys absent from the local file still come from the project .env.
    assert settings.llm_base_url == "https://api.base.example"


def test_empty_value_clears_key(tmp_path):
    target = tmp_path / "settings.local.env"
    save_local_settings({"LOCAL_LLM_MODEL": "qwen3:4b"}, path=target)
    save_local_settings({"LOCAL_LLM_MODEL": ""}, path=target)
    settings = Settings(_env_file=str(target))
    assert not settings.local_llm_model


def test_save_never_touches_project_env(tmp_path):
    base = tmp_path / ".env"
    base.write_text("LLM_MODEL=base-model\n")
    before = base.read_text(encoding="utf-8")
    save_local_settings(
        {"LLM_MODEL": "local-model"}, path=tmp_path / "settings.local.env"
    )
    assert base.read_text(encoding="utf-8") == before


def test_save_clears_cached_settings(tmp_path):
    get_settings.cache_clear()
    cached = get_settings()
    save_local_settings({"LLM_MODEL": "whatever"}, path=tmp_path / "settings.local.env")
    try:
        assert get_settings() is not cached
    finally:
        get_settings.cache_clear()


def test_value_with_special_chars_is_quoted(tmp_path):
    target = tmp_path / "settings.local.env"
    save_local_settings({"LLM_PROVIDER": "my provider #1"}, path=target)
    settings = Settings(_env_file=str(target))
    assert settings.llm_provider == "my provider #1"


def test_mask_secret():
    assert mask_secret(None) == ""
    assert mask_secret("") == ""
    assert mask_secret("sk-abcdef123456") == "sk-••••3456"
    assert mask_secret("abcdef123456") == "••••3456"
    assert mask_secret("abc") == "••••"
    assert "abcdef" not in mask_secret("sk-abcdef123456")
