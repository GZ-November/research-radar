"""Claim candidate extraction and human gate G0."""

import difflib
import hashlib
import re
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from radar.config import Settings, estimate_llm_cost_usd, get_settings
from radar.db import SessionLocal, session_scope
from radar.llm.base import LLMClient
from radar.llm.factory import build_analysis_llm
from radar.llm.text_utils import truncate_for_prompt
from radar.models import AuditEvent, Claim, ClaimRevision, ManuscriptVersion, ModelRun
from radar.schemas import ClaimCandidateBatch, ClaimCandidateOutput, EmpiricalClaimContract
from radar.services.evidence_service import (
    _normalized_text_with_offsets,
    resolve_exact_quote,
)
from radar.services.trust_service import TrustService


PROMPT_PATH = (
    Path(__file__).parents[1] / "llm" / "prompts" / "claim_candidate_extraction.txt"
)
DEFAULT_FALSIFIABLE_CONDITION = (
    "A matched evaluation does not reproduce the reported result."
)
DEFAULT_CARRY_SIMILARITY = 0.85

SENTENCE_SPAN = re.compile(
    r"(?:^|(?<=[.!?])\s+)(.{45,900}?[.!?])"
    r"(?=\s+(?:[A-Z]|\d+(?:\.\d+)*\s+[A-Z]|[•])|\s*$)",
    re.DOTALL,
)
OUTCOME_CUES = re.compile(
    r"\b(improv\w*|outperform\w*|surpass\w*|reduc\w*|lower\w*|higher|superior|"
    r"maintain\w*|reach\w*|achiev\w*|decreas\w*|increas\w*|"
    r"fragile|sensitive\s+to|regression|underperform\w*)\b",
    re.IGNORECASE,
)
EVIDENCE_FRAMES = re.compile(
    r"\b(results?|findings?|experiments?|evaluation|analysis)\b.{0,160}"
    r"\b(show\w*|reveal\w*|indicate\w*|demonstrate\w*|find\w*|achieve\w*)\b",
    re.IGNORECASE | re.DOTALL,
)
EMPIRICAL_TERMS = re.compile(
    r"\b(score|accuracy|exact[ -]match|f1|precision|recall|latency|throughput|rate|"
    r"robustness|queries|questions|documents|benchmark|dataset|domain|model)\b",
    re.IGNORECASE,
)
DATASET_CLAIM = re.compile(
    r"\b(?:construct|create|compris\w*|span\w*)\b.{0,180}\b\d[\d,]*\b.{0,120}"
    r"\b(?:questions|queries|documents|examples|instances|domains)\b",
    re.IGNORECASE | re.DOTALL,
)
LOW_QUALITY = re.compile(
    r"(^|\s)(?:Table|Figure)\s+\d|\bRelated Work\b|\bet al\.\b|"
    r"importance of (?:evaluating|improving)|^\s*\[\d+\]|^Appendix\b|"
    r"^It includes\b|\[\d+\].{0,100}\b(?:analy[sz]ed|found|reported)\b|"
    r"\bwe define\b|\bpipeline\b.{0,100}\bensures\b|"
    r"\b(?:E-Agent|Model|Assistant)\s+Response:\s|\bUser:\s|\bQuestion:\s",
    re.IGNORECASE,
)


def default_llm_client(settings: Settings) -> LLMClient | None:
    """Pick the configured analysis model via the shared factory.

    Returns None when no LLM is configured so callers can fall back to the
    deterministic heuristic without attempting a network call.
    """

    return build_analysis_llm(settings)


def _readable_statement(quote: str) -> str:
    """Normalize layout artifacts for display while preserving the exact quote separately."""
    statement = re.sub(r"(?<=[a-z])-\s*\n\s*(?=[a-z])", "", quote)
    statement = re.sub(r"\n\d+\.\s*$", "", statement)
    statement = re.sub(r"\s+", " ", statement).strip()
    return re.sub(r"-\s+(?=[A-Z])", "-", statement)


def _candidate_score(quote: str) -> int:
    if "\x00" in quote or len(quote) > 900:
        return -100
    scoring_text = _readable_statement(quote)
    score = 0
    outcome = OUTCOME_CUES.search(scoring_text)
    if outcome:
        score += 3
        if re.search(r"\b(RAG systems?|models?|scores?|queries|performance)\b", scoring_text, re.I):
            score += 1
    if EVIDENCE_FRAMES.search(scoring_text):
        score += 3
    if DATASET_CLAIM.search(scoring_text):
        score += 4
    if EMPIRICAL_TERMS.search(scoring_text):
        score += 1
    if re.search(r"\d", scoring_text):
        score += 1
    if LOW_QUALITY.search(scoring_text):
        score -= 5
    if re.search(r"\b(?:should|must)\b", scoring_text, re.IGNORECASE):
        score -= 3
    if re.match(r"^(?:This|It|They|Surprisingly,?\s+it)\b", scoring_text, re.IGNORECASE):
        score -= 2
    return score


def _rank_candidate_spans(content: str, limit: int = 20) -> list[tuple[int, int, str, int]]:
    """Find cross-line empirical sentences and rank them without changing source spans."""
    ranked: list[tuple[int, int, str, int]] = []
    references = re.search(r"\nReferences\s*\n\s*\[\d+\]", content, re.IGNORECASE)
    searchable_content = content[: references.start()] if references else content
    for match in SENTENCE_SPAN.finditer(searchable_content):
        quote = match.group(1).strip()
        score = _candidate_score(quote)
        if score < 5:
            continue
        start = content.find(quote, match.start(1), match.end(1) + 1)
        if start < 0:
            continue
        ranked.append((start, start + len(quote), quote, score))
    ranked.sort(key=lambda item: (-item[3], item[0]))
    selected = ranked[:limit]
    selected.sort(key=lambda item: item[0])
    return selected


def _overlaps(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < taken_end and end > taken_start for taken_start, taken_end in ranges)


SEGMENT_END = re.compile(r"[.!?]+\s+")


def _locate_carried_quote(
    quote: str, content: str, threshold: float
) -> tuple[int, int, float] | None:
    """Locate a previous claim quote exactly, else by normalized fuzzy match.

    Returns ``(start, end, similarity)`` on the original content, or None when
    the best fuzzy segment scores below ``threshold``. The fuzzy path compares
    whitespace/hyphenation-normalized text so reworded sentences still carry,
    while the returned span always comes from the original content and is
    therefore exact-span verifiable downstream.
    """

    index = content.find(quote)
    if index >= 0:
        return index, index + len(quote), 1.0
    normalized_content, offsets = _normalized_text_with_offsets(content)
    normalized_quote, _ = _normalized_text_with_offsets(quote)
    if not normalized_quote or not offsets:
        return None
    # Compare against one-to-three consecutive sentence-like segments so a
    # reworded (possibly longer or shorter) claim still lines up, while a
    # sliding fixed-size window cannot.
    bounds: list[tuple[int, int]] = []
    position = 0
    for match in SEGMENT_END.finditer(normalized_content):
        bounds.append((position, match.end()))
        position = match.end()
    bounds.append((position, len(normalized_content)))
    best: tuple[float, int, int] | None = None
    for first in range(len(bounds)):
        for span in (1, 2, 3):
            if first + span > len(bounds):
                break
            start = bounds[first][0]
            end = bounds[first + span - 1][1]
            window = normalized_content[start:end]
            matcher = difflib.SequenceMatcher(None, normalized_quote, window)
            if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                continue
            # Trim leading/trailing non-matching characters so the carried
            # span covers exactly the reworded claim, not segment padding.
            blocks = [block for block in matcher.get_matching_blocks() if block.size]
            if not blocks:
                continue
            trimmed_start = start + blocks[0].b
            trimmed_end = start + blocks[-1].b + blocks[-1].size
            ratio = difflib.SequenceMatcher(
                None, normalized_quote, normalized_content[trimmed_start:trimmed_end]
            ).ratio()
            if ratio >= threshold and (best is None or ratio > best[0]):
                best = (ratio, trimmed_start, trimmed_end)
    if best is None:
        return None
    ratio, start, end = best
    return offsets[start], offsets[end - 1] + 1, ratio


class ClaimService:
    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        llm_client: LLMClient | None = None,
        settings: Settings | None = None,
        carry_similarity_threshold: float = DEFAULT_CARRY_SIMILARITY,
    ):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.llm_client = llm_client
        self.carry_similarity_threshold = carry_similarity_threshold
        self.trust = TrustService()

    def _resolve_llm_client(self) -> LLMClient | None:
        if self.llm_client is not None:
            return self.llm_client
        return default_llm_client(self.settings)

    def extract_candidates(self, manuscript_version_id: str) -> list[ClaimRevision]:
        with session_scope(self.session_factory) as session:
            manuscript = session.get(ManuscriptVersion, manuscript_version_id)
            if manuscript is None:
                raise LookupError(f"manuscript not found: {manuscript_version_id}")
            existing = list(
                session.scalars(
                    select(ClaimRevision).where(
                        ClaimRevision.manuscript_version_id == manuscript_version_id
                    )
                )
            )
            if existing:
                return existing

            next_number = self._next_stable_key_number(session, manuscript.case_id)
            client, batch, prompt, llm_error, latency_ms = self._try_llm_extraction(manuscript)
            if batch is not None:
                candidates, dropped_anchors = self._persist_llm_candidates(
                    session, manuscript, batch.candidates,
                    excluded_ranges=[], next_number=next_number,
                )
                self._record_extraction_run(
                    session, manuscript, client=client, prompt=prompt, batch=batch,
                    candidates=candidates, dropped_anchors=dropped_anchors,
                    latency_ms=latency_ms,
                )
            else:
                candidates = self._persist_heuristic_candidates(
                    session, manuscript, excluded_ranges=[], next_number=next_number,
                )
                self._record_extraction_fallback_run(
                    session, manuscript, candidates=candidates, llm_error=llm_error,
                )

            session.add(
                AuditEvent(
                    id=str(uuid4()), case_id=manuscript.case_id,
                    event_type="claim_candidates_extracted", object_type="ManuscriptVersion",
                    object_id=manuscript.id, payload_json={"count": len(candidates)},
                    actor_type="system", actor_id="claim_service",
                )
            )
            session.flush()
            for candidate in candidates:
                session.expunge(candidate)
            return candidates

    def _try_llm_extraction(
        self, manuscript: ManuscriptVersion
    ) -> tuple[LLMClient | None, ClaimCandidateBatch | None, str, str | None, int]:
        """Attempt one structured extraction call; never raise into the caller.

        Returns ``(client, batch, prompt, error, latency_ms)``; ``batch`` is
        None when no LLM is configured or the call failed, in which case
        ``error`` describes why the deterministic fallback was used.
        """

        client = self._resolve_llm_client()
        if client is None:
            return None, None, "", "llm_not_configured", 0
        instructions = PROMPT_PATH.read_text(encoding="utf-8").strip()
        prompt = (
            f"{instructions}\n\nMANUSCRIPT TEXT:\n"
            f"{truncate_for_prompt(manuscript.content_text, purpose='claim candidate extraction')}"
        )
        started = time.perf_counter()
        try:
            batch = client.generate_structured(
                stage="claim_extraction",
                prompt=prompt,
                response_model=ClaimCandidateBatch,
            )
        except Exception as exc:
            return client, None, prompt, str(exc), int((time.perf_counter() - started) * 1000)
        return client, batch, prompt, None, int((time.perf_counter() - started) * 1000)

    def _persist_llm_candidates(
        self,
        session: Session,
        manuscript: ManuscriptVersion,
        items: list[ClaimCandidateOutput],
        *,
        excluded_ranges: list[tuple[int, int]],
        next_number: int,
    ) -> tuple[list[ClaimRevision], list[str]]:
        """Persist LLM candidates whose source_quote resolves to an exact span.

        Candidates whose anchor cannot be located verbatim (same standard as
        EvidenceService.resolve_exact) are dropped and reported, never stored.
        """

        candidates: list[ClaimRevision] = []
        dropped: list[str] = []
        taken_ranges = list(excluded_ranges)
        for item in items:
            resolved = resolve_exact_quote(item.source_quote, manuscript.content_text)
            if resolved is None:
                dropped.append(item.statement[:120])
                continue
            quote, start, end = resolved
            if _overlaps(taken_ranges, start, end):
                continue
            claim = Claim(
                id=str(uuid4()),
                case_id=manuscript.case_id,
                stable_key=f"C{next_number}",
                lifecycle_state="active",
            )
            next_number += 1
            revision = ClaimRevision(
                id=str(uuid4()),
                claim_id=claim.id,
                manuscript_version_id=manuscript.id,
                revision_no=1,
                statement=item.statement.strip() or _readable_statement(quote),
                claim_type=item.claim_type,
                centrality=item.centrality_suggestion,
                contract_json=item.contract.model_dump(),
                falsifiable_condition=(
                    item.falsifiable_condition.strip() or DEFAULT_FALSIFIABLE_CONDITION
                ),
                source_quote=quote,
                source_locator=f"offset:{start}-{end}",
                review_state="candidate",
            )
            session.add(claim)
            session.flush()
            session.add(revision)
            session.flush()
            taken_ranges.append((start, end))
            candidates.append(revision)
        return candidates, dropped

    def _persist_heuristic_candidates(
        self,
        session: Session,
        manuscript: ManuscriptVersion,
        *,
        excluded_ranges: list[tuple[int, int]],
        next_number: int,
    ) -> list[ClaimRevision]:
        """Regex/cue-based extraction kept as the deterministic fallback path."""

        candidates: list[ClaimRevision] = []
        for start, end, quote, score in _rank_candidate_spans(manuscript.content_text):
            if _overlaps(excluded_ranges, start, end):
                continue
            if self.trust.verify_claim_quote(quote, manuscript.content_text).state == "blocked":
                continue
            claim = Claim(
                id=str(uuid4()),
                case_id=manuscript.case_id,
                stable_key=f"C{next_number}",
                lifecycle_state="active",
            )
            next_number += 1
            revision = ClaimRevision(
                id=str(uuid4()),
                claim_id=claim.id,
                manuscript_version_id=manuscript.id,
                revision_no=1,
                statement=_readable_statement(quote),
                claim_type="empirical_result",
                centrality="core" if score >= 7 else "major",
                contract_json=EmpiricalClaimContract().model_dump(),
                falsifiable_condition=DEFAULT_FALSIFIABLE_CONDITION,
                source_quote=quote,
                source_locator=f"offset:{start}-{end}",
                review_state="candidate",
            )
            session.add(claim)
            session.flush()
            session.add(revision)
            candidates.append(revision)
        return candidates

    def _record_extraction_run(
        self,
        session: Session,
        manuscript: ManuscriptVersion,
        *,
        client: LLMClient,
        prompt: str,
        batch: ClaimCandidateBatch,
        candidates: list[ClaimRevision],
        dropped_anchors: list[str],
        latency_ms: int,
    ) -> None:
        receipt = getattr(client, "last_receipt", {}) or {}
        usage = receipt.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        model_name = (
            getattr(client, "model_name", None) or self.settings.llm_model or "unknown"
        )
        session.add(
            ModelRun(
                id=str(uuid4()),
                stage="claim_extraction",
                case_id=manuscript.case_id,
                provider=(
                    getattr(client, "provider_name", None)
                    or self.settings.llm_provider
                    or client.__class__.__name__
                ),
                model=model_name,
                prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
                schema_version="ClaimCandidateBatch.v1",
                input_refs_json=[manuscript.id],
                raw_response=receipt.get("raw_response") or batch.model_dump_json(),
                parsed_output_json=batch.model_dump(),
                validation_json={
                    "pydantic": True,
                    "path": "llm",
                    "anchors_resolved": len(candidates),
                    "anchors_dropped": dropped_anchors,
                },
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimate_llm_cost_usd(
                    model_name, input_tokens, output_tokens
                ),
                latency_ms=int(receipt.get("latency_ms", latency_ms)),
            )
        )

    def _record_extraction_fallback_run(
        self,
        session: Session,
        manuscript: ManuscriptVersion,
        *,
        candidates: list[ClaimRevision],
        llm_error: str | None,
    ) -> None:
        session.add(
            ModelRun(
                id=str(uuid4()),
                stage="claim_extraction",
                case_id=manuscript.case_id,
                provider="deterministic_fallback",
                model="empirical-cue-v1",
                prompt_hash=hashlib.sha256(manuscript.content_text.encode()).hexdigest(),
                schema_version="ClaimCandidateOutput.v1",
                input_refs_json=[manuscript.id],
                raw_response="",
                parsed_output_json={"candidate_ids": [item.id for item in candidates]},
                validation_json={"all_quotes_exact": True, "path": "heuristic", "llm_error": llm_error},
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                latency_ms=0,
            )
        )

    @staticmethod
    def _next_stable_key_number(session: Session, case_id: str) -> int:
        all_stable_keys = list(
            session.scalars(select(Claim.stable_key).where(Claim.case_id == case_id))
        )
        existing_numbers = [
            int(match.group(1))
            for stable_key in all_stable_keys
            if (match := re.fullmatch(r"C(\d+)", stable_key))
        ]
        return max(existing_numbers, default=0) + 1

    def sync_manuscript_version(self, manuscript_version_id: str) -> dict:
        """Carry exact Claims forward and extract candidates from a new manuscript version.

        Carry-over first tries the exact quote, then a normalized fuzzy match
        (``carry_similarity_threshold``). Previous claims that can no longer be
        located are returned explicitly in ``lost_claims`` instead of being
        silently counted, so the UI can surface them.
        """

        with session_scope(self.session_factory) as session:
            manuscript = session.get(ManuscriptVersion, manuscript_version_id)
            if manuscript is None:
                raise LookupError(f"manuscript not found: {manuscript_version_id}")
            existing_for_version = list(
                session.scalars(
                    select(ClaimRevision).where(
                        ClaimRevision.manuscript_version_id == manuscript_version_id
                    )
                )
            )
            if existing_for_version:
                return {
                    "carried_claims": sum(
                        item.supersedes_id is not None for item in existing_for_version
                    ),
                    "new_candidates": sum(
                        item.supersedes_id is None for item in existing_for_version
                    ),
                    "previous_claims_not_found": 0,
                    "lost_claims": [],
                }

            rows = list(
                session.execute(
                    select(Claim, ClaimRevision)
                    .join(ClaimRevision, ClaimRevision.claim_id == Claim.id)
                    .where(
                        Claim.case_id == manuscript.case_id,
                        ClaimRevision.manuscript_version_id != manuscript.id,
                        ClaimRevision.review_state.in_(["candidate", "confirmed"]),
                    )
                    .order_by(ClaimRevision.revision_no.desc(), ClaimRevision.created_at.desc())
                )
            )
            latest_by_claim: dict[str, tuple[Claim, ClaimRevision]] = {}
            for claim, revision in rows:
                latest_by_claim.setdefault(claim.id, (claim, revision))

            next_number = self._next_stable_key_number(session, manuscript.case_id)
            carried_ranges: list[tuple[int, int]] = []
            carried = 0
            fuzzy_carried = 0
            lost_claims: list[dict[str, str]] = []
            for claim, previous in latest_by_claim.values():
                located = _locate_carried_quote(
                    previous.source_quote,
                    manuscript.content_text,
                    self.carry_similarity_threshold,
                )
                if located is None:
                    lost_claims.append(
                        {
                            "claim_id": claim.id,
                            "stable_key": claim.stable_key,
                            "statement": previous.statement,
                        }
                    )
                    continue
                start, end, similarity = located
                carried_quote = manuscript.content_text[start:end]
                previous_state = previous.review_state
                previous.review_state = "superseded"
                revision = ClaimRevision(
                    id=str(uuid4()),
                    claim_id=claim.id,
                    manuscript_version_id=manuscript.id,
                    revision_no=previous.revision_no + 1,
                    statement=previous.statement,
                    claim_type=previous.claim_type,
                    centrality=previous.centrality,
                    contract_json=previous.contract_json,
                    falsifiable_condition=previous.falsifiable_condition,
                    source_quote=carried_quote,
                    source_locator=f"offset:{start}-{end}",
                    review_state=previous_state,
                    supersedes_id=previous.id,
                )
                session.add(revision)
                carried_ranges.append((start, end))
                carried += 1
                if similarity < 1.0:
                    fuzzy_carried += 1

            client, batch, prompt, llm_error, latency_ms = self._try_llm_extraction(manuscript)
            dropped_anchors: list[str] = []
            if batch is not None:
                candidates, dropped_anchors = self._persist_llm_candidates(
                    session, manuscript, batch.candidates,
                    excluded_ranges=carried_ranges, next_number=next_number,
                )
            else:
                candidates = self._persist_heuristic_candidates(
                    session, manuscript,
                    excluded_ranges=carried_ranges, next_number=next_number,
                )

            session.add(
                ModelRun(
                    id=str(uuid4()),
                    stage="claim_version_sync",
                    case_id=manuscript.case_id,
                    provider=(
                        (
                            getattr(client, "provider_name", None)
                            or self.settings.llm_provider
                            or client.__class__.__name__
                        )
                        if batch is not None
                        else "deterministic_fallback"
                    ),
                    model=(
                        (
                            getattr(client, "model_name", None)
                            or self.settings.llm_model
                            or "unknown"
                        )
                        if batch is not None
                        else "fuzzy-carry-and-empirical-cue-v2"
                    ),
                    prompt_hash=hashlib.sha256(
                        (prompt or manuscript.content_text).encode()
                    ).hexdigest(),
                    schema_version="ClaimVersionSync.v1",
                    input_refs_json=[manuscript.id],
                    raw_response="",
                    parsed_output_json={
                        "carried_claims": carried,
                        "fuzzy_carried_claims": fuzzy_carried,
                        "new_candidate_ids": [item.id for item in candidates],
                        "previous_claims_not_found": len(lost_claims),
                        "lost_claims": lost_claims,
                    },
                    validation_json={
                        "all_quotes_exact": True,
                        "carry_similarity_threshold": self.carry_similarity_threshold,
                        "candidate_extraction": "llm" if batch is not None else "heuristic",
                        "anchors_dropped": dropped_anchors,
                        "llm_error": llm_error,
                    },
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost=0.0,
                    latency_ms=0,
                )
            )
            session.add(
                AuditEvent(
                    id=str(uuid4()),
                    case_id=manuscript.case_id,
                    event_type="manuscript_claims_synchronized",
                    object_type="ManuscriptVersion",
                    object_id=manuscript.id,
                    payload_json={
                        "carried_claims": carried,
                        "new_candidates": len(candidates),
                        "previous_claims_not_found": len(lost_claims),
                        "lost_stable_keys": [item["stable_key"] for item in lost_claims],
                    },
                    actor_type="system",
                    actor_id="claim_service",
                )
            )
            return {
                "carried_claims": carried,
                "new_candidates": len(candidates),
                "previous_claims_not_found": len(lost_claims),
                "lost_claims": lost_claims,
            }

    def confirm_candidate(self, revision_id: str) -> ClaimRevision:
        return self._set_state(revision_id, "confirmed")

    def reject_candidate(self, revision_id: str) -> ClaimRevision:
        return self._set_state(revision_id, "rejected")

    def _set_state(self, revision_id: str, state: str) -> ClaimRevision:
        with session_scope(self.session_factory) as session:
            revision = session.get(ClaimRevision, revision_id)
            if revision is None:
                raise LookupError(f"claim revision not found: {revision_id}")
            manuscript = session.get(ManuscriptVersion, revision.manuscript_version_id)
            if state == "confirmed" and (
                manuscript is None or revision.source_quote not in manuscript.content_text
            ):
                raise ValueError("span_failed")
            revision.review_state = state
            claim = session.get(Claim, revision.claim_id)
            session.add(
                AuditEvent(
                    id=str(uuid4()), case_id=claim.case_id if claim else "unknown",
                    event_type=f"claim_{state}", object_type="ClaimRevision",
                    object_id=revision.id, payload_json={}, actor_type="human", actor_id="local_user",
                )
            )
            session.flush()
            session.expunge(revision)
            return revision

    def edit_candidate(
        self, revision_id: str, *, statement: str, centrality: str,
        contract: dict, falsifiable_condition: str,
    ) -> ClaimRevision:
        with session_scope(self.session_factory) as session:
            current = session.get(ClaimRevision, revision_id)
            if current is None:
                raise LookupError(f"claim revision not found: {revision_id}")
            max_revision = session.scalar(
                select(func.max(ClaimRevision.revision_no)).where(ClaimRevision.claim_id == current.claim_id)
            ) or 1
            current.review_state = "superseded"
            revised = ClaimRevision(
                id=str(uuid4()), claim_id=current.claim_id,
                manuscript_version_id=current.manuscript_version_id,
                revision_no=max_revision + 1, statement=statement,
                claim_type="empirical_result", centrality=centrality,
                contract_json=EmpiricalClaimContract.model_validate(contract).model_dump(),
                falsifiable_condition=falsifiable_condition,
                source_quote=current.source_quote, source_locator=current.source_locator,
                review_state="confirmed", supersedes_id=current.id,
            )
            session.add(revised)
            session.flush()
            session.expunge(revised)
            return revised

    def split_candidate(self, revision_id: str, statements: list[str]) -> list[ClaimRevision]:
        cleaned = [statement.strip() for statement in statements if statement.strip()]
        if len(cleaned) < 2:
            raise ValueError("split requires at least two statements")
        with session_scope(self.session_factory) as session:
            original = session.get(ClaimRevision, revision_id)
            if original is None:
                raise LookupError(f"claim revision not found: {revision_id}")
            original.review_state = "superseded"
            original_claim = session.get(Claim, original.claim_id)
            created: list[ClaimRevision] = []
            for index, statement in enumerate(cleaned, start=1):
                claim = Claim(
                    id=str(uuid4()), case_id=original_claim.case_id,
                    stable_key=f"{original_claim.stable_key}.{index}", lifecycle_state="active",
                )
                revision = ClaimRevision(
                    id=str(uuid4()), claim_id=claim.id,
                    manuscript_version_id=original.manuscript_version_id, revision_no=1,
                    statement=statement, claim_type="empirical_result",
                    centrality=original.centrality, contract_json=original.contract_json,
                    falsifiable_condition=original.falsifiable_condition,
                    source_quote=original.source_quote, source_locator=original.source_locator,
                    review_state="candidate", supersedes_id=original.id,
                )
                session.add(claim)
                session.flush()
                session.add(revision)
                session.flush()
                created.append(revision)
            session.flush()
            for revision in created:
                session.expunge(revision)
            return created
