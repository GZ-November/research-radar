"""Multi-project Research Radar workspace."""

import streamlit as st
from sqlalchemy import func, select

from radar.config import get_settings
from radar.db import init_database, session_scope
from radar.llm.factory import describe_llm_setup
from radar.models import ActionItem, ScanRun
from radar.services.case_service import CaseService
from radar.services.scan_runner import recover_interrupted_scans
from radar.ui.action_page import render_action_page
from radar.ui.case_page import render_case_page
from radar.ui.components import (
    inject_theme,
    pending_pill,
    render_pending_confirmation,
    sidebar_brand,
    sidebar_section,
    sidebar_status_row,
)
from radar.ui.home import render_home
from radar.ui.impact_page import render_impact_page
from radar.ui.ledger_page import render_ledger_page
from radar.ui.settings_page import render_settings_page


PAGES = ["项目工作台", "本周行动", "文献雷达", "改进工作台", "我的论文", "设置"]
NAV_ALIASES = {
    "Home": "项目工作台",
    "Action Center": "本周行动",
    "Weekly Radar": "文献雷达",
    "搜索最新论文": "文献雷达",
    "Case & Claims": "我的论文",
    "Claim Ledger": "改进工作台",
}


def _normalized_navigation(value: str | None) -> str:
    mapped = NAV_ALIASES.get(value or "", value)
    return mapped if mapped in PAGES else PAGES[0]


def _project_label(research_case) -> str:
    return f"{research_case.title}{' · 示例' if CaseService.is_demo_case(research_case) else ''}"


def _sidebar_case_summary(case_id: str) -> None:
    """Global per-case summary: pending actions and last scan time."""

    with session_scope() as session:
        pending = session.scalar(
            select(func.count(ActionItem.id)).where(
                ActionItem.case_id == case_id,
                ActionItem.status.in_(["proposed", "open", "in_progress"]),
            )
        ) or 0
        last_scan_at = session.scalar(
            select(ScanRun.created_at)
            .where(ScanRun.case_id == case_id)
            .order_by(ScanRun.created_at.desc())
        )
    pending_pill(pending)
    st.sidebar.caption(
        f"上次扫描：{last_scan_at.strftime('%Y-%m-%d %H:%M')}" if last_scan_at else "尚未扫描"
    )


def main() -> None:
    st.set_page_config(page_title="Research Radar", page_icon="🔭", layout="wide")
    inject_theme()
    init_database()
    if not st.session_state.get("_scan_recovery_done"):
        # One zombie-scan sweep per browser session; cheap when nothing is stale.
        recover_interrupted_scans()
        st.session_state["_scan_recovery_done"] = True
    case_service = CaseService()
    cases = case_service.list_cases(include_synthetic_demo=False)
    case_by_id = {item.id: item for item in cases}

    next_project_id = st.session_state.pop("_next_project_id", None)
    active_case_id = next_project_id or st.session_state.get("active_case_id")
    if active_case_id not in case_by_id:
        own_cases = [item for item in cases if not CaseService.is_demo_case(item)]
        active_case_id = (own_cases or cases)[0].id if cases else None
    if next_project_id and next_project_id in case_by_id:
        st.session_state["project_selector"] = next_project_id

    st.session_state["navigation"] = _normalized_navigation(
        st.session_state.get("navigation")
    )
    if "_next_navigation" in st.session_state:
        st.session_state["navigation"] = _normalized_navigation(
            st.session_state.pop("_next_navigation")
        )

    sidebar_brand()
    sidebar_section("项目")
    if cases:
        option_ids = [item.id for item in cases]
        if st.session_state.get("project_selector") not in option_ids:
            st.session_state["project_selector"] = active_case_id
        selected_id = st.sidebar.selectbox(
            "当前项目",
            option_ids,
            format_func=lambda case_id: _project_label(case_by_id[case_id]),
            key="project_selector",
        )
        active_case_id = selected_id
        st.session_state["active_case_id"] = selected_id
        st.sidebar.caption(case_by_id[selected_id].research_question)
        _sidebar_case_summary(selected_id)
    else:
        active_case_id = None
        st.sidebar.info("创建第一个研究项目后即可开始 Radar。")

    if st.sidebar.button("＋ 创建或管理项目", width="stretch"):
        st.session_state["_next_navigation"] = "项目工作台"
        st.rerun()
    sidebar_section("导航")
    page = st.sidebar.radio("导航", PAGES, key="navigation", label_visibility="collapsed")

    settings = get_settings()
    llm_setup = describe_llm_setup(settings)
    sidebar_section("系统状态")
    if llm_setup["configured"]:
        mode_label = "本地" if llm_setup["mode"] == "local" else "远程"
        sidebar_status_row("分析模型", f"`{llm_setup['model']}` · {mode_label}")
    else:
        sidebar_status_row("分析模型", "未配置", ok=False)
    if settings.embedding_provider and settings.embedding_model:
        sidebar_status_row("向量模型", f"`{settings.embedding_model}`")
    else:
        sidebar_status_row("向量模型", "未配置 · 退化为关键词检索", ok=False)

    render_pending_confirmation()

    if page == "设置":
        # Settings must stay reachable before the first project exists.
        render_settings_page()
    elif page == "项目工作台" or active_case_id is None:
        render_home()
    elif page == "本周行动":
        render_action_page(active_case_id)
    elif page == "文献雷达":
        render_impact_page(active_case_id)
    elif page == "改进工作台":
        render_ledger_page(active_case_id)
    elif page == "我的论文":
        render_case_page(active_case_id)


if __name__ == "__main__":
    main()
