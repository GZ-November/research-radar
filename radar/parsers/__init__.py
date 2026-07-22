"""Document parsers selected by file extension."""

from pathlib import Path

from radar.parsers.base import DocumentParser
from radar.parsers.latex import LatexParser
from radar.parsers.markdown import MarkdownParser
from radar.parsers.pdf_fallback import PdfFallbackParser


def parser_for(path: Path) -> DocumentParser:
    suffix = path.suffix.lower()
    if suffix == ".tex":
        return LatexParser()
    if suffix in {".md", ".markdown"}:
        return MarkdownParser()
    if suffix == ".pdf":
        return PdfFallbackParser()
    raise ValueError(f"unsupported manuscript type: {suffix or 'unknown'}")


__all__ = ["DocumentParser", "LatexParser", "MarkdownParser", "PdfFallbackParser", "parser_for"]
