"""Explicit, bounded workflow orchestrator—no autonomous agent loop."""

from pathlib import Path

from radar.db import init_database
from radar.services.case_service import CaseService
from radar.services.patch_service import PatchService
from radar.services.retrieval_service import RetrievalService
from radar.services.review_service import ReviewService
from radar.services.weekly_radar_service import WeeklyRadarService


class ResearchRadarOrchestrator:
    """Coordinate explicit user-triggered stages and their human gates."""

    def bootstrap(self) -> None:
        init_database()

    def explore_demo(self, *, reset: bool = False) -> str:
        case_id = CaseService().load_demo_case(reset=reset)
        RetrievalService().rebuild_fts()
        return case_id

    def create_case(self, title: str, research_question: str, manuscript_path: Path) -> str:
        return CaseService().create_case(
            title=title, research_question=research_question, manuscript_path=manuscript_path
        )

    def review_impact(self, impact_id: str, decision: str, payload: dict | None = None):
        review = ReviewService()
        if decision == "confirm":
            return review.confirm_impact(impact_id)
        if decision == "edit":
            return review.edit_impact(impact_id, payload or {})
        if decision == "dismiss":
            return review.dismiss_impact(impact_id)
        raise ValueError(f"unsupported decision: {decision}")

    def generate_patch(self, impact_id: str):
        return PatchService().generate_patch(impact_id)

    def run_weekly_radar(
        self, case_id: str, *, query: str, max_results: int = 20, analysis_limit: int = 7
    ) -> str:
        return WeeklyRadarService().run(
            case_id,
            query=query,
            max_results=max_results,
            analysis_limit=analysis_limit,
        )
