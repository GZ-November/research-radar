# Research Radar

Research Radar 是一个围绕研究者项目持续工作的研究决策 Agent：它理解论文版本和稳定 Claim，联网搜索最新 arXiv 公开论文，读取命中的公开 PDF，再生成实验、数据和写作任务。

用户可以创建和切换多个研究项目、上传自己的论文并持续同步新版本。RARE 只作为可选示例项目。结构化判断由统一配置的分析模型完成：配置了 `LOCAL_LLM_MODEL` 时走本地 Ollama（文稿不出本机），否则走远程 OpenAI-compatible API（如 DeepSeek）；命中论文全文和当前项目文稿只发送给实际启用的那个模型。两者都未配置时，UI 会给出配置引导。

## 已实现

- 多项目工作台：项目独立保存文稿版本、Claim、Radar、证据和行动
- 文稿版本同步：精确保留稳定 Claim，新增或改写结果进入确认队列
- Claim 抽取：配置分析模型时 LLM 优先，正则启发式作为确定性 fallback
- 从全文画像自动生成多组 arXiv 查询，不要求用户写关键词
- arXiv 按提交日期最新优先，自动排除用户自己的预印本
- 对命中论文下载并解析公开 PDF，在全文中定位 exact evidence
- Qwen3 Embedding 混合检索（FTS5 预筛 + lexical/embedding 混合 rerank），结构化全文影响判断
- 扫描作为后台任务执行：前端轮询进度、可取消，30 分钟无心跳的僵尸扫描自动标记 interrupted，每 case 防重入
- Crossref 研究诚信检查已接入扫描管线：发现撤稿会产生 research_integrity impact 和对应行动
- 不为每个 Claim 强行匹配论文；零变化和弱相关结果不生成行动
- Action Center 把真实影响转成可执行项目动作
- 自动 Claim 注意态：Disputed、竞争压力、需要重新验证、需要审查、新支持证据
- critical challenge → 48 小时团队决策会 + 条件匹配复现实验
- competitor alert → 72 小时加速/调整角度决策 + head-to-head 实验
- retraction/integrity → 重新验证任务 + 暂缓相关强表述
- 支持证据、反证、边界/prior art、完整性风险写作工作台和 Discussion Brief 导出
- Action open / in progress / done / dismissed 状态流转与审计
- `.tex` / `.md` 文稿导入和文本型 PDF fallback
- Claim candidate 的 confirm / edit / split / reject
- SQLite FTS5 检索、paper → top Claims routing、competitor aliases
- 双边 exact evidence、六字段 condition delta、hard-mismatch gate
- supports / challenges / neutral / uncertain 与 severity/action policy
- Impact confirm / edit / dismiss 持久化及 AuditEvent
- retraction → linked Claim candidate propagation
- confirmed-only Claim Ledger、派生 Claim Health、Evidence Pack
- PatchProposal 生成、citation/exact-span/locked-number 校验、approve/reject/export
- ModelRun / latency / cost receipt（Golden stages 为零成本 mock/deterministic run）
- arXiv daily cache、3 秒请求间隔，以及 live → fixture fallback
- 可选 Crossref integrity adapter（撤稿/研究诚信检查）

## 安装

推荐 Python 3.12；项目也允许 Python 3.13。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Demo 需要一个可用的分析模型：填远程 OpenAI-compatible API Key（`.env.example` 有 DeepSeek 示例值），或配置本地 Ollama 模型（`LOCAL_LLM_MODEL`，见下文）。`.env`、SQLite 数据库和上传文稿均被 Git 忽略。

## 启动

```bash
streamlit run app.py
```

打开输出的本地地址（通常是 `http://localhost:8501`）。应用会进入 **项目工作台**，可以新建自己的项目或打开 RARE 示例。

推荐演示流程：

1. 在 **项目工作台** 创建项目并上传当前论文。
2. 到 **我的论文** 确认核心 Claim，并可随时同步新文稿版本。
3. 到 **文献雷达**，点击 **搜索最新公开论文并告诉我该做什么**。扫描在后台线程执行，前端轮询进度，可随时取消；中断的僵尸扫描（30 分钟无心跳）会自动标记为 interrupted。
4. 查看原文、DOI、exact evidence 和六字段 condition delta，并决定是否采用。
5. 回到 **本周行动**，执行实验、数据和写作任务。

## 测试

```bash
pytest
python -m pip check
```

当前测试套件共 131 个测试，覆盖 Golden flow、六类行动生成、自动 Claim 注意态、行动状态流转、Trust invariants、状态 Gate、撤稿传播、检索、parser、failure injection、Patch 数字锁定和 Streamlit 入口。

配好分析模型后，可选跑一次真实端到端验证（真 arXiv + 真 LLM + 临时数据库，不碰工作库；任一步失败 exit code 非 0）：

```bash
python scripts/verify_live_stack.py
```

## 数据库

默认位置：`data/research_radar.db`。

```bash
python -c "from radar.db import init_database; init_database()"
```

应用启动时也会自动建表，并自动应用 `radar/db.py` 中的轻量迁移（`MIGRATIONS`，当前 3 个版本，幂等）。Demo Reset 只重建 Golden Demo 数据，不覆盖上传的其他 Case。

## 架构

```text
Streamlit UI
  → explicit ResearchRadarOrchestrator
  → typed services / trust gates
  → SQLAlchemy 2 + SQLite / FTS5
  → fixture-first adapters
  → one structured LLM factory (local Ollama or remote, optional)
```

系统没有自由 ReAct、多 Agent loop、队列或云服务依赖。

## Trust invariants

- No source, no assertion.
- No exact evidence, no impact.
- No condition alignment, no contradiction.
- No human confirmation, no semantic memory.
- No validated and approved diff, no manuscript mutation.

LLM/fixture 输出始终是 candidate；Claim Health 只从人工确认的决定派生；Patch 只导出，绝不自动改写原稿。

Action Center 会立即从 verified candidate 计算 **Current Radar Attention** 和建议动作，确保团队在人工审核前也能看到风险；Claim Ledger 的 **Confirmed Claim Health** 仍只由人工确认结果改变。两层状态在 Ledger 中并排显示。

### 远程分析模型（OpenAI-compatible，如 DeepSeek）

未配置 `LOCAL_LLM_MODEL` 时，结构化 LLM 调用走远程 OpenAI-compatible Chat Completions API。
在本地 `.env` 中配置（不要提交 API Key；以下为 DeepSeek 示例，`.env.example` 有带中文注释的完整模板）：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
LLM_THINKING=enabled
LLM_REASONING_EFFORT=high
LLM_MAX_TOKENS=4096
```

远程请求使用 `json_object`，并把 Pydantic JSON Schema 注入 system prompt；返回值仍会在本地经过 Pydantic、exact-span 和 trust gate 校验。
全文画像和影响判断阶段会把当前项目文稿和命中论文的可用 PDF 全文发送给该模型。

### 向量检索（本地 Ollama 或远程 OpenAI-compatible API）

混合检索默认使用 Ollama 本地运行的 `qwen3-embedding:0.6b`，无需 API Key：

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_API_KEY=
EMBEDDING_MODEL=qwen3-embedding:0.6b
EMBEDDING_BASE_URL=http://127.0.0.1:11434
```

也可以使用任意 OpenAI-compatible 的远程 embedding API（OpenAI、SiliconFlow、Jina 等），需同时提供 Key、模型名和 Base URL：

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1
```

Source ranking 和 paper-to-Claim routing 默认采用 `55% lexical + 45% semantic`。
向量请求会批量执行、L2 归一化并在单次进程中按文本哈希缓存；远程 API 对 429/5xx 按指数退避重试（默认最多 3 次）。embedding 不可用或未配置时明确记录错误并降级为 lexical retrieval。

### 本地分析模型（Ollama，配置后优先于远程）

所有结构化 LLM 调用统一由 `radar/llm/factory.py` 的 `build_analysis_llm` 构造。只要设置了 `LOCAL_LLM_MODEL`，全文画像、影响判断、Patch 改写等全部走本地 Ollama，文稿不出本机，不会再调用远程 API：

```env
LOCAL_LLM_MODEL=qwen3:4b
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434
LOCAL_LLM_TIMEOUT_SECONDS=300
```

```bash
ollama pull qwen3:4b
```

`LOCAL_LLM_MODEL` 留空时使用上面的远程模型；两者都未配置时，相关功能在 UI 中给出配置引导而不是直接报错。

## 可选 Live Adapters

`ArxivSearchAdapter` 提供 daily cache、单连接和至少 3 秒请求间隔。将它放进 `FallbackSearchAdapter` 可在超时、429 或网络失败时明确降级到 `FixtureSearchAdapter`。Crossref integrity adapter 已接入扫描管线，对命中论文做撤稿/研究诚信检查（可通过 `CROSSREF_MAILTO` 配置联系邮箱），不影响离线 Demo。
