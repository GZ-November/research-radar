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
    settings = Settings(_env_file=None, llm_max_tokens=4_096)
    budget = prompt_char_budget(settings)
    assert budget == int(4_096 * 3.5) - 6_000

    text = "y" * (budget + 5_000)
    truncated = truncate_for_prompt(text, purpose="test")
    assert len(truncated) <= budget
