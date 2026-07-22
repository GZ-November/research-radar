"""Impact policy functions and integrity propagation; outputs remain candidates."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from radar.db import SessionLocal, session_scope
from radar.models import Claim, ClaimRevision, ClaimSourceLink, ImpactCandidate, ScanRun, Source, SourceSnapshot
from radar.schemas import ConditionDifference


class ImpactService:
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal):
        self.session_factory = session_factory

    @staticmethod
    def enforce_stance(stance: str, comparability: str) -> str:
        if (
            stance in {"supports", "challenges"}
            and comparability != "compatible"
        ):
            return "uncertain"
        return stance

    @staticmethod
    def severity(
        *, centrality: str, stance: str, comparability: str,
        impact_mode: str, change_depth: int, strategic_flags: list[str],
    ) -> str:
        if impact_mode == "research_integrity" and change_depth >= 3:
            return "critical"
        if centrality == "core" and stance == "challenges" and comparability == "compatible":
            return "critical"
        if stance == "challenges" and comparability == "partial":
            return "review"
        if "competitor" in strategic_flags or change_depth >= 2:
            return "review"
        return "informative"

    @staticmethod
    def hard_mismatch(differences: list[ConditionDifference]) -> bool:
        return any(
            item.field in {"task", "dataset", "metric", "comparator"}
            and item.status == "mismatch"
            for item in differences
        )

    def propagate_retraction(
        self, source_id: str, *, scan_run_id: str | None = None
    ) -> list[str]:
        """Create candidate integrity impacts for confirmed claim-source links."""
        with session_scope(self.session_factory) as session:
            source = session.get(Source, source_id)
            if source is None or source.integrity_state not in {
                "retracted",
                "expression_of_concern",
            }:
                return []
            snapshot = session.scalar(
                select(SourceSnapshot).where(SourceSnapshot.source_id == source_id)
                .order_by(SourceSnapshot.created_at.desc())
            )
            if snapshot is None:
                return []
            links = list(
                session.scalars(
                    select(ClaimSourceLink).where(
                        ClaimSourceLink.source_id == source_id,
                        ClaimSourceLink.review_state == "confirmed",
                    )
                )
            )
            impact_ids: list[str] = []
            for link in links:
                existing = session.scalar(
                    select(ImpactCandidate).where(
                        ImpactCandidate.claim_revision_id == link.claim_revision_id,
                        ImpactCandidate.source_snapshot_id == snapshot.id,
                        ImpactCandidate.event_type == "retraction",
                    )
                )
                if existing:
                    impact_ids.append(existing.id)
                    continue
                revision = session.get(ClaimRevision, link.claim_revision_id)
                claim = session.get(Claim, revision.claim_id)
                scan = (
                    session.get(ScanRun, scan_run_id)
                    if scan_run_id
                    else session.scalar(
                        select(ScanRun).where(ScanRun.case_id == claim.case_id)
                        .order_by(ScanRun.created_at.desc())
                    )
                )
                if scan is None:
                    # ImpactCandidate.scan_run_id is required; with no ScanRun
                    # for the case there is nothing to attach the alert to, so
                    # skip this link instead of crashing on scan.id.
                    continue
                impact = ImpactCandidate(
                    id=str(uuid4()), scan_run_id=scan.id, claim_revision_id=revision.id,
                    source_snapshot_id=snapshot.id, event_type="retraction", stance="uncertain",
                    impact_mode="research_integrity", strategic_flags_json=[],
                    comparability="unknown", condition_differences_json=[],
                    evidence_own_json={"quote": revision.source_quote, "locator": revision.source_locator},
                    evidence_new_json={
                        "quote": snapshot.content_text, "locator": "integrity_notice:full",
                        "source_snapshot_id": snapshot.id,
                    },
                    change_depth=4, severity="critical", suggested_action="revalidate",
                    uncertainty_json=["Downstream magnitude has not been measured."],
                    review_state="candidate", trust_state="verified",
                )
                session.add(impact)
                session.flush()
                impact_ids.append(impact.id)
            return impact_ids
