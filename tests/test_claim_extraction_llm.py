"""LLM-backed claim extraction and fuzzy version carry-over."""

import hashlib
from uuid import uuid4

from sqlalchemy import select

from radar.models import Claim, ClaimRevision, ManuscriptVersion, ModelRun, ResearchCase
from radar.services.case_service import CaseService
from radar.services.claim_service import (
    DEFAULT_FALSIFIABLE_CONDITION,
    ClaimService,
)


class StubLLM:
    """Structured stub implementing the LLMClient protocol for claim tests."""

    provider_name = "stub"
    model_name = "stub-v1"

    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    def generate_structured(self, *, stage, prompt, response_model):
        if self.error is not None:
            raise self.error
        return response_model.model_validate(self.response)


def _make_manuscript(db_session_factory, content: str) -> str:
    case_id = str(uuid4())
    manuscript_id = str(uuid4())
    with db_session_factory() as session:
        session.add(
            ResearchCase(
                id=case_id,
                title="LLM extraction test",
                research_question="Does it improve?",
                field="cs_ai",
                settings_json={},
            )
        )
        session.flush()
        session.add(
            ManuscriptVersion(
                id=manuscript_id,
                case_id=case_id,
                version_no=1,
                file_name="paper.md",
                source_type="md",
                content_text=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                is_current=True,
            )
        )
        session.commit()
    return manuscript_id


def _extraction_run(db_session_factory):
    with db_session_factory() as session:
        return session.scalar(
            select(ModelRun)
            .where(ModelRun.stage == "claim_extraction")
            .order_by(ModelRun.created_at.desc())
        )


def test_llm_extraction_fills_contract_and_falsifiable_condition(db_session_factory):
    quote = (
        "RadarNet improves exact match by 7.0 points over BM25 on the "
        "DomainQA unseen-domain split."
    )
    content = (
        f"# Results\n\n{quote}\n\n"
        "We study retrieval-augmented question answering in open research settings."
    )
    manuscript_id = _make_manuscript(db_session_factory, content)
    llm = StubLLM(
        {
            "candidates": [
                {
                    "statement": "RadarNet improves exact match over BM25 on DomainQA.",
                    "centrality_suggestion": "core",
                    "contract": {
                        "task": "retrieval-augmented question answering",
                        "dataset": "DomainQA",
                        "split": "unseen-domain",
                        "metric": "exact match",
                        "comparator": "BM25",
                        "scope": None,
                    },
                    "falsifiable_condition": (
                        "A rerun on DomainQA shows no exact-match gain over BM25."
                    ),
                    "source_quote": quote,
                    "source_locator": "auto",
                }
            ]
        }
    )

    candidates = ClaimService(
        db_session_factory, llm_client=llm
    ).extract_candidates(manuscript_id)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.contract_json["dataset"] == "DomainQA"
    assert candidate.contract_json["metric"] == "exact match"
    assert candidate.falsifiable_condition == (
        "A rerun on DomainQA shows no exact-match gain over BM25."
    )
    assert candidate.centrality == "core"
    assert candidate.source_quote == quote
    assert candidate.source_quote in content
    start = content.index(quote)
    assert candidate.source_locator == f"offset:{start}-{start + len(quote)}"

    run = _extraction_run(db_session_factory)
    assert run.provider == "stub"
    assert run.model == "stub-v1"
    assert run.validation_json["path"] == "llm"
    assert run.validation_json["anchors_resolved"] == 1
    assert run.validation_json["anchors_dropped"] == []


def test_llm_failure_falls_back_to_heuristic(db_session_factory):
    content = (
        "# Results\n\nOur method improves exact match by 7.0 points over BM25.\n\n"
        "We study retrieval-augmented question answering in open research settings. "
        "The project context and setup are described before the measurements."
    )
    manuscript_id = _make_manuscript(db_session_factory, content)
    llm = StubLLM(error=RuntimeError("provider unreachable"))

    candidates = ClaimService(
        db_session_factory, llm_client=llm
    ).extract_candidates(manuscript_id)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert not any(candidate.contract_json.values())
    assert candidate.falsifiable_condition == DEFAULT_FALSIFIABLE_CONDITION

    run = _extraction_run(db_session_factory)
    assert run.provider == "deterministic_fallback"
    assert run.validation_json["path"] == "heuristic"
    assert "provider unreachable" in run.validation_json["llm_error"]


def test_llm_candidate_with_unlocatable_anchor_is_dropped(db_session_factory):
    quote = "RadarNet improves exact match by 7.0 points over BM25 on DomainQA."
    content = f"# Results\n\n{quote}\n\nSome closing discussion of the setup."
    manuscript_id = _make_manuscript(db_session_factory, content)
    llm = StubLLM(
        {
            "candidates": [
                {
                    "statement": "RadarNet improves exact match over BM25 on DomainQA.",
                    "centrality_suggestion": "major",
                    "contract": {"dataset": "DomainQA"},
                    "falsifiable_condition": "The gain does not reproduce.",
                    "source_quote": quote,
                    "source_locator": "auto",
                },
                {
                    "statement": "RadarNet doubles throughput on every benchmark.",
                    "centrality_suggestion": "minor",
                    "contract": {},
                    "falsifiable_condition": "Throughput stays flat.",
                    "source_quote": "This sentence was never written in the manuscript.",
                    "source_locator": "auto",
                },
            ]
        }
    )

    candidates = ClaimService(
        db_session_factory, llm_client=llm
    ).extract_candidates(manuscript_id)

    assert [candidate.statement for candidate in candidates] == [
        "RadarNet improves exact match over BM25 on DomainQA."
    ]
    run = _extraction_run(db_session_factory)
    assert run.validation_json["anchors_resolved"] == 1
    assert run.validation_json["anchors_dropped"] == [
        "RadarNet doubles throughput on every benchmark."
    ]


STABLE_CLAIM = (
    "Our evaluation reveals that RadarNet improves exact match by 7.0 points "
    "over BM25 on the DomainQA unseen-domain split."
)


def _versioned_case(db_session_factory, tmp_path, first_text: str):
    first = tmp_path / "paper-v1.md"
    first.write_text(first_text, encoding="utf-8")
    service = CaseService(db_session_factory)
    case_id = service.create_case(
        title="Versioned project",
        research_question="Does RadarNet improve unseen-domain retrieval?",
        manuscript_path=first,
    )
    with db_session_factory() as session:
        initial = session.scalar(
            select(ClaimRevision)
            .join(Claim, Claim.id == ClaimRevision.claim_id)
            .where(Claim.case_id == case_id)
        )
    ClaimService(db_session_factory).confirm_candidate(initial.id)
    return service, case_id


def test_reworded_claim_is_carried_by_fuzzy_match(db_session_factory, tmp_path):
    service, case_id = _versioned_case(
        db_session_factory,
        tmp_path,
        f"# Results\n\n{STABLE_CLAIM}\n\n"
        "We study retrieval-augmented question answering in open research settings. "
        "The project context and setup are described before the measurements.",
    )
    reworded = (
        "Our evaluation reveals that RadarNet improves exact-match scores by 7.0 "
        "points over the BM25 baseline on the DomainQA unseen-domain split."
    )
    second = tmp_path / "paper-v2.md"
    second.write_text(f"# Results\n\n{reworded}\n", encoding="utf-8")

    result = service.add_manuscript_version(case_id, second)

    assert result["carried_claims"] == 1
    assert result["previous_claims_not_found"] == 0
    assert result["lost_claims"] == []
    with db_session_factory() as session:
        carried = session.scalar(
            select(ClaimRevision)
            .join(Claim, Claim.id == ClaimRevision.claim_id)
            .where(Claim.case_id == case_id, ClaimRevision.supersedes_id.is_not(None))
        )
    assert carried.review_state == "confirmed"
    assert carried.source_quote in second.read_text(encoding="utf-8")
    assert "exact-match scores" in carried.source_quote


def test_rewritten_claim_is_listed_as_lost(db_session_factory, tmp_path):
    service, case_id = _versioned_case(
        db_session_factory,
        tmp_path,
        f"# Results\n\n{STABLE_CLAIM}\n\n"
        "We study retrieval-augmented question answering in open research settings. "
        "The project context and setup are described before the measurements.",
    )
    replacement = (
        "Our ablation analysis shows that removing retrieval calibration reduces "
        "exact match by 4.0 points on DomainQA."
    )
    second = tmp_path / "paper-v2.md"
    second.write_text(f"# Results\n\n{replacement}\n", encoding="utf-8")

    result = service.add_manuscript_version(case_id, second)

    assert result["carried_claims"] == 0
    assert result["previous_claims_not_found"] == 1
    assert len(result["lost_claims"]) == 1
    lost = result["lost_claims"][0]
    assert lost["stable_key"] == "C1"
    assert "7.0 points" in lost["statement"]
