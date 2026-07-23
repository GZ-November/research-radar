"""Pydantic schemas for the FastAPI JSON API — mirrors the React frontend data model.

These models are pure Pydantic (no SQLAlchemy dependency).  They carry
``from_attributes=True`` so they can be built directly from ORM objects
with ``.model_validate(orm_obj)``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Shared / leaf models
# ---------------------------------------------------------------------------

class MatrixRow(BaseModel):
    """One row in a claim-vs-paper condition-comparison matrix."""
    field: str = ""
    ours: str = ""
    theirs: str = ""
    status: Literal["same", "partial", "diff"] = "same"


class EvidenceItem(BaseModel):
    kind: Literal["support", "challenge", "completeness"] = "support"
    paperId: str = ""
    note: str = ""


class Contract(BaseModel):
    task: str = ""
    dataset: str = ""
    split: str = ""
    metric: str = ""
    baseline: str = ""
    scope: str = ""


class CheckItem(BaseModel):
    label: str = ""
    ok: bool = True


class CompetitorEntry(BaseModel):
    team: str = ""
    aliases: list[str] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    question: str = ""
    thesis: str = ""
    contributions: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)


class RewriteView(BaseModel):
    patchId: str = ""
    claimId: str = ""
    before: str = ""
    after: str = ""
    loc: str = ""
    checks: list[CheckItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main resource models
# ---------------------------------------------------------------------------

class ClaimOut(BaseModel):
    """Serialised view of one confirmed claim for the React frontend."""
    model_config = {"from_attributes": True}

    id: str = ""
    text: str = ""
    status: Literal["valid", "supported", "disputed", "revalidate"] = "valid"
    confirmed: Literal["yes", "pending", "history"] = "pending"
    radarWatch: bool = False
    quote: str = ""
    loc: str = ""
    contract: Contract = Field(default_factory=Contract)
    falsifiable: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)


class PaperOut(BaseModel):
    """Serialised view of one impact-candidate paper for the React frontend."""
    model_config = {"from_attributes": True}

    id: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    arxivId: str = ""
    date: str = ""
    verdict: Literal["challenge", "support", "boundary", "prior", "none"] = "none"
    urgency: Literal["urgent", "review", "info"] = "info"
    claimIds: list[str] = Field(default_factory=list)
    quote: str = ""
    quoteLoc: str = ""
    yourQuote: str = ""
    yourLoc: str = ""
    matrix: list[MatrixRow] = Field(default_factory=list)
    why: str = ""
    suggestion: str = ""
    uncertainty: str = ""
    reviewState: Literal["candidate", "edited", "confirmed", "dismissed"] = "candidate"


class ActionItemOut(BaseModel):
    """Serialised view of one action item for the React frontend."""
    model_config = {"from_attributes": True}

    id: str = ""
    kind: Literal["experiment", "data", "writing", "competitive", "revalidate"] = "writing"
    priority: Literal["P0", "P1", "P2"] = "P2"
    title: str = ""
    due: str = ""
    claimId: str = ""
    sourcePaperId: str = ""
    reason: str = ""
    checklist: list[str] = Field(default_factory=list)
    status: Literal["proposed", "open", "in_progress", "done", "dismissed"] = "proposed"


class VersionRecOut(BaseModel):
    """Serialised view of one manuscript version record."""
    model_config = {"from_attributes": True}

    v: str = ""
    date: str = ""
    file: str = ""
    claims: int = 0
    note: str = ""


class AuditRecOut(BaseModel):
    """Serialised view of one audit / model-run record."""
    model_config = {"from_attributes": True}

    stage: str = ""
    provider: str = ""
    model: str = ""
    duration: str = ""
    cost: str = ""
    result: Literal["pass", "warn", "fail"] = "pass"


class ProjectOut(BaseModel):
    """Top-level project view returned by ``GET /api/cases/{id}``."""
    model_config = {"from_attributes": True}

    id: str = ""
    name: str = ""
    short: str = ""
    question: str = ""
    version: str = ""
    file: str = ""
    claimsConfirmed: int = 0
    claimsTotal: int = 0
    lastScan: str = ""
    urgent: int = 0
    topics: list[str] = Field(default_factory=list)
    claims: list[ClaimOut] = Field(default_factory=list)
    papers: list[PaperOut] = Field(default_factory=list)
    actions: list[ActionItemOut] = Field(default_factory=list)
    versions: list[VersionRecOut] = Field(default_factory=list)
    audit: list[AuditRecOut] = Field(default_factory=list)
    competitors: list[CompetitorEntry] = Field(default_factory=list)
    profile: ProjectProfile = Field(default_factory=ProjectProfile)
    rewrite: RewriteView = Field(default_factory=RewriteView)


class ProjectSummary(BaseModel):
    """Lightweight list item returned by ``GET /api/cases``."""
    model_config = {"from_attributes": True}

    id: str = ""
    name: str = ""
    short: str = ""
    question: str = ""
    version: str = ""
    file: str = ""
    claimsConfirmed: int = 0
    claimsTotal: int = 0
    lastScan: str = ""
    urgent: int = 0
    topics: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CreateCaseRequest(BaseModel):
    title: str
    research_question: str = ""


class EditClaimRequest(BaseModel):
    statement: str = ""
    centrality: str = "major"
    contract: Contract = Field(default_factory=Contract)
    falsifiable_condition: str = ""


class SplitClaimRequest(BaseModel):
    statements: list[str]


class EditImpactRequest(BaseModel):
    review_state: str | None = None
    stance: str | None = None
    severity: str | None = None
    comparability: str | None = None
    suggested_action: str | None = None


class ActionStatusRequest(BaseModel):
    status: str


class ScanStartRequest(BaseModel):
    max_results: int = Field(default=32, ge=1, le=100)
    analysis_limit: int = Field(default=3, ge=1, le=20)


class CompetitorRequest(BaseModel):
    team: str
    aliases: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    """Key-value pairs for the settings endpoint.  Keys are env-var names."""
    updates: dict[str, str]


# ---------------------------------------------------------------------------
# Mapping helpers (ORM object → Pydantic schema)
# ---------------------------------------------------------------------------

_STANCE_VERDICT: dict[str, str] = {
    "supports": "support",
    "challenges": "challenge",
    "neutral": "none",
    "uncertain": "none",
}

_SEVERITY_URGENCY: dict[str, str] = {
    "critical": "urgent",
    "review": "review",
    "informative": "info",
}

_REVIEW_STATE_CLAIM_STATUS: dict[str, str] = {
    "confirmed": "valid",
    "edited": "valid",
    "candidate": "valid",
    "rejected": "revalidate",
    "superseded": "history",
}

_ACTION_TYPE_KIND: dict[str, str] = {
    "team_decision": "competitive",
    "experiment": "experiment",
    "data": "data",
    "writing": "writing",
    "cite": "writing",
    "competitor_response": "competitive",
    "revalidation": "revalidate",
}

_PRIORITY_MAP: dict[str, str] = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P2",
}

_IMPACT_SUGGESTION: dict[str, str] = {
    "cite": "建议引用于 Related Work，明确条件差异。",
    "add_boundary_discussion": "建议在 Discussion 中补充适用边界。",
    "run_comparison": "建议增补对照实验，锁定差异来源。",
    "narrow_claim": "建议收窄主张的适用范围。",
    "team_review": "建议团队复核，确认是否影响主要结论。",
    "revalidate": "建议重新验证受影响结论。",
    "watch": "无需立即行动，纳入持续关注。",
    "no_action": "无需操作。",
}


def _parse_date(dt: datetime | str | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return str(dt)[:10]


def _parse_datetime(dt: datetime | str | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)[:16]


def _duration_ms(ms: int | None) -> str:
    if ms is None:
        return ""
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def _cost_yuan(usd: float | None) -> str:
    if usd is None or usd == 0:
        return "¥0.00"
    return f"¥{usd * 7.2:.2f}"
