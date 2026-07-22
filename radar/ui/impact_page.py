"""Weekly Radar and three-column Impact Workspace."""

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from radar.config import get_settings
from radar.db import session_scope
from radar.models import (
    Claim,
    ClaimRevision,
    ImpactCandidate,
    ManuscriptVersion,
    ResearchCase,
    ScanRun,
    Source,
    SourceSnapshot,
)
from radar.llm.factory import describe_llm_setup
from radar.services import scan_runner
from radar.services.manuscript_understanding_service import (
    ManuscriptUnderstandingService,
)
from radar.services.report_service import ReportService
from radar.services.weekly_radar_service import WeeklyRadarService
from radar.ui.components import (
    COMPARABILITY_LABEL,
    CONDITION_STATUS_LABEL,
    IMPACT_MODE_LABEL,
    SEVERITY_ICON,
    STANCE_LABEL,
    SUGGESTED_ACTION_LABEL,
    TRUST_STATE_LABEL,
    empty_state,
    evidence_block,
    label_for,
    page_header,
    render_impact_decision,
    render_impact_status,
    render_llm_setup_guidance,
    render_source_traceability,
)


def _contains_cjk(text: str) -> bool:
    """Detect CJK characters that make an arXiv keyword query ineffective."""

    return any("\u4e00" <= character <= "\u9fff" for character in text)


@st.fragment(run_every=2)
def _render_active_scan(scan_id: str) -> None:
    """Poll one active ScanRun until it reaches a terminal state."""

    with session_scope() as session:
        scan = session.get(ScanRun, scan_id)
        if scan is None:
            return
        status = scan.status
        progress = dict((scan.stats_json or {}).get("progress") or {})
    if status in scan_runner.ACTIVE_STATUSES:
        value = float(progress.get("value") or 0.0)
        message = str(progress.get("message") or "扫描进行中…")
        with st.container(border=True):
            st.markdown(
                '<div class="rr-agent-head"><span class="rr-agent-pulse"></span>'
                "Agent 正在工作：联网搜索并逐篇比较公开论文</div>",
                unsafe_allow_html=True,
            )
            st.progress(value, text=message)
            if status == "cancel_requested":
                st.caption("已请求取消：扫描将在当前阶段结束后停止。")
            elif st.button("取消扫描", key=f"cancel-scan-{scan_id}", width="stretch"):
                scan_runner.request_cancel(scan_id)
                st.toast("已请求取消，扫描将在阶段边界停止")
        return
    # Terminal state: rerun the full app once so the summary below refreshes.
    st.rerun()


def render_impact_page(case_id: str) -> None:
    page_header(
        "搜索最新公开论文",
        "系统根据你论文的全文画像和核心 Claim 自动搜索，不需要你自己写检索词。",
    )

    with session_scope() as session:
        research_case = session.get(ResearchCase, case_id)
        manuscript = session.scalar(
            select(ManuscriptVersion).where(
                ManuscriptVersion.case_id == case_id,
                ManuscriptVersion.is_current.is_(True),
            )
        )
        confirmed_count = session.scalar(
            select(func.count(ClaimRevision.id))
            .join(Claim, Claim.id == ClaimRevision.claim_id)
            .where(
                Claim.case_id == case_id,
                ClaimRevision.review_state == "confirmed",
                ClaimRevision.manuscript_version_id == manuscript.id
                if manuscript
                else False,
            )
        ) or 0
        scan = session.scalar(
            select(ScanRun).where(ScanRun.case_id == case_id).order_by(ScanRun.created_at.desc())
        )
        impacts = (
            list(
                session.scalars(
                    select(ImpactCandidate)
                    .where(ImpactCandidate.scan_run_id == scan.id)
                    .order_by(ImpactCandidate.created_at, ImpactCandidate.id)
                )
            )
            if scan
            else []
        )
        context = {}
        for impact in impacts:
            revision = session.get(ClaimRevision, impact.claim_revision_id)
            claim = session.get(Claim, revision.claim_id)
            snapshot = session.get(SourceSnapshot, impact.source_snapshot_id)
            source = session.get(Source, snapshot.source_id)
            context[impact.id] = (claim, revision, source, snapshot)

    settings = get_settings()
    radar_service = WeeklyRadarService()
    llm_setup = describe_llm_setup(settings)
    configured = llm_setup["configured"]
    analysis_model = llm_setup["model"]
    suggested_queries = radar_service.suggested_queries(case_id)
    manuscript_profile = ManuscriptUnderstandingService.latest_profile(case_id)
    st.subheader(f"当前项目：{research_case.title if research_case else case_id}")
    analysis_step = (
        f"{analysis_model} 读取你的文稿和公开论文全文并逐项比较"
        if llm_setup["mode"] == "remote"
        else "本地模型与你的 Claim 对比"
    )
    st.write(
        "点击一次后，Agent 会完成：**arXiv 最新论文搜索 → 混合检索 → "
        f"公开 PDF 全文提取 → {analysis_step} → 生成项目行动**。"
    )
    st.caption("自动搜索主题：" + " · ".join(suggested_queries))
    if manuscript is not None and manuscript_profile is None:
        st.caption(
            "未运行 AI 全文画像：搜索主题由研究问题自动生成。"
            "到“我的论文”跑一次 AI 全文画像，搜索会更准。"
        )
    if any(_contains_cjk(query) for query in suggested_queries):
        st.warning(
            "当前搜索主题包含非英文内容，而 arXiv 是英文库，检索结果可能严重偏离。"
            "建议先运行 AI 全文画像，或把研究问题补充上英文关键词。"
        )
    if configured:
        st.caption(
            f"分析模型：`{analysis_model}`"
            + (
                "（本地）"
                if llm_setup["mode"] == "local"
                else "（远程 API，发送完整文稿与命中论文全文）"
            )
            + (
                f" · 向量：`{settings.embedding_provider}/"
                f"{settings.embedding_model}` · "
                if settings.embedding_provider
                else " · 向量：未启用（纯关键词检索） · "
            )
            + f"已确认核心 Claim：{confirmed_count}"
        )
    else:
        render_llm_setup_guidance(llm_setup)
    if confirmed_count == 0:
        st.warning("请先到“我的论文”确认至少一条核心 Claim。")
        if st.button("去确认 Claim", key=f"goto-claims-{case_id}"):
            st.session_state["_next_navigation"] = "我的论文"
            st.rerun()

    with st.expander("扫描范围"):
        option_a, option_b = st.columns(2)
        max_results = option_a.number_input(
            "最多搜索公开论文", 8, 60, 32, 4, key=f"weekly-results-{case_id}"
        )
        analysis_limit = option_b.number_input(
            "最多深度比较", 1, 10, 3, 1, key=f"weekly-analysis-{case_id}"
        )
        st.caption(
            "结果按 arXiv 提交日期从新到旧；只深度分析与已确认 Claim 最相关的论文。"
            "每篇论文需要两次结构化判断，Demo 建议保持 3 篇。"
        )

    active_scan = scan_runner.get_active_scan(case_id)
    if st.button(
        "搜索最新公开论文并告诉我该做什么",
        type="primary",
        disabled=not configured or confirmed_count == 0 or active_scan is not None,
        key=f"weekly-run-{case_id}",
        width="stretch",
    ):
        try:
            scan_runner.start(
                case_id,
                max_results=int(max_results),
                analysis_limit=int(analysis_limit),
            )
        except scan_runner.ScanAlreadyRunningError:
            st.warning("已有扫描进行中，请等待完成或先取消。")
        else:
            st.rerun()

    if active_scan is not None:
        _render_active_scan(active_scan.id)

    if scan is None:
        empty_state(
            "🛰️", "还没有联网扫描结果",
            "点击上方按钮，Agent 会完成搜索、全文比较并生成项目行动。",
        )
        return
    if scan.status in scan_runner.ACTIVE_STATUSES:
        st.caption("扫描进行中：完成后这里会显示本次扫描的完整摘要。")
        return
    if scan.status == "failed":
        st.error(f"最近一次扫描失败：{scan.error_message or '未知错误'}")
        if st.button("重试扫描", key=f"retry-scan-{scan.id}", width="stretch"):
            try:
                scan_runner.start(
                    case_id,
                    max_results=int(max_results),
                    analysis_limit=int(analysis_limit),
                )
            except scan_runner.ScanAlreadyRunningError:
                st.warning("已有扫描进行中，请等待完成或先取消。")
            else:
                st.rerun()
    elif scan.status == "interrupted":
        st.warning("上次扫描被中断（页面刷新或服务重启），结果可能不完整，可重新发起扫描。")
    elif scan.status == "cancelled":
        st.info("上次扫描已取消，取消前完成的中途结果已保留。")
    elif scan.error_message:
        st.warning(scan.error_message)
    if scan.stats_json.get("embedding_provider") not in {None, "disabled"}:
        if scan.stats_json.get("embedding_degraded"):
            st.warning(
                "Embedding 暂时不可用，本次扫描已降级为关键词检索："
                + "; ".join(scan.stats_json.get("embedding_errors", []))
            )
        else:
            st.caption(
                "混合检索 · "
                f"`{scan.stats_json.get('embedding_provider')}` / "
                f"`{scan.stats_json.get('embedding_model')}` · "
                "55% 关键词 + 45% 语义"
            )

    summary = ReportService().get_weekly_summary(scan.id)
    st.divider()
    st.subheader("最近一次真实扫描")
    if scan.created_at:
        st.caption(f"最近一次扫描：{scan.created_at.strftime('%Y-%m-%d %H:%M')}")
    stats = scan.stats_json or {}
    scan_notices: list[str] = []
    if stats.get("integrity_flagged"):
        scan_notices.append(f"⚠️ {stats['integrity_flagged']} 篇文献被撤稿标记")
    abstract_only = max(
        int(stats.get("routed_pairs", 0)) - int(stats.get("full_text_papers", 0)), 0
    )
    if abstract_only:
        scan_notices.append(f"{abstract_only} 篇仅有摘要（PDF 全文不可用）")
    if stats.get("crossref_enrich_failures"):
        scan_notices.append(
            f"{stats['crossref_enrich_failures']} 篇 DOI/发表信息补全失败"
        )
    for notice in scan_notices:
        st.warning(notice)
    metrics = st.columns(6)
    for column, (label, key) in zip(
        metrics,
        [
            ("公开论文", "scanned_papers"), ("深度比较", "routed_papers"),
            ("材料影响", "related_papers"), ("紧急", "critical"),
            ("竞争预警", "competitor_alerts"), ("完整性", "integrity_alerts"),
        ],
    ):
        column.metric(label, summary[key])

    action_report = ReportService().get_weekly_action_report(scan.id)
    action_notice, action_button = st.columns([4, 1])
    action_notice.info(action_report["headline"])
    if action_button.button("查看我要做什么", type="primary", width="stretch"):
        st.session_state["_next_navigation"] = "本周行动"
        st.rerun()

    if not impacts:
        st.success("本次扫描没有需要审查的材料性影响。")
        if st.button("查看本周行动", type="primary"):
            st.session_state["_next_navigation"] = "本周行动"
            st.rerun()
        return

    def impact_label(impact_id: str) -> str:
        impact = next(item for item in impacts if item.id == impact_id)
        claim, _, source, _ = context[impact_id]
        return (
            f"{SEVERITY_ICON.get(impact.severity, '•')} {claim.stable_key} · "
            f"{STANCE_LABEL.get(impact.stance, impact.stance)} · {source.title}"
        )

    queue_col, detail_col = st.columns([0.9, 2.2], gap="large")
    with queue_col:
        selected_id = st.radio(
            "影响队列",
            [impact.id for impact in impacts],
            format_func=impact_label,
            key="selected_impact_id",
        )
    impact = next(item for item in impacts if item.id == selected_id)
    claim, revision, source, snapshot = context[selected_id]

    with detail_col:
        st.markdown(
            f"### {SEVERITY_ICON.get(impact.severity, '•')} {claim.stable_key} — {revision.statement}"
        )
        st.caption(f"证据状态：{label_for(TRUST_STATE_LABEL, impact.trust_state)}")
        render_impact_status(impact)
        if "competitor" in impact.strategic_flags_json:
            st.warning("竞争团队提醒：这是战略标记，不代表 support 或 challenge。")
        if impact.event_type == "retraction":
            st.error("该引用来源出现撤稿记录。确认后 Claim Health 才会变为“需要重新验证”。")

        compare_tab, evidence_tab, decision_tab = st.tabs(["比较矩阵", "证据", "决策"])
        with compare_tab:
            st.markdown(f"总体可比性：**{label_for(COMPARABILITY_LABEL, impact.comparability)}**")
            if impact.comparability != "compatible":
                st.warning(
                    "当前条件不是“可比”：程序禁止输出支持/挑战结论，"
                    "只能作为信息不足、边界、在先工作或后续实验线索。"
                )
            delta_rows = [
                {
                    "字段": item["field"], "本方": item.get("own_value") or "—",
                    "公开论文": item.get("incoming_value") or "—",
                    "状态": label_for(CONDITION_STATUS_LABEL, item["status"]),
                }
                for item in impact.condition_differences_json
            ]
            st.dataframe(pd.DataFrame(delta_rows), hide_index=True, width="stretch")
            with st.expander("逐项比较说明"):
                for item in impact.condition_differences_json:
                    st.caption(
                        f"{item['field']} · {label_for(CONDITION_STATUS_LABEL, item['status'])}"
                        f" — {item['explanation']}"
                    )
        with evidence_tab:
            st.write("**可追溯来源**")
            render_source_traceability(source)
            st.divider()
            evidence_block("你的文稿", impact.evidence_own_json)
            st.write("")
            evidence_block("公开论文", impact.evidence_new_json)
            st.caption("两段引文均经过原文精确区间校验。")
        with decision_tab:
            st.write("**为什么重要**")
            st.caption(
                f"当前判断：{label_for(IMPACT_MODE_LABEL, impact.impact_mode)} · "
                f"建议动作：{label_for(SUGGESTED_ACTION_LABEL, impact.suggested_action)}"
                "（可在下方“修改判断”中调整）"
            )
            if impact.uncertainty_json:
                st.write("**不确定因素**")
                for uncertainty in impact.uncertainty_json:
                    st.caption(f"• {uncertainty}")
            st.divider()
            if impact.impact_mode == "no_material_change":
                st.info(
                    "当前判断为“无需改变”。你仍可以根据条件矩阵和原文证据，把它改为 "
                    "在先工作、边界条件或方法替代，再采用相应动作。"
                )
            render_impact_decision(impact, key_prefix=f"impact-{impact.id}")
