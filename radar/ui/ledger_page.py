"""Claim Ledger, Evidence Pack, Patch Review, and audit UI."""

import json

import streamlit as st
from sqlalchemy import select

from radar.db import session_scope
from radar.llm.factory import describe_llm_setup
from radar.models import Claim, ModelRun, PatchProposal, ResearchCase
from radar.services.case_service import CaseService, DEMO_CASE_ID
from radar.services.action_service import ActionService
from radar.services.ledger_service import LedgerService
from radar.services.patch_service import PatchService
from radar.services.report_service import ReportService
from radar.ui.components import (
    APPROVAL_STATE_LABEL,
    ATTENTION_LABEL,
    COMPARABILITY_LABEL,
    EDIT_CLASS_LABEL,
    IMPACT_MODE_LABEL,
    REVIEW_STATE_LABEL,
    SUGGESTED_ACTION_LABEL,
    VALIDATION_LABEL,
    health_badge,
    empty_state,
    label_for,
    page_header,
    render_llm_setup_guidance,
    render_validation_checklist,
    request_confirmation,
    state_badge,
    validation_summary,
)


def _reset_demo_case() -> None:
    CaseService().load_demo_case(reset=True)
    st.session_state.pop("selected_impact_id", None)


_PATCH_GENERATE_ERROR_LABEL = {
    "candidate_cannot_generate_patch": "这条影响还未人工采用，不能生成改写方案。",
    "no_material_change_cannot_generate_patch": "判断为“无需改变”的影响不需要改写方案。",
    "patch_source_missing": "触发论文的来源记录缺失，无法生成改写方案。",
}


def _patch_generate_error_message(code: str) -> str:
    """Translate PatchService ValueError codes into user-facing Chinese."""

    if code.startswith("patch_generation_validation_failed"):
        return "AI 生成的改写未通过自动校验，请重试生成；仍失败可换一条影响或稍后再试。"
    return _PATCH_GENERATE_ERROR_LABEL.get(code, f"无法生成改写方案：{code}")


def _approve_error_message(validations: dict | None) -> str:
    """Explain an approval refusal, naming the failed validation checks."""

    failed = [label_for(VALIDATION_LABEL, key) for key, passed in (validations or {}).items() if not passed]
    message = "这版改写未通过校验，不能批准。"
    if failed:
        message += "未通过项：" + "；".join(failed) + "。"
    return message + "请查看上方校验清单，修正后重新生成。"


def render_ledger_page(case_id: str) -> None:
    with session_scope() as session:
        research_case = session.get(ResearchCase, case_id)
        claims = list(session.scalars(select(Claim).where(Claim.case_id == case_id).order_by(Claim.stable_key)))
    if research_case is None:
        st.warning("项目不存在，请返回项目工作台。")
        return
    page_header(
        "改进工作台",
        "核对已采用影响，生成可审阅的最小改写；原论文文件永远不会被自动覆盖。",
    )
    st.info(
        "工作流：① 在文献雷达核对条件矩阵和证据 → ② 采用或修正影响 → "
        "③ AI 生成最小改写 → ④ 验证数字、引用和原文定位 → ⑤ 人工批准并下载。"
    )
    with st.expander("三个真实论文例子：影响应该怎样变成改进", expanded=False):
        st.markdown(
            "- **边界条件**：[*Emergent Abilities of Large Language Models*]"
            "(https://arxiv.org/abs/2206.07682) 与 "
            "[*Are Emergent Abilities ... a Mirage?*]"
            "(https://arxiv.org/abs/2304.15004)。如果突变来自 metric，动作应是补连续指标、"
            "收窄 emergence 表述和增加 limitation，而不是简单写成被反驳。\n"
            "- **不同任务，不能直接反驳**：[*TAP-RAG*]"
            "(https://arxiv.org/abs/2607.18917v1) 与当前 E-Agent 项目。"
            "任务和数据不一致时，应进入跨设置 comparison 或继续观察。\n"
            "- **Prior art / 定位变化**：[*Agentic RAG SoK*]"
            "(https://arxiv.org/abs/2603.07379v1)。综述不直接改变实验数字，"
            "但可以改为 `prior_art + cite`，生成 Related Work 改写。"
        )
    if not claims:
        empty_state(
            "🧾", "这个项目还没有 Claim",
            "先到“我的论文”确认至少一条核心 Claim，再回来生成改写方案。",
        )
        if st.button("去确认 Claim", type="primary"):
            st.session_state["_next_navigation"] = "我的论文"
            st.rerun()
        ledger = None
    else:
        claim_id = st.selectbox(
            "选择要改进的 Claim", [claim.id for claim in claims],
            format_func=lambda value: next(
                f"{claim.stable_key}" for claim in claims if claim.id == value
            ),
        )
        ledger = LedgerService().get_claim_ledger(claim_id)
    if ledger is not None:
        st.subheader(f"{ledger['stable_key']} · {ledger['statement']}")
        health = ledger["health"]
        attention = ActionService().claim_attention_state(claim_id)
        st.markdown(
            f"Claim 状态 {health_badge(health)} ・ 当前 Radar 关注 "
            f"{state_badge(ATTENTION_LABEL, attention)}"
        )
        if health == "active":
            st.caption("当前没有已人工确认的支持/挑战/完整性影响；待确认的判断不会改变本状态。")

        supports_tab, challenges_tab, integrity_tab = st.tabs(
            [f"支持证据 · {len(ledger['supports'])}", f"挑战证据 · {len(ledger['challenges'])}", f"完整性 · {len(ledger['integrity'])}"]
        )
        for tab, entries in zip(
            [supports_tab, challenges_tab, integrity_tab],
            [ledger["supports"], ledger["challenges"], ledger["integrity"]],
        ):
            with tab:
                if not entries:
                    st.caption("暂无人工确认记录。")
                for entry in entries:
                    st.markdown(
                        f"**{entry['source_title']}** · "
                        f"{IMPACT_MODE_LABEL.get(entry['impact_mode'], entry['impact_mode'])} · "
                        f"{REVIEW_STATE_LABEL.get(entry['review_state'], entry['review_state'])}"
                    )
                    st.markdown(f"> {entry['evidence'].get('quote', '')}")
                    st.caption(entry["evidence"].get("locator", ""))

        pack = ReportService().get_evidence_pack(claim_id)
        st.download_button(
            "导出证据包（JSON）", json.dumps(pack, ensure_ascii=False, indent=2),
            file_name=f"evidence-pack-{ledger['stable_key']}.json", mime="application/json",
        )

    st.divider()
    st.subheader("最小改写方案")
    llm_setup = describe_llm_setup()
    confirmed_impacts = ledger["confirmed_decisions"] if ledger else []
    if not confirmed_impacts:
        st.info("先到“文献雷达”核对并采用一条材料性影响，才能生成改写方案。")
    elif not llm_setup["configured"]:
        render_llm_setup_guidance(llm_setup)
    for entry in confirmed_impacts:
        with st.expander(
            f"{entry['source_title']} · "
            f"{IMPACT_MODE_LABEL.get(entry['impact_mode'], entry['impact_mode'])} · "
            f"{SUGGESTED_ACTION_LABEL.get(entry['action'], entry['action'])}",
            expanded=False,
        ):
            if entry.get("source_url"):
                st.markdown(f"[查看触发论文原文]({entry['source_url']})")
            st.markdown(f"> {entry['evidence'].get('quote', '')}")
            policy = PatchService.action_policy(entry["impact_mode"])
            st.caption(
                f"建议落点：{policy['target']} · 改进方式：{policy['change']} · "
                f"条件可比性：{COMPARABILITY_LABEL.get(entry.get('comparability', 'unknown'), '未知')}"
            )
            if st.button(
                "用 AI 生成最小改写方案",
                key=f"generate-{entry['id']}",
                type="primary",
                disabled=not llm_setup["configured"],
            ):
                try:
                    with st.spinner("AI 正在根据全文、条件差异和精确证据生成改写…"):
                        PatchService().generate_patch(entry["id"])
                except ValueError as exc:
                    st.error(_patch_generate_error_message(str(exc)))
                except RuntimeError as exc:
                    st.error(f"AI 改写失败：{exc}")
                else:
                    st.rerun()

    with session_scope() as session:
        patches = list(
            session.scalars(
                select(PatchProposal).where(PatchProposal.case_id == case_id).order_by(PatchProposal.created_at.desc())
            )
        )
    for patch in patches:
        with st.expander(
            f"{EDIT_CLASS_LABEL.get(patch.edit_class, patch.edit_class)} · "
            f"{APPROVAL_STATE_LABEL.get(patch.approval_state, patch.approval_state)} · "
            f"{patch.target_locator}",
            expanded=True,
        ):
            before, after = st.columns(2)
            before.markdown("**改写前**")
            before.code(patch.before_text, language=None)
            after.markdown("**改写后**")
            after.code(patch.after_text, language=None)
            st.write("**自动验证结果**")
            render_validation_checklist(patch.validations_json)
            approve, reject = st.columns(2)
            if approve.button("批准并允许导出", key=f"approve-{patch.id}", type="primary", width="stretch"):
                try:
                    PatchService().approve_patch(patch.id)
                except ValueError:
                    st.error(_approve_error_message(patch.validations_json))
                else:
                    st.rerun()
            if reject.button("拒绝这版改写", key=f"reject-patch-{patch.id}", width="stretch"):
                request_confirmation(
                    key=f"reject-patch-{patch.id}",
                    title="拒绝这版改写",
                    body="拒绝后该改写方案会标记为已拒绝；之后可以重新生成新的改写方案。",
                    confirm_label="确认拒绝",
                    on_confirm=lambda patch_id=patch.id: PatchService().reject_patch(patch_id),
                )
                st.rerun()
            if patch.approval_state == "approved":
                st.download_button(
                    "下载已批准改写", PatchService.export_markdown(patch),
                    file_name=f"patch-{patch.id}.md", mime="text/markdown", key=f"download-{patch.id}",
                )

    st.divider()
    with st.expander("证据、模型运行与审计记录"):
        audit_json = ReportService().audit_export(case_id)
        events = json.loads(audit_json)
        st.caption(f"共 {len(events)} 条审计事件（仅最近 500 条）· 仅保存在本机")
        st.dataframe(events, hide_index=True, width="stretch")
        with session_scope() as session:
            runs = list(session.scalars(select(ModelRun).order_by(ModelRun.created_at.desc()).limit(20)))
        if runs:
            st.write("**模型运行与确定性阶段（最近 20 条）**")
            st.dataframe(
                [
                    {
                        "阶段": run.stage, "提供方": run.provider, "模型": run.model,
                        "耗时(ms)": run.latency_ms, "估算成本": run.estimated_cost,
                        "验证结果": validation_summary(run.validation_json),
                    }
                    for run in runs
                ],
                hide_index=True, width="stretch",
            )
        st.download_button(
            "导出审计记录（JSON）", audit_json, file_name="research-radar-audit.json", mime="application/json"
        )
    if case_id == DEMO_CASE_ID:
        if st.button("重置 Demo 决策", help="仅重建 Golden Demo，不修改上传的其他项目。"):
            request_confirmation(
                key="reset-demo-decisions",
                title="重置 Demo 决策",
                body="将删除并重建 Golden Demo 项目的全部扫描、影响和决策记录；你自己上传的项目不受影响。",
                confirm_label="确认重置",
                on_confirm=_reset_demo_case,
            )
            st.rerun()
