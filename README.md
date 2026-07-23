# Research Radar

围绕你的研究论文持续工作的 Agent。上传论文 → 自动理解 Claim → 扫描最新文献 → 判断对你的每个核心主张是支持还是挑战 → 生成具体的【改实验 / 补数据 / 调整写作】行动建议。

## 快速开始

只需要 [Docker Desktop](https://www.docker.com/products/docker-desktop/)：

```bash
git clone https://github.com/GZ-November/research-radar.git
cd research-radar
docker compose up -d --build
```

打开 **http://localhost:8501**，在设置页选择 DeepSeek、OpenAI、任意
OpenAI-compatible 服务或本地 Ollama，填入 API Key 后点击“保存并检测连接”。
数据库和设置保存在 `./data` 目录，容器重建不丢失。

### 使用流程

1. **项目工作台** — 新建项目、上传论文 PDF
2. **我的论文** — 确认 LLM 抽取的候选 Claim、管理文稿版本
3. **文献雷达** — 点击扫描，Agent 自动搜索 arXiv + OpenAlex、追溯参考文献引用图、下载全文并逐篇比较
4. **本周行动** — 查看影响判断（支持/挑战/边界条件）和 LLM 生成的执行建议
5. **改进工作台** — 生成改写补丁、审计日志导出

扫描在后台线程执行，前端实时轮询进度，可随时取消。

### 配置

打开设置页直接填，或者编辑 `.env`（不提交到 Git）。最少只需配分析模型：

```env
# 远程 API（DeepSeek / OpenAI / 任意 OpenAI-compatible）
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-你的密钥
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
```

默认推荐 DeepSeek V4 Flash；质量优先可切换 V4 Pro。OpenAI 默认推荐
GPT-5.6 Terra，最复杂的分析可选 Sol，高吞吐轻量任务可选 Luna。模型 ID
也可以直接输入，设置页不会把兼容服务限制在内置列表中。

配了 `LOCAL_LLM_MODEL` 则优先走本地 Ollama，全文不出本机。分析模型与
embedding 模型相互独立；DeepSeek 的分析接口不能当作 OpenAI embedding
接口使用。详见 `.env.example`。

### 可选增强

- **向量检索**：配置 embedding API，检索从关键词升级为语义匹配（不配也能用）
- **Docling 解析**：表格/公式密集的论文可切换 `PDF_PARSER_BACKEND=docling`（需 `pip install '.[docling]'`）

## 开发

```bash
# 后端（FastAPI）
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn radar.api:app --reload --port 8501

# 前端（React / Vite）
cd app && npm install && npm run dev
# → http://localhost:5173（自动代理 API 到 8501）
```

## 测试

```bash
python -m pytest                # 232 个测试
python scripts/verify_live_stack.py  # 真实端到端验证（arXiv + LLM）
```

## 架构

```
React SPA (Vite / TypeScript / Tailwind)
  → FastAPI (/api/* REST 端点)
  → typed services / trust gates
  → SQLAlchemy 2 + SQLite / FTS5
  → arXiv / OpenAlex / Unpaywall 适配器
  → 统一 LLM factory（本地 Ollama 或远程 OpenAI-compatible）
```

系统没有自由 ReAct、多 Agent loop、队列或云服务依赖。客户只需要一个 LLM API Key。

## 文献源

- **arXiv** — 按提交日期最新优先，每日缓存，3 秒礼貌间隔
- **OpenAlex** — 2.7 亿篇免费检索，提供引用数和期刊来源作为质量信号
- **引用图谱发现** — LLM 抽取你论文的参考文献 → OpenAlex 找近期引用了它们的论文
- **Unpaywall** — 非 arXiv 论文自动获取合法 OA 全文
- **Crossref 诚信检查** — 发现撤稿产生 research_integrity 告警

检索排序：FTS5 预筛 → 混合 rerank（lexical + embedding + 质量加分）→ LLM 重排序。

## Trust invariants

- No source, no assertion.
- No exact evidence, no impact.
- No condition alignment, no contradiction.
- No human confirmation, no semantic memory.
- No validated and approved diff, no manuscript mutation.

LLM 输出始终是 candidate；Claim Health 只从人工确认的决定派生；Patch 只导出，绝不自动改写原稿。
