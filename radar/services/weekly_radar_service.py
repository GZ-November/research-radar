"""Bounded live Weekly Radar scan with explicit LLM and trust gates."""

import hashlib
import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import ceil, log1p
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from radar.adapters.arxiv import ArxivSearchAdapter
from radar.adapters.base import SearchAdapter
from radar.adapters.crossref import CrossrefIntegrityAdapter
from radar.adapters.openalex import OpenAlexSearchAdapter
from radar.adapters.unpaywall import UnpaywallAdapter
from radar.config import Settings, estimate_llm_cost_usd, get_settings
from radar.db import SessionLocal, session_scope
from radar.embeddings.factory import configured_embedding_client
from radar.llm.base import LLMClient
from radar.llm.factory import build_analysis_llm
from radar.llm.ollama import OllamaLLMClient
from radar.llm.provider import ProviderLLMClient
from radar.llm.text_utils import truncate_for_prompt
from radar.models import (
    AuditEvent,
    Claim,
    ClaimRevision,
    ClaimSourceLink,
    ImpactCandidate,
    ManuscriptVersion,
    ModelRun,
    ResearchCase,
    ScanRun,
    Source,
    SourceSnapshot,
)
from radar.schemas import (
    ActionAdviceOutput,
    EmpiricalClaimContract,
    ExtractedReference,
    ExtractedReferenceBatch,
    HydeAbstractOutput,
    ImpactAssessmentOutput,
    IncomingResult,
    RerankBatchOutput,
    SearchQueryBatch,
    SourceRecord,
    WatchQuery,
)
from radar.services.condition_service import ConditionService
from radar.services.action_service import ActionService
from radar.services.evidence_service import EvidenceService
from radar.services.impact_service import ImpactService
from radar.services.manuscript_understanding_service import (
    ManuscriptUnderstandingService,
)
from radar.services.retrieval_service import RetrievalService
from radar.services.trust_service import TrustService


PROMPT_DIR = Path(__file__).parents[1] / "llm" / "prompts"

# Sanitizing rules for LLM-distilled arXiv queries: keep plain keyword text so
# a model can never inject arXiv field prefixes or boolean query syntax.
_ARXIV_FIELD_PREFIX = re.compile(
    r"\b(?:ti|au|abs|co|jr|cat|rn|id|all):", re.IGNORECASE
)
_ARXIV_BOOLEAN_TOKENS = {"AND", "OR", "ANDNOT"}
_QUERY_NUMBERING_PREFIX = re.compile(r"^(?:\d+\s*[.)、]|-|•|\*)\s*")
_QUERY_MAX_WORDS = 10
_QUERY_MAX_CHARS = 120

# Citation-graph discovery: references live at the manuscript tail; expansion
# is bounded so it can never dominate the keyword-searched candidate pool.
_REFERENCE_TAIL_CHARS = 20_000
_CITATION_MAX_SEEDS = 10
_CITATION_PER_SEED = 5
_CITATION_MAX_TOTAL = 30
_CITATION_SINCE_DAYS = 365
# The HyDE abstract joins keyword search as one natural-language query; only
# its head is used so the query stays within API length limits.
_HYDE_QUERY_CHARS = 200
# LLM-as-reranker: only the head of the hybrid ranking is re-scored so the
# extra cost stays bounded; larger heads are scored in batches per prompt.
_RERANK_MAX_CANDIDATES = 12
_RERANK_BATCH_SIZE = 12
_RERANK_ABSTRACT_CHARS = 600
# Fusion of the hybrid combined score with the LLM relevance score; the LLM
# score is one of two equal signals, so the hybrid score can still correct it.
_LLM_RERANK_WEIGHT = 0.5


class ScanCancelled(Exception):
    """Raised at stage boundaries when a cooperative cancel was requested."""


def _raise_if_cancelled(cancel_check: Callable[[], bool] | None) -> None:
    if cancel_check is not None and cancel_check():
        raise ScanCancelled("scan cancelled by user")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Sources disagree on offsets (arXiv ships +00:00, OpenAlex ships bare
    # dates); normalize to aware UTC so they stay comparable.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _prompt(name: str, payload: dict) -> str:
    instructions = (PROMPT_DIR / name).read_text(encoding="utf-8").strip()
    return f"{instructions}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


class WeeklyRadarService:
    """Run one finite search/route/assess workflow; never confirm its own output."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        search_adapter: SearchAdapter | None = None,
        search_adapters: list[SearchAdapter] | None = None,
        llm_client: LLMClient | None = None,
        integrity_adapter: CrossrefIntegrityAdapter | None = None,
        unpaywall_adapter: UnpaywallAdapter | None = None,
        settings: Settings | None = None,
    ):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        if search_adapters is not None:
            adapters = list(search_adapters)
        elif search_adapter is not None:
            adapters = [search_adapter]
        else:
            adapters = [
                ArxivSearchAdapter(self.settings.data_dir / "cache" / "arxiv"),
                OpenAlexSearchAdapter(),
            ]
        if not adapters:
            raise ValueError("search_adapter_required")
        self.search_adapters = adapters
        # Kept for callers that still expect a single primary adapter.
        self.search_adapter = adapters[0]
        # A fully configured local/remote LLM comes from the shared factory;
        # an unconfigured remote still builds so the explicit
        # "llm_not_configured" error surfaces at call time, not import time.
        self.llm_client = (
            llm_client
            or build_analysis_llm(self.settings)
            or ProviderLLMClient(self.settings)
        )
        self.integrity = integrity_adapter or CrossrefIntegrityAdapter(
            mailto=self.settings.crossref_mailto
        )
        # Bibliographic enrichment uses its own adapter because injected test
        # doubles for ``integrity`` only implement the retraction check API.
        self.crossref_metadata = CrossrefIntegrityAdapter(
            mailto=self.settings.crossref_mailto
        )
        self.unpaywall = unpaywall_adapter or UnpaywallAdapter(
            email=self.settings.crossref_mailto
        )
        self.retrieval = RetrievalService(
            session_factory,
            embedding_client=configured_embedding_client(self.settings),
        )
        self.conditions = ConditionService()
        self.impacts = ImpactService(session_factory)
        self.trust = TrustService()

    def _remote_full_context_enabled(self) -> bool:
        return (
            not isinstance(self.llm_client, OllamaLLMClient)
            and not bool(self.settings.local_llm_model)
            and bool(self.settings.llm_provider)
        )

    def _arxiv_search_adapter(self) -> ArxivSearchAdapter | None:
        """Return the arXiv adapter among the configured sources, if any."""

        return next(
            (
                adapter
                for adapter in self.search_adapters
                if isinstance(adapter, ArxivSearchAdapter)
            ),
            None,
        )

    def _openalex_adapter(self) -> OpenAlexSearchAdapter | None:
        """Return the OpenAlex adapter among the configured sources, if any."""

        return next(
            (
                adapter
                for adapter in self.search_adapters
                if isinstance(adapter, OpenAlexSearchAdapter)
            ),
            None,
        )

    @staticmethod
    def _source_name(adapter: SearchAdapter) -> str:
        """Short stable source label used in scan stats (arxiv/openalex/...)."""

        if isinstance(adapter, ArxivSearchAdapter):
            return "arxiv"
        if isinstance(adapter, OpenAlexSearchAdapter):
            return "openalex"
        return adapter.__class__.__name__.lower()

    @staticmethod
    def _dedupe_key(record: SourceRecord) -> str:
        """Cross-source identity: DOI when present, else a normalized title."""

        if record.doi:
            return f"doi:{record.doi.lower()}"
        normalized = " ".join(
            "".join(
                character.lower() if character.isalnum() else " "
                for character in record.title
            ).split()
        )
        return f"title:{normalized}"

    def _analysis_model_label(self) -> str:
        """Return the active analysis model name for user-facing progress."""

        configured = self.settings.local_llm_model or self.settings.llm_model
        return getattr(self.llm_client, "model_name", None) or configured or "AI"

    def run(
        self,
        case_id: str,
        *,
        query: str,
        max_results: int = 20,
        analysis_limit: int = 7,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> str:
        """Return a completed/failed ScanRun id or raise an explicit stage error."""

        if not query.strip():
            raise ValueError("watch_query_required")
        return self._run_queries(
            case_id,
            queries=[query.strip()],
            max_results=max_results,
            analysis_limit=analysis_limit,
            mode="live_arxiv_llm",
            progress_callback=progress_callback,
        )

    def suggested_queries(self, case_id: str, *, limit: int = 4) -> list[str]:
        """Build focused public-paper searches from the user's manuscript profile."""

        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            if research_case is None:
                raise LookupError(f"case not found: {case_id}")
            manuscript = session.scalar(
                select(ManuscriptVersion).where(
                    ManuscriptVersion.case_id == case_id,
                    ManuscriptVersion.is_current.is_(True),
                )
            )
            fallback = research_case.research_question
            has_manuscript = manuscript is not None

        profile = (
            ManuscriptUnderstandingService.latest_profile(
                case_id, self.session_factory
            )
            if has_manuscript
            else None
        )
        candidates = list(profile.watch_topics) if profile else []
        if profile and profile.terminology and len(candidates) < limit:
            candidates.append(" ".join(profile.terminology[:2]))
        if not candidates:
            # Without a profile the raw research question (often non-English)
            # is a poor arXiv query; distill English keyword queries with the
            # LLM and degrade to the raw question when that is unavailable.
            candidates = self._generated_search_queries(
                case_id, fallback, limit=limit
            )
        if not candidates:
            candidates = [fallback]

        # Preserve topic diversity instead of issuing one over-constrained query.
        if len(candidates) > limit:
            indexes = [round(index * (len(candidates) - 1) / (limit - 1)) for index in range(limit)]
            candidates = [candidates[index] for index in indexes]
        result: list[str] = []
        for candidate in candidates:
            normalized = " ".join(candidate.split()).strip()
            if normalized and normalized.lower() not in {item.lower() for item in result}:
                result.append(normalized)
        return result[:limit]

    def _generated_search_queries(
        self, case_id: str, research_question: str, *, limit: int
    ) -> list[str]:
        """Distill English arXiv keyword queries from the research question.

        Results are cached on the case (keyed by question hash) so page
        renders do not re-call the LLM. Returns [] — letting the caller fall
        back to the raw question — whenever the LLM is unconfigured, fails,
        or yields nothing usable; query generation must never block a scan.
        """

        question = " ".join(research_question.split()).strip()
        if not question:
            return []
        question_hash = hashlib.sha256(question.encode()).hexdigest()[:16]
        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            cached = (
                (research_case.settings_json or {}).get("generated_search_queries")
                if research_case
                else None
            )
        if cached and cached.get("question_hash") == question_hash:
            return [
                query for query in cached.get("queries", []) if query.strip()
            ][:limit]

        try:
            output = self.llm_client.generate_structured(
                stage="search_query_generation",
                prompt=_prompt(
                    "search_query_generation.txt",
                    {"research_question": question},
                ),
                response_model=SearchQueryBatch,
            )
        except Exception:
            # Any LLM/parse failure degrades to the raw research question.
            return []
        queries: list[str] = []
        for raw_query in output.queries:
            cleaned = self._sanitize_search_query(raw_query)
            if cleaned and cleaned.lower() not in {item.lower() for item in queries}:
                queries.append(cleaned)
        queries = queries[:limit]
        if queries:
            with session_scope(self.session_factory) as session:
                research_case = session.get(ResearchCase, case_id)
                if research_case is not None:
                    research_case.settings_json = {
                        **(research_case.settings_json or {}),
                        "generated_search_queries": {
                            "question_hash": question_hash,
                            "queries": queries,
                        },
                    }
        return queries

    @staticmethod
    def _sanitize_search_query(raw_query: str) -> str:
        """Reduce one LLM-suggested line to a safe plain-keyword arXiv query."""

        text = raw_query.strip().splitlines()[0] if raw_query.strip() else ""
        text = _QUERY_NUMBERING_PREFIX.sub("", text)
        text = re.sub(r"[*_`\"'“”‘’()]", " ", text)
        text = _ARXIV_FIELD_PREFIX.sub(" ", text)
        words = [
            word
            for word in text.split()
            if word not in _ARXIV_BOOLEAN_TOKENS
        ]
        text = " ".join(words[:_QUERY_MAX_WORDS])
        return text[:_QUERY_MAX_CHARS].strip()

    def _extracted_references(
        self, case_id: str, manuscript: ManuscriptVersion, *, limit: int = 15
    ) -> list[ExtractedReference]:
        """Parse the manuscript's bibliography with the LLM, cached per content.

        Results are cached on the case (keyed by the manuscript content hash)
        so repeated scans do not re-call the model. Returns [] — skipping
        citation-graph discovery — whenever the LLM is unconfigured, fails,
        or finds no bibliography; discovery must never block a scan.
        """

        content_hash = manuscript.content_hash
        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            cached = (
                (research_case.settings_json or {}).get("extracted_references")
                if research_case
                else None
            )
        if cached and cached.get("content_hash") == content_hash:
            return [
                ExtractedReference.model_validate(item)
                for item in cached.get("references", [])
            ][:limit]

        # References sit at the end of a manuscript, so only the tail is sent.
        tail = manuscript.content_text[-_REFERENCE_TAIL_CHARS:]
        try:
            output = self.llm_client.generate_structured(
                stage="reference_extraction",
                prompt=_prompt(
                    "reference_extraction.txt",
                    {
                        "manuscript_tail": truncate_for_prompt(
                            tail, purpose="reference list extraction"
                        )
                    },
                ),
                response_model=ExtractedReferenceBatch,
                # Reasoning models burn output budget on hidden thinking;
                # long bibliographies need a larger cap than the default.
                max_tokens=16_384,
            )
        except Exception:
            # Any LLM/parse failure skips citation-graph discovery.
            return []
        references = [
            reference for reference in output.references if reference.title.strip()
        ][:limit]
        if references:
            with session_scope(self.session_factory) as session:
                research_case = session.get(ResearchCase, case_id)
                if research_case is not None:
                    research_case.settings_json = {
                        **(research_case.settings_json or {}),
                        "extracted_references": {
                            "content_hash": content_hash,
                            "references": [
                                reference.model_dump() for reference in references
                            ],
                        },
                    }
        return references

    def _citation_graph_candidates(
        self,
        case_id: str,
        manuscript: ManuscriptVersion,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> tuple[list[SourceRecord], dict]:
        """Find recent papers citing the manuscript's references via OpenAlex.

        Every per-reference failure skips that seed so discovery can never
        abort the scan; the returned stats describe how far it got.
        """

        stats = {
            "citation_discovery": "skipped:llm",
            "citation_seeds": 0,
            "citation_hits": 0,
        }
        references = self._extracted_references(case_id, manuscript)
        if not references:
            return [], stats
        adapter = self._openalex_adapter()
        if adapter is None:
            stats["citation_discovery"] = "skipped:no_openalex"
            return [], stats
        records: list[SourceRecord] = []
        seeds = 0
        for reference in references:
            if seeds >= _CITATION_MAX_SEEDS or len(records) >= _CITATION_MAX_TOTAL:
                break
            _raise_if_cancelled(cancel_check)
            try:
                openalex_id = adapter.resolve_work(reference.title)
            except Exception:
                continue
            if not openalex_id:
                continue
            seeds += 1
            try:
                records.extend(
                    adapter.get_citing_works(
                        openalex_id,
                        since_days=_CITATION_SINCE_DAYS,
                        max_results=_CITATION_PER_SEED,
                    )
                )
            except Exception:
                continue
        stats["citation_seeds"] = seeds
        stats["citation_discovery"] = "ok" if records else "no_hits"
        return records[:_CITATION_MAX_TOTAL], stats

    def _hyde_abstract(
        self, case_id: str, confirmed: list[ClaimRevision]
    ) -> str | None:
        """Return a cached hypothetical abstract of a relevant paper (HyDE).

        Keyed by the research question plus the confirmed claim statements so
        page renders and repeat scans do not re-call the LLM. Returns None —
        degrading to plain keyword queries — whenever the LLM is
        unconfigured, fails, or yields no usable text.
        """

        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            if research_case is None:
                return None
            question = " ".join((research_case.research_question or "").split())
            cached = (research_case.settings_json or {}).get("hyde_abstract")
        statements = sorted(
            revision.statement.strip()
            for revision in confirmed
            if revision.statement.strip()
        )
        if not question and not statements:
            return None
        key_hash = hashlib.sha256(
            f"{question}\n{'\n'.join(statements)}".encode()
        ).hexdigest()[:16]
        if cached and cached.get("key_hash") == key_hash:
            text = " ".join((cached.get("abstract") or "").split()).strip()
            return text or None
        try:
            output = self.llm_client.generate_structured(
                stage="hyde_abstract",
                prompt=_prompt(
                    "hyde_abstract.txt",
                    {
                        "research_question": question,
                        "confirmed_claims": statements,
                    },
                ),
                response_model=HydeAbstractOutput,
            )
        except Exception:
            return None
        text = " ".join(output.abstract.split()).strip()
        if not text:
            return None
        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            if research_case is not None:
                research_case.settings_json = {
                    **(research_case.settings_json or {}),
                    "hyde_abstract": {"key_hash": key_hash, "abstract": text},
                }
        return text

    def run_auto(
        self,
        case_id: str,
        *,
        max_results: int = 32,
        analysis_limit: int = 3,
        progress_callback: Callable[[float, str], None] | None = None,
        scan_id: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        """Search the newest public papers using topics extracted from one manuscript.

        ``scan_id`` reuses a ScanRun row pre-created by the background runner;
        ``cancel_check`` is polled at stage boundaries for cooperative cancel.
        """

        return self._run_queries(
            case_id,
            queries=self.suggested_queries(case_id),
            max_results=max_results,
            analysis_limit=analysis_limit,
            mode="auto_public_paper_radar",
            progress_callback=progress_callback,
            scan_id=scan_id,
            cancel_check=cancel_check,
        )

    def refresh_source_traceability(self, scan_run_id: str) -> int:
        """Refresh links, venue and DOI for papers already selected by a scan."""

        adapter = self._arxiv_search_adapter()
        if adapter is None:
            return 0
        with session_scope(self.session_factory) as session:
            arxiv_ids = list(
                session.scalars(
                    select(Source.arxiv_id)
                    .join(SourceSnapshot, SourceSnapshot.source_id == Source.id)
                    .join(
                        ImpactCandidate,
                        ImpactCandidate.source_snapshot_id == SourceSnapshot.id,
                    )
                    .where(
                        ImpactCandidate.scan_run_id == scan_run_id,
                        Source.arxiv_id.is_not(None),
                    )
                    .distinct()
                )
            )
        records = adapter.lookup(arxiv_ids)
        self._enrich_bibliographic_metadata(records)
        self._store_records(records)
        return len(records)

    def _enrich_bibliographic_metadata(self, records: list[SourceRecord]) -> int:
        """Resolve DOI-backed venue data without making a scan depend on Crossref.

        Lookups run with bounded concurrency. Failures are counted and
        returned so the caller can record them in the scan stats.
        """

        type_map = {
            "journal-article": "journal_article",
            "proceedings-article": "conference_paper",
        }
        targets = [record for record in records if record.doi]
        if not targets:
            return 0

        def lookup(record: SourceRecord) -> dict | None:
            try:
                return self.crossref_metadata.metadata(record.doi)
            except RuntimeError:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            metadata_results = list(pool.map(lookup, targets))
        failures = 0
        for record, metadata in zip(targets, metadata_results):
            if metadata is None:
                failures += 1
                continue
            record.venue = metadata.get("venue") or record.venue
            record.publication_type = type_map.get(
                metadata.get("crossref_type"), "other"
            )
        return failures

    def _check_source_integrity(
        self, case_id: str, records: list[SourceRecord], *, scan_id: str
    ) -> dict[str, int]:
        """Check DOI-backed sources for retraction signals and propagate alerts.

        Covers both papers found by this scan and sources that confirmed
        claims rely on. A failed Crossref lookup is counted and skipped so it
        can never abort the scan.
        """

        dois = {record.doi for record in records if record.doi}
        with session_scope(self.session_factory) as session:
            dois.update(
                session.scalars(
                    select(Source.doi)
                    .join(ClaimSourceLink, ClaimSourceLink.source_id == Source.id)
                    .join(
                        ClaimRevision,
                        ClaimRevision.id == ClaimSourceLink.claim_revision_id,
                    )
                    .join(Claim, Claim.id == ClaimRevision.claim_id)
                    .where(
                        Claim.case_id == case_id,
                        ClaimSourceLink.review_state == "confirmed",
                        Source.doi.is_not(None),
                    )
                    .distinct()
                )
            )
        checked = 0
        failures = 0
        flagged: list[tuple[str, str]] = []
        for doi in sorted(dois):
            try:
                result = self.integrity.check(doi)
            except RuntimeError:
                failures += 1
                continue
            checked += 1
            state = result.get("integrity_state", "normal")
            if state != "normal":
                flagged.append((doi, state))
        for doi, state in flagged:
            with session_scope(self.session_factory) as session:
                source = session.scalar(select(Source).where(Source.doi == doi))
                if source is None:
                    continue
                source.integrity_state = state
                source_id = source.id
            self.impacts.propagate_retraction(source_id, scan_run_id=scan_id)
        return {
            "integrity_checked": checked,
            "integrity_flagged": len(flagged),
            "integrity_failures": failures,
        }

    def _run_queries(
        self,
        case_id: str,
        *,
        queries: list[str],
        max_results: int,
        analysis_limit: int,
        mode: str,
        progress_callback: Callable[[float, str], None] | None = None,
        scan_id: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        queries = [query.strip() for query in queries if query.strip()]
        if not queries:
            raise ValueError("watch_query_required")
        confirmed, manuscript = self._confirmed_claims(case_id)
        if not confirmed:
            raise ValueError("confirmed_claim_required")
        if manuscript is None:
            raise ValueError("manuscript_missing")

        scan_id = self._start_scan(
            case_id, queries, max_results, analysis_limit, mode=mode, scan_id=scan_id
        )
        records: list[SourceRecord] = []
        try:
            source_labels = "、".join(
                dict.fromkeys(
                    self._source_name(adapter) for adapter in self.search_adapters
                )
            )
            self._emit_progress(
                progress_callback, 0.04, f"正在搜索 {source_labels} 最新公开论文…"
            )
            # HyDE path one: the hypothetical abstract is issued as one extra
            # natural-language query against the keyword search sources.
            hyde_text = self._hyde_abstract(case_id, confirmed)
            search_queries = list(queries)
            if hyde_text:
                search_queries.append(hyde_text[:_HYDE_QUERY_CHARS])
            per_query = max(5, ceil(max_results / len(search_queries)))
            records_by_key: dict[str, SourceRecord] = {}
            source_counts: dict[str, int] = {}
            source_failures: dict[str, str] = {}
            sources_succeeded = 0
            for query in search_queries:
                _raise_if_cancelled(cancel_check)
                for adapter in self.search_adapters:
                    source_name = self._source_name(adapter)
                    try:
                        results = adapter.search(
                            case_id,
                            WatchQuery(query=query, max_results=min(per_query, 100)),
                        )
                    except Exception as exc:
                        # One failing source must not abort the others; the
                        # failure is recorded in the scan stats instead.
                        source_failures[source_name] = str(exc)
                        continue
                    sources_succeeded += 1
                    source_counts[source_name] = source_counts.get(source_name, 0) + len(results)
                    for record in results:
                        key = self._dedupe_key(record)
                        existing = records_by_key.get(key)
                        if existing is None or (not existing.doi and record.doi):
                            records_by_key[key] = record
            if sources_succeeded == 0:
                # Every configured source failed: fail the scan explicitly
                # instead of silently reporting an empty literature day.
                details = "; ".join(
                    f"{name}: {error}" for name, error in source_failures.items()
                )
                raise RuntimeError(f"all_search_sources_failed: {details}")
            # Citation-graph discovery: recent papers citing the manuscript's
            # own references join the same deduped candidate pool.
            self._emit_progress(
                progress_callback, 0.1, "正在沿文稿参考文献追溯最新引用论文…"
            )
            citation_records, citation_stats = self._citation_graph_candidates(
                case_id, manuscript, cancel_check=cancel_check
            )
            citation_hits = 0
            for record in citation_records:
                key = self._dedupe_key(record)
                existing = records_by_key.get(key)
                if existing is None:
                    records_by_key[key] = record
                    citation_hits += 1
                elif not existing.doi and record.doi:
                    records_by_key[key] = record
            citation_stats["citation_hits"] = citation_hits
            if citation_hits:
                source_counts["citation_graph"] = citation_hits
            records = sorted(
                records_by_key.values(),
                key=lambda item: _parse_datetime(item.published_at)
                or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:max_results]
            own_titles = self._own_titles(case_id)
            records = [
                record
                for record in records
                if not self._is_own_work(record.title, own_titles)
            ]
            self._emit_progress(
                progress_callback,
                0.16,
                f"找到 {len(records)} 篇候选论文，正在补全 DOI 与发表信息…",
            )
            crossref_enrich_failures = self._enrich_bibliographic_metadata(records)
            snapshots = self._store_records(records)
            self._emit_progress(
                progress_callback, 0.2, "正在检查撤稿与研究诚信信号…"
            )
            integrity_stats = self._check_source_integrity(
                case_id, records, scan_id=scan_id
            )
            self._emit_progress(progress_callback, 0.25, "正在运行混合检索排序…")
            # HyDE path two: with embeddings configured, the hypothetical
            # abstract is a richer semantic ranking query than raw keywords.
            rank_queries = list(queries)
            if hyde_text and self.retrieval.embedding_enabled:
                rank_queries.append(hyde_text)
            rerank_stats: dict = {}
            pairs = self._rank_pairs(
                snapshots,
                confirmed,
                analysis_limit,
                query=rank_queries,
                case_id=case_id,
                scan_run_id=scan_id,
                stats=rerank_stats,
            )
            self._emit_progress(
                progress_callback,
                0.32,
                f"选出 {len(pairs)} 篇最相关论文，正在下载并解析公开 PDF…",
            )
            full_text_stats = self._enrich_public_full_text(
                [snapshot_id for snapshot_id, _, _ in pairs],
                cancel_check=cancel_check,
            )
            # Rebuild the FTS index only after PDF full text has landed so the
            # index covers complete papers, not abstracts alone.
            self.retrieval.rebuild_fts()

            impact_ids: list[str] = []
            failed_pairs = 0
            blocked_pairs = 0
            for index, (snapshot_id, revision_id, route_score) in enumerate(pairs, start=1):
                _raise_if_cancelled(cancel_check)
                self._emit_progress(
                    progress_callback,
                    0.38 + (0.56 * (index - 1) / max(len(pairs), 1)),
                    f"{self._analysis_model_label()} 正在比较第 {index}/{len(pairs)} 篇论文全文…",
                )
                try:
                    impact_id = self._assess_pair(
                        scan_id=scan_id,
                        case_id=case_id,
                        manuscript=manuscript,
                        snapshot_id=snapshot_id,
                        revision_id=revision_id,
                        route_score=route_score,
                    )
                    if impact_id:
                        impact_ids.append(impact_id)
                    else:
                        blocked_pairs += 1
                except Exception as exc:
                    failed_pairs += 1
                    self._audit_pair_failure(case_id, scan_id, snapshot_id, revision_id, exc)
                self._emit_progress(
                    progress_callback,
                    0.38 + (0.56 * index / max(len(pairs), 1)),
                    f"已完成 {index}/{len(pairs)} 篇全文比较",
                )

            status = "completed" if failed_pairs < len(pairs) or not pairs else "failed"
            publication_dates = [
                parsed
                for record in records
                if (parsed := _parse_datetime(record.published_at)) is not None
            ]
            self._finish_scan(
                scan_id,
                status=status,
                stats={
                    "scanned_papers": len(records),
                    "routed_pairs": len(pairs),
                    "routed_source_snapshot_ids": list(
                        dict.fromkeys(snapshot_id for snapshot_id, _, _ in pairs)
                    ),
                    "impact_candidates": len(impact_ids),
                    "blocked_pairs": blocked_pairs,
                    "failed_pairs": failed_pairs,
                    "search_queries": queries,
                    "hyde": bool(hyde_text),
                    **rerank_stats,
                    "source_counts": source_counts,
                    "source_failures": source_failures,
                    **citation_stats,
                    "unpaywall_hits": full_text_stats.get("unpaywall_hits", 0),
                    "newest_publication": (
                        max(publication_dates).isoformat() if publication_dates else None
                    ),
                    "oldest_publication": (
                        min(publication_dates).isoformat() if publication_dates else None
                    ),
                    **full_text_stats,
                    **integrity_stats,
                    "crossref_enrich_failures": crossref_enrich_failures,
                    "analysis_provider": getattr(
                        self.llm_client,
                        "provider_name",
                        self.settings.llm_provider or self.llm_client.__class__.__name__,
                    ),
                    "analysis_model": getattr(
                        self.llm_client,
                        "model_name",
                        self.settings.llm_model or "injected-test-model",
                    ),
                    "analysis_context": (
                        "full_manuscript_and_public_paper"
                        if self._remote_full_context_enabled()
                        else "focused_local_context"
                    ),
                    "embedding_provider": self.settings.embedding_provider or "disabled",
                    "embedding_model": self.settings.embedding_model,
                    "embedding_degraded": bool(self.retrieval.embedding_errors),
                    "embedding_errors": self.retrieval.embedding_errors[-3:],
                },
                error_message=(
                    f"{failed_pairs} routed pair(s) failed; see audit log."
                    if failed_pairs
                    else None
                ),
            )
            self._emit_progress(
                progress_callback, 0.97, "正在生成针对你论文的具体行动建议…"
            )
            advice_by_impact = self._action_advice(scan_id, case_id)
            ActionService(self.session_factory).sync_scan_actions(
                scan_id, advice_by_impact=advice_by_impact
            )
            self._emit_progress(progress_callback, 1.0, "扫描完成，正在生成项目行动…")
            return scan_id
        except ScanCancelled:
            # Cooperative cancel: keep everything already persisted and exit
            # cleanly instead of failing the scan.
            self._finish_scan(
                scan_id,
                status="cancelled",
                stats={"scanned_papers": len(records), "cancelled": True},
                error_message="Scan cancelled by user.",
            )
            return scan_id
        except Exception as exc:
            self._finish_scan(
                scan_id,
                status="failed",
                stats={"scanned_papers": 0, "impact_candidates": 0},
                error_message=str(exc),
            )
            raise

    @staticmethod
    def _emit_progress(
        callback: Callable[[float, str], None] | None,
        progress: float,
        message: str,
    ) -> None:
        if callback is None:
            return
        try:
            callback(max(0.0, min(progress, 1.0)), message)
        except Exception:
            # A UI rendering issue must not invalidate a completed scientific scan.
            return

    def _confirmed_claims(
        self, case_id: str
    ) -> tuple[list[ClaimRevision], ManuscriptVersion | None]:
        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            if research_case is None:
                raise LookupError(f"case not found: {case_id}")
            manuscript = session.scalar(
                select(ManuscriptVersion).where(
                    ManuscriptVersion.case_id == case_id,
                    ManuscriptVersion.is_current.is_(True),
                )
            )
            confirmed = list(
                session.scalars(
                    select(ClaimRevision)
                    .join(Claim, Claim.id == ClaimRevision.claim_id)
                    .where(
                        Claim.case_id == case_id,
                        ClaimRevision.review_state == "confirmed",
                        ClaimRevision.manuscript_version_id == manuscript.id
                        if manuscript
                        else False,
                    )
                )
            )
            for revision in confirmed:
                session.expunge(revision)
            if manuscript:
                session.expunge(manuscript)
            return confirmed, manuscript

    def _own_titles(self, case_id: str) -> list[str]:
        with session_scope(self.session_factory) as session:
            research_case = session.get(ResearchCase, case_id)
            titles = [research_case.title] if research_case else []
        profile = ManuscriptUnderstandingService.latest_profile(
            case_id, self.session_factory
        )
        if profile:
            titles.append(profile.title)
        return titles

    @staticmethod
    def _is_own_work(candidate_title: str, own_titles: list[str]) -> bool:
        normalize = lambda value: " ".join(
            "".join(character.lower() if character.isalnum() else " " for character in value).split()
        )
        candidate = normalize(candidate_title)
        return any(
            candidate == own
            or (len(own) >= 24 and candidate.startswith(own))
            or (len(candidate) >= 24 and own.startswith(candidate))
            for title in own_titles
            if (own := normalize(title))
        )

    def _start_scan(
        self,
        case_id: str,
        queries: list[str],
        max_results: int,
        analysis_limit: int,
        *,
        mode: str,
        scan_id: str | None = None,
    ) -> str:
        """Create the ScanRun row, or claim one pre-created by the scan runner."""

        query_payload = {
            "query": queries[0],
            "queries": queries,
            "max_results": max_results,
            "analysis_limit": analysis_limit,
        }
        with session_scope(self.session_factory) as session:
            existing = session.get(ScanRun, scan_id) if scan_id else None
            if existing is not None:
                existing.mode = mode
                existing.status = "running"
                existing.started_at = datetime.now(timezone.utc)
                existing.finished_at = None
                existing.query_json = query_payload
                return existing.id
            scan_id = scan_id or str(uuid4())
            session.add(
                ScanRun(
                    id=scan_id,
                    case_id=case_id,
                    mode=mode,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    query_json=query_payload,
                    stats_json={},
                )
            )
        return scan_id

    def _store_records(self, records: list[SourceRecord]) -> list[str]:
        snapshot_ids: list[str] = []
        with session_scope(self.session_factory) as session:
            for record in records:
                content = record.abstract.strip()
                if not content:
                    continue
                source = session.scalar(
                    select(Source).where(Source.external_id == record.external_id)
                )
                if source is None:
                    source = Source(
                        id=str(uuid4()),
                        external_id=record.external_id,
                        title=record.title,
                        authors_json=record.authors,
                        published_at=_parse_datetime(record.published_at),
                        url=record.url,
                        doi=record.doi,
                        arxiv_id=record.arxiv_id,
                        license=record.license,
                        venue=record.venue,
                        publication_type=record.publication_type,
                        pdf_url=record.pdf_url,
                        cited_by_count=record.cited_by_count,
                        integrity_state="normal",
                    )
                    session.add(source)
                    session.flush()
                else:
                    source.title = record.title or source.title
                    source.authors_json = record.authors or source.authors_json
                    source.published_at = _parse_datetime(record.published_at) or source.published_at
                    source.url = record.url or source.url
                    source.doi = record.doi or source.doi
                    source.arxiv_id = record.arxiv_id or source.arxiv_id
                    source.license = record.license or source.license
                    source.venue = record.venue or source.venue
                    source.publication_type = record.publication_type or source.publication_type
                    source.pdf_url = record.pdf_url or source.pdf_url
                    if record.cited_by_count is not None:
                        source.cited_by_count = record.cited_by_count
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                snapshot = session.scalar(
                    select(SourceSnapshot).where(
                        SourceSnapshot.source_id == source.id,
                        SourceSnapshot.content_hash == content_hash,
                    )
                )
                if snapshot is None:
                    snapshot = SourceSnapshot(
                        id=str(uuid4()),
                        source_id=source.id,
                        version_label=record.published_at or "observed",
                        title=record.title,
                        abstract=record.abstract,
                        content_text=content,
                        content_hash=content_hash,
                        event_time=_parse_datetime(record.published_at),
                        observed_at=datetime.now(timezone.utc),
                    )
                    session.add(snapshot)
                    session.flush()
                snapshot_ids.append(snapshot.id)
        return snapshot_ids

    @staticmethod
    def _quality_bonus(cited_by_count: int | None, venue: str | None) -> float:
        """Small trust signal on top of relevance scores.

        Recent papers all sit near zero citations, so the weight must stay
        tiny: at most ~0.06 combined, never enough to outrank relevance.
        """

        citation_bonus = 0.01 * min(log1p(cited_by_count or 0), 4.0)
        venue_bonus = (
            0.02 if venue and venue.strip().lower() not in {"", "arxiv"} else 0.0
        )
        return citation_bonus + venue_bonus

    def _source_quality_by_snapshot(
        self, snapshot_ids: list[str]
    ) -> dict[str, tuple[int | None, str | None]]:
        """Map snapshot ids to (cited_by_count, venue) of their source."""

        with session_scope(self.session_factory) as session:
            rows = session.execute(
                select(SourceSnapshot.id, Source.cited_by_count, Source.venue)
                .join(Source, Source.id == SourceSnapshot.source_id)
                .where(SourceSnapshot.id.in_(snapshot_ids))
            ).all()
        return {row[0]: (row[1], row[2]) for row in rows}

    def _rank_pairs(
        self,
        snapshot_ids: list[str],
        confirmed: list[ClaimRevision],
        analysis_limit: int,
        *,
        query: str | list[str],
        case_id: str | None = None,
        scan_run_id: str | None = None,
        stats: dict | None = None,
    ) -> list[tuple[str, str, float]]:
        ranked: list[tuple[str, str, float]] = []
        limit = max(1, min(analysis_limit, 20))
        centrality_by_revision = {
            revision.id: getattr(revision, "centrality", "major")
            for revision in confirmed
        }
        queries = [query] if isinstance(query, str) else query
        source_scores: dict[str, float] = {}
        for search_query in queries:
            for snapshot_id, score, _ in self.retrieval.rank_sources(
                search_query,
                top_k=len(snapshot_ids),
                snapshot_ids=set(snapshot_ids),
            ):
                source_scores[snapshot_id] = max(
                    score, source_scores.get(snapshot_id, 0.0)
                )
        source_ranking = sorted(
            source_scores.items(), key=lambda item: (-item[1], item[0])
        )
        try:
            quality_by_snapshot = self._source_quality_by_snapshot(snapshot_ids)
        except Exception:
            # The quality bonus is a tie-breaker only; losing it must never
            # break ranking (e.g. unit tests without a database session).
            quality_by_snapshot = {}
        # The candidate pool must cover the LLM rerank head (limit * 3, capped
        # at _RERANK_MAX_CANDIDATES); the legacy 2x pool wins when larger.
        head_size = min(limit * 3, _RERANK_MAX_CANDIDATES)
        source_limit = min(len(source_ranking), max(analysis_limit * 2, head_size))
        for snapshot_id, source_score in source_ranking[:source_limit]:
            if source_score <= 0:
                continue
            cited_by_count, venue = quality_by_snapshot.get(snapshot_id, (None, None))
            quality_bonus = self._quality_bonus(cited_by_count, venue)
            for revision_id, score, _reason in self.retrieval.route_claims(
                snapshot_id, confirmed, top_k=len(confirmed)
            ):
                if score > 0:
                    centrality_bonus = (
                        0.08
                        if centrality_by_revision.get(revision_id) == "core"
                        else 0.0
                    )
                    combined_score = (
                        0.6 * source_scores[snapshot_id]
                        + 0.4 * score
                        + centrality_bonus
                        + quality_bonus
                    )
                    ranked.append((snapshot_id, revision_id, combined_score))
        ranked.sort(key=lambda item: (-item[2], item[0], item[1]))

        # LLM-as-reranker: re-score the head of the hybrid ranking and fuse.
        # Any failure (unconfigured/failing LLM, missing metadata) keeps the
        # hybrid order untouched and records llm_rerank: false in the stats.
        rerank_stats: dict = {"llm_rerank": False}
        head, tail = ranked[:head_size], ranked[head_size:]
        if head and getattr(self, "llm_client", None) is not None:
            try:
                reranked = self._llm_rerank_pairs(
                    head,
                    {revision.id: revision for revision in confirmed},
                    case_id=case_id,
                    scan_run_id=scan_run_id,
                )
            except Exception:
                reranked = None
            if reranked is not None:
                head, rank_changes = reranked
                rerank_stats = {
                    "llm_rerank": True,
                    "llm_rerank_rank_changes": rank_changes,
                }
        if stats is not None:
            stats.update(rerank_stats)
        ranked = head + tail

        # Choose the strongest distinct papers. Do not force weak coverage for
        # every Claim: an unrelated paper must not become an action merely to
        # fill a per-Claim quota.
        selected: list[tuple[str, str, float]] = []
        selected_keys: set[tuple[str, str]] = set()
        source_counts: dict[str, int] = {}
        for candidate in ranked:
            if len(selected) >= limit:
                break
            key = (candidate[0], candidate[1])
            if key in selected_keys:
                continue
            if source_counts.get(candidate[0], 0) >= 1:
                continue
            selected.append(candidate)
            selected_keys.add(key)
            source_counts[candidate[0]] = source_counts.get(candidate[0], 0) + 1
        return sorted(selected, key=lambda item: (-item[2], item[0], item[1]))

    def _llm_rerank_pairs(
        self,
        head: list[tuple[str, str, float]],
        confirmed_by_id: dict[str, ClaimRevision],
        *,
        case_id: str | None,
        scan_run_id: str | None,
    ) -> tuple[list[tuple[str, str, float]], int] | None:
        """Re-score the ranking head with the LLM and fuse with hybrid scores.

        Returns (reranked head, number of rank changes), or None when the
        rerank produced nothing usable — the caller then keeps the hybrid
        order. Candidates are scored in batches keyed by claim revision so
        one prompt compares papers against a single claim statement.
        """

        with session_scope(self.session_factory) as session:
            rows = session.execute(
                select(SourceSnapshot.id, SourceSnapshot.title, SourceSnapshot.abstract)
                .where(SourceSnapshot.id.in_({item[0] for item in head}))
            ).all()
        metadata = {row[0]: (row[1], row[2] or "") for row in rows}
        if len(metadata) < len({item[0] for item in head}):
            return None

        # Group by claim revision: relevance is judged against one claim.
        groups: dict[str, list[tuple[str, str, float]]] = {}
        for pair in head:
            groups.setdefault(pair[1], []).append(pair)

        llm_scores: dict[tuple[str, str], float] = {}
        for revision_id, pairs in groups.items():
            revision = confirmed_by_id.get(revision_id)
            statement = getattr(revision, "statement", "") if revision else ""
            if not statement.strip():
                continue
            for start in range(0, len(pairs), _RERANK_BATCH_SIZE):
                batch = pairs[start : start + _RERANK_BATCH_SIZE]
                candidates = [
                    {
                        "key": f"P{index}",
                        "title": metadata[snapshot_id][0],
                        "abstract": metadata[snapshot_id][1][:_RERANK_ABSTRACT_CHARS],
                    }
                    for index, (snapshot_id, _, _) in enumerate(batch, start=1)
                ]
                output = self._call_model(
                    stage="retrieval_rerank",
                    prompt=_prompt(
                        "retrieval_rerank.txt",
                        {
                            "claim_statement": statement,
                            "candidates": candidates,
                        },
                    ),
                    response_model=RerankBatchOutput,
                    input_refs=[revision_id, *(pair[0] for pair in batch)],
                    case_id=case_id,
                    scan_run_id=scan_run_id,
                )
                key_to_snapshot = {
                    candidate["key"]: pair[0]
                    for candidate, pair in zip(candidates, batch)
                }
                for scored in output.scores:
                    snapshot_id = key_to_snapshot.get(scored.key)
                    if snapshot_id is not None:
                        llm_scores[(snapshot_id, revision_id)] = scored.score
        if not llm_scores:
            return None

        maximum = max(score for _, _, score in head)
        if maximum <= 0:
            return None

        def fused(index: int) -> float:
            snapshot_id, revision_id, combined = head[index]
            combined_norm = combined / maximum
            llm_norm = llm_scores.get((snapshot_id, revision_id))
            if llm_norm is None:
                # Unscored pairs keep their hybrid signal at full weight.
                return combined_norm
            return (
                (1 - _LLM_RERANK_WEIGHT) * combined_norm
                + _LLM_RERANK_WEIGHT * (llm_norm / 10.0)
            )

        order = sorted(
            range(len(head)), key=lambda index: (-fused(index), index)
        )
        rank_changes = sum(
            1 for position, index in enumerate(order) if position != index
        )
        return [head[index] for index in order], rank_changes

    def _store_full_text(self, snapshot_id: str, full_text: str) -> bool:
        """Write parsed public PDF text onto one snapshot."""

        with session_scope(self.session_factory) as session:
            snapshot = session.get(SourceSnapshot, snapshot_id)
            if snapshot is None:
                return False
            snapshot.content_text = full_text
            snapshot.content_hash = hashlib.sha256(full_text.encode()).hexdigest()
            if not snapshot.version_label.endswith(":public-pdf"):
                snapshot.version_label = f"{snapshot.version_label}:public-pdf"
        return True

    def _enrich_public_full_text(
        self,
        snapshot_ids: list[str],
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        """Replace selected abstract-only snapshots with parsed public PDF text.

        arXiv papers resolve through the arXiv adapter; other DOI-backed
        sources without a pdf_url go through Unpaywall, and sources with no
        open-access full text keep abstract-level comparison. Downloads run
        with bounded concurrency; the arXiv adapter's per-host slot
        reservation keeps request starts on arxiv.org politely spaced.
        """

        adapter = self._arxiv_search_adapter()
        enriched = 0
        work: list[tuple[str, str]] = []
        oa_work: list[tuple[str, str]] = []
        for snapshot_id in dict.fromkeys(snapshot_ids):
            _raise_if_cancelled(cancel_check)
            with session_scope(self.session_factory) as session:
                snapshot = session.get(SourceSnapshot, snapshot_id)
                source = session.get(Source, snapshot.source_id) if snapshot else None
                if snapshot is None or source is None:
                    continue
                has_full_text = (
                    len(snapshot.content_text) > len(snapshot.abstract or "") + 1_000
                )
                if source.arxiv_id:
                    if adapter is None:
                        continue
                    if has_full_text:
                        # Skip unless the complete cached parse holds more text
                        # than the snapshot (e.g. a legacy truncated write); this
                        # replaces the old length-window guess that forced genuine
                        # short papers to be re-downloaded on every scan.
                        cached = adapter.cached_full_text(source.arxiv_id)
                        if cached is None or len(cached) <= len(snapshot.content_text):
                            enriched += 1
                            continue
                    work.append((snapshot_id, source.arxiv_id))
                elif source.doi and not source.pdf_url:
                    # Non-arXiv source with a DOI but no known PDF: try to
                    # resolve an open-access PDF through Unpaywall.
                    if has_full_text:
                        enriched += 1
                        continue
                    oa_work.append((snapshot_id, source.doi))

        def fetch(arxiv_id: str) -> str | None:
            try:
                return adapter.fetch_full_text(arxiv_id)
            except Exception:
                return None

        failures = 0
        if work:
            with ThreadPoolExecutor(max_workers=4) as pool:
                full_texts = list(pool.map(fetch, [arxiv_id for _, arxiv_id in work]))
            for (snapshot_id, _), full_text in zip(work, full_texts):
                _raise_if_cancelled(cancel_check)
                if full_text is None:
                    failures += 1
                    continue
                if self._store_full_text(snapshot_id, full_text):
                    enriched += 1

        stats = {"full_text_papers": enriched, "full_text_failures": failures}
        if not oa_work:
            return stats

        def fetch_oa(doi: str) -> tuple[str | None, bool]:
            """Return (full_text, found_oa_pdf) for one DOI."""

            try:
                pdf_url = self.unpaywall.get_oa_pdf_url(doi)
            except Exception:
                return None, False
            if not pdf_url:
                return None, False
            try:
                return self.unpaywall.download_pdf_text(pdf_url), True
            except Exception:
                return None, True

        unpaywall_hits = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            oa_results = list(pool.map(fetch_oa, [doi for _, doi in oa_work]))
        for (snapshot_id, _), (full_text, found_oa) in zip(oa_work, oa_results):
            _raise_if_cancelled(cancel_check)
            if not found_oa:
                # No open-access full text: abstract-level comparison stands.
                continue
            unpaywall_hits += 1
            if full_text is None:
                failures += 1
                continue
            if self._store_full_text(snapshot_id, full_text):
                enriched += 1
        return {
            "full_text_papers": enriched,
            "full_text_failures": failures,
            "unpaywall_hits": unpaywall_hits,
        }

    def _assess_pair(
        self,
        *,
        scan_id: str,
        case_id: str,
        manuscript: ManuscriptVersion,
        snapshot_id: str,
        revision_id: str,
        route_score: float,
    ) -> str | None:
        with session_scope(self.session_factory) as session:
            revision = session.get(ClaimRevision, revision_id)
            snapshot = session.get(SourceSnapshot, snapshot_id)
            source = session.get(Source, snapshot.source_id) if snapshot else None
            if revision is None or snapshot is None or source is None:
                raise LookupError("routed_source_or_claim_missing")
            claim = session.get(Claim, revision.claim_id)
            manuscript_profile = ManuscriptUnderstandingService.latest_profile(
                case_id, self.session_factory
            )
            profile_claim = next(
                (
                    item
                    for item in (manuscript_profile.claim_profiles if manuscript_profile else [])
                    if claim is not None and item.stable_key == claim.stable_key
                ),
                None,
            )
            stored_contract = EmpiricalClaimContract.model_validate(
                revision.contract_json
            )
            own_contract = (
                profile_claim.contract
                if profile_claim is not None
                and not any(stored_contract.model_dump().values())
                else stored_contract
            )
            query_terms = [
                revision.statement,
                *[str(value) for value in own_contract.model_dump().values() if value],
            ]
            evidence_new = EvidenceService.extract_relevant_evidence(
                query_terms, snapshot.content_text, snapshot.id
            )
            if evidence_new is None:
                return None
            remote_full_context = self._remote_full_context_enabled()
            incoming = self._call_model(
                stage="incoming_result",
                prompt=_prompt(
                    "incoming_result.txt",
                    {
                        "incoming_title": source.title,
                        "incoming_abstract": snapshot.abstract,
                        "incoming_exact_evidence": evidence_new.model_dump(),
                    },
                ),
                response_model=IncomingResult,
                input_refs=[snapshot.id],
                case_id=case_id,
                scan_run_id=scan_id,
            )
            differences = self.conditions.compare(own_contract, incoming)
            comparability = self.conditions.overall_comparability(differences)
            assessment = self._call_model(
                stage="impact_assessment",
                prompt=_prompt(
                    "impact_assessment.txt",
                    {
                        "confirmed_claim": revision.statement,
                        "claim_centrality": revision.centrality,
                        "claim_contract": own_contract.model_dump(),
                        "full_manuscript_profile": (
                            manuscript_profile.model_dump()
                            if manuscript_profile is not None
                            else None
                        ),
                        "own_full_manuscript_text": (
                            # Prompt background only; evidence verification
                            # below runs on the full database text.
                            truncate_for_prompt(
                                manuscript.content_text,
                                purpose="own manuscript background",
                            )
                            if remote_full_context
                            else None
                        ),
                        "selected_claim_profile": (
                            profile_claim.model_dump() if profile_claim is not None else None
                        ),
                        "own_exact_evidence": {
                            "quote": revision.source_quote,
                            "locator": revision.source_locator,
                        },
                        "incoming_title": source.title,
                        "incoming_abstract": snapshot.abstract,
                        "incoming_public_paper_text": (
                            truncate_for_prompt(
                                snapshot.content_text,
                                purpose="incoming paper background",
                            )
                            if remote_full_context
                            else None
                        ),
                        "incoming_text_scope": (
                            "public_full_text_retrieval"
                            if len(snapshot.content_text) > len(snapshot.abstract or "") + 1_000
                            else "abstract"
                        ),
                        "incoming_result": incoming.model_dump(),
                        "incoming_exact_evidence": evidence_new.model_dump(),
                        "programmatic_comparability": comparability,
                        "programmatic_condition_differences": [
                            difference.model_dump() for difference in differences
                        ],
                    },
                ),
                response_model=ImpactAssessmentOutput,
                input_refs=[revision.id, snapshot.id],
                case_id=case_id,
                scan_run_id=scan_id,
            )
            assessment = assessment.model_copy(
                update={
                    "comparability": comparability,
                    "condition_differences": differences,
                    "stance": self.impacts.enforce_stance(
                        assessment.stance, comparability
                    ),
                }
            )
            verified_own_evidence = EvidenceService.resolve_exact(
                assessment.evidence_own, manuscript.content_text
            )
            verified_new_evidence = EvidenceService.resolve_exact(
                assessment.evidence_new, snapshot.content_text
            )
            if verified_own_evidence is None or verified_new_evidence is None:
                self._add_audit(
                    session,
                    case_id=case_id,
                    event_type="impact_blocked",
                    object_type="ClaimRevision",
                    object_id=revision.id,
                    payload={
                        "snapshot_id": snapshot.id,
                        "errors": [
                            name
                            for name, value in {
                                "span_failed:own": verified_own_evidence,
                                "span_failed:new": verified_new_evidence,
                            }.items()
                            if value is None
                        ],
                    },
                )
                return None
            assessment = assessment.model_copy(
                update={
                    "evidence_own": verified_own_evidence,
                    "evidence_new": verified_new_evidence,
                }
            )
            is_no_material_change = (
                assessment.impact_mode == "no_material_change"
                and assessment.change_depth == 0
                and assessment.suggested_action == "no_action"
            )
            if is_no_material_change:
                self._add_audit(
                    session,
                    case_id=case_id,
                    event_type="impact_filtered_no_change",
                    object_type="ClaimRevision",
                    object_id=revision.id,
                    payload={
                        "snapshot_id": snapshot.id,
                        "reason": "model reported zero required project change",
                    },
                )
            trust = self.trust.verify_impact(
                assessment, manuscript.content_text, snapshot.content_text
            )
            if trust.state == "blocked":
                self._add_audit(
                    session,
                    case_id=case_id,
                    event_type="impact_blocked",
                    object_type="ClaimRevision",
                    object_id=revision.id,
                    payload={"snapshot_id": snapshot.id, "errors": trust.errors},
                )
                return None
            strategic_flags = (
                ["competitor"]
                if self.retrieval.competitor_flag(case_id, source.id)
                else []
            )
            severity = self.impacts.severity(
                centrality=revision.centrality,
                stance=assessment.stance,
                comparability=comparability,
                impact_mode=assessment.impact_mode,
                change_depth=assessment.change_depth,
                strategic_flags=strategic_flags,
            )
            impact = ImpactCandidate(
                id=str(uuid4()),
                scan_run_id=scan_id,
                claim_revision_id=revision.id,
                source_snapshot_id=snapshot.id,
                event_type="paper",
                stance=assessment.stance,
                impact_mode=assessment.impact_mode,
                strategic_flags_json=strategic_flags,
                comparability=comparability,
                condition_differences_json=[item.model_dump() for item in differences],
                evidence_own_json=assessment.evidence_own.model_dump(),
                evidence_new_json={
                    **assessment.evidence_new.model_dump(),
                    "source_snapshot_id": snapshot.id,
                },
                change_depth=assessment.change_depth,
                severity=severity,
                suggested_action=assessment.suggested_action,
                uncertainty_json=assessment.uncertainty_sources,
                review_state="informative" if is_no_material_change else "candidate",
                trust_state="verified",
            )
            session.add(impact)
            session.flush()
            self._add_audit(
                session,
                case_id=case_id,
                event_type="impact_candidate_created",
                object_type="ImpactCandidate",
                object_id=impact.id,
                payload={"route_score": route_score, "scan_run_id": scan_id},
            )
            return impact.id

    def materialize_completed_assessments(self, scan_run_id: str) -> int:
        """Backfill persisted comparisons for scans created before no-change retention."""

        created = 0
        with session_scope(self.session_factory) as session:
            scan = session.get(ScanRun, scan_run_id)
            if scan is None:
                raise LookupError(f"scan not found: {scan_run_id}")
            existing = {
                (item.claim_revision_id, item.source_snapshot_id)
                for item in session.scalars(
                    select(ImpactCandidate).where(
                        ImpactCandidate.scan_run_id == scan_run_id
                    )
                )
            }
            # Prefer the persisted scan_run_id; fall back to the legacy time
            # window for ModelRuns recorded before traceability columns existed.
            legacy_window = and_(
                ModelRun.scan_run_id.is_(None),
                ModelRun.created_at >= scan.started_at,
            )
            if scan.finished_at:
                legacy_window = and_(
                    legacy_window, ModelRun.created_at <= scan.finished_at
                )
            query = select(ModelRun).where(
                ModelRun.stage == "impact_assessment",
                or_(ModelRun.scan_run_id == scan_run_id, legacy_window),
            )
            runs = list(session.scalars(query.order_by(ModelRun.created_at)))

            for run in runs:
                if len(run.input_refs_json or []) < 2:
                    continue
                revision_id, snapshot_id = map(str, run.input_refs_json[:2])
                if (revision_id, snapshot_id) in existing:
                    continue
                revision = session.get(ClaimRevision, revision_id)
                snapshot = session.get(SourceSnapshot, snapshot_id)
                source = session.get(Source, snapshot.source_id) if snapshot else None
                manuscript = (
                    session.get(ManuscriptVersion, revision.manuscript_version_id)
                    if revision
                    else None
                )
                if not all([revision, snapshot, source, manuscript]):
                    continue
                try:
                    assessment = ImpactAssessmentOutput.model_validate(
                        run.parsed_output_json
                    )
                except ValueError:
                    continue
                comparability = self.conditions.overall_comparability(
                    assessment.condition_differences
                )
                assessment = assessment.model_copy(
                    update={
                        "comparability": comparability,
                        "stance": self.impacts.enforce_stance(
                            assessment.stance, comparability
                        ),
                    }
                )
                verified_own_evidence = EvidenceService.resolve_exact(
                    assessment.evidence_own, manuscript.content_text
                )
                verified_new_evidence = EvidenceService.resolve_exact(
                    assessment.evidence_new, snapshot.content_text
                )
                if verified_own_evidence is None or verified_new_evidence is None:
                    continue
                assessment = assessment.model_copy(
                    update={
                        "evidence_own": verified_own_evidence,
                        "evidence_new": verified_new_evidence,
                    }
                )
                trust = self.trust.verify_impact(
                    assessment, manuscript.content_text, snapshot.content_text
                )
                if trust.state == "blocked":
                    continue
                strategic_flags = (
                    ["competitor"]
                    if self.retrieval.competitor_flag(scan.case_id, source.id)
                    else []
                )
                is_no_material_change = (
                    assessment.impact_mode == "no_material_change"
                    and assessment.change_depth == 0
                    and assessment.suggested_action == "no_action"
                )
                impact = ImpactCandidate(
                    id=str(uuid4()),
                    scan_run_id=scan.id,
                    claim_revision_id=revision.id,
                    source_snapshot_id=snapshot.id,
                    event_type="paper",
                    stance=assessment.stance,
                    impact_mode=assessment.impact_mode,
                    strategic_flags_json=strategic_flags,
                    comparability=comparability,
                    condition_differences_json=[
                        item.model_dump() for item in assessment.condition_differences
                    ],
                    evidence_own_json=assessment.evidence_own.model_dump(),
                    evidence_new_json={
                        **assessment.evidence_new.model_dump(),
                        "source_snapshot_id": snapshot.id,
                    },
                    change_depth=assessment.change_depth,
                    severity=self.impacts.severity(
                        centrality=revision.centrality,
                        stance=assessment.stance,
                        comparability=comparability,
                        impact_mode=assessment.impact_mode,
                        change_depth=assessment.change_depth,
                        strategic_flags=strategic_flags,
                    ),
                    suggested_action=assessment.suggested_action,
                    uncertainty_json=assessment.uncertainty_sources,
                    review_state=(
                        "informative" if is_no_material_change else "candidate"
                    ),
                    trust_state="verified",
                )
                session.add(impact)
                self._add_audit(
                    session,
                    case_id=scan.case_id,
                    event_type="impact_comparison_materialized",
                    object_type="ImpactCandidate",
                    object_id=impact.id,
                    payload={"scan_run_id": scan.id, "model_run_id": run.id},
                )
                existing.add((revision_id, snapshot_id))
                created += 1
        return created

    def _action_advice(
        self, scan_id: str, case_id: str
    ) -> dict[str, ActionAdviceOutput]:
        """Draft one concrete action per verified impact of a finished scan.

        Runs once inside the scan pipeline (LLM client already configured) so
        page renders never call the model. Integrity events and no-change
        comparisons are left to the deterministic rule path. Any LLM failure
        (unconfigured client, network, parse) stops the batch and degrades the
        remaining impacts to rule templates.
        """

        pending: list[dict] = []
        with session_scope(self.session_factory) as session:
            impacts = list(
                session.scalars(
                    select(ImpactCandidate).where(
                        ImpactCandidate.scan_run_id == scan_id,
                        ImpactCandidate.trust_state == "verified",
                        ImpactCandidate.review_state != "dismissed",
                    )
                )
            )
            for impact in impacts:
                if (
                    impact.impact_mode == "research_integrity"
                    or impact.event_type == "retraction"
                ):
                    continue
                if (
                    impact.impact_mode == "no_material_change"
                    and impact.suggested_action == "no_action"
                ):
                    continue
                revision = session.get(ClaimRevision, impact.claim_revision_id)
                snapshot = session.get(SourceSnapshot, impact.source_snapshot_id)
                source = session.get(Source, snapshot.source_id) if snapshot else None
                if not all([revision, snapshot, source]):
                    continue
                pending.append(
                    {
                        "impact_id": impact.id,
                        "revision_id": revision.id,
                        "snapshot_id": snapshot.id,
                        "payload": {
                            "claim_statement": revision.statement,
                            "claim_centrality": revision.centrality,
                            "claim_contract": revision.contract_json,
                            "impact": {
                                "stance": impact.stance,
                                "impact_mode": impact.impact_mode,
                                "comparability": impact.comparability,
                                "severity": impact.severity,
                                "suggested_action": impact.suggested_action,
                                "strategic_flags": impact.strategic_flags_json,
                                "condition_differences": (
                                    impact.condition_differences_json
                                ),
                                "uncertainty_sources": impact.uncertainty_json,
                                "incoming_evidence_quote": (
                                    impact.evidence_new_json.get("quote")
                                ),
                            },
                            "incoming_title": source.title,
                            "incoming_abstract": snapshot.abstract,
                        },
                    }
                )
        advice: dict[str, ActionAdviceOutput] = {}
        for item in pending:
            try:
                output = self._call_model(
                    stage="action_advice",
                    prompt=_prompt("action_advice.txt", item["payload"]),
                    response_model=ActionAdviceOutput,
                    input_refs=[item["revision_id"], item["snapshot_id"]],
                    case_id=case_id,
                    scan_run_id=scan_id,
                )
            except Exception:
                # Unconfigured or failing LLM: rule templates take over for
                # every remaining impact of this scan.
                break
            advice[item["impact_id"]] = output
        return advice

    def _call_model(
        self,
        *,
        stage: str,
        prompt: str,
        response_model,
        input_refs: list[str],
        case_id: str | None = None,
        scan_run_id: str | None = None,
    ):
        started = time.perf_counter()
        output = self.llm_client.generate_structured(
            stage=stage, prompt=prompt, response_model=response_model
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        receipt = getattr(self.llm_client, "last_receipt", {}) or {}
        raw_response = receipt.get("raw_response") or output.model_dump_json()
        usage = receipt.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        model_name = getattr(
            self.llm_client,
            "model_name",
            self.settings.llm_model or "injected-test-model",
        )
        with session_scope(self.session_factory) as session:
            session.add(
                ModelRun(
                    id=str(uuid4()),
                    stage=stage,
                    case_id=case_id,
                    scan_run_id=scan_run_id,
                    provider=getattr(
                        self.llm_client,
                        "provider_name",
                        self.settings.llm_provider or self.llm_client.__class__.__name__,
                    ),
                    model=model_name,
                    prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
                    schema_version=f"{response_model.__name__}.v1",
                    input_refs_json=input_refs,
                    raw_response=raw_response,
                    parsed_output_json=output.model_dump(),
                    validation_json={"pydantic": True},
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimate_llm_cost_usd(
                        model_name, input_tokens, output_tokens
                    ),
                    latency_ms=int(receipt.get("latency_ms", latency_ms)),
                )
            )
        return output

    def _finish_scan(
        self, scan_id: str, *, status: str, stats: dict, error_message: str | None
    ) -> None:
        with session_scope(self.session_factory) as session:
            scan = session.get(ScanRun, scan_id)
            if scan is None:
                return
            scan.status = status
            scan.finished_at = datetime.now(timezone.utc)
            # Merge so runner-written progress/cancel markers survive the finish.
            scan.stats_json = {**(scan.stats_json or {}), **stats}
            scan.error_message = error_message
            self._add_audit(
                session,
                case_id=scan.case_id,
                event_type=f"weekly_scan_{status}",
                object_type="ScanRun",
                object_id=scan.id,
                payload=stats,
            )

    def _audit_pair_failure(
        self,
        case_id: str,
        scan_id: str,
        snapshot_id: str,
        revision_id: str,
        exc: Exception,
    ) -> None:
        with session_scope(self.session_factory) as session:
            self._add_audit(
                session,
                case_id=case_id,
                event_type="weekly_pair_failed",
                object_type="ScanRun",
                object_id=scan_id,
                payload={
                    "snapshot_id": snapshot_id,
                    "claim_revision_id": revision_id,
                    "error": str(exc),
                },
            )

    @staticmethod
    def _add_audit(
        session: Session,
        *,
        case_id: str,
        event_type: str,
        object_type: str,
        object_id: str,
        payload: dict,
    ) -> None:
        session.add(
            AuditEvent(
                id=str(uuid4()),
                case_id=case_id,
                event_type=event_type,
                object_type=object_type,
                object_id=object_id,
                payload_json=payload,
                actor_type="system",
                actor_id="weekly_radar_service",
            )
        )
