from sqlalchemy import select

from radar.models import ActionItem
from radar.services.action_service import ActionService
from radar.services.report_service import ReportService
from radar.services.review_service import ReviewService


def test_golden_impacts_generate_all_project_action_types(
    db_session_factory, golden_case
):
    service = ActionService(db_session_factory)
    actions = service.list_actions(golden_case)
    action_types = {item.action_type for item in actions}

    assert {
        "team_decision",
        "experiment",
        "data",
        "writing",
        "competitor_response",
        "revalidation",
    } <= action_types
    assert any(
        item.action_type == "team_decision"
        and item.priority == "critical"
        and item.status == "open"
        for item in actions
    )
    assert any(
        item.action_type == "competitor_response" and item.due_label == "72_hours"
        for item in actions
    )
    assert any(
        item.action_type == "revalidation" and item.status == "open"
        for item in actions
    )


def test_candidate_impacts_create_automatic_attention_states(
    db_session_factory, golden_case
):
    service = ActionService(db_session_factory)

    assert service.claim_attention_state("claim-01") == "disputed"
    assert service.claim_attention_state("claim-03") == "competitor_pressure"
    assert service.claim_attention_state("claim-09") == "revalidation_required"
    assert service.claim_attention_state("claim-10") == "stable"


def test_action_lifecycle_and_impact_dismissal_are_synchronized(
    db_session_factory, golden_case
):
    service = ActionService(db_session_factory)
    competitor = next(
        item
        for item in service.list_actions(golden_case)
        if item.action_type == "competitor_response"
    )
    service.update_status(competitor.id, "in_progress")
    with db_session_factory() as session:
        assert session.get(ActionItem, competitor.id).status == "in_progress"

    ReviewService(db_session_factory).dismiss_impact("impact-03")
    with db_session_factory() as session:
        statuses = set(
            session.scalars(
                select(ActionItem.status).where(
                    ActionItem.impact_candidate_id == "impact-03"
                )
            )
        )
    assert statuses == {"dismissed"}


def test_weekly_action_report_and_writing_brief(
    db_session_factory, golden_case
):
    report_service = ReportService(db_session_factory)
    report = report_service.get_weekly_action_report("scan-demo-week-29")
    brief = report_service.get_writing_brief(golden_case)
    markdown = report_service.export_writing_brief(golden_case)

    assert report["urgent"] >= 3
    assert report["counts_by_type"]["experiment"] >= 1
    assert report["counts_by_type"]["competitor_response"] == 1
    assert report["counts_by_type"]["revalidation"] == 1
    assert len(brief["supports"]) == 2
    assert len(brief["challenges"]) == 2
    assert len(brief["integrity"]) == 1
    assert "# Research Radar — Discussion Evidence Brief" in markdown
    assert "## Counter-evidence" in markdown
    assert "- Venue:" in markdown
    assert "- Original:" in markdown
    assert "- PDF:" in markdown
    assert "- DOI:" in markdown
