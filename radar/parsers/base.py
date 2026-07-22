"""Parser protocol and shared stable-locator helpers."""

from pathlib import Path
from typing import Protocol

from radar.schemas import ParsedDocument


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...


def slugify(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "document"

