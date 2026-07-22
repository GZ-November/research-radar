"""Pydantic contracts shared by deterministic and model-assisted stages."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceSpan(BaseModel):
    quote: str
    locator: str
    source_snapshot_id: str | None = None

    @field_validator("quote", "locator")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence fields cannot be blank")
        return value


class EmpiricalClaimContract(BaseModel):
    task: str | None = None
    dataset: str | None = None
    split: str | None = None
    metric: str | None = None
    comparator: str | None = None
    scope: str | None = None


class ManuscriptClaimProfile(BaseModel):
    stable_key: str
    role: Literal["core", "major", "minor"]
    claim_summary: str
    contract: EmpiricalClaimContract
    boundary_conditions: list[str] = Field(default_factory=list)
    falsification_tests: list[str] = Field(default_factory=list)


class ManuscriptUnderstandingOutput(BaseModel):
    title: str
    research_problem: str
    central_thesis: str
    contributions: list[str]
    methods: list[str]
    datasets: list[str]
    evaluation_protocol: list[str]
    key_findings: list[str]
    limitations: list[str]
    terminology: list[str]
    watch_topics: list[str]
    claim_profiles: list[ManuscriptClaimProfile]


class ActionRecommendation(BaseModel):
    action_type: Literal[
        "team_decision",
        "experiment",
        "data",
        "writing",
        "cite",
        "competitor_response",
        "revalidation",
    ]
    priority: Literal["critical", "high", "medium", "low"]
    title: str
    rationale: str
    checklist: list[str]
    due_label: str
    initial_status: Literal["proposed", "open"] = "proposed"
    advice_source: Literal["llm", "rule"] = "rule"


class ActionAdviceOutput(BaseModel):
    """One concrete project action drafted by the analysis LLM for an impact.

    Categories map to stored ActionItem.action_type values: 补实验
    (experiment), 补数据 (data), 调整写作 (writing), 引用/关注 (cite),
    验证重跑 (revalidation).
    """

    category: Literal["experiment", "data", "writing", "cite", "revalidation"]
    title: str
    rationale: str
    checklist: list[str] = Field(default_factory=list)


class ClaimCandidateOutput(BaseModel):
    statement: str
    claim_type: Literal["empirical_result"] = "empirical_result"
    centrality_suggestion: Literal["core", "major", "minor"]
    contract: EmpiricalClaimContract
    falsifiable_condition: str
    source_quote: str
    source_locator: str


class ClaimCandidateBatch(BaseModel):
    """LLM response wrapper: the model returns claims as one JSON object."""

    candidates: list[ClaimCandidateOutput] = Field(default_factory=list)


class ConditionDifference(BaseModel):
    field: Literal["task", "dataset", "split", "metric", "comparator", "scope"]
    own_value: str | None
    incoming_value: str | None
    status: Literal["match", "compatible_alias", "partial", "mismatch", "unknown"]
    explanation: str


class ImpactAssessmentOutput(BaseModel):
    stance: Literal["supports", "challenges", "neutral", "uncertain"]
    impact_mode: Literal[
        "replication", "boundary_condition", "method_substitution", "prior_art",
        "research_integrity", "no_material_change",
    ]
    comparability: Literal["compatible", "partial", "incompatible", "unknown"]
    condition_differences: list[ConditionDifference]
    evidence_own: EvidenceSpan
    evidence_new: EvidenceSpan
    change_depth: Literal[0, 1, 2, 3, 4]
    suggested_action: Literal[
        "cite", "add_boundary_discussion", "run_comparison", "narrow_claim",
        "team_review", "revalidate", "watch", "no_action",
    ]
    uncertainty_sources: list[str] = Field(default_factory=list)


class PatchProposalOutput(BaseModel):
    edit_class: Literal[
        "add_citation", "add_boundary_discussion", "add_limitation",
        "qualify_claim", "experiment_todo",
    ]
    target_locator: str
    before_text: str
    after_text: str
    citation_source_ids: list[str]
    assertions_added: list[str]
    assertions_weakened_or_removed: list[str]
    rationale: str


class ParsedSection(BaseModel):
    title: str
    locator: str
    text: str


class ParsedBlock(BaseModel):
    text: str
    locator: str


class ParsedDocument(BaseModel):
    path: Path
    full_text: str
    sections: list[ParsedSection]
    paragraphs: list[ParsedBlock]
    sentences: list[ParsedBlock]
    content_hash: str


class IncomingResult(EmpiricalClaimContract):
    direction: Literal["supports", "challenges", "neutral", "uncertain"] = "uncertain"


class WatchQuery(BaseModel):
    query: str
    max_results: int = Field(default=50, ge=1, le=100)


class SearchQueryBatch(BaseModel):
    """English arXiv keyword queries distilled from one research question."""

    queries: list[str] = Field(default_factory=list, max_length=5)


class SourceRecord(BaseModel):
    external_id: str
    title: str
    authors: list[str]
    abstract: str
    url: str
    published_at: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    license: str | None = None
    venue: str | None = None
    publication_type: Literal["preprint", "journal_article", "conference_paper", "other"] = "preprint"
    pdf_url: str | None = None


class TrustResult(BaseModel):
    state: Literal["generated", "grounded", "verified", "blocked"]
    errors: list[str] = Field(default_factory=list)
