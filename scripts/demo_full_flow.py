"""Full end-to-end demo: wipe the previous demo case, then run the whole
pipeline fresh — create case, LLM claim extraction (full-context budget),
confirm top claims, weekly scan, print impacts and LLM action advice.

Run: PYTHONPATH=. .venv/bin/python scripts/demo_full_flow.py
"""

from pathlib import Path

from radar.db import session_scope
from radar.models import (
    ActionItem, AuditEvent, Claim, ClaimRevision, ClaimSourceLink, ClaimSurface,
    ImpactCandidate, ManuscriptVersion, ModelRun, PatchProposal, ResearchCase,
    ReviewDecision, ScanRun,
)
from radar.services.case_service import CaseService
from radar.services.claim_service import ClaimService
from radar.services.weekly_radar_service import WeeklyRadarService

PDF = Path("data/uploads/42d75fe2-d427-4186-989d-c8f3bbccbaa4/Efficient_Agent_2508.08816.pdf")
QUESTION = (
    "Does single-pass planning with dynamic tool orchestration improve accuracy "
    "of multimodal RAG while reducing redundant retrieval?"
)
OLD_CASE_ID = "29638b62-4055-4495-8e11-3fcc2c3341a1"

# --- wipe previous demo case (FK-safe order) -------------------------------
with session_scope() as s:
    rev_ids = [r.id for r in s.query(ClaimRevision).join(Claim).filter(Claim.case_id == OLD_CASE_ID)]
    claim_ids = [c.id for c in s.query(Claim).filter_by(case_id=OLD_CASE_ID)]
    impact_ids = [i.id for i in s.query(ImpactCandidate).filter(ImpactCandidate.claim_revision_id.in_(rev_ids))] if rev_ids else []
    s.query(ReviewDecision).filter(ReviewDecision.impact_candidate_id.in_(impact_ids or ["-"])).delete(synchronize_session=False)
    s.query(PatchProposal).filter(PatchProposal.impact_candidate_id.in_(impact_ids or ["-"])).delete(synchronize_session=False)
    if rev_ids:
        s.query(ActionItem).filter(ActionItem.claim_revision_id.in_(rev_ids)).delete(synchronize_session=False)
        s.query(ImpactCandidate).filter(ImpactCandidate.claim_revision_id.in_(rev_ids)).delete(synchronize_session=False)
        s.query(ClaimSourceLink).filter(ClaimSourceLink.claim_revision_id.in_(rev_ids)).delete(synchronize_session=False)
        s.query(ClaimSurface).filter(ClaimSurface.claim_revision_id.in_(rev_ids)).delete(synchronize_session=False)
    s.query(ActionItem).filter_by(case_id=OLD_CASE_ID).delete(synchronize_session=False)
    s.query(ModelRun).filter_by(case_id=OLD_CASE_ID).delete(synchronize_session=False)
    s.query(ScanRun).filter_by(case_id=OLD_CASE_ID).delete(synchronize_session=False)
    s.query(AuditEvent).filter_by(case_id=OLD_CASE_ID).delete(synchronize_session=False)
    if rev_ids:
        s.query(ClaimRevision).filter(ClaimRevision.id.in_(rev_ids)).delete(synchronize_session=False)
    if claim_ids:
        s.query(Claim).filter(Claim.id.in_(claim_ids)).delete(synchronize_session=False)
    mv_ids = [m.id for m in s.query(ManuscriptVersion).filter_by(case_id=OLD_CASE_ID)]
    if mv_ids:
        s.query(PatchProposal).filter(PatchProposal.manuscript_version_id.in_(mv_ids)).delete(synchronize_session=False)
        s.query(ClaimSurface).filter(ClaimSurface.manuscript_version_id.in_(mv_ids)).delete(synchronize_session=False)
        s.query(ManuscriptVersion).filter(ManuscriptVersion.id.in_(mv_ids)).delete(synchronize_session=False)
    s.query(ResearchCase).filter_by(id=OLD_CASE_ID).delete(synchronize_session=False)
print("旧演示项目已清理\n")

print("=" * 70)
print("阶段 1/4  创建项目并解析文稿")
print("=" * 70)
case_id = CaseService().create_case(
    title="E-Agent 多模态检索规划（全流程演示）",
    research_question=QUESTION,
    manuscript_path=PDF,
)
print(f"case_id = {case_id}\n")

print("=" * 70)
print("阶段 2/4  LLM 抽取的候选 Claim（取前 4 条确认）")
print("=" * 70)
claim_service = ClaimService()
with session_scope() as s:
    rows = (
        s.query(ClaimRevision, Claim.stable_key)
        .join(Claim, ClaimRevision.claim_id == Claim.id)
        .filter(Claim.case_id == case_id, ClaimRevision.review_state == "candidate")
        .all()
    )
    picked = sorted(rows, key=lambda t: 0 if t[0].centrality == "core" else 1)[:4]
    for rev, key in picked:
        print(f"- [{key}] {rev.statement[:100]}")
for rev, _ in picked:
    claim_service.confirm_candidate(rev.id)
print(f"\n已确认 {len(picked)} 条核心 Claim\n")

print("=" * 70)
print("阶段 3/4  文献雷达扫描（arXiv → 全文 → LLM 比较 → 行动建议）")
print("=" * 70)
scan_id = WeeklyRadarService().run_auto(
    case_id,
    max_results=16,
    analysis_limit=3,
    progress_callback=lambda v, m: print(f"  {v:>4.0%} {m}", flush=True),
)

print()
print("=" * 70)
print("阶段 4/4  结果：影响判断与行动建议")
print("=" * 70)
with session_scope() as s:
    impacts = (
        s.query(ImpactCandidate)
        .filter(ImpactCandidate.scan_run_id == scan_id)
        .all()
    )
    print(f"\n影响判断 {len(impacts)} 条：")
    for im in impacts:
        print(f"- stance={im.stance} · comparability={im.comparability} · "
              f"severity={im.severity} · 建议={im.suggested_action}")
    actions = (
        s.query(ActionItem)
        .filter(ActionItem.case_id == case_id, ActionItem.scan_run_id == scan_id)
        .all()
    )
    print(f"\n行动建议 {len(actions)} 条：")
    for a in actions:
        print(f"\n【{a.action_type} · {a.priority} · 来源={a.advice_source}】{a.title}")
        print(f"  理由：{a.rationale}")
        for item in (a.checklist_json or [])[:4]:
            print(f"  ☐ {item}")
print("\n演示完成。")
