"""Project manuscript versions, Claim review and watch settings."""

import re
from math import ceil

import streamlit as st
from sqlalchemy import select

from radar.config import get_settings
from radar.db import session_scope
from radar.llm.factory import describe_llm_setup
from radar.models import Claim, ClaimRevision, ManuscriptVersion, ResearchCase, WatchEntity
from radar.services.case_service import CaseService
from radar.services.claim_service import ClaimService
from radar.services.manuscript_understanding_service import ManuscriptUnderstandingService
from radar.ui.components import (
    CENTRALITY_LABEL,
    REVIEW_STATE_LABEL,
    empty_state,
    page_header,
    render_contract,
    render_llm_setup_guidance,
)
from radar.ui.upload_helpers import persist_uploaded_manuscript


# Keep claim edit/split forms out of the per-claim expanders: with many claims
# the inline forms created hundreds of widgets on every rerun.
CLAIM_PAGE_SIZE = 20
_CLAIM_DIALOG_KEY = "_claim_dialog"
WATCH_ENTITY_TYPE_LABEL = {"lab": "实验室/团队", "author": "作者", "org": "机构"}


@st.dialog("编辑 Claim")
def _edit_claim_dialog(revision) -> None:
    with st.form(f"dialog-edit-{revision.id}"):
        statement = st.text_area("编辑 Claim", value=revision.statement)
        centrality = st.selectbox(
            "重要程度",
            ["core", "major", "minor"],
            index=["core", "major", "minor"].index(revision.centrality),
            format_func=lambda value: CENTRALITY_LABEL.get(value, value),
        )
        falsifiable = st.text_area(
            "可证伪条件", value=revision.falsifiable_condition
        )
        if st.form_submit_button("保存为已确认版本", type="primary", width="stretch"):
            ClaimService().edit_candidate(
                revision.id,
                statement=statement,
                centrality=centrality,
                contract=revision.contract_json,
                falsifiable_condition=falsifiable,
            )
            st.session_state.pop(_CLAIM_DIALOG_KEY, None)
            st.rerun()
    if st.button("取消", key=f"dialog-edit-cancel-{revision.id}", width="stretch"):
        st.session_state.pop(_CLAIM_DIALOG_KEY, None)
        st.rerun()


@st.dialog("拆分 Claim")
def _split_claim_dialog(revision) -> None:
    with st.form(f"dialog-split-{revision.id}"):
        split_text = st.text_area("拆分（每行一条 Claim）")
        if st.form_submit_button("拆分为多条候选", type="primary", width="stretch"):
            try:
                ClaimService().split_candidate(
                    revision.id, split_text.splitlines()
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop(_CLAIM_DIALOG_KEY, None)
                st.rerun()
    if st.button("取消", key=f"dialog-split-cancel-{revision.id}", width="stretch"):
        st.session_state.pop(_CLAIM_DIALOG_KEY, None)
        st.rerun()


def render_case_page(case_id: str) -> None:
    with session_scope() as session:
        research_case = session.get(ResearchCase, case_id)
        versions = list(
            session.scalars(
                select(ManuscriptVersion)
                .where(ManuscriptVersion.case_id == case_id)
                .order_by(ManuscriptVersion.version_no.desc())
            )
        )
        manuscript = next((item for item in versions if item.is_current), None)
        rows = list(
            session.execute(
                select(Claim, ClaimRevision)
                .join(ClaimRevision, ClaimRevision.claim_id == Claim.id)
                .where(
                    Claim.case_id == case_id,
                    ClaimRevision.review_state != "superseded",
                )
                .order_by(ClaimRevision.created_at, ClaimRevision.revision_no.desc())
            )
        )
        rows.sort(
            key=lambda row: (
                int(match.group(1))
                if (match := re.match(r"C(\d+)$", row[0].stable_key))
                else 10_000,
                row[0].stable_key,
            )
        )
        watches = list(
            session.scalars(select(WatchEntity).where(WatchEntity.case_id == case_id))
        )
    if research_case is None:
        st.warning("项目不存在，请返回项目工作台。")
        return

    page_header(
        research_case.title,
        research_case.research_question,
    )
    current_rows = [
        (claim, revision)
        for claim, revision in rows
        if manuscript and revision.manuscript_version_id == manuscript.id
    ]
    metrics = st.columns(4)
    metrics[0].metric("当前文稿", manuscript.file_name if manuscript else "—")
    metrics[1].metric("版本", f"v{manuscript.version_no}" if manuscript else "—")
    metrics[2].metric("当前 Claim", len(current_rows))
    metrics[3].metric(
        "已确认",
        sum(revision.review_state == "confirmed" for _, revision in current_rows),
    )

    sync_result = st.session_state.pop("_manuscript_sync_result", None)
    if sync_result and sync_result.get("case_id") == case_id:
        if sync_result["unchanged"]:
            st.info("上传文件与当前版本内容相同，没有创建重复版本。")
        else:
            st.success(
                f"已同步 v{sync_result['version_no']}：保留 "
                f"{sync_result['carried_claims']} 条稳定 Claim，发现 "
                f"{sync_result['new_candidates']} 条新候选。"
            )
            if sync_result["previous_claims_not_found"]:
                st.warning(
                    f"有 {sync_result['previous_claims_not_found']} 条旧 Claim 未在新版本中找到原文，"
                    "已保留在历史记录中，不会进入当前版本 Radar。"
                )
                lost_claims = sync_result.get("lost_claims") or []
                if lost_claims:
                    with st.expander("查看未承接的 Claim 清单"):
                        for item in lost_claims:
                            st.write(f"- **{item['stable_key']}**：{item['statement']}")

    version_tab, claims_tab, profile_tab, watch_tab = st.tabs(
        ["文稿与版本", "项目主张", "AI 全文画像", "竞争监控"]
    )
    with version_tab:
        st.subheader("同步当前论文")
        st.caption(
            "上传新版本不会覆盖历史文件。系统会保留仍然存在的 Claim，"
            "把新增或改写结果放入待确认队列。"
        )
        with st.form(f"upload-version-{case_id}"):
            uploaded = st.file_uploader(
                "上传新版本", type=["tex", "md", "markdown", "pdf"]
            )
            submitted = st.form_submit_button(
                "同步为新版本", type="primary", width="stretch"
            )
        if submitted:
            if uploaded is None:
                st.error("请选择新版本文稿。")
            else:
                upload_path = persist_uploaded_manuscript(uploaded)
                try:
                    with st.spinner("正在同步新版本：解析文稿、承接稳定 Claim 并抽取新候选…"):
                        result = CaseService().add_manuscript_version(case_id, upload_path)
                except ValueError as exc:
                    st.error(str(exc))
                except RuntimeError as exc:
                    st.error(f"文稿同步失败：{exc}")
                else:
                    st.session_state["_manuscript_sync_result"] = {
                        "case_id": case_id,
                        **result,
                    }
                    st.rerun()

        st.write("**版本历史**")
        st.dataframe(
            [
                {
                    "版本": f"v{version.version_no}",
                    "文件": version.file_name,
                    "状态": "当前" if version.is_current else "历史",
                    "导入时间": version.created_at.isoformat(timespec="minutes"),
                }
                for version in versions
            ],
            hide_index=True,
            width="stretch",
        )

    with claims_tab:
        if not rows:
            empty_state(
                "📝", "尚未找到实验类 Claim 候选",
                "请检查文稿中的实验结论，或同步一个新版本文稿。",
            )
        visible_rows = rows
        if len(rows) > CLAIM_PAGE_SIZE:
            filter_col, page_col = st.columns(2)
            state_filter = filter_col.selectbox(
                "按状态过滤",
                ["全部", "待确认", "已确认", "历史记录"],
                key=f"claim-filter-{case_id}",
            )
            if state_filter == "待确认":
                visible_rows = [
                    (claim, revision)
                    for claim, revision in rows
                    if revision.review_state == "candidate"
                    and manuscript
                    and revision.manuscript_version_id == manuscript.id
                ]
            elif state_filter == "已确认":
                visible_rows = [
                    (claim, revision)
                    for claim, revision in rows
                    if revision.review_state == "confirmed"
                ]
            elif state_filter == "历史记录":
                visible_rows = [
                    (claim, revision)
                    for claim, revision in rows
                    if not manuscript or revision.manuscript_version_id != manuscript.id
                ]
            total_pages = max(1, ceil(len(visible_rows) / CLAIM_PAGE_SIZE))
            page_key = f"claim-page-{case_id}"
            if st.session_state.get(page_key, 1) > total_pages:
                st.session_state[page_key] = total_pages
            page_no = page_col.number_input(
                f"页码（共 {total_pages} 页）", 1, total_pages, key=page_key
            )
            visible_rows = visible_rows[
                (page_no - 1) * CLAIM_PAGE_SIZE : page_no * CLAIM_PAGE_SIZE
            ]
        for index, (claim, revision) in enumerate(visible_rows):
            is_current = bool(manuscript and revision.manuscript_version_id == manuscript.id)
            if is_current and revision.review_state == "confirmed":
                state_icon = "✓"
            elif is_current:
                state_icon = "○"
            else:
                state_icon = "↺"
            with st.expander(
                f"{state_icon} {claim.stable_key} · {CENTRALITY_LABEL.get(revision.centrality, revision.centrality)} · {revision.statement}",
                expanded=is_current and revision.review_state == "candidate" and index == 0,
            ):
                source_version = next(
                    (
                        version.version_no
                        for version in versions
                        if version.id == revision.manuscript_version_id
                    ),
                    "?",
                )
                st.caption(
                    f"状态：{REVIEW_STATE_LABEL.get(revision.review_state, revision.review_state)} · "
                    f"来自 v{source_version} · {revision.source_locator}"
                )
                if not is_current:
                    st.warning("这条 Claim 未在当前版本中精确匹配，只保留为历史记录。")
                st.markdown(f"> {revision.source_quote}")
                st.write("**实验条件（Claim 合同）**")
                render_contract(revision.contract_json)
                st.write("**可证伪条件**", revision.falsifiable_condition)
                if is_current and revision.review_state == "candidate":
                    col1, col2 = st.columns(2)
                    if col1.button(
                        "确认 Claim",
                        key=f"confirm-{revision.id}",
                        type="primary",
                        width="stretch",
                    ):
                        try:
                            ClaimService().confirm_candidate(revision.id)
                        except ValueError as exc:
                            if str(exc) == "span_failed":
                                st.error(
                                    "确认失败：这条 Claim 的原文引文未能在当前文稿中精确定位，"
                                    "请先“编辑”修正后再确认。"
                                )
                            else:
                                st.error(f"确认失败：{exc}")
                        else:
                            st.rerun()
                    if col2.button(
                        "拒绝",
                        key=f"reject-{revision.id}",
                        width="stretch",
                    ):
                        ClaimService().reject_candidate(revision.id)
                        st.rerun()
                    edit_col, split_col = st.columns(2)
                    if edit_col.button(
                        "编辑", key=f"open-edit-{revision.id}", width="stretch"
                    ):
                        st.session_state[_CLAIM_DIALOG_KEY] = ("edit", revision.id)
                        st.rerun()
                    if split_col.button(
                        "拆分", key=f"open-split-{revision.id}", width="stretch"
                    ):
                        st.session_state[_CLAIM_DIALOG_KEY] = ("split", revision.id)
                        st.rerun()
        pending_dialog = st.session_state.get(_CLAIM_DIALOG_KEY)
        if pending_dialog:
            kind, revision_id = pending_dialog
            target = next(
                (revision for _, revision in rows if revision.id == revision_id), None
            )
            if target is None:
                st.session_state.pop(_CLAIM_DIALOG_KEY, None)
            elif kind == "edit":
                _edit_claim_dialog(target)
            else:
                _split_claim_dialog(target)

    with profile_tab:
        manuscript_profile = (
            ManuscriptUnderstandingService.latest_profile(case_id)
            if manuscript is not None
            else None
        )
        confirmed_current = sum(
            revision.review_state == "confirmed" for _, revision in current_rows
        )
        if confirmed_current:
            llm_setup = describe_llm_setup(get_settings())
            if not llm_setup["configured"]:
                render_llm_setup_guidance(llm_setup)
            else:
                analysis_model = llm_setup["model"] or "AI"
                if st.button(
                    f"用 {analysis_model} 分析当前版本全文",
                    type="primary",
                    key=f"analyze-manuscript-{case_id}",
                ):
                    try:
                        with st.spinner(f"{analysis_model} 正在理解当前文稿和已确认 Claim…"):
                            ManuscriptUnderstandingService().analyze(case_id)
                    except ValueError as exc:
                        if str(exc).startswith("manuscript_profile_claim_keys_invalid"):
                            st.error("AI 返回的画像与已确认 Claim 不完全对应，请重试一次。")
                        else:
                            st.error(f"全文分析失败：{exc}")
                    except RuntimeError as exc:
                        st.error(f"全文分析失败：{exc}")
                    else:
                        st.rerun()
                if llm_setup["mode"] == "local":
                    st.caption(f"会用本地模型 {analysis_model} 分析当前完整文稿和已确认 Claim。")
                else:
                    st.caption(f"会把当前完整文稿和已确认 Claim 发送给 {analysis_model}。")
        else:
            st.info("先在“项目主张”中确认至少一条当前版本 Claim。")
        if manuscript_profile is None:
            st.info("当前版本尚未生成全文理解画像。")
        else:
            st.subheader(manuscript_profile.title)
            st.write("**研究问题**", manuscript_profile.research_problem)
            st.write("**核心论点**", manuscript_profile.central_thesis)
            overview_a, overview_b = st.columns(2)
            with overview_a:
                st.write("**主要贡献**")
                for item in manuscript_profile.contributions:
                    st.markdown(f"- {item}")
                st.write("**关键发现**")
                for item in manuscript_profile.key_findings:
                    st.markdown(f"- {item}")
            with overview_b:
                st.write("**局限**")
                for item in manuscript_profile.limitations:
                    st.markdown(f"- {item}")
                st.write("**每周监控主题**")
                for item in manuscript_profile.watch_topics:
                    st.markdown(f"- {item}")
            st.write("**已确认 Claim 画像**")
            for item in manuscript_profile.claim_profiles:
                with st.expander(
                    f"{item.stable_key} · {CENTRALITY_LABEL.get(item.role, item.role)} · {item.claim_summary}"
                ):
                    render_contract(item.contract.model_dump())
                    for boundary in item.boundary_conditions:
                        st.markdown(f"- {boundary}")

    with watch_tab:
        if watches:
            for watch in watches:
                name_col, remove_col = st.columns([4, 1])
                with name_col:
                    st.markdown(
                        f"**{watch.canonical_name}** · "
                        f"`{WATCH_ENTITY_TYPE_LABEL.get(watch.entity_type, watch.entity_type)}`  \n"
                        f"别名：{', '.join(watch.aliases_json)}"
                    )
                if remove_col.button(
                    "删除", key=f"remove-watch-{watch.id}", width="stretch"
                ):
                    CaseService().remove_watch_entity(watch.id)
                    st.rerun()
        else:
            st.info("当前项目尚未配置竞争对手别名。")
        with st.form(f"add-watch-{case_id}"):
            st.write("**添加监控对象**")
            canonical_name = st.text_input("团队/作者名称")
            entity_type = st.selectbox(
                "类型",
                list(WATCH_ENTITY_TYPE_LABEL),
                format_func=lambda value: WATCH_ENTITY_TYPE_LABEL.get(value, value),
            )
            aliases_text = st.text_input("别名（用逗号分隔，可留空）")
            if st.form_submit_button("添加监控", type="primary", width="stretch"):
                if not canonical_name.strip():
                    st.error("请填写团队/作者名称。")
                else:
                    CaseService().add_watch_entity(
                        case_id,
                        entity_type=entity_type,
                        canonical_name=canonical_name.strip(),
                        aliases=[
                            alias.strip()
                            for alias in aliases_text.split(",")
                            if alias.strip()
                        ],
                    )
                    st.rerun()
