"""FastAPI application for the Research Radar React frontend.

Routes are organised by resource under ``/api/``.  Every request opens its own
database session via ``session_scope()``; no session is reused across requests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from radar.api_schemas import (
    _ACTION_TYPE_KIND,
    _IMPACT_SUGGESTION,
    _PRIORITY_MAP,
    _REVIEW_STATE_CLAIM_STATUS,
    _SEVERITY_URGENCY,
    _STANCE_VERDICT,
    _cost_yuan,
    _duration_ms,
    _parse_date,
    _parse_datetime,
    ActionItemOut,
    ActionStatusRequest,
    AuditRecOut,
    ClaimOut,
    CompetitorEntry,
    CompetitorRequest,
    Contract,
    CreateCaseRequest,
    EditClaimRequest,
    EditImpactRequest,
    EvidenceItem,
    MatrixRow,
    PaperOut,
    ProjectOut,
    ProjectProfile,
    ProjectSummary,
    RewriteView,
    ScanStartRequest,
    SettingsUpdate,
    SplitClaimRequest,
    VersionRecOut,
)
from radar.config import get_settings, save_local_settings
from radar.db import SessionLocal, session_scope
from radar.llm.factory import describe_llm_setup
from radar.models import (
    ActionItem,
    AuditEvent,
    Claim,
    ClaimRevision,
    ImpactCandidate,
    ManuscriptVersion,
    ModelRun,
    PatchProposal,
    ResearchCase,
    ScanRun,
    Source,
    SourceSnapshot,
    WatchEntity,
)
from radar.services.action_service import ActionService
from radar.services.case_service import CaseService
from radar.services.claim_service import ClaimService
from radar.services.impact_service import ImpactService
from radar.services.manuscript_understanding_service import (
    ManuscriptUnderstandingService,
)
from radar.services.patch_service import PatchService
from radar.services.report_service import ReportService
from radar.services.scan_runner import (
    ScanAlreadyRunningError,
    request_cancel,
    start,
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Research Radar API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(klass):
    # Do NOT default session_factory — it would capture the import-time value
    # and ignore monkeypatched SessionLocal in tests.
    return klass(SessionLocal)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

@app.get("/api/cases", response_model=list[ProjectSummary])
def list_cases() -> list[dict[str, Any]]:
    """Return a lightweight list of all research cases."""
    cases = _service(CaseService).list_cases()
    result: list[dict[str, Any]] = []
    for case in cases:
        summary = _build_summary(case)
        result.append(summary)
    return result


@app.post("/api/cases", response_model=ProjectSummary)
async def create_case(
    title: str = File(...),
    research_question: str = File(default=""),
    manuscript: UploadFile = File(...),
) -> dict[str, Any]:
    """Create a new research case by uploading a manuscript PDF/TeX/MD file."""
    suffix = Path(manuscript.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await manuscript.read())
        tmp_path = Path(tmp.name)

    try:
        case_id = _service(CaseService).create_case(
            title=title,
            research_question=research_question,
            manuscript_path=tmp_path,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    case = _service(CaseService).get_case(case_id)
    if case is None:
        raise HTTPException(500, "case created but not found")
    return _build_summary(case)


@app.get("/api/cases/{case_id}", response_model=ProjectOut)
def get_case(case_id: str) -> dict[str, Any]:
    """Return the full project view for one research case."""
    case = _service(CaseService).get_case(case_id)
    if case is None:
        raise HTTPException(404, f"case not found: {case_id}")
    return _build_project(case_id, case)


@app.post("/api/cases/{case_id}/upload")
async def upload_manuscript(case_id: str, manuscript: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a new manuscript version for an existing case."""
    suffix = Path(manuscript.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await manuscript.read())
        tmp_path = Path(tmp.name)

    try:
        result = _service(CaseService).add_manuscript_version(case_id, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return result


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/claims", response_model=list[ClaimOut])
def list_claims(case_id: str) -> list[dict[str, Any]]:
    """Return all claims (confirmed + candidate) for a case, newest revision per claim."""
    claims_out = _build_claims(case_id)
    return [claim.model_dump() for claim in claims_out]


@app.post("/api/cases/{case_id}/claims/{rev_id}/confirm")
def confirm_claim(case_id: str, rev_id: str) -> dict[str, Any]:
    """Confirm a claim candidate (human gate G0)."""
    try:
        revision = _service(ClaimService).confirm_candidate(rev_id)
    except LookupError:
        raise HTTPException(404, f"claim revision not found: {rev_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _revision_to_claim_out(revision).model_dump()


@app.post("/api/cases/{case_id}/claims/{rev_id}/reject")
def reject_claim(case_id: str, rev_id: str) -> dict[str, Any]:
    """Reject a claim candidate."""
    try:
        revision = _service(ClaimService).reject_candidate(rev_id)
    except LookupError:
        raise HTTPException(404, f"claim revision not found: {rev_id}")
    return _revision_to_claim_out(revision).model_dump()


@app.put("/api/cases/{case_id}/claims/{rev_id}")
def edit_claim(case_id: str, rev_id: str, body: EditClaimRequest) -> dict[str, Any]:
    """Edit a claim (creates a new revision, supersedes the old one)."""
    try:
        revision = _service(ClaimService).edit_candidate(
            rev_id,
            statement=body.statement,
            centrality=body.centrality,
            contract=body.contract.model_dump(),
            falsifiable_condition=body.falsifiable_condition,
        )
    except LookupError:
        raise HTTPException(404, f"claim revision not found: {rev_id}")
    return _revision_to_claim_out(revision).model_dump()


@app.post("/api/cases/{case_id}/claims/{rev_id}/split")
def split_claim(case_id: str, rev_id: str, body: SplitClaimRequest) -> list[dict[str, Any]]:
    """Split one claim into multiple child claims."""
    try:
        revisions = _service(ClaimService).split_candidate(rev_id, body.statements)
    except LookupError:
        raise HTTPException(404, f"claim revision not found: {rev_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return [_revision_to_claim_out(rev).model_dump() for rev in revisions]


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/scans")
def start_scan(case_id: str, body: ScanStartRequest = ScanStartRequest()) -> dict[str, Any]:
    """Launch a background radar scan for this case."""
    try:
        scan_id = start(
            case_id,
            max_results=body.max_results,
            analysis_limit=body.analysis_limit,
        )
    except ScanAlreadyRunningError as exc:
        raise HTTPException(409, str(exc))
    return {"scan_id": scan_id, "status": "running"}


@app.get("/api/cases/{case_id}/scans")
def list_scans(case_id: str) -> list[dict[str, Any]]:
    """Return all scan runs for a case (most recent first)."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        scans = list(
            session.scalars(
                select(ScanRun)
                .where(ScanRun.case_id == case_id)
                .order_by(ScanRun.created_at.desc())
            )
        )
        result = []
        for scan in scans:
            result.append({
                "id": scan.id,
                "mode": scan.mode,
                "status": scan.status,
                "started_at": _parse_datetime(scan.started_at),
                "finished_at": _parse_datetime(scan.finished_at),
                "progress": (scan.stats_json or {}).get("progress", {}),
                "stats": {k: v for k, v in (scan.stats_json or {}).items() if k != "progress"},
                "error_message": scan.error_message,
            })
        return result


@app.get("/api/cases/{case_id}/scans/{scan_id}")
def get_scan_status(case_id: str, scan_id: str) -> dict[str, Any]:
    """Poll the status and progress of one scan run."""
    with session_scope(SessionLocal) as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            raise HTTPException(404, f"scan not found: {scan_id}")
        return {
            "id": scan.id,
            "mode": scan.mode,
            "status": scan.status,
            "started_at": _parse_datetime(scan.started_at),
            "finished_at": _parse_datetime(scan.finished_at),
            "progress": (scan.stats_json or {}).get("progress", {}),
            "stats": {k: v for k, v in (scan.stats_json or {}).items() if k != "progress"},
            "error_message": scan.error_message,
        }


@app.delete("/api/cases/{case_id}/scans/{scan_id}")
def cancel_scan(case_id: str, scan_id: str) -> dict[str, Any]:
    """Request cancellation of a running scan."""
    try:
        accepted = request_cancel(scan_id)
    except LookupError:
        raise HTTPException(404, f"scan not found: {scan_id}")
    return {"scan_id": scan_id, "cancelled": accepted}


# ---------------------------------------------------------------------------
# Impacts
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/impacts", response_model=list[PaperOut])
def list_impacts(case_id: str) -> list[dict[str, Any]]:
    """Return all impact-candidate papers for a case."""
    return _build_papers(case_id)


@app.post("/api/cases/{case_id}/impacts/{impact_id}/confirm")
def confirm_impact(case_id: str, impact_id: str) -> dict[str, Any]:
    """Confirm an impact candidate as accepted evidence."""
    from radar.services.review_service import ReviewService

    try:
        impact = _service(ReviewService).confirm(impact_id)
    except LookupError:
        raise HTTPException(404, f"impact not found: {impact_id}")
    return _impact_to_paper_out(impact).model_dump()


@app.post("/api/cases/{case_id}/impacts/{impact_id}/dismiss")
def dismiss_impact(case_id: str, impact_id: str) -> dict[str, Any]:
    """Dismiss an impact candidate."""
    from radar.services.review_service import ReviewService

    try:
        impact = _service(ReviewService).dismiss(impact_id)
    except LookupError:
        raise HTTPException(404, f"impact not found: {impact_id}")
    return _impact_to_paper_out(impact).model_dump()


@app.put("/api/cases/{case_id}/impacts/{impact_id}")
def edit_impact(case_id: str, impact_id: str, body: EditImpactRequest) -> dict[str, Any]:
    """Edit an impact candidate's metadata."""
    from radar.services.review_service import ReviewService

    try:
        impact = _service(ReviewService).edit(impact_id, body.model_dump(exclude_none=True))
    except LookupError:
        raise HTTPException(404, f"impact not found: {impact_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _impact_to_paper_out(impact).model_dump()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/actions", response_model=list[ActionItemOut])
def list_actions(case_id: str) -> list[dict[str, Any]]:
    """Return all active action items for a case."""
    items = _service(ActionService).list_actions(case_id)
    return [_action_to_out(item) for item in items]


@app.put("/api/cases/{case_id}/actions/{action_id}/status")
def update_action_status(case_id: str, action_id: str, body: ActionStatusRequest) -> dict[str, Any]:
    """Update an action item's status."""
    try:
        item = _service(ActionService).update_status(action_id, body.status)
    except LookupError:
        raise HTTPException(404, f"action not found: {action_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _action_to_out(item)


# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

@app.post("/api/cases/{case_id}/patches")
def generate_patch_for_impact(impact_id: str = File(...)) -> dict[str, Any]:
    """Generate a manuscript rewrite patch for a confirmed impact."""
    try:
        patch = _service(PatchService).generate_patch(impact_id)
    except LookupError:
        raise HTTPException(404, f"impact not found: {impact_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    claim_id = ""
    with session_scope(SessionLocal) as session:
        impact = session.get(ImpactCandidate, patch.impact_candidate_id)
        if impact:
            rev = session.get(ClaimRevision, impact.claim_revision_id)
            if rev:
                claim_id = rev.claim_id

    return {
        "claimId": claim_id,
        "loc": patch.target_locator,
        "before": patch.before_text,
        "after": patch.after_text,
        "checks": [
            {"label": k, "ok": v}
            for k, v in (patch.validations_json or {}).items()
        ],
    }


@app.post("/api/cases/{case_id}/patches/{patch_id}/approve")
def approve_patch(case_id: str, patch_id: str) -> dict[str, Any]:
    """Approve a generated patch."""
    try:
        patch = _service(PatchService).approve_patch(patch_id)
    except LookupError:
        raise HTTPException(404, f"patch not found: {patch_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _patch_to_rewrite(patch)


@app.post("/api/cases/{case_id}/patches/{patch_id}/reject")
def reject_patch(case_id: str, patch_id: str) -> dict[str, Any]:
    """Reject a generated patch."""
    try:
        patch = _service(PatchService).reject_patch(patch_id)
    except LookupError:
        raise HTTPException(404, f"patch not found: {patch_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _patch_to_rewrite(patch)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/audit", response_model=list[AuditRecOut])
def export_audit(case_id: str) -> list[dict[str, Any]]:
    """Export the audit trail (model runs + audit events) as a list."""
    return _build_audit(case_id)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/profile")
def get_profile(case_id: str) -> dict[str, Any]:
    """Return the latest manuscript-understanding profile for a case."""
    profile = ManuscriptUnderstandingService.latest_profile(case_id)
    if profile is None:
        return ProjectProfile().model_dump()
    return ProjectProfile(
        question=profile.research_problem,
        thesis=profile.central_thesis,
        contributions=profile.contributions,
        findings=profile.key_findings,
        limits=profile.limitations,
    ).model_dump()


@app.post("/api/cases/{case_id}/profile/analyze")
def analyze_profile(case_id: str) -> dict[str, Any]:
    """Run a full manuscript-understanding analysis (may be slow)."""
    try:
        _, profile = _service(ManuscriptUnderstandingService).analyze(case_id)
    except LookupError:
        raise HTTPException(404, f"case not found: {case_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return ProjectProfile(
        question=profile.research_problem,
        thesis=profile.central_thesis,
        contributions=profile.contributions,
        findings=profile.key_findings,
        limits=profile.limitations,
    ).model_dump()


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/competitors", response_model=list[CompetitorEntry])
def list_competitors(case_id: str) -> list[dict[str, Any]]:
    """Return the competitor watchlist for a case."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        entities = list(
            session.scalars(
                select(WatchEntity).where(WatchEntity.case_id == case_id)
            )
        )
        return [
            CompetitorEntry(team=entity.canonical_name, aliases=entity.aliases_json)
            for entity in entities
        ]


@app.post("/api/cases/{case_id}/competitors")
def add_competitor(case_id: str, body: CompetitorRequest) -> dict[str, Any]:
    """Add a competitor/team to the watchlist."""
    try:
        watch_id = _service(CaseService).add_watch_entity(
            case_id,
            entity_type="competitor",
            canonical_name=body.team,
            aliases=body.aliases,
        )
    except LookupError:
        raise HTTPException(404, f"case not found: {case_id}")
    return {"id": watch_id, "team": body.team, "aliases": body.aliases}


@app.delete("/api/cases/{case_id}/competitors/{watch_id}")
def remove_competitor(case_id: str, watch_id: str) -> dict[str, Any]:
    """Remove a competitor from the watchlist."""
    try:
        _service(CaseService).remove_watch_entity(watch_id)
    except LookupError:
        raise HTTPException(404, f"watch entity not found: {watch_id}")
    return {"deleted": watch_id}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def get_app_settings() -> dict[str, Any]:
    """Return the current LLM and embedding configuration."""
    settings = get_settings()
    llm = describe_llm_setup(settings)
    return {
        "llm": {
            "configured": llm["configured"],
            "mode": llm["mode"],
            "model": llm["model"],
            "missing": llm["missing"],
            "provider": settings.llm_provider,
            "base_url": settings.llm_base_url,
        },
        "embedding": {
            "configured": bool(settings.embedding_model),
            "model": settings.embedding_model,
            "provider": settings.embedding_provider,
            "base_url": settings.embedding_base_url,
        },
        "local_llm": {
            "model": settings.local_llm_model,
            "base_url": settings.local_llm_base_url,
        },
        "pdf_parser_backend": settings.pdf_parser_backend,
    }


@app.put("/api/settings")
def update_app_settings(body: SettingsUpdate) -> dict[str, Any]:
    """Write one or more settings keys to the local override env file."""
    try:
        save_local_settings(body.updates)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    return {"saved": list(body.updates.keys())}


# ===========================================================================
# Internal builders (ORM → dict via Pydantic schemas)
# ===========================================================================

def _build_summary(case: ResearchCase) -> dict[str, Any]:
    """Build a ProjectSummary from a ResearchCase row + derived counts."""
    claims_total = 0
    claims_confirmed = 0
    latest_scan = ""
    file_name = ""
    version_label = "v1"
    urgent_count = 0

    with session_scope(SessionLocal) as session:
        from sqlalchemy import func, select

        claims_total = session.scalar(
            select(func.count(Claim.id)).where(Claim.case_id == case.id)
        ) or 0

        confirmed_ct = session.scalar(
            select(func.count(Claim.id))
            .join(ClaimRevision, ClaimRevision.claim_id == Claim.id)
            .where(
                Claim.case_id == case.id,
                ClaimRevision.review_state == "confirmed",
            )
        ) or 0
        # Count distinct claims that have at least one confirmed revision
        claims_confirmed = confirmed_ct

        latest_scan_row = session.scalar(
            select(ScanRun)
            .where(ScanRun.case_id == case.id)
            .order_by(ScanRun.created_at.desc())
        )
        if latest_scan_row:
            latest_scan = _parse_datetime(latest_scan_row.finished_at or latest_scan_row.created_at)

        manuscript = session.scalar(
            select(ManuscriptVersion)
            .where(
                ManuscriptVersion.case_id == case.id,
                ManuscriptVersion.is_current.is_(True),
            )
        )
        if manuscript:
            file_name = manuscript.file_name
            version_label = f"v{manuscript.version_no}"

        # Urgent = sum of critical + high priority open actions
        urgent_count = session.scalar(
            select(func.count(ActionItem.id)).where(
                ActionItem.case_id == case.id,
                ActionItem.priority.in_(["critical", "high"]),
                ActionItem.status.in_(["proposed", "open", "in_progress"]),
            )
        ) or 0

    # Derive "short" from title: first acronym-like segment or first few words
    short = case.title
    if ":" in short:
        short = short.split(":", 1)[0].strip()
    elif len(short) > 30:
        short = short[:30]

    return ProjectSummary(
        id=case.id,
        name=case.title,
        short=short,
        question=case.research_question,
        version=version_label,
        file=file_name,
        claimsConfirmed=claims_confirmed,
        claimsTotal=claims_total,
        lastScan=latest_scan,
        urgent=urgent_count,
        topics=_case_topics(case),
    ).model_dump()


def _build_project(case_id: str, case: ResearchCase) -> dict[str, Any]:
    """Build a full ProjectOut from a ResearchCase."""
    summary = _build_summary(case)
    claims = _build_claims(case_id)
    papers = _build_papers(case_id)
    actions = _build_actions(case_id)
    versions = _build_versions(case_id)
    audit = _build_audit(case_id)
    competitors = _build_competitors(case_id)
    profile = _build_profile(case_id)
    rewrite = _build_rewrite(case_id)

    return {
        **summary,
        "claims": [c.model_dump() for c in claims],
        "papers": papers,
        "actions": actions,
        "versions": versions,
        "audit": audit,
        "competitors": competitors,
        "profile": profile,
        "rewrite": rewrite,
    }


def _build_claims(case_id: str) -> list[ClaimOut]:
    """Build ClaimOut list: one entry per claim, using the latest revision."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        claims = list(
            session.scalars(
                select(Claim).where(Claim.case_id == case_id)
            )
        )
        result: list[ClaimOut] = []
        for claim in claims:
            rev = session.scalar(
                select(ClaimRevision)
                .where(ClaimRevision.claim_id == claim.id)
                .order_by(ClaimRevision.revision_no.desc())
            )
            if rev is None:
                continue
            result.append(_revision_to_claim_out(rev))
        return result


def _revision_to_claim_out(rev: ClaimRevision) -> ClaimOut:
    """Map one ClaimRevision to a ClaimOut."""
    contract_raw = rev.contract_json or {}
    contract = Contract(
        task=contract_raw.get("task") or "",
        dataset=contract_raw.get("dataset") or "",
        split=contract_raw.get("split") or "",
        metric=contract_raw.get("metric") or "",
        baseline=contract_raw.get("comparator") or contract_raw.get("baseline") or "",
        scope=contract_raw.get("scope") or "",
    )

    # Collect evidence from confirmed impact candidates
    evidence: list[EvidenceItem] = []
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        impacts = list(
            session.scalars(
                select(ImpactCandidate).where(
                    ImpactCandidate.claim_revision_id == rev.id,
                    ImpactCandidate.review_state.in_(["confirmed", "edited"]),
                )
            )
        )
        for imp in impacts:
            evidence.append(
                EvidenceItem(
                    kind=_stance_evidence_kind(imp.stance),
                    paperId=imp.id,
                    note=_IMPACT_SUGGESTION.get(imp.suggested_action, imp.suggested_action),
                )
            )

    # radarWatch: claim has challenge or competitor impacts
    radar_watch = any(
        e.kind == "challenge" or e.kind == "completeness" for e in evidence
    )

    return ClaimOut(
        id=rev.id,
        text=rev.statement,
        status=_REVIEW_STATE_CLAIM_STATUS.get(rev.review_state, "valid"),
        confirmed="yes" if rev.review_state in ("confirmed", "edited") else "pending",
        radarWatch=radar_watch,
        quote=rev.source_quote,
        loc=rev.source_locator,
        contract=contract,
        falsifiable=rev.falsifiable_condition,
        evidence=evidence,
    )


def _build_papers(case_id: str) -> list[dict[str, Any]]:
    """Build PaperOut list from impact candidates."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        impacts = list(
            session.scalars(
                select(ImpactCandidate)
                .join(ScanRun, ScanRun.id == ImpactCandidate.scan_run_id)
                .where(ScanRun.case_id == case_id)
                .order_by(ImpactCandidate.created_at.desc())
            )
        )
        result: list[dict[str, Any]] = []
        for imp in impacts:
            result.append(_impact_to_paper_out(imp).model_dump())
        return result


def _impact_to_paper_out(imp: ImpactCandidate) -> PaperOut:
    """Map one ImpactCandidate to a PaperOut."""
    title = ""
    authors: list[str] = []
    arxiv_id = ""
    date_str = ""
    claim_ids: list[str] = []

    with session_scope(SessionLocal) as session:
        snapshot = session.get(SourceSnapshot, imp.source_snapshot_id)
        if snapshot:
            source = session.get(Source, snapshot.source_id)
            if source:
                title = source.title
                authors = source.authors_json or []
                arxiv_id = source.arxiv_id or ""
                date_str = _parse_date(source.published_at)

        # Find which claims this impact relates to
        rev = session.get(ClaimRevision, imp.claim_revision_id)
        if rev:
            claim_ids = [rev.claim_id]

    # Matrix from condition_differences_json
    matrix: list[MatrixRow] = []
    for diff in imp.condition_differences_json or []:
        matrix.append(
            MatrixRow(
                field=diff.get("field", ""),
                ours=diff.get("own_value") or "",
                theirs=diff.get("incoming_value") or "",
                status=_diff_status(diff.get("status", "")),
            )
        )

    evidence_new = imp.evidence_new_json or {}
    evidence_own = imp.evidence_own_json or {}

    # why / suggestion from suggested_action
    suggestion = _IMPACT_SUGGESTION.get(imp.suggested_action, imp.suggested_action)

    # uncertainty from uncertainty_json
    uncertainty = ""
    if imp.uncertainty_json:
        uncertainty = "; ".join(imp.uncertainty_json)

    return PaperOut(
        id=imp.id,
        title=title,
        authors=authors,
        arxivId=arxiv_id,
        date=date_str,
        verdict=_STANCE_VERDICT.get(imp.stance, "none"),
        urgency=_SEVERITY_URGENCY.get(imp.severity, "info"),
        claimIds=claim_ids,
        quote=evidence_new.get("quote", ""),
        quoteLoc=evidence_new.get("locator", ""),
        yourQuote=evidence_own.get("quote", ""),
        yourLoc=evidence_own.get("locator", ""),
        matrix=[m.model_dump() for m in matrix],
        why=suggestion,
        suggestion=suggestion,
        uncertainty=uncertainty,
    )


def _build_actions(case_id: str) -> list[dict[str, Any]]:
    """Build ActionItemOut list."""
    items = _service(ActionService).list_actions(case_id)
    return [_action_to_out(item) for item in items]


def _action_to_out(item: ActionItem) -> dict[str, Any]:
    """Map one ActionItem to ActionItemOut dict."""
    return ActionItemOut(
        id=item.id,
        kind=_ACTION_TYPE_KIND.get(item.action_type, "writing"),
        priority=_PRIORITY_MAP.get(item.priority, "P2"),
        title=item.title,
        due=item.due_label,
        claimId=item.claim_revision_id or "",
        sourcePaperId=item.impact_candidate_id or "",
        reason=item.rationale or "",
        checklist=item.checklist_json,
    ).model_dump()


def _build_versions(case_id: str) -> list[dict[str, Any]]:
    """Build VersionRecOut list from manuscript versions."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import func, select

        versions = list(
            session.scalars(
                select(ManuscriptVersion)
                .where(ManuscriptVersion.case_id == case_id)
                .order_by(ManuscriptVersion.version_no.desc())
            )
        )
        result: list[dict[str, Any]] = []
        for ver in versions:
            claims_count = session.scalar(
                select(func.count(ClaimRevision.id)).where(
                    ClaimRevision.manuscript_version_id == ver.id
                )
            ) or 0
            result.append(
                VersionRecOut(
                    v=f"v{ver.version_no}",
                    date=_parse_date(ver.created_at),
                    file=ver.file_name,
                    claims=claims_count,
                    note=ver.source_type,
                ).model_dump()
            )
        return result


def _build_audit(case_id: str) -> list[dict[str, Any]]:
    """Build AuditRecOut list from ModelRun rows."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        runs = list(
            session.scalars(
                select(ModelRun)
                .where(ModelRun.case_id == case_id)
                .order_by(ModelRun.created_at.asc())
            )
        )
        result: list[dict[str, Any]] = []
        for run in runs:
            result.append(
                AuditRecOut(
                    stage=run.stage,
                    provider=run.provider,
                    model=run.model,
                    duration=_duration_ms(run.latency_ms),
                    cost=_cost_yuan(run.estimated_cost),
                    result="pass",
                ).model_dump()
            )
        return result


def _build_competitors(case_id: str) -> list[dict[str, Any]]:
    """Build competitor list."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        entities = list(
            session.scalars(
                select(WatchEntity).where(WatchEntity.case_id == case_id)
            )
        )
        return [
            CompetitorEntry(team=e.canonical_name, aliases=e.aliases_json).model_dump()
            for e in entities
        ]


def _build_profile(case_id: str) -> dict[str, Any]:
    """Build profile dict from latest manuscript understanding."""
    profile = ManuscriptUnderstandingService.latest_profile(case_id)
    if profile is None:
        return ProjectProfile().model_dump()
    return ProjectProfile(
        question=profile.research_problem,
        thesis=profile.central_thesis,
        contributions=profile.contributions,
        findings=profile.key_findings,
        limits=profile.limitations,
    ).model_dump()


def _build_rewrite(case_id: str) -> dict[str, Any]:
    """Build the latest rewrite / patch proposal for the case."""
    with session_scope(SessionLocal) as session:
        from sqlalchemy import select

        patch = session.scalar(
            select(PatchProposal)
            .where(
                PatchProposal.case_id == case_id,
                PatchProposal.approval_state.in_(["candidate", "approved"]),
            )
            .order_by(PatchProposal.created_at.desc())
        )
        if patch is None:
            return RewriteView().model_dump()

        claim_id = ""
        impact = session.get(ImpactCandidate, patch.impact_candidate_id)
        if impact:
            rev = session.get(ClaimRevision, impact.claim_revision_id)
            if rev:
                claim_id = rev.claim_id

        return RewriteView(
            claimId=claim_id,
            before=patch.before_text,
            after=patch.after_text,
            loc=patch.target_locator,
            checks=[
                CheckItem(label=k, ok=bool(v))
                for k, v in (patch.validations_json or {}).items()
            ],
        ).model_dump()


def _case_topics(case: ResearchCase) -> list[str]:
    """Derive topics from the claim contracts and manuscript understanding."""
    topics: list[str] = []
    settings = case.settings_json or {}
    if isinstance(settings.get("topics"), list):
        topics.extend(settings["topics"])
    if case.field and case.field not in topics:
        topics.insert(0, case.field)
    return topics or []


def _stance_evidence_kind(stance: str) -> str:
    if stance == "challenges":
        return "challenge"
    if stance == "supports":
        return "support"
    return "completeness"


def _diff_status(raw: str) -> str:
    mapping = {
        "match": "same",
        "compatible_alias": "same",
        "partial": "partial",
        "mismatch": "diff",
        "unknown": "diff",
    }
    return mapping.get(raw, "same")


# ---------------------------------------------------------------------------
# In production (Docker image) the React build lives at /app/static; in local
# development it lives at app/dist relative to the project root.  Serve the
# single-page application on the root after all /api routes are defined.
_STATIC_DIRS = [
    Path("/app/static"),                  # Docker image
    Path(__file__).resolve().parent.parent / "app" / "dist",  # local dev
]
for _dir in _STATIC_DIRS:
    if _dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_dir), html=True), name="static")
        break
