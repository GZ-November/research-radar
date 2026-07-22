"""Shared prompt-size guards for long manuscript and paper text."""

from radar.config import Settings, get_settings


# Rough English/academic text estimate; slightly conservative so mixed
# CJK/LaTeX content still fits the model context window.
CHARS_PER_TOKEN = 3.5
# Reserve for instructions, the JSON wrapper around the text, and the
# model's own output budget.
PROMPT_OVERHEAD_CHARS = 6_000
OMISSION_MARKER_TEMPLATE = "\n[... omitted {omitted} chars ...]\n"


def prompt_char_budget(settings: Settings | None = None) -> int:
    """Return the character budget for one large text block inside a prompt."""

    settings = settings or get_settings()
    budget = int(settings.llm_max_tokens * CHARS_PER_TOKEN) - PROMPT_OVERHEAD_CHARS
    return max(budget, 1_000)


def truncate_for_prompt(
    text: str, max_chars: int | None = None, *, purpose: str = ""
) -> str:
    """Keep the head and tail of ``text`` within ``max_chars``.

    Conclusions and discussion sections usually sit at the end of a paper,
    so the middle is omitted first and the omission is marked explicitly.
    ``purpose`` only labels log-free call sites; it never changes the output.
    """

    if max_chars is None:
        max_chars = prompt_char_budget()
    if len(text) <= max_chars:
        return text
    marker = OMISSION_MARKER_TEMPLATE.format(omitted=0)
    keep = max(max_chars - len(marker) - 6, 0)
    head_chars = keep // 2
    tail_chars = keep - head_chars
    omitted = len(text) - head_chars - tail_chars
    marker = OMISSION_MARKER_TEMPLATE.format(omitted=omitted)
    return f"{text[:head_chars]}{marker}{text[len(text) - tail_chars:]}"
