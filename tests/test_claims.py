from pathlib import Path

import pytest
from sqlalchemy import select

from radar.models import ClaimRevision, ManuscriptVersion, ResearchCase
from radar.parsers.latex import LatexParser
from radar.parsers.markdown import MarkdownParser
from radar.services.case_service import CaseService
from radar.services.claim_service import ClaimService, _rank_candidate_spans
from radar.services.trust_service import TrustService


def test_golden_source_quotes_are_exact(db_session_factory, golden_case):
    with db_session_factory() as session:
        manuscript = session.scalar(
            select(ManuscriptVersion).where(ManuscriptVersion.case_id == golden_case)
        )
        revisions = list(session.scalars(select(ClaimRevision)))
    assert len(revisions) == 10
    assert all(revision.source_quote in manuscript.content_text for revision in revisions)


def test_source_quote_failure_blocks_candidate():
    result = TrustService().verify_claim_quote("invented result", "supplied manuscript")
    assert result.state == "blocked"
    assert result.errors == ["span_failed"]


def test_uploaded_markdown_requires_confirmation(db_session_factory, tmp_path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Results\n\nOur method improves exact match by 7.0 points over BM25.\n\n"
        "We study retrieval-augmented question answering in open research settings. "
        "The project context and setup are described before the measurements.",
        encoding="utf-8",
    )
    case_id = CaseService(db_session_factory).create_case(
        title="Upload test", research_question="Does it improve?", manuscript_path=manuscript
    )
    with db_session_factory() as session:
        candidate = session.scalar(
            select(ClaimRevision).join(ManuscriptVersion).where(ManuscriptVersion.case_id == case_id)
        )
    assert candidate.review_state == "candidate"
    ClaimService(db_session_factory).confirm_candidate(candidate.id)
    with db_session_factory() as session:
        assert session.get(ClaimRevision, candidate.id).review_state == "confirmed"


def test_multiline_pdf_style_result_is_not_reduced_to_a_fragment(db_session_factory, tmp_path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Results\n\nOur evaluation reveals that the model consistently\n"
        "outperforms BM25 by 7.0 exact-match points across three domains.\n\n"
        "We study retrieval-augmented question answering in open research settings. "
        "The project context and setup are described before the measurements.\n",
        encoding="utf-8",
    )
    case_id = CaseService(db_session_factory).create_case(
        title="Multiline test", research_question="Does the model outperform BM25?",
        manuscript_path=manuscript,
    )
    with db_session_factory() as session:
        candidate = session.scalar(
            select(ClaimRevision).join(ManuscriptVersion).where(ManuscriptVersion.case_id == case_id)
        )
        stored = session.scalar(
            select(ManuscriptVersion).where(ManuscriptVersion.case_id == case_id)
        )
    assert "outperforms BM25" in candidate.statement
    assert "\n" in candidate.source_quote
    assert candidate.source_quote in stored.content_text


def test_tex_and_markdown_parsers_have_stable_locators(golden_dir, tmp_path):
    latex = LatexParser().parse(golden_dir / "own_paper.tex")
    markdown_path = tmp_path / "notes.md"
    markdown_path.write_text("# Results\n\nA result improves by 2 points.", encoding="utf-8")
    markdown = MarkdownParser().parse(markdown_path)
    assert latex.sections[0].locator.startswith("sec:")
    assert markdown.paragraphs[0].locator == "sec:results:p:1"
    assert len(latex.content_hash) == 64


def test_pdf_section_heading_does_not_leak_into_empirical_claim():
    content = (
        "Experiments across RemPlan and three benchmarks demonstrate a 13% accuracy gain "
        "while reducing redundant searches by 37%.\n"
        "1 Introduction\n"
        "Visual question answering systems often require external knowledge.\n"
        "E-Agent Response: This waterfall reaches a height of 979 meters. "
        "User: Is this food suitable?"
    )
    quotes = [item[2] for item in _rank_candidate_spans(content)]
    assert quotes[0].endswith("37%.")
    assert "Introduction" not in quotes[0]
    assert all("E-Agent Response:" not in quote for quote in quotes)


def test_manuscript_without_text_layer_is_rejected_upfront(db_session_factory, tmp_path):
    manuscript = tmp_path / "scanned.md"
    manuscript.write_text("# Scanned\n\n  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="扫描件或缺少文本层"):
        CaseService(db_session_factory).create_case(
            title="Scanned upload",
            research_question="Is there a text layer?",
            manuscript_path=manuscript,
        )
    with db_session_factory() as session:
        assert session.scalar(select(ResearchCase)) is None
