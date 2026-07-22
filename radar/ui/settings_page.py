"""Browser settings page: persist model configuration without editing .env.

Writes go to ``data/settings.local.env`` via ``save_local_settings`` and take
effect immediately (the settings cache is cleared on save), so end users never
touch the project ``.env`` file.
"""

import httpx
import streamlit as st

from radar.config import Settings, get_settings, mask_secret, save_local_settings
from radar.llm.factory import describe_llm_setup


def probe_llm_connection(settings: Settings) -> tuple[bool, str]:
    """Probe the configured analysis LLM with a lightweight metadata request."""

    setup = describe_llm_setup(settings)
    if not setup["configured"]:
        return False, "尚未配置分析模型，请先在上方填写并保存。"
    try:
        if setup["mode"] == "local":
            response = httpx.get(
                f"{settings.local_llm_base_url.rstrip('/')}/api/tags", timeout=10
            )
            response.raise_for_status()
            models = [item.get("name", "") for item in response.json().get("models", [])]
            if settings.local_llm_model in models:
                return True, f"连接成功：本地模型 `{settings.local_llm_model}` 可用。"
            return (
                False,
                f"已连上 Ollama，但未找到模型 `{settings.local_llm_model}`，"
                "请先在终端执行 `ollama pull` 拉取该模型。",
            )
        response = httpx.get(
            f"{settings.llm_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        return True, f"连接成功：远程服务可用，当前模型 `{settings.llm_model}`。"
    except httpx.HTTPStatusError as exc:
        return (
            False,
            f"连接失败：服务返回 HTTP {exc.response.status_code}，"
            "请检查 Base URL 和 API Key 是否正确。",
        )
    except httpx.HTTPError:
        return False, "连接失败：无法访问该地址，请检查网络与 Base URL。"


def render_settings_page() -> None:
    """Render the settings form and the connection probe."""

    st.title("设置")
    settings = get_settings()
    setup = describe_llm_setup(settings)
    if setup["configured"]:
        mode_label = "本地 Ollama" if setup["mode"] == "local" else "远程 API"
        st.success(f"当前分析模型：`{setup['model']}`（{mode_label}）")
    else:
        st.warning("尚未配置分析模型。在下方填写并保存后，AI 分析功能即可使用。")

    updates: dict[str, str] = {}
    with st.form("settings_form"):
        st.subheader("分析模型")
        mode = st.radio(
            "模式",
            ["远程 API", "本地 Ollama"],
            index=1 if settings.local_llm_model else 0,
            horizontal=True,
            help="本地 Ollama 模式下文稿不出本机，配置后优先于远程 API。",
        )
        if mode == "远程 API":
            provider = st.text_input(
                "Provider", value=settings.llm_provider or "", placeholder="deepseek"
            )
            base_url = st.text_input(
                "Base URL",
                value=settings.llm_base_url or "",
                placeholder="https://api.deepseek.com",
            )
            model = st.text_input(
                "模型名称", value=settings.llm_model or "", placeholder="deepseek-chat"
            )
            api_key = st.text_input(
                "API Key",
                type="password",
                value="",
                placeholder=mask_secret(settings.llm_api_key) or "sk-...",
                help="已保存 Key 时只显示后 4 位；留空表示不修改。",
            )
            updates.update(
                {
                    "LLM_PROVIDER": provider.strip(),
                    "LLM_BASE_URL": base_url.strip(),
                    "LLM_MODEL": model.strip(),
                    # Switching back to remote clears the local-first override.
                    "LOCAL_LLM_MODEL": "",
                }
            )
            if api_key.strip():
                updates["LLM_API_KEY"] = api_key.strip()
        else:
            local_model = st.text_input(
                "本地模型名称",
                value=settings.local_llm_model or "",
                placeholder="qwen3:4b",
            )
            local_base_url = st.text_input(
                "Ollama 地址",
                value=settings.local_llm_base_url or "",
                placeholder="http://127.0.0.1:11434",
                help="Docker 容器内访问宿主机 Ollama 时填 http://host.docker.internal:11434",
            )
            updates.update(
                {
                    "LOCAL_LLM_MODEL": local_model.strip(),
                    "LOCAL_LLM_BASE_URL": local_base_url.strip(),
                }
            )

        st.subheader("向量检索（可选）")
        embedding_labels = ["不启用", "本地 Ollama", "OpenAI-compatible API"]
        embedding_providers = {"不启用": "", "本地 Ollama": "ollama", "OpenAI-compatible API": "openai"}
        current_provider = (settings.embedding_provider or "").strip().lower()
        embedding_index = {"": 0, "ollama": 1}.get(current_provider, 2)
        embedding_choice = st.selectbox(
            "向量模型 Provider",
            embedding_labels,
            index=embedding_index,
            help="不启用时检索退化为纯关键词匹配，其他功能不受影响。",
        )
        embedding_provider = embedding_providers[embedding_choice]
        updates["EMBEDDING_PROVIDER"] = embedding_provider
        if embedding_provider == "ollama":
            embedding_model = st.text_input(
                "Embedding 模型",
                value=settings.embedding_model or "",
                placeholder="qwen3-embedding:0.6b",
            )
            embedding_base_url = st.text_input(
                "Ollama 地址 ",
                value=settings.embedding_base_url or "http://127.0.0.1:11434",
            )
            updates.update(
                {
                    "EMBEDDING_MODEL": embedding_model.strip(),
                    "EMBEDDING_BASE_URL": embedding_base_url.strip(),
                    "EMBEDDING_API_KEY": "",
                }
            )
        elif embedding_provider == "openai":
            embedding_model = st.text_input(
                "Embedding 模型",
                value=settings.embedding_model or "",
                placeholder="text-embedding-3-small",
            )
            embedding_base_url = st.text_input(
                "Embedding Base URL",
                value=settings.embedding_base_url or "",
                placeholder="https://api.openai.com/v1",
            )
            embedding_key = st.text_input(
                "Embedding API Key",
                type="password",
                value="",
                placeholder=mask_secret(settings.embedding_api_key) or "sk-...",
                help="已保存 Key 时只显示后 4 位；留空表示不修改。",
            )
            updates.update(
                {
                    "EMBEDDING_MODEL": embedding_model.strip(),
                    "EMBEDDING_BASE_URL": embedding_base_url.strip(),
                }
            )
            if embedding_key.strip():
                updates["EMBEDDING_API_KEY"] = embedding_key.strip()

        st.subheader("其他")
        mailto = st.text_input(
            "Crossref 联系邮箱",
            value=settings.crossref_mailto,
            help="发送给 Crossref API 的联系地址（礼貌池），建议填真实邮箱。",
        )
        updates["CROSSREF_MAILTO"] = mailto.strip()

        submitted = st.form_submit_button("保存设置", type="primary")

    if submitted:
        save_local_settings(updates)
        st.success("设置已保存，立即生效。")
        st.rerun()

    st.divider()
    st.caption("测试连接基于当前已保存的配置；失败不影响保存。")
    if st.button("测试连接"):
        with st.spinner("正在测试连接…"):
            ok, message = probe_llm_connection(get_settings())
        (st.success if ok else st.error)(message)
