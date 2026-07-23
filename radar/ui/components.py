"""Shared Streamlit presentation helpers."""

from urllib.parse import quote

import streamlit as st

from radar.config import get_settings
from radar.llm.factory import describe_llm_setup
from radar.services.review_service import ReviewService


SEVERITY_ICON = {"critical": "🔴", "review": "🟠", "informative": "🔵"}
SEVERITY_LABEL = {"critical": "紧急", "review": "需审查", "informative": "参考"}
STANCE_LABEL = {
    "supports": "支持", "challenges": "挑战", "neutral": "中性", "uncertain": "信息不足"
}
HEALTH_LABEL = {
    "active": "有效", "corroborated": "已被支持", "contested": "存在争议",
    "revalidation_required": "需要重新验证",
}
ATTENTION_LABEL = {
    "stable": "稳定",
    "new_support": "出现新的支持证据",
    "needs_review": "需要审查",
    "disputed": "存在争议 · 需要团队决策",
    "competitor_pressure": "竞争压力",
    "revalidation_required": "需要重新验证",
}
REVIEW_STATE_LABEL = {
    "candidate": "待确认",
    "confirmed": "已确认",
    "edited": "已修改确认",
    "dismissed": "未采用",
    "informative": "参考信息",
    "rejected": "已拒绝",
    "superseded": "已被新版本替代",
}
PRIORITY_LABEL = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}
COMPARABILITY_LABEL = {
    "compatible": "可比", "partial": "部分可比",
    "incompatible": "不可比", "unknown": "未知",
}
ACTION_STATUS_LABEL = {
    "proposed": "待采用", "open": "已采用 · 待开始", "in_progress": "进行中",
    "done": "已完成", "dismissed": "已关闭",
}
SCAN_STATUS_LABEL = {
    "pending": "排队中", "running": "扫描中", "cancel_requested": "取消中",
    "completed": "已完成", "failed": "失败", "interrupted": "已中断", "cancelled": "已取消",
}
IMPACT_MODE_LABEL = {
    "replication": "独立复现",
    "boundary_condition": "边界条件",
    "method_substitution": "方法替代",
    "prior_art": "在先工作",
    "research_integrity": "研究完整性",
    "no_material_change": "无材料性变化",
}
SUGGESTED_ACTION_LABEL = {
    "cite": "引用",
    "add_boundary_discussion": "补边界讨论",
    "run_comparison": "跑对比实验",
    "narrow_claim": "收窄 Claim",
    "team_review": "团队评审",
    "revalidate": "重新验证",
    "watch": "继续观察",
    "no_action": "无需行动",
}
TRUST_STATE_LABEL = {
    "generated": "已生成", "grounded": "已定位",
    "verified": "已核验", "blocked": "未通过校验",
}
CONDITION_STATUS_LABEL = {
    "match": "一致",
    "compatible_alias": "别名一致",
    "partial": "部分一致",
    "mismatch": "不一致",
    "unknown": "未知",
}
CENTRALITY_LABEL = {"core": "核心", "major": "重要", "minor": "次要"}
EDIT_CLASS_LABEL = {
    "add_citation": "补充引用",
    "add_boundary_discussion": "补充边界讨论",
    "add_limitation": "增加局限说明",
    "qualify_claim": "收窄表述",
    "experiment_todo": "实验待办",
}
APPROVAL_STATE_LABEL = {"candidate": "待审批", "approved": "已批准", "rejected": "已拒绝"}
# Keep in sync with PatchService._validate keys.
VALIDATION_LABEL = {
    "impact_confirmed": "影响已经人工采用",
    "before_text_exact": "改写前文本可在当前文稿中精确定位",
    "citations_resolved": "所有引用来源均已登记",
    "citation_marker_safe": "未引入新的数字编号引用标记",
    "locked_numbers_unchanged": "原文数字在改写后保持不变",
    "original_file_untouched": "原论文文件未被修改",
}
CONTRACT_FIELD_LABEL = {
    "task": "任务",
    "dataset": "数据集",
    "split": "数据划分",
    "metric": "指标",
    "comparator": "对比基线",
    "scope": "适用范围",
}

PUBLICATION_LABEL = {
    "preprint": "预印本",
    "journal_article": "已发表版本",
    "conference_paper": "会议论文",
    "other": "公开论文",
}

IMPACT_MODES = [
    "replication", "boundary_condition", "method_substitution", "prior_art",
    "research_integrity", "no_material_change",
]
SUGGESTED_ACTIONS = [
    "cite", "add_boundary_discussion", "run_comparison", "narrow_claim",
    "team_review", "revalidate", "watch", "no_action",
]

_BADGE_COLOR = {
    "critical": "red", "high": "orange", "medium": "blue", "low": "gray",
    "review": "orange",
    "supports": "green", "challenges": "red", "neutral": "gray", "uncertain": "yellow",
    "active": "green", "corroborated": "green", "contested": "orange",
    "revalidation_required": "red",
    "candidate": "orange", "confirmed": "green", "edited": "green",
    "dismissed": "gray", "informative": "blue", "rejected": "gray", "superseded": "gray",
}


# Design tokens (kept in sync with .streamlit/config.toml):
#   accent deep teal #0E7490 on a neutral gray scale; one 8/10px radius,
#   one hairline border + two-level shadow, and a four-step type scale
#   (page title 1.7rem / section 1.05-1.3rem / body .95rem / caption .8rem).
_THEME_CSS = """
<style>
:root {
  --rr-accent: #0e7490;
  --rr-accent-hover: #155e75;
  --rr-accent-soft: #f0fafb;
  --rr-ink: #111827;
  --rr-body: #374151;
  --rr-muted: #6b7280;
  --rr-faint: #9ca3af;
  --rr-border: #e5e7eb;
  --rr-border-strong: #d1d5db;
  --rr-surface: #ffffff;
  --rr-bg: #f8f9fa;
  --rr-success: #047857;
  --rr-warning: #b45309;
  --rr-danger: #b91c1c;
  --rr-radius: 10px;
  --rr-radius-sm: 8px;
  --rr-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
  --rr-shadow-hover: 0 6px 16px rgba(16, 24, 40, 0.08);
  --rr-font: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei",
    "Segoe UI", system-ui, sans-serif;
  --rr-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

html, body, .stApp { font-family: var(--rr-font); }
.stApp { background: var(--rr-bg); color: var(--rr-ink); }

/* Keep the wide layout from feeling loose. */
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 2.2rem; }

/* Type scale */
h1 { font-size: 1.7rem !important; font-weight: 700 !important; letter-spacing: -0.02em; }
h2 { font-size: 1.3rem !important; font-weight: 650 !important; letter-spacing: -0.015em; }
h3 { font-size: 1.05rem !important; font-weight: 650 !important; letter-spacing: -0.01em; }
p, li { font-size: 0.95rem; line-height: 1.65; }
[data-testid="stCaptionContainer"] { color: var(--rr-muted); font-size: 0.8rem; }

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--rr-surface);
  border: 1px solid var(--rr-border);
  border-radius: var(--rr-radius);
  padding: 14px 16px;
  box-shadow: var(--rr-shadow);
}
[data-testid="stMetricLabel"] p { color: var(--rr-muted); font-size: 0.78rem; font-weight: 500; }
[data-testid="stMetricValue"] { color: var(--rr-ink); font-weight: 700; }

/* Bordered containers: softer hairline + gentle hover lift */
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--rr-border);
  border-radius: var(--rr-radius);
  background: var(--rr-surface);
  box-shadow: var(--rr-shadow);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: var(--rr-border-strong);
  box-shadow: var(--rr-shadow-hover);
}

/* Buttons: flat primary accent, quiet outlined secondary */
button[data-testid^="stBaseButton-primary"] {
  background: var(--rr-accent);
  border: 1px solid var(--rr-accent);
  border-radius: var(--rr-radius-sm);
  font-weight: 600;
}
button[data-testid^="stBaseButton-primary"]:hover {
  background: var(--rr-accent-hover);
  border-color: var(--rr-accent-hover);
}
button[data-testid^="stBaseButton-secondary"] {
  background: var(--rr-surface);
  border: 1px solid var(--rr-border-strong);
  border-radius: var(--rr-radius-sm);
  color: var(--rr-body);
  font-weight: 500;
}
button[data-testid^="stBaseButton-secondary"]:hover {
  border-color: var(--rr-accent);
  color: var(--rr-accent);
}

/* Tabs */
[data-testid="stTabs"] [role="tab"] { color: var(--rr-muted); font-weight: 500; }
[data-testid="stTabs"] [aria-selected="true"] { color: var(--rr-accent); font-weight: 600; }

/* Expanders */
[data-testid="stExpander"] details {
  border: 1px solid var(--rr-border);
  border-radius: var(--rr-radius);
  background: var(--rr-surface);
}
[data-testid="stExpander"] details summary { font-weight: 500; }

/* Progress + alerts + dialogs */
[data-testid="stProgress"] div[role="progressbar"] { background-color: var(--rr-accent); }
[data-testid="stAlert"] { border-radius: var(--rr-radius-sm); }
[data-testid="stDialog"] > div { border-radius: 14px; }

/* Sidebar: dark slate with quiet sectioning */
[data-testid="stSidebar"] { background: #0d1420; }
[data-testid="stSidebar"] * { color: #e6eaf2; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #8fa1b3; }
[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.08); }
[data-testid="stSidebar"] button[data-testid^="stBaseButton-secondary"] {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.16);
  color: #e6eaf2;
}
[data-testid="stSidebar"] button[data-testid^="stBaseButton-secondary"]:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.3);
  color: #ffffff;
}

/* Brand block (sidebar + home hero) */
.rr-brand { display: flex; align-items: center; gap: 10px; padding: 4px 2px 10px; }
.rr-brand-mark {
  width: 32px; height: 32px; flex: none; border-radius: 9px;
  background: linear-gradient(135deg, #0e7490, #164e63);
  display: flex; align-items: center; justify-content: center;
  color: #ffffff; font-size: 15px; font-weight: 700;
}
.rr-brand-name { font-weight: 700; font-size: 1rem; letter-spacing: -0.01em; line-height: 1.25; }
.rr-brand-tag { font-size: 0.72rem; color: #8fa1b3; line-height: 1.3; }
.rr-hero {
  padding: 18px 22px; margin-bottom: 18px;
  border-radius: var(--rr-radius);
  background: linear-gradient(135deg, #123a47 0%, #0e7490 100%);
  box-shadow: var(--rr-shadow);
}
.rr-hero-name { color: #ffffff; font-size: 1.05rem; font-weight: 700; letter-spacing: 0.01em; }
.rr-hero-tag { color: rgba(255, 255, 255, 0.85); font-size: 0.85rem; margin-top: 2px; }

/* Sidebar section labels and pending pill */
.rr-section-label {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: #71809a; margin: 14px 0 4px;
}
.rr-pill {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 0.75rem; font-weight: 600;
}
.rr-pill-warn { background: #422006; color: #fbbf24; border: 1px solid #713f12; }
.rr-pill-ok { background: #052e22; color: #6ee7b7; border: 1px solid #065f46; }

/* Agent working panel (scan progress) */
.rr-agent-head { display: flex; align-items: center; gap: 8px; font-weight: 650; }
.rr-agent-pulse {
  width: 8px; height: 8px; flex: none; border-radius: 50%;
  background: var(--rr-accent); animation: rr-pulse 1.2s ease-in-out infinite;
}
@keyframes rr-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Unified empty state */
.rr-empty {
  text-align: center; padding: 34px 20px; margin: 8px 0 16px;
  border: 1px dashed var(--rr-border-strong); border-radius: var(--rr-radius);
  background: var(--rr-surface);
}
.rr-empty-icon { font-size: 1.6rem; }
.rr-empty-title { font-weight: 650; margin-top: 6px; }
.rr-empty-hint { color: var(--rr-muted); font-size: 0.85rem; margin-top: 2px; }

/* Evidence quote block */
.evidence {
  border-left: 3px solid var(--rr-accent);
  padding: 12px 14px; background: var(--rr-accent-soft);
  border-radius: 0 var(--rr-radius-sm) var(--rr-radius-sm) 0;
  font-size: 0.92rem; line-height: 1.6;
}
.locator { color: var(--rr-muted); font-family: var(--rr-mono); font-size: 0.78rem; margin-top: 6px; }
.trust-note { color: var(--rr-muted); font-size: 0.85rem; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str | None = None) -> None:
    """Uniform page header: title plus one muted line explaining the page."""

    st.title(title)
    if subtitle:
        st.caption(subtitle)


def empty_state(icon: str, title: str, hint: str) -> None:
    """Unified empty state: centered icon, one-line title and a guiding hint."""

    st.markdown(
        f'<div class="rr-empty"><div class="rr-empty-icon">{icon}</div>'
        f'<div class="rr-empty-title">{title}</div>'
        f'<div class="rr-empty-hint">{hint}</div></div>',
        unsafe_allow_html=True,
    )


def home_hero() -> None:
    """Lightweight brand strip shown at the top of the project workspace."""

    st.markdown(
        '<div class="rr-hero"><div class="rr-hero-name">Research Radar</div>'
        '<div class="rr-hero-tag">盯住公开文献对你论文的影响，把变化变成可执行的行动。</div></div>',
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.markdown(
        '<div class="rr-brand"><div class="rr-brand-mark">⌖</div>'
        '<div><div class="rr-brand-name">Research Radar</div>'
        '<div class="rr-brand-tag">文献影响监控 Agent</div></div></div>',
        unsafe_allow_html=True,
    )


def sidebar_section(label: str) -> None:
    st.markdown(f'<div class="rr-section-label">{label}</div>', unsafe_allow_html=True)


def pending_pill(pending: int) -> None:
    """Pending-action summary as a pill; neutral when there is nothing to do."""

    if pending:
        st.sidebar.markdown(
            f'<span class="rr-pill rr-pill-warn">{pending} 项待处理行动</span>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<span class="rr-pill rr-pill-ok">没有待处理行动</span>',
            unsafe_allow_html=True,
        )


def evidence_block(label: str, evidence: dict) -> None:
    st.markdown(f"**{label}**")
    st.markdown(
        f'<div class="evidence">{evidence.get("quote", "")}</div>'
        f'<div class="locator">{evidence.get("locator", "未登记位置")}</div>',
        unsafe_allow_html=True,
    )


def source_venue_label(source) -> str:
    venue = (source.venue or "").strip()
    publication_type = source.publication_type or "preprint"
    if not venue or venue.lower() == "arxiv":
        return "arXiv 预印本"
    return f"{venue} · {PUBLICATION_LABEL.get(publication_type, '公开论文')}"


def source_links_markdown(source) -> str:
    links = [f"[查看原文]({source.url})"]
    if source.pdf_url:
        links.append(f"[打开 PDF 全文]({source.pdf_url})")
    if source.doi:
        doi_url = f"https://doi.org/{quote(source.doi, safe='/():')}"
        links.append(f"[DOI: {source.doi}]({doi_url})")
    else:
        links.append("DOI：未登记")
    return " · ".join(links)


def render_source_traceability(source, *, show_title: bool = True) -> None:
    """Render the same audit-friendly source metadata everywhere."""

    if show_title:
        st.markdown(f"**[{source.title}]({source.url})**")
    published = source.published_at.date().isoformat() if source.published_at else "日期未登记"
    st.caption(f"发表载体：{source_venue_label(source)} · 公开日期：{published}")
    if source.authors_json:
        st.caption("作者：" + ", ".join(source.authors_json))
    st.markdown(source_links_markdown(source))


def render_llm_setup_guidance(setup: dict | None = None) -> None:
    """Show actionable Chinese setup guidance when no analysis LLM is configured.

    Renders nothing when a model is already configured, so callers can invoke
    it unconditionally in place of a generic "not configured" warning.
    """

    setup = setup or describe_llm_setup(get_settings())
    if setup["configured"]:
        return
    st.warning("尚未配置可用的分析模型，AI 分析功能暂时不可用。")
    st.markdown(
        "请在左侧导航的 **设置** 页选择远程 API 或本地 Ollama，填入对应信息并保存，"
        "**保存后立即生效，无需重启**。"
    )
    with st.expander("高级选项：直接编辑 .env 文件"):
        missing = "、".join(f"`{name}`" for name in setup["missing"])
        st.markdown(
            f"远程模型缺少环境变量：{missing}。也可以在项目根目录的 `.env` 文件中"
            "按以下任一方案补全，保存后重启应用生效。"
        )
        remote_tab, local_tab = st.tabs(
            ["方案一：远程 API（DeepSeek 示例）", "方案二：本地模型（Ollama，文稿不出本机）"]
        )
        with remote_tab:
            st.code(
                "LLM_PROVIDER=deepseek\n"
                "LLM_API_KEY=sk-你的密钥\n"
                "LLM_MODEL=deepseek-chat\n"
                "LLM_BASE_URL=https://api.deepseek.com",
                language="bash",
            )
            st.caption("分析时会把文稿全文发送给远程 API。")
        with local_tab:
            st.code(
                "LOCAL_LLM_MODEL=qwen3:4b\n"
                "LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
                language="bash",
            )
            st.caption("需先安装并启动 Ollama 并拉取对应模型；配置后优先于远程 API。")


def label_for(labels: dict[str, str], value: str) -> str:
    """Look up a Chinese label, falling back to the raw enum value."""

    return labels.get(value, value)


def badge_markdown(text: str, color: str = "gray") -> str:
    """Inline Streamlit badge markup, to be rendered via st.markdown."""

    return f":{color}-badge[{text}]"


def state_badge(labels: dict[str, str], value: str) -> str:
    return badge_markdown(label_for(labels, value), _BADGE_COLOR.get(value, "gray"))


def priority_badge(value: str) -> str:
    return state_badge(PRIORITY_LABEL, value)


def health_badge(value: str) -> str:
    return state_badge(HEALTH_LABEL, value)


def stance_badge(value: str) -> str:
    return state_badge(STANCE_LABEL, value)


def review_state_badge(value: str) -> str:
    return state_badge(REVIEW_STATE_LABEL, value)


def impact_status_badges(impact) -> str:
    """One-line badge summary of an impact's severity, stance, mode and state."""

    return " ".join(
        [
            state_badge(SEVERITY_LABEL, impact.severity),
            stance_badge(impact.stance),
            badge_markdown(label_for(IMPACT_MODE_LABEL, impact.impact_mode), "blue"),
            review_state_badge(impact.review_state),
        ]
    )


def impact_guidance_callout(impact) -> tuple[str, str, str]:
    """Return (title, text, level) for the adoption guidance of an impact."""

    title, text = adoption_guidance(impact)
    if impact.review_state in {"confirmed", "edited"}:
        level = "success"
    elif impact.review_state == "dismissed":
        level = "info"
    else:
        level = "warning"
    return title, text, level


def render_impact_status(impact) -> None:
    """Badges plus guidance callout; shared by the Radar queue and papers tab."""

    st.markdown(impact_status_badges(impact))
    title, text, level = impact_guidance_callout(impact)
    message = f"**{title}：** {text}"
    if level == "success":
        st.success(message)
    elif level == "info":
        st.info(message)
    else:
        st.warning(message)


def validation_summary(validation: dict | None) -> str:
    """Compact pass/fail summary for a validation mapping."""

    if not validation:
        return "—"
    failed = sum(1 for passed in validation.values() if not passed)
    passed_count = len(validation) - failed
    if failed:
        return f"{passed_count} 项通过 · {failed} 项未通过"
    return f"{passed_count} 项全部通过"


def render_validation_checklist(validations: dict | None) -> None:
    """Render patch validations as a Chinese checklist instead of raw JSON."""

    if not validations:
        st.caption("暂无验证记录。")
        return
    for key, passed in validations.items():
        icon = "✅" if passed else "❌"
        st.markdown(f"{icon} {label_for(VALIDATION_LABEL, key)}")


def render_contract(contract: dict) -> None:
    """Render an empirical claim contract as a labeled two-column table."""

    rows = [
        {
            "字段": label_for(CONTRACT_FIELD_LABEL, key),
            "值": value if value not in (None, "") else "—",
        }
        for key, value in contract.items()
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


_PENDING_CONFIRMATION_KEY = "_pending_confirmation"


def request_confirmation(
    *, key: str, title: str, body: str, confirm_label: str, on_confirm
) -> None:
    """Mark a destructive action as pending confirmation.

    The caller should st.rerun() afterwards; render_pending_confirmation (wired
    once in app.py) opens the dialog on the next run and executes on_confirm
    only when the user confirms.
    """

    st.session_state[_PENDING_CONFIRMATION_KEY] = {
        "key": key,
        "title": title,
        "body": body,
        "confirm_label": confirm_label,
        "on_confirm": on_confirm,
    }


@st.dialog("操作确认")
def _confirmation_dialog(payload: dict) -> None:
    st.markdown(f"**{payload['title']}**")
    st.write(payload["body"])
    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button(
        payload["confirm_label"],
        type="primary",
        key=f"confirm-{payload['key']}",
        width="stretch",
    ):
        st.session_state.pop(_PENDING_CONFIRMATION_KEY, None)
        payload["on_confirm"]()
        st.rerun()
    if cancel_col.button("取消", key=f"cancel-{payload['key']}", width="stretch"):
        st.session_state.pop(_PENDING_CONFIRMATION_KEY, None)
        st.rerun()


def render_pending_confirmation() -> None:
    """Open the confirmation dialog for the pending action, if any."""

    payload = st.session_state.get(_PENDING_CONFIRMATION_KEY)
    if payload:
        _confirmation_dialog(payload)


def _dismiss_impact(impact_id: str, note_key: str) -> None:
    try:
        ReviewService().dismiss_impact(impact_id, st.session_state.get(note_key) or None)
    except ValueError as exc:
        st.error(f"操作失败：{exc}")
        return
    st.toast("已记录不采用，并关闭相关行动")


def render_impact_decision(impact, *, key_prefix: str) -> None:
    """Unified impact decision block: adopt (optionally with edits) or dismiss.

    Mirrors ReviewService semantics: when the mode/action selects inside the
    popover differ from the stored judgment, adoption goes through edit_impact,
    otherwise confirm_impact. Dismissal requires a confirmation dialog. The
    decision note widget keeps its value in session_state across reruns.
    """

    note_key = f"{key_prefix}-decision-note"
    mode_key = f"{key_prefix}-impact-mode"
    action_key = f"{key_prefix}-suggested-action"
    st.text_area("决策备注（可选）", key=note_key)
    with st.popover("修改判断（可选）"):
        st.selectbox(
            "影响类型",
            IMPACT_MODES,
            index=IMPACT_MODES.index(impact.impact_mode),
            format_func=lambda value: label_for(IMPACT_MODE_LABEL, value),
            key=mode_key,
        )
        st.selectbox(
            "建议动作",
            SUGGESTED_ACTIONS,
            index=SUGGESTED_ACTIONS.index(impact.suggested_action),
            format_func=lambda value: label_for(SUGGESTED_ACTION_LABEL, value),
            key=action_key,
        )
        st.caption("不修改时“采用”会直接确认当前判断。")
    adopt_col, dismiss_col = st.columns(2)
    confirm_label = (
        "确认无需行动" if impact.impact_mode == "no_material_change" else "采用这项影响"
    )
    if adopt_col.button(
        confirm_label,
        type="primary",
        key=f"{key_prefix}-adopt",
        disabled=impact.review_state in {"confirmed", "edited"},
        width="stretch",
    ):
        note = st.session_state.get(note_key) or None
        selected_mode = st.session_state.get(mode_key, impact.impact_mode)
        selected_action = st.session_state.get(action_key, impact.suggested_action)
        service = ReviewService()
        try:
            if (
                selected_mode != impact.impact_mode
                or selected_action != impact.suggested_action
            ):
                service.edit_impact(
                    impact.id,
                    {"impact_mode": selected_mode, "suggested_action": selected_action},
                    note,
                )
            else:
                service.confirm_impact(impact.id, note)
        except ValueError as exc:
            if str(exc) == "state_blocked":
                st.error("这条影响的证据校验未通过，暂时不能采用；请先补齐原文证据。")
            else:
                st.error(f"采用失败：{exc}")
            return
        st.toast("已采用：影响进入证据账本，相关行动已打开")
        st.rerun()
    if dismiss_col.button(
        "不采用",
        key=f"{key_prefix}-dismiss",
        disabled=impact.review_state == "dismissed",
        width="stretch",
    ):
        request_confirmation(
            key=f"{key_prefix}-dismiss",
            title="不采用这项影响",
            body="不采用会关闭这项影响生成的相关行动；之后仍可重新采用。",
            confirm_label="确认不采用",
            on_confirm=lambda: _dismiss_impact(impact.id, note_key),
        )
        st.rerun()


def adoption_guidance(impact) -> tuple[str, str]:
    """Explain what accepting an impact will and will not change."""

    if impact.review_state == "dismissed":
        return "已选择不采用", "相关自动行动已关闭；你仍可重新采用这项影响。"
    if impact.review_state in {"confirmed", "edited"}:
        return "已采用", "这个判断已进入证据账本，相关行动已转为可执行。"
    if impact.trust_state == "blocked":
        return "暂不可采用", "证据校验未通过，需要先补齐原文证据。"
    if impact.impact_mode == "no_material_change":
        return "无需改变", "条件矩阵和精确证据已保存；当前不要求修改实验、数据或写作。"
    if impact.impact_mode == "research_integrity" or impact.event_type == "retraction":
        return "建议采用（紧急）", "用于重新验证引用和实验；采用后会打开重新验证行动。"
    if impact.stance == "challenges" and impact.comparability in {"compatible", "partial"}:
        return "建议采用", "用于团队决策和条件匹配实验；不会自动改写你的 Claim。"
    if impact.stance == "supports" and impact.comparability in {"compatible", "partial"}:
        return "建议采用为支持证据", "用于 Discussion 和证据账本；仍需你确认引用方式。"
    if impact.impact_mode in {"boundary_condition", "prior_art"} or impact.comparability == "incompatible":
        return "建议部分采用", "只用于补实验边界、Related Work 或 Limitations，不作为直接支持/反驳。"
    if impact.stance == "uncertain":
        return "先核对再采用", "先检查原文条件和精确证据，再决定是否打开行动。"
    return "建议作为背景采用", "用于研究定位或后续观察，不会自动改变核心主张。"
