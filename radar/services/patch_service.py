"""Candidate-only manuscript patches with G2 validation and approval."""

import json
import hashlib
import re
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from radar.db import SessionLocal, session_scope
from radar.config import Settings, estimate_llm_cost_usd, get_settings
from radar.llm.base import LLMClient
from radar.llm.factory import build_analysis_llm
from radar.llm.provider import ProviderLLMClient
from radar.models import (
    AuditEvent, Claim, ClaimRevision, ImpactCandidate, ManuscriptVersion,
    ModelRun, PatchProposal, ResearchCase, ScanRun, Source, SourceSnapshot,
)
from radar.schemas import PatchProposalOutput
from radar.llm.text_utils import truncate_for_prompt
from radar.services.evidence_service import resolve_exact_quote


PROMPT_PATH = Path(__file__).parents[1] / "llm" / "prompts" / "patch_generation.txt"


PATCH_POLICIES = {
    "prior_art": {
        "target": "Introduction / Related Work / Discussion",
        "change": "更新文献定位与差异化表述；不改实验数字。",
    },
    "boundary_condition": {
        "target": "Discussion / Limitations",
        "change": "写明 Task、Dataset、Split、Metric、Comparator、Scope 中的具体边界。",
    },
    "replication": {
        "target": "Results / Discussion / Limitations",
        "change": "条件可比时收窄结论，并加入复现或团队复核；锁定原始数字。",
    },
    "method_substitution": {
        "target": "Methods / Experiments",
        "change": "加入最小 head-to-head 实验计划；跑完前不宣称胜负。",
    },
    "research_integrity": {
        "target": "Citations / Methods / Results",
        "change": "标记受影响证据和结果，要求重新验证。",
    },
}


def _numbers(text: str) -> list[str]:
    return re.findall(r"(?<![\w-])\d+(?:\.\d+)?%?", text)


class PatchService:
    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        llm_client: LLMClient | None = None,
        settings: Settings | None = None,
    ):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.llm_client = (
            llm_client
            or build_analysis_llm(self.settings)
            or ProviderLLMClient(self.settings)
        )

    def generate_patch(self, confirmed_impact_id: str) -> PatchProposal:
        with session_scope(self.session_factory) as session:
            existing = session.scalar(
                select(PatchProposal)
                .where(
                    PatchProposal.impact_candidate_id == confirmed_impact_id,
                    PatchProposal.approval_state.in_({"candidate", "approved"}),
                )
                .order_by(PatchProposal.created_at.desc())
            )
            if existing:
                session.expunge(existing)
                return existing
            impact = session.get(ImpactCandidate, confirmed_impact_id)
            if impact is None:
                raise LookupError(f"impact not found: {confirmed_impact_id}")
            if impact.review_state not in {"confirmed", "edited"}:
                raise ValueError("candidate_cannot_generate_patch")
            if impact.impact_mode == "no_material_change":
                raise ValueError("no_material_change_cannot_generate_patch")
            revision = session.get(ClaimRevision, impact.claim_revision_id)
            manuscript = session.get(ManuscriptVersion, revision.manuscript_version_id)
            claim = session.get(Claim, revision.claim_id)
            research_case = session.get(ResearchCase, claim.case_id)
            snapshot = session.get(SourceSnapshot, impact.source_snapshot_id)
            source = session.get(Source, snapshot.source_id) if snapshot else None
            if source is None or snapshot is None:
                raise ValueError("patch_source_missing")

            template = self._find_template(research_case, confirmed_impact_id)
            if template is None:
                template = self._generate_model_template(
                    session=session,
                    research_case=research_case,
                    manuscript=manuscript,
                    claim=claim,
                    revision=revision,
                    impact=impact,
                    source=source,
                    snapshot=snapshot,
                )
            patch = PatchProposal(
                id=str(uuid4()), case_id=research_case.id, manuscript_version_id=manuscript.id,
                impact_candidate_id=impact.id, target_locator=template["target_locator"],
                edit_class=template["edit_class"], before_text=template["before_text"],
                after_text=template["after_text"], citations_json=template["citation_source_ids"],
                evidence_refs_json=[impact.evidence_own_json, impact.evidence_new_json],
                validations_json={}, approval_state="candidate",
            )
            session.add(patch)
            session.flush()
            validations = self._validate(session, patch, manuscript)
            patch.validations_json = validations
            session.add(
                AuditEvent(
                    id=str(uuid4()), case_id=research_case.id, event_type="patch_generated",
                    object_type="PatchProposal", object_id=patch.id,
                    payload_json={"validations": validations}, actor_type="model",
                    actor_id=getattr(
                        self.llm_client,
                        "model_name",
                        self.settings.llm_model or "deterministic-fixture",
                    ),
                )
            )
            session.flush()
            session.expunge(patch)
            return patch

    def _generate_model_template(
        self,
        *,
        session: Session,
        research_case: ResearchCase,
        manuscript: ManuscriptVersion,
        claim: Claim,
        revision: ClaimRevision,
        impact: ImpactCandidate,
        source: Source,
        snapshot: SourceSnapshot,
    ) -> dict:
        instructions = PROMPT_PATH.read_text(encoding="utf-8").strip()
        payload = {
            "project": {
                "title": research_case.title,
                "research_question": research_case.research_question,
            },
            # Background context only; before_text exactness is validated
            # against the untruncated manuscript stored in the database.
            "full_manuscript": truncate_for_prompt(
                manuscript.content_text,
                purpose="full manuscript background",
            ),
            "confirmed_claim": {
                "stable_key": claim.stable_key,
                "statement": revision.statement,
                "source_quote": revision.source_quote,
                "source_locator": revision.source_locator,
                "locked_numbers": _numbers(revision.source_quote),
            },
            "confirmed_impact": {
                "stance": impact.stance,
                "impact_mode": impact.impact_mode,
                "comparability": impact.comparability,
                "condition_differences": impact.condition_differences_json,
                "suggested_action": impact.suggested_action,
                "uncertainty": impact.uncertainty_json,
                "own_evidence": impact.evidence_own_json,
                "incoming_evidence": impact.evidence_new_json,
            },
            "action_policy": self.action_policy(impact.impact_mode),
            "citation": {
                "source_id": source.id,
                "title": source.title,
                "authors": source.authors_json,
                "url": source.url,
                "doi": source.doi,
                "venue": source.venue,
                "published_at": (
                    source.published_at.date().isoformat()
                    if source.published_at
                    else None
                ),
            },
            "incoming_paper_abstract": snapshot.abstract,
        }
        prompt = (
            f"{instructions}\n\nINPUT JSON — FULL MANUSCRIPT INCLUDED:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        started = time.perf_counter()
        output = None
        validation_issues: list[str] = []
        active_prompt = prompt
        for attempt in range(2):
            output = self.llm_client.generate_structured(
                stage="patch_generation",
                prompt=active_prompt,
                response_model=PatchProposalOutput,
            )
            output = self._exactify_model_output(output, manuscript.content_text)
            validation_issues = self._model_output_issues(
                output=output,
                manuscript=manuscript,
                revision=revision,
                impact=impact,
            )
            if not validation_issues:
                break
            if attempt == 0:
                active_prompt = (
                    f"{prompt}\n\nYOUR PREVIOUS OUTPUT WAS BLOCKED BY PROGRAMMATIC CHECKS: "
                    f"{', '.join(validation_issues)}. Generate a corrected proposal."
                )
        if output is None or validation_issues:
            raise ValueError(
                "patch_generation_validation_failed:" + ",".join(validation_issues)
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        receipt = getattr(self.llm_client, "last_receipt", {}) or {}
        usage = receipt.get("usage") or {}
        raw_response = receipt.get("raw_response") or output.model_dump_json()
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        model_name = getattr(
            self.llm_client,
            "model_name",
            self.settings.llm_model or "injected-test-model",
        )
        session.add(
            ModelRun(
                id=str(uuid4()),
                stage="patch_generation",
                case_id=research_case.id,
                scan_run_id=impact.scan_run_id,
                provider=getattr(
                    self.llm_client,
                    "provider_name",
                    self.settings.llm_provider or self.llm_client.__class__.__name__,
                ),
                model=model_name,
                prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
                schema_version="PatchProposalOutput.v1",
                input_refs_json=[manuscript.id, impact.id, snapshot.id],
                raw_response=raw_response,
                parsed_output_json=output.model_dump(),
                validation_json={
                    "pydantic": True,
                    "before_text_exact": True,
                    "citation_locked_to_supplied_source": True,
                    "action_target_policy": True,
                    "citation_marker_safe": True,
                },
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimate_llm_cost_usd(
                    model_name, input_tokens, output_tokens
                ),
                latency_ms=int(receipt.get("latency_ms", latency_ms)),
            )
        )
        return {
            "edit_class": output.edit_class,
            "target_locator": output.target_locator,
            "before_text": output.before_text,
            "after_text": output.after_text,
            "citation_source_ids": [source.id],
        }

    @staticmethod
    def _exactify_model_output(
        output: PatchProposalOutput, manuscript_text: str
    ) -> PatchProposalOutput:
        if output.before_text in manuscript_text:
            return output
        resolved = resolve_exact_quote(output.before_text, manuscript_text)
        if resolved is None:
            return output
        exact_before, _, _ = resolved
        if output.before_text not in output.after_text:
            return output
        exact_after = output.after_text.replace(output.before_text, exact_before, 1)
        return output.model_copy(
            update={"before_text": exact_before, "after_text": exact_after}
        )

    @staticmethod
    def action_policy(impact_mode: str) -> dict[str, str]:
        return PATCH_POLICIES.get(
            impact_mode,
            {
                "target": "Discussion / project action list",
                "change": "只做证据支持的最小修改。",
            },
        )

    @staticmethod
    def _nearest_section(text: str, offset: int) -> str | None:
        headings = re.compile(
            r"(?:^|\n)\s*(?:\d+(?:\.\d+)?)?\s*"
            r"(Introduction|Related Work|Discussion|Limitations?|Conclusion)\s*(?:\n|$)",
            re.IGNORECASE,
        )
        matches = [match for match in headings.finditer(text, 0, max(offset, 0) + 1)]
        return matches[-1].group(1).lower() if matches else None

    def _model_output_issues(
        self,
        *,
        output: PatchProposalOutput,
        manuscript: ManuscriptVersion,
        revision: ClaimRevision,
        impact: ImpactCandidate,
    ) -> list[str]:
        issues: list[str] = []
        offset = manuscript.content_text.find(output.before_text)
        if offset < 0:
            issues.append("before_text_not_exact")
            return issues
        new_numeric_citations = set(re.findall(r"\[(?:\d+[\s,\-]*)+\]", output.after_text)) - set(
            re.findall(r"\[(?:\d+[\s,\-]*)+\]", output.before_text)
        )
        if new_numeric_citations:
            issues.append("invented_numeric_citation")
        if impact.impact_mode == "prior_art":
            section = self._nearest_section(manuscript.content_text, offset)
            if section not in {"introduction", "related work", "discussion"}:
                issues.append("prior_art_target_not_positioning_section")
            if output.before_text.strip() == revision.source_quote.strip():
                issues.append("prior_art_targeted_empirical_claim")
            if "[CITATION]" not in output.after_text:
                issues.append("citation_placeholder_missing")
        return issues

    def _find_template(self, research_case: ResearchCase, impact_id: str) -> dict | None:
        fixture_dir = research_case.settings_json.get("fixture_dir")
        if not fixture_dir:
            return None
        path = Path(fixture_dir) / "expected_patches.json"
        if not path.exists():
            return None
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item["impact_candidate_id"] == impact_id:
                return item
        return None

    def _validate(
        self, session: Session, patch: PatchProposal, manuscript: ManuscriptVersion
    ) -> dict[str, bool]:
        citations_resolved = all(session.get(Source, source_id) is not None for source_id in patch.citations_json)
        before_exact = patch.before_text in manuscript.content_text
        before_numbers = _numbers(patch.before_text)
        after_numbers = _numbers(patch.after_text)
        locked_numbers_unchanged = all(after_numbers.count(number) >= count for number, count in {
            number: before_numbers.count(number) for number in before_numbers
        }.items())
        new_numeric_citations = set(re.findall(r"\[(?:\d+[\s,\-]*)+\]", patch.after_text)) - set(
            re.findall(r"\[(?:\d+[\s,\-]*)+\]", patch.before_text)
        )
        return {
            "impact_confirmed": True,
            "before_text_exact": before_exact,
            "citations_resolved": citations_resolved,
            "citation_marker_safe": not new_numeric_citations,
            "locked_numbers_unchanged": locked_numbers_unchanged,
            "original_file_untouched": True,
        }

    def validate_patch(self, patch_id: str) -> dict[str, bool]:
        with session_scope(self.session_factory) as session:
            patch = session.get(PatchProposal, patch_id)
            if patch is None:
                raise LookupError(f"patch not found: {patch_id}")
            manuscript = session.get(ManuscriptVersion, patch.manuscript_version_id)
            validations = self._validate(session, patch, manuscript)
            patch.validations_json = validations
            return validations

    def approve_patch(self, patch_id: str) -> PatchProposal:
        return self._set_approval(patch_id, "approved")

    def reject_patch(self, patch_id: str) -> PatchProposal:
        return self._set_approval(patch_id, "rejected")

    def _set_approval(self, patch_id: str, state: str) -> PatchProposal:
        with session_scope(self.session_factory) as session:
            patch = session.get(PatchProposal, patch_id)
            if patch is None:
                raise LookupError(f"patch not found: {patch_id}")
            if state == "approved" and not all(patch.validations_json.values()):
                raise ValueError("patch_validation_failed")
            patch.approval_state = state
            session.add(
                AuditEvent(
                    id=str(uuid4()), case_id=patch.case_id, event_type=f"patch_{state}",
                    object_type="PatchProposal", object_id=patch.id,
                    payload_json={"export_only": True}, actor_type="human", actor_id="local_user",
                )
            )
            session.flush()
            session.expunge(patch)
            return patch

    @staticmethod
    def export_markdown(patch: PatchProposal) -> str:
        return (
            f"# Research Radar Patch Proposal\n\n"
            f"- State: {patch.approval_state}\n- Edit class: {patch.edit_class}\n"
            f"- Target: {patch.target_locator}\n- Citations: {', '.join(patch.citations_json)}\n\n"
            f"## Before\n\n{patch.before_text}\n\n## After\n\n{patch.after_text}\n"
        )
