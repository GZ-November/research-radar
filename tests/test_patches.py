import hashlib

import pytest
from sqlalchemy import select

from radar.models import Claim, ClaimRevision, ImpactCandidate, ManuscriptVersion, ModelRun, ResearchCase
from radar.schemas import PatchProposalOutput
from radar.services.patch_service import PatchService
from radar.services.review_service import ReviewService


def test_candidate_cannot_generate_patch(db_session_factory, golden_case):
    with pytest.raises(ValueError, match="candidate_cannot_generate_patch"):
        PatchService(db_session_factory).generate_patch("impact-01")


def test_confirmed_impact_generates_valid_export_only_patch(db_session_factory, golden_case):
    with db_session_factory() as session:
        manuscript = session.scalar(select(ManuscriptVersion))
        original_hash = hashlib.sha256(manuscript.content_text.encode()).hexdigest()
    ReviewService(db_session_factory).confirm_impact("impact-01")
    patch = PatchService(db_session_factory).generate_patch("impact-01")
    assert all(patch.validations_json.values())
    assert "61.2%" in patch.after_text and "68.7%" in patch.after_text
    approved = PatchService(db_session_factory).approve_patch(patch.id)
    assert approved.approval_state == "approved"
    with db_session_factory() as session:
        manuscript = session.scalar(select(ManuscriptVersion))
        assert hashlib.sha256(manuscript.content_text.encode()).hexdigest() == original_hash


class ScriptedPatchLLM:
    def __init__(self, before_text):
        self.before_text = before_text
        self.stages = []
        self.last_receipt = {
            "raw_response": "{}",
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
            "latency_ms": 12,
        }

    def generate_structured(self, *, stage, prompt, response_model):
        self.stages.append(stage)
        return PatchProposalOutput(
            edit_class="add_boundary_discussion",
            target_locator="sec:main-results:p:1",
            before_text=self.before_text,
            after_text=(
                self.before_text
                + " This finding should be interpreted within the matched evaluation conditions."
            ),
            citation_source_ids=[],
            assertions_added=["The interpretation is bounded by matched conditions."],
            assertions_weakened_or_removed=[],
            rationale="Adds the smallest evidence-grounded boundary statement.",
        )


class PriorArtPatchLLM:
    def __init__(self, result_sentence, related_work_sentence):
        self.result_sentence = result_sentence
        self.related_work_sentence = related_work_sentence
        self.calls = 0
        self.last_receipt = {
            "raw_response": "{}",
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
            "latency_ms": 12,
        }

    def generate_structured(self, *, stage, prompt, response_model):
        self.calls += 1
        if self.calls == 1:
            return PatchProposalOutput(
                edit_class="add_citation",
                target_locator="results",
                before_text=self.result_sentence,
                after_text=self.result_sentence + " [28].",
                citation_source_ids=[],
                assertions_added=[],
                assertions_weakened_or_removed=[],
                rationale="Bad first attempt.",
            )
        return PatchProposalOutput(
            edit_class="add_citation",
            target_locator="Related Work",
            before_text=self.related_work_sentence,
            after_text=(
                self.related_work_sentence
                + " A recent taxonomy positions this design within agentic RAG [CITATION]."
            ),
            citation_source_ids=[],
            assertions_added=["The design is positioned within agentic RAG."],
            assertions_weakened_or_removed=[],
            rationale="Adds the citation in the positioning section.",
        )


def test_uploaded_project_uses_structured_llm_patch_generation(
    db_session_factory, golden_case
):
    ReviewService(db_session_factory).confirm_impact("impact-01")
    with db_session_factory() as session:
        impact = session.get(ImpactCandidate, "impact-01")
        revision = session.get(ClaimRevision, impact.claim_revision_id)
        claim = session.get(Claim, revision.claim_id)
        research_case = session.get(ResearchCase, claim.case_id)
        research_case.settings_json = {}
        before_text = revision.source_quote
        session.commit()

    llm = ScriptedPatchLLM(before_text)
    patch = PatchService(
        db_session_factory,
        llm_client=llm,
    ).generate_patch("impact-01")

    assert llm.stages == ["patch_generation"]
    assert patch.edit_class == "add_boundary_discussion"
    assert all(patch.validations_json.values())
    with db_session_factory() as session:
        run = session.scalar(
            select(ModelRun).where(ModelRun.stage == "patch_generation")
        )
        assert run is not None
        assert run.input_tokens == 100


def test_prior_art_patch_retries_wrong_section_and_numeric_citation(
    db_session_factory, golden_case
):
    with db_session_factory() as session:
        impact = session.get(ImpactCandidate, "impact-03")
        impact.review_state = "edited"
        impact.comparability = "unknown"
        revision = session.get(ClaimRevision, impact.claim_revision_id)
        manuscript = session.get(ManuscriptVersion, revision.manuscript_version_id)
        claim = session.get(Claim, revision.claim_id)
        research_case = session.get(ResearchCase, claim.case_id)
        research_case.settings_json = {}
        result_sentence = revision.source_quote
        related_work_sentence = "Retrieval systems increasingly use hierarchical routing."
        exact_related_work_sentence = "Retrieval systems increasingly use hierar-\nchical routing."
        manuscript.content_text = (
            f"Abstract\n{result_sentence}\n\n1 Introduction\nBackground.\n\n"
            f"2 Related Work\n{exact_related_work_sentence}\n"
        )
        session.commit()

    llm = PriorArtPatchLLM(result_sentence, related_work_sentence)
    patch = PatchService(db_session_factory, llm_client=llm).generate_patch("impact-03")

    assert llm.calls == 2
    assert patch.target_locator == "Related Work"
    assert "hierar-\nchical" in patch.before_text
    assert "[CITATION]" in patch.after_text
    assert patch.validations_json["citation_marker_safe"] is True
