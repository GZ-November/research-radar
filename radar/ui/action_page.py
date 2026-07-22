"""Weekly action center: turn research events into project decisions."""

import re

import streamlit as st
from sqlalchemy import select

from radar.config import get_settings
from radar.db import session_scope
from radar.models import (
    ActionItem,
    Claim,
    ClaimRevision,
    ImpactCandidate,
    ModelRun,
    ResearchCase,
    ScanRun,
    Source,
    SourceSnapshot,
)
from radar.services.action_service import ActionService
from radar.services.report_service import ReportService
from radar.ui.components import (
    ACTION_STATUS_LABEL,
    ATTENTION_LABEL,
    COMPARABILITY_LABEL,
    IMPACT_MODE_LABEL,
    PRIORITY_LABEL,
    REVIEW_STATE_LABEL,
    STANCE_LABEL,
    SUGGESTED_ACTION_LABEL,
    TRUST_STATE_LABEL,
    adoption_guidance,
    empty_state,
    evidence_block,
    page_header,
    priority_badge,
    render_impact_decision,
    render_impact_status,
    render_source_traceability,
    request_confirmation,
    source_venue_label,
    state_badge,
)


ACTION_LABEL = {
    "team_decision": "团队决策",
    "experiment": "改实验",
    "data": "补数据/条件",
    "writing": "调整写作",
    "cite": "引用/关注",
    "competitor_response": "竞争响应",
    "revalidation": "重新验证",
}
PRIORITY_ICON = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🔵",
    "low": "⚪",
}


def _context_for_actions(actions: list[ActionItem]) -> dict[str, dict]:
    """Batch-load impact/claim/source context for a list of actions (no N+1)."""

    if not actions:
        return {}
    impact_ids = {
        action.impact_candidate_id for action in actions if action.impact_candidate_id
    }
    revision_ids = {
        action.claim_revision_id for action in actions if action.claim_revision_id
    }
    with session_scope() as session:
        impacts = (
            {
                item.id: item
                for item in session.scalars(
                    select(ImpactCandidate).where(ImpactCandidate.id.in_(impact_ids))
                )
            }
            if impact_ids
            else {}
        )
        revisions = (
            {
                item.id: item
                for item in session.scalars(
                    select(ClaimRevision).where(ClaimRevision.id.in_(revision_ids))
                )
            }
            if revision_ids
            else {}
        )
        claim_ids = {item.claim_id for item in revisions.values()}
        claims = (
            {
                item.id: item
                for item in session.scalars(select(Claim).where(Claim.id.in_(claim_ids)))
            }
            if claim_ids
            else {}
        )
        snapshot_ids = {item.source_snapshot_id for item in impacts.values()}
        snapshots = (
            {
                item.id: item
                for item in session.scalars(
                    select(SourceSnapshot).where(SourceSnapshot.id.in_(snapshot_ids))
                )
            }
            if snapshot_ids
            else {}
        )
        source_ids = {item.source_id for item in snapshots.values()}
        sources = (
            {
                item.id: item
                for item in session.scalars(select(Source).where(Source.id.in_(source_ids)))
            }
            if source_ids
            else {}
        )
    context: dict[str, dict] = {}
    for action in actions:
        impact = (
            impacts.get(action.impact_candidate_id) if action.impact_candidate_id else None
        )
        revision = (
            revisions.get(action.claim_revision_id) if action.claim_revision_id else None
        )
        claim = claims.get(revision.claim_id) if revision else None
        snapshot = snapshots.get(impact.source_snapshot_id) if impact else None
        source = sources.get(snapshot.source_id) if snapshot else None
        context[action.id] = {
            "impact": impact,
            "claim": claim,
            "revision": revision,
            "source": source,
        }
    return context


def _paper_impacts(scan_run_id: str) -> list[dict]:
    with session_scope() as session:
        impacts = list(
            session.scalars(
                select(ImpactCandidate)
                .where(ImpactCandidate.scan_run_id == scan_run_id)
                .order_by(ImpactCandidate.created_at, ImpactCandidate.id)
            )
        )
        if not impacts:
            return []
        revisions = {
            item.id: item
            for item in session.scalars(
                select(ClaimRevision).where(
                    ClaimRevision.id.in_({item.claim_revision_id for item in impacts})
                )
            )
        }
        claims = {
            item.id: item
            for item in session.scalars(
                select(Claim).where(
                    Claim.id.in_({item.claim_id for item in revisions.values()})
                )
            )
        } if revisions else {}
        snapshots = {
            item.id: item
            for item in session.scalars(
                select(SourceSnapshot).where(
                    SourceSnapshot.id.in_({item.source_snapshot_id for item in impacts})
                )
            )
        }
        sources = {
            item.id: item
            for item in session.scalars(
                select(Source).where(
                    Source.id.in_({item.source_id for item in snapshots.values()})
                )
            )
        } if snapshots else {}
    rows: list[dict] = []
    for impact in impacts:
        revision = revisions.get(impact.claim_revision_id)
        claim = claims.get(revision.claim_id) if revision else None
        snapshot = snapshots.get(impact.source_snapshot_id)
        source = sources.get(snapshot.source_id) if snapshot else None
        if all([revision, claim, snapshot, source]):
            rows.append(
                {
                    "impact": impact,
                    "revision": revision,
                    "claim": claim,
                    "snapshot": snapshot,
                    "source": source,
                }
            )
    return rows


def _routed_papers(scan: ScanRun, material_snapshot_ids: set[str]) -> list[Source]:
    """Return papers that received full comparison but produced no material impact."""

    snapshot_ids = list(scan.stats_json.get("routed_source_snapshot_ids") or [])
    with session_scope() as session:
        # Compatibility for scans created before routed ids were persisted.
        if not snapshot_ids:
            query = select(ModelRun).where(
                ModelRun.stage == "incoming_result",
                ModelRun.scan_run_id == scan.id,
            )
            for run in session.scalars(query.order_by(ModelRun.created_at)):
                if run.input_refs_json:
                    snapshot_ids.append(str(run.input_refs_json[0]))

        snapshots = (
            {
                item.id: item
                for item in session.scalars(
                    select(SourceSnapshot).where(SourceSnapshot.id.in_(snapshot_ids))
                )
            }
            if snapshot_ids
            else {}
        )
        source_ids = {item.source_id for item in snapshots.values()}
        sources = (
            {
                item.id: item
                for item in session.scalars(select(Source).where(Source.id.in_(source_ids)))
            }
            if source_ids
            else {}
        )
        papers: list[Source] = []
        seen: set[str] = set()
        for snapshot_id in snapshot_ids:
            if snapshot_id in material_snapshot_ids:
                continue
            snapshot = snapshots.get(snapshot_id)
            source = sources.get(snapshot.source_id) if snapshot else None
            if source and source.id not in seen:
                papers.append(source)
                seen.add(source.id)
        return papers


def _render_evidence_entries(entries: list[dict]) -> None:
    if not entries:
        st.caption("暂无记录。")
        return
    for entry in entries:
        state = "已确认" if entry["review_state"] in {"confirmed", "edited"} else "待确认"
        with st.expander(
            f"{entry['claim']} · {entry['source_title']} · {state}",
            expanded=False,
        ):
            st.caption(
                f"{STANCE_LABEL.get(entry['stance'], entry['stance'])} · "
                f"{IMPACT_MODE_LABEL.get(entry['impact_mode'], entry['impact_mode'])} · "
                f"可比性：{COMPARABILITY_LABEL.get(entry['comparability'], entry['comparability'])}"
            )
            st.markdown(f"> {entry['evidence'].get('quote', '')}")
            st.caption(entry["evidence"].get("locator", ""))
            metadata = (
                f"发表载体：{entry['source_venue']} · "
                f"公开日期：{entry['source_published_at'] or '未登记'}"
            )
            st.caption(metadata)
            links = [f"[查看原文]({entry['source_url']})"]
            if entry["source_pdf_url"]:
                links.append(f"[PDF 全文]({entry['source_pdf_url']})")
            if entry["source_doi"]:
                links.append(
                    f"[DOI: {entry['source_doi']}](https://doi.org/{entry['source_doi']})"
                )
            else:
                links.append("DOI：未登记")
            st.markdown(" · ".join(links))


def render_action_page(case_id: str) -> None:
    with session_scope() as session:
        research_case = session.get(ResearchCase, case_id)
        scan = session.scalar(
            select(ScanRun)
            .where(ScanRun.case_id == case_id)
            .order_by(ScanRun.created_at.desc())
        )
        claims = list(session.scalars(select(Claim).where(Claim.case_id == case_id)))
    page_header(
        "这个项目现在需要做什么？",
        (
            f"所有判断和行动都属于项目《{research_case.title}》。"
            if research_case
            else "基于当前项目与最新公开研究生成行动。"
        ),
    )
    if scan is None:
        empty_state(
            "🔭", "还没有联网搜索结果",
            "先搜索最新公开论文，系统才能给出行动建议。",
        )
        if st.button("开始搜索最新公开论文", type="primary"):
            st.session_state["_next_navigation"] = "文献雷达"
            st.rerun()
        return

    action_service = ActionService()
    action_service.sync_scan_actions(scan.id)
    actions = action_service.list_actions(case_id, scan_run_id=scan.id)
    report = ReportService().get_weekly_action_report(scan.id)
    counts = report["counts_by_type"]

    if report["urgent"]:
        st.error(f"**需要马上处理：** {report['headline']}")
    elif report["open_actions"]:
        st.warning(f"**本周建议：** {report['headline']}")
    else:
        st.success("最新公开论文中没有发现需要改变实验、数据或写作的材料性影响。")
    search_queries = scan.stats_json.get("search_queries") or scan.query_json.get("queries") or []
    newest = scan.stats_json.get("newest_publication")
    analysis_model = scan.stats_json.get("analysis_model")
    provenance = [
        "arXiv 最新优先",
        "混合检索",
        f"{analysis_model} 影响判断" if analysis_model else "结构化影响判断",
    ]
    if scan.stats_json.get("full_text_papers"):
        provenance.append(f"{scan.stats_json['full_text_papers']} 篇公开 PDF 全文")
    st.caption(
        " · ".join(provenance)
        + (f" · 最新论文日期 {newest[:10]}" if newest else "")
        + (f" · 搜索主题：{' / '.join(search_queries)}" if search_queries else "")
    )
    current_settings = get_settings()
    current_model = current_settings.local_llm_model or current_settings.llm_model
    if analysis_model and current_model and analysis_model != current_model:
        st.info(
            f"这是一份由 `{analysis_model}` 生成的历史扫描。当前已切换为 "
            f"`{current_model}`；点击重新搜索后，新报告会直接使用当前配置模型的全文分析。"
        )
    rerun_col, improve_col = st.columns(2)
    if rerun_col.button("重新搜索最新公开论文", width="stretch"):
        st.session_state["_next_navigation"] = "文献雷达"
        st.rerun()
    if improve_col.button("打开改进工作台", type="primary", width="stretch"):
        st.session_state["_next_navigation"] = "改进工作台"
        st.rerun()
    metrics = st.columns(6)
    for column, label, value in zip(
        metrics,
        ["紧急", "改实验", "补数据", "调整写作", "竞争预警", "重新验证"],
        [
            report["urgent"],
            counts["experiment"],
            counts["data"],
            counts["writing"],
            counts["competitor_response"],
            counts["revalidation"],
        ],
    ):
        column.metric(label, value)

    actions_tab, papers_tab, risks_tab, writing_tab = st.tabs(
        ["你要做什么", "有用论文", "受影响的主张", "写作证据"]
    )
    with actions_tab:
        if not actions:
            empty_state(
                "✅", "本周没有开放行动",
                "最新扫描没有发现需要执行的任务；可以重新扫描查看最新公开论文。",
            )
            if st.button("重新扫描最新公开论文", key="empty-actions-rescan"):
                st.session_state["_next_navigation"] = "文献雷达"
                st.rerun()
        context = _context_for_actions(actions)
        for action in actions:
            item_context = context[action.id]
            claim = item_context["claim"]
            source = item_context["source"]
            impact = item_context["impact"]
            title = (
                f"{PRIORITY_ICON.get(action.priority, '•')} "
                f"{ACTION_LABEL.get(action.action_type, action.action_type)} · {action.title}"
            )
            with st.expander(title, expanded=action.priority == "critical"):
                st.markdown(
                    f"{priority_badge(action.priority)} "
                    f"{state_badge(ACTION_STATUS_LABEL, action.status)}"
                )
                st.caption(
                    f"建议期限：{action.due_label} · "
                    f"关联 Claim：{claim.stable_key if claim else '—'}"
                )
                st.write(action.rationale)
                if action.advice_source == "llm" and source:
                    st.caption(f"AI 建议 · 基于《{source.title}》")
                if source:
                    st.markdown("**触发来源**")
                    render_source_traceability(source)
                if impact:
                    st.caption(
                        f"影响：{STANCE_LABEL.get(impact.stance, impact.stance)} / "
                        f"{IMPACT_MODE_LABEL.get(impact.impact_mode, impact.impact_mode)} · "
                        f"可比性：{COMPARABILITY_LABEL.get(impact.comparability, impact.comparability)} · "
                        f"审查状态：{REVIEW_STATE_LABEL.get(impact.review_state, impact.review_state)}"
                    )
                st.write("**执行清单**")
                for checklist_item in action.checklist_json:
                    st.markdown(f"- [ ] {checklist_item}")
                if action.status == "proposed":
                    st.info("先在“有用论文”中采用对应影响，再开始执行这项行动。")
                start, done, dismiss, inspect = st.columns(4)
                if start.button(
                    "开始",
                    key=f"start-action-{action.id}",
                    disabled=action.status == "proposed",
                    width="stretch",
                ):
                    action_service.update_status(action.id, "in_progress")
                    st.rerun()
                if done.button(
                    "完成",
                    key=f"done-action-{action.id}",
                    type="primary",
                    disabled=action.status == "proposed",
                    width="stretch",
                ):
                    action_service.update_status(action.id, "done")
                    st.rerun()
                if dismiss.button("不处理", key=f"dismiss-action-{action.id}", width="stretch"):
                    request_confirmation(
                        key=f"dismiss-action-{action.id}",
                        title="不处理这项行动",
                        body="行动会被关闭；之后如需恢复，可在“有用论文”中重新采用对应影响。",
                        confirm_label="确认不处理",
                        on_confirm=lambda action_id=action.id: ActionService().update_status(
                            action_id, "dismissed"
                        ),
                    )
                    st.rerun()
                if impact and inspect.button("查看证据", key=f"inspect-action-{action.id}", width="stretch"):
                    st.session_state["selected_impact_id"] = impact.id
                    st.session_state["_next_navigation"] = "文献雷达"
                    st.rerun()

    with papers_tab:
        st.subheader("这次搜索中值得你决策或继续观察的论文")
        st.caption(
            "“采用”表示接受 Agent 对这篇论文影响的判断，并打开相关行动；"
            "不会自动修改你的论文或 Claim。每项判断都保留原文、PDF、DOI 和精确证据。"
        )
        all_paper_rows = _paper_impacts(scan.id)
        paper_rows = [
            row
            for row in all_paper_rows
            if row["impact"].impact_mode != "no_material_change"
            or row["impact"].event_type == "retraction"
            or bool(row["impact"].strategic_flags_json)
        ]
        no_change_rows = [
            row for row in all_paper_rows if row not in paper_rows
        ]
        assessed_snapshot_ids = {
            row["snapshot"].id for row in all_paper_rows
        }
        monitored_papers = _routed_papers(scan, assessed_snapshot_ids)
        if not paper_rows and monitored_papers:
            st.info(
                "本次没有达到材料性影响阈值，但以下论文已完成全文比较。"
                "它们不会生成强制行动，仍可追溯并用于人工观察。"
            )
        elif not paper_rows:
            st.success("本次没有达到材料性影响阈值的论文。")
        for row in paper_rows:
            impact = row["impact"]
            source = row["source"]
            claim = row["claim"]
            revision = row["revision"]
            guidance_title = adoption_guidance(impact)[0]
            with st.expander(
                f"{source.title} · {source_venue_label(source)} · {guidance_title}",
                expanded=impact.review_state == "candidate",
            ):
                render_source_traceability(source)
                st.divider()
                render_impact_status(impact)
                st.markdown(f"**影响的 Claim：{claim.stable_key}** — {revision.statement}")
                st.caption(
                    f"建议动作：{SUGGESTED_ACTION_LABEL.get(impact.suggested_action, impact.suggested_action)} · "
                    f"证据状态：{TRUST_STATE_LABEL.get(impact.trust_state, impact.trust_state)}"
                )
                evidence_block("这篇论文中的精确证据", impact.evidence_new_json)
                if impact.uncertainty_json:
                    st.write("**采用前需要注意**")
                    for uncertainty in impact.uncertainty_json:
                        st.caption(f"• {uncertainty}")
                render_impact_decision(impact, key_prefix=f"paper-{impact.id}")
                if st.button(
                    "查看完整比较",
                    key=f"inspect-paper-{impact.id}",
                    width="stretch",
                ):
                    st.session_state["selected_impact_id"] = impact.id
                    st.session_state["_next_navigation"] = "文献雷达"
                    st.rerun()

        if no_change_rows or monitored_papers:
            st.markdown("#### 已深度比较 · 暂无材料性影响")
            for row in no_change_rows:
                impact = row["impact"]
                source = row["source"]
                claim = row["claim"]
                with st.expander(
                    f"{source.title} · {source_venue_label(source)} · 无需改变",
                    expanded=False,
                ):
                    render_source_traceability(source)
                    st.caption(
                        f"比较对象：{claim.stable_key} · 总体可比性："
                        f"{COMPARABILITY_LABEL.get(impact.comparability, impact.comparability)} · "
                        f"判断状态：{REVIEW_STATE_LABEL.get(impact.review_state, impact.review_state)}"
                    )
                    evidence_block("用于判断的精确证据", impact.evidence_new_json)
                    st.caption(
                        f"{analysis_model or 'AI'} 已完成双方全文比较；你可以打开条件矩阵，"
                        "把判断改为 prior art、边界条件或方法替代。"
                    )
                    if st.button(
                        "查看条件矩阵并修正判断",
                        key=f"inspect-no-change-{impact.id}",
                        width="stretch",
                    ):
                        st.session_state["selected_impact_id"] = impact.id
                        st.session_state["_next_navigation"] = "文献雷达"
                        st.rerun()
            for source in monitored_papers:
                with st.expander(
                    f"{source.title} · {source_venue_label(source)} · 继续观察",
                    expanded=False,
                ):
                    render_source_traceability(source)
                    st.caption(
                        f"{analysis_model or 'AI'} 已读取公开全文并与当前 Claim 比较；"
                        "现有证据不足以要求改实验、补数据或调整写作。"
                    )

    with risks_tab:
        claims.sort(
            key=lambda item: (
                int(match.group(1)) if (match := re.match(r"C(\d+)$", item.stable_key)) else 10_000,
                item.stable_key,
            )
        )
        for claim in claims:
            state = action_service.claim_attention_state(claim.id)
            with session_scope() as session:
                revision = session.scalar(
                    select(ClaimRevision)
                    .where(
                        ClaimRevision.claim_id == claim.id,
                        ClaimRevision.review_state == "confirmed",
                    )
                    .order_by(ClaimRevision.revision_no.desc())
                )
            label = ATTENTION_LABEL.get(state, state)
            icon = "🔴" if state in {"disputed", "revalidation_required"} else "🟠" if state in {"competitor_pressure", "needs_review"} else "🟢"
            with st.container(border=True):
                st.markdown(f"**{icon} {claim.stable_key} · {label}**")
                st.write(revision.statement if revision else "")

    with writing_tab:
        brief = ReportService().get_writing_brief(case_id)
        writing_metrics = st.columns(4)
        for column, label, key in zip(
            writing_metrics,
            ["支持证据", "反证", "边界/相关工作", "完整性风险"],
            ["supports", "challenges", "boundary_and_prior_art", "integrity"],
        ):
            column.metric(label, len(brief[key]))
        support_tab, challenge_tab, context_tab, integrity_tab = st.tabs(
            ["支持证据", "反证", "边界与 prior art", "完整性"]
        )
        for tab, key in zip(
            [support_tab, challenge_tab, context_tab, integrity_tab],
            ["supports", "challenges", "boundary_and_prior_art", "integrity"],
        ):
            with tab:
                _render_evidence_entries(brief[key])
        st.write("**建议写作动作**")
        for item in brief["writing_actions"]:
            st.markdown(
                f"- {PRIORITY_LABEL.get(item['priority'], item['priority'])} · "
                f"{ACTION_STATUS_LABEL.get(item['status'], item['status'])} "
                f"**{item['title']}** — {item['rationale']}"
            )
        st.download_button(
            "下载 Discussion Evidence Brief",
            ReportService().export_writing_brief(case_id),
            file_name="discussion-evidence-brief.md",
            mime="text/markdown",
        )
