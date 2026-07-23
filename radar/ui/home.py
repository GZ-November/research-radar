"""Research project workspace and onboarding entry points."""

import streamlit as st
from sqlalchemy import func, select

from radar.db import session_scope
from radar.models import Claim, ClaimRevision, ManuscriptVersion, ScanRun
from radar.services.case_service import CaseService
from radar.ui.components import empty_state, home_hero, page_header
from radar.ui.upload_helpers import discard_uploaded_manuscript, persist_uploaded_manuscript


def _is_sample_project(research_case) -> bool:
    return CaseService.is_demo_case(research_case)


def _project_stats(case_id: str) -> dict:
    with session_scope() as session:
        manuscript = session.scalar(
            select(ManuscriptVersion)
            .where(ManuscriptVersion.case_id == case_id)
            .order_by(ManuscriptVersion.version_no.desc())
        )
        confirmed = session.scalar(
            select(func.count(ClaimRevision.id))
            .join(Claim, Claim.id == ClaimRevision.claim_id)
            .where(
                Claim.case_id == case_id,
                ClaimRevision.review_state == "confirmed",
                ClaimRevision.manuscript_version_id == manuscript.id if manuscript else False,
            )
        ) or 0
        latest_scan = session.scalar(
            select(ScanRun)
            .where(ScanRun.case_id == case_id)
            .order_by(ScanRun.created_at.desc())
        )
    return {
        "version": manuscript.version_no if manuscript else 0,
        "file_name": manuscript.file_name if manuscript else "—",
        "confirmed": confirmed,
        "last_scan": (
            latest_scan.finished_at.date().isoformat()
            if latest_scan and latest_scan.finished_at
            else "尚未扫描"
        ),
    }


def _open_project_button(case_id: str, *, key: str) -> None:
    if st.button("打开项目", type="primary", key=key, width="stretch"):
        st.session_state["_next_project_id"] = case_id
        st.session_state["_next_navigation"] = "本周行动"
        st.rerun()


def _render_project_list(cases: list) -> None:
    if not cases:
        empty_state(
            "🗂️", "还没有研究项目",
            "到“新建项目”上传第一篇论文，即可开始监控公开文献的影响。",
        )
        return
    for research_case in cases:
        stats = _project_stats(research_case.id)
        with st.container(border=True):
            title_col, action_col = st.columns([4, 1])
            with title_col:
                st.subheader(research_case.title)
                st.caption(research_case.research_question)
            with action_col:
                _open_project_button(research_case.id, key=f"open-project-{research_case.id}")
            metrics = st.columns(3)
            metrics[0].metric("当前版本", f"v{stats['version']}")
            metrics[1].metric("已确认 Claim", stats["confirmed"])
            metrics[2].metric("最近 Radar", stats["last_scan"])
            st.caption(f"当前文稿：{stats['file_name']}")


def render_home() -> None:
    home_hero()
    page_header(
        "你的研究项目",
        "上传或同步你正在推进的论文；Radar、证据和行动会按项目长期积累。",
    )
    cases = CaseService().list_cases(include_synthetic_demo=False)
    own_cases = [item for item in cases if not _is_sample_project(item)]
    sample_cases = [item for item in cases if _is_sample_project(item)]

    projects_tab, create_tab = st.tabs(["我的项目", "新建项目"])
    with projects_tab:
        _render_project_list(own_cases)
        if sample_cases:
            st.divider()
            st.subheader("示例项目")
            st.caption("示例只用于体验产品，不限制你创建和切换自己的研究项目。")
            _render_project_list(sample_cases)

    with create_tab:
        st.subheader("创建研究项目")
        st.write("支持 `.tex`、`.md` 或文本可提取的 `.pdf`；之后可以继续上传新版本。")
        with st.form("create_case"):
            title = st.text_input("项目/论文标题", placeholder="例如：My retrieval robustness project")
            question = st.text_area("核心研究问题", placeholder="这个项目希望回答什么？")
            uploaded = st.file_uploader(
                "当前文稿", type=["tex", "md", "markdown", "pdf"]
            )
            submitted = st.form_submit_button(
                "创建项目并提取 Claim", type="primary", width="stretch"
            )
        if submitted:
            if not title or not question or uploaded is None:
                st.error("请填写项目标题、研究问题并选择当前文稿。")
            else:
                upload_path = persist_uploaded_manuscript(uploaded)
                try:
                    with st.spinner("正在解析文稿并抽取候选 Claim，可能需要几十秒…"):
                        case_id = CaseService().create_case(
                            title=title,
                            research_question=question,
                            manuscript_path=upload_path,
                        )
                except ValueError as exc:
                    # create_case raises pre-translated Chinese validation
                    # messages (e.g. scanned PDF without a text layer).
                    discard_uploaded_manuscript(upload_path)
                    st.error(str(exc))
                except RuntimeError as exc:
                    discard_uploaded_manuscript(upload_path)
                    st.error(f"项目创建失败：{exc}")
                else:
                    st.session_state["_next_project_id"] = case_id
                    st.session_state["_next_navigation"] = "我的论文"
                    st.rerun()

    st.divider()
    st.markdown(
        "**工作流程** · 导入/同步文稿 → 确认项目 Claim → 搜索最新公开论文 → "
        "采用有用影响 → 执行实验、数据和写作行动"
    )
