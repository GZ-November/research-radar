from radar.config import Settings
from radar.llm.text_utils import prompt_char_budget, truncate_for_prompt


def test_short_text_is_returned_unchanged():
    text = "short manuscript text"
    assert truncate_for_prompt(text, max_chars=1_000) == text


def test_long_text_keeps_head_and_tail_with_omission_marker():
    head = "INTRO " + "a" * 500
    middle = "m" * 5_000
    tail = "CONCLUSION " + "z" * 500
    text = head + middle + tail

    truncated = truncate_for_prompt(text, max_chars=2_000)

    assert len(truncated) <= 2_000
    assert truncated.startswith("INTRO ")
    assert truncated.endswith("z" * 500)
    assert "[... omitted " in truncated
    assert " chars ...]" in truncated
    assert middle not in truncated


def test_explicit_budget_overrides_settings_default():
    text = "x" * 10_000
    truncated = truncate_for_prompt(text, max_chars=500)
    assert len(truncated) <= 500


def test_default_budget_derives_from_settings_token_limit():
    # Output cap no longer drives the input budget; the context window does.
    settings = Settings(_env_file=None, llm_max_tokens=4_096, llm_context_tokens=8_000)
    budget = prompt_char_budget(settings)
    assert budget == int(8_000 * 3.5) - 6_000

    text = "y" * (budget + 5_000)
    truncated = truncate_for_prompt(text, max_chars=budget, purpose="test")
    assert len(truncated) <= budget


def test_default_budget_uses_mode_defaults():
    remote = Settings(_env_file=None)
    assert prompt_char_budget(remote) == int(60_000 * 3.5) - 6_000
    local = Settings(_env_file=None, local_llm_model="qwen3:4b")
    assert prompt_char_budget(local) == int(28_000 * 3.5) - 6_000
