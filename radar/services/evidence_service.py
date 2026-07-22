"""Evidence extraction and exact-span verification helpers."""

import re

from radar.schemas import EvidenceSpan


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]*", re.IGNORECASE)
# Some source APIs collapse whitespace between abstract sentences ("...model.Existing").
# Split both conventional and collapsed boundaries while preserving exact quotes.
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s*(?=[A-Z0-9])")
RESULT_CUES = re.compile(
    r"\b(result|results|find|finds|found|show|shows|demonstrate|demonstrates|"
    r"outperform|outperforms|lower|higher|improve|improves|reduce|reduces|"
    r"robust|robustness|fragile|sensitive|score|scores)\b",
    re.IGNORECASE,
)
STOPWORDS = {
    "about", "after", "again", "against", "also", "among", "and", "are",
    "been", "being", "between", "compared", "consistently", "does", "each",
    "for", "from", "have", "into", "more", "most", "not", "our", "over",
    "paper", "reported", "research", "some", "still", "study", "than", "that",
    "the", "their", "these", "this", "under", "using", "were", "which", "with",
}


def _normalized_text_with_offsets(text: str) -> tuple[str, list[int]]:
    """Normalize PDF line wrapping while retaining exact source offsets."""
    normalized: list[str] = []
    offsets: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x00":
            index += 1
            continue
        if char == "-" and index + 1 < len(text) and text[index + 1] in "\r\n":
            next_index = index + 1
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1
            if (
                index > 0
                and text[index - 1].isalpha()
                and next_index < len(text)
                and text[next_index].isalpha()
            ):
                index = next_index
                continue
        if char.isspace():
            if normalized and normalized[-1] != " ":
                normalized.append(" ")
                offsets.append(index)
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            continue
        normalized.append(char.lower())
        offsets.append(index)
        index += 1
    return "".join(normalized).strip(), offsets


def resolve_exact_quote(quote: str, content: str) -> tuple[str, int, int] | None:
    """Return one exact source span; reject missing or ambiguous normalized matches."""
    exact_offset = content.find(quote)
    if exact_offset >= 0:
        if content.find(quote, exact_offset + 1) >= 0:
            return None
        return quote, exact_offset, exact_offset + len(quote)
    normalized_content, offsets = _normalized_text_with_offsets(content)
    normalized_quote, _ = _normalized_text_with_offsets(quote)
    if not normalized_quote or not offsets:
        return None
    match = normalized_content.find(normalized_quote)
    if match < 0 or normalized_content.find(normalized_quote, match + 1) >= 0:
        return None
    start = offsets[match]
    end = offsets[match + len(normalized_quote) - 1] + 1
    return content[start:end], start, end


def _canonical_token(token: str) -> str:
    """Collapse a few common English inflections without changing source text."""

    value = token.lower().strip("-")
    if len(value) > 6 and value.endswith("ness"):
        value = value[:-4]
    elif len(value) > 5 and value.endswith("ies"):
        value = value[:-3] + "y"
    elif len(value) > 5 and value.endswith("ing"):
        value = value[:-3]
    elif len(value) > 4 and value.endswith("ed"):
        value = value[:-2]
    elif len(value) > 4 and value.endswith("s"):
        value = value[:-1]
    return value


def _keywords(values: list[str]) -> set[str]:
    return {
        normalized
        for value in values
        for raw in TOKEN_RE.findall(value)
        if len(raw) > 2 and raw.lower() not in STOPWORDS
        if len(normalized := _canonical_token(raw)) > 2
    }


class EvidenceService:
    @staticmethod
    def verify_exact(span: EvidenceSpan | dict, content: str) -> bool:
        evidence = span if isinstance(span, EvidenceSpan) else EvidenceSpan.model_validate(span)
        return evidence.quote in content

    @staticmethod
    def resolve_exact(
        span: EvidenceSpan | dict, content: str
    ) -> EvidenceSpan | None:
        evidence = (
            span if isinstance(span, EvidenceSpan) else EvidenceSpan.model_validate(span)
        )
        resolved = resolve_exact_quote(evidence.quote, content)
        if resolved is None:
            return None
        quote, start, end = resolved
        return evidence.model_copy(
            update={"quote": quote, "locator": f"offset:{start}-{end}"}
        )

    @staticmethod
    def extract_relevant_evidence(query_terms: list[str], content: str, source_snapshot_id: str) -> EvidenceSpan | None:
        query_keywords = _keywords(query_terms)
        if not query_keywords:
            return None

        units: list[tuple[str, str]] = []
        sentence_number = 0
        for paragraph_number, raw_paragraph in enumerate(content.split("\n"), start=1):
            paragraph = raw_paragraph.strip()
            if not paragraph:
                continue
            sentences = [part.strip() for part in SENTENCE_BREAK.split(paragraph) if part.strip()]
            if len(sentences) == 1:
                units.append((f"paragraph:{paragraph_number}", paragraph))
                continue
            for sentence in sentences:
                sentence_number += 1
                units.append((f"sentence:{sentence_number}", sentence))

        ranked: list[tuple[float, int, str, str]] = []
        for locator, quote in units:
            evidence_keywords = _keywords([quote])
            overlap = len(query_keywords & evidence_keywords)
            if overlap == 0:
                continue
            empirical_bonus = 1.0 if RESULT_CUES.search(quote) else 0.0
            numeric_bonus = 0.5 if re.search(r"\d", quote) else 0.0
            score = overlap * 3.0 + empirical_bonus + numeric_bonus
            ranked.append((score, -len(quote), locator, quote))

        if not ranked:
            return None
        _, _, locator, quote = max(ranked)
        return EvidenceSpan(
            quote=quote,
            locator=locator,
            source_snapshot_id=source_snapshot_id,
        )
