# Research Radar v0.6：MVP Demo 开工规格

> 日期：2026-07-21  
> 上位路线：[`Research Radar v0.5`](./research_radar_MVP研究与技术路线_v0.5.md)  
> 本文只回答一个问题：**如果现在正式搭建，一个人如何在 2-3 周内做出可信、可演示、不过度工程化的 MVP？**
>
> **产品开工结论**：产品定位、首次价值、范围与正确开发顺序的最终审查见 [`v0.7`](./research_radar_产品开工审查_v0.7.md)。

---

## 0. 最终结论：可以开始搭建

### 0.1 可行性判断

**结论：技术路线可行，建议按本文冻结范围后立即开工。**

整体可行性为“中高”。其中：

- Claim 候选抽取、人工确认、检索漏斗、影响卡 UI、审计账本和 PatchProposal 都是成熟工程组合；
- 真正具有研究难度的是“新论文是否在可比条件下支持或挑战某条 Claim”；
- 这项风险可以通过固定 CS/AI empirical Claim、使用历史样例、字段级条件对齐、精确证据定位、允许弃权和人工 Gate 控制；
- Demo 不需要证明系统已经达到可无人值守的科学准确率，只需证明这条受控工作流能工作，并且错误不会直接进入项目记忆或论文。

### 0.2 MVP 的一句话验收标准

> 给定一篇用户论文和一批新论文，系统能在 10 分钟内帮助用户确认 3-7 个“影响哪条 Claim、为何支持/挑战、条件差在哪里、论文哪里需要改”的候选判断，并把确认结果保存为可追溯账本和论文修改建议。

### 0.3 预估工期

| 情况 | 预估 |
|---|---|
| 已有可调用 LLM、一个真实 Case、熟悉 Python | 10-15 个工作日 |
| 需要同时选择模型、准备样例数据、处理复杂 LaTeX | 15-20 个工作日 |
| 同时做团队权限、实时调度、DOCX、邮件和完整论文评测 | 超出 MVP，不建议并入 |

---

## 1. Demo 要讲清的唯一故事

```text
打开一个 Research Case
  -> 看到 10-15 条已确认 Claim
  -> 运行一次 Historical Replay
  -> 系统从 20-50 篇候选论文中找到 3-7 条待确认影响
  -> 用户打开一张 challenge 卡
  -> 左侧看到自己的 Claim 原文
  -> 右侧看到新论文的精确证据
  -> 中间看到 dataset / metric / baseline / scope 条件差异
  -> 用户确认、修正或忽略
  -> 系统生成一份 Discussion / Related Work 的最小修改建议
  -> Claim Ledger 保存判断、证据、动作和审计记录
```

默认使用固定历史样例，保证每次演示都有稳定结果。Live arXiv scan 可以作为附加按钮，但不能成为 Demo 成败的依赖。

### 1.1 五个规划场景的 Demo 覆盖

| 使用场景 | MVP 是否覆盖 | Demo 中如何实现 | 产品化后补什么 |
|---|:---:|---|---|
| 周一查看“本周 3 篇论文与你的主张相关” | **覆盖** | 每次 ScanRun 生成 `Weekly Radar Summary`，按 critical/review/informative 汇总 | cron + 邮件/飞书/钉钉 |
| 新论文反驳核心主张 | **覆盖，但增加安全 Gate** | 自动生成 `candidate challenge` 和 `team_review` 建议；用户确认后 Claim Health 显示 `contested` | 团队审批、责任人和会议集成 |
| 竞争对手发布相同方法论文 | **覆盖** | Case 配置简单 competitor author/lab aliases；命中后显示 `strategic_flag=competitor` | ORCID/ROR 实体消歧和组织变更历史 |
| 引用论文被撤稿 | **覆盖** | Historical Fixture 注入 retraction event，沿 `claim_source_link` 找到受影响 Claim，建议 `revalidation_required` | Live Crossref 扫描与通知 |
| 写作时查看支持与反证 | **覆盖** | Claim Ledger 按 supports/challenges/integrity 分组，生成 Discussion Evidence Pack 和 PatchProposal | Zotero/Overleaf/DOCX 集成 |

因此，五个场景都应在首个 Demo 中“看得见、走得通”，但外部定时触达和实时数据源可以后接。反证和撤稿的自动化边界是：**系统自动发现并提出状态变化，用户确认后才改变正式 Claim Health。**

---

## 2. MVP 范围冻结

### 2.1 P0：必须完成

1. **单用户、单 Research Case**；
2. 上传或加载 `.tex` / `.md` 论文；PDF 只做文本回退；
3. LLM 提取 10-20 条 Claim candidates；
4. 用户 confirm / edit / split / reject Claim；
5. 只支持 `empirical_result` 为主要 ClaimContract；
6. 加载 20-50 篇历史候选论文；
7. BM25/FTS + embedding 的简化混合检索；
8. top Claim routing + top paper rerank；
9. 生成 3-7 张 Impact Cards；
10. 每张卡含双方精确证据、条件差异、stance、change depth、action；
11. Impact confirm / edit / dismiss；
12. append-only audit event；
13. Claim Ledger 当前视图；
14. 对 confirmed impact 生成 PatchProposal；
15. Trust checks：span、citation、condition、numeric lock、candidate/confirmed 隔离；
16. 每次 ScanRun 自动生成 Weekly Radar Summary 页面；
17. Case 可配置 competitor author/lab aliases，并在命中时添加战略标记；
18. Golden Case 必须含一个 retraction event，并传播到相关 Claim；
19. Claim Ledger 可按支持、挑战和研究完整性事件分组，并导出 Discussion Evidence Pack。

### 2.2 P0.5：有余力再做

- arXiv 按钮式 live scan；
- Semantic Scholar 元数据与 citation expansion；
- Crossref live retraction 状态检查；
- 一页 Coverage Receipt；
- 将 PatchProposal 导出为 Markdown diff。

### 2.3 本轮明确不做

- cron 每周自动运行；
- 邮件、飞书、钉钉推送；
- Obsidian、Zotero、Overleaf 插件；
- 团队账号、RBAC、评论和审批；
- 独立代码、数据集、GitHub release 监测；
- 自动执行或复现实验；
- 自动应用论文修改；
- DOCX tracked changes；
- 多 Agent 自由协作或辩论；
- Graph DB / GraphRAG；
- 在线学习与自动微调；
- 精确概率校准和 Bayesian evidence update；
- 全学科通用 Claim schema；
- OCR-first PDF ingestion；
- 完整 RadarBench-CS 论文实验。

这些能力不删除，只是不进入首个可运行 Demo。

---

## 3. 功能可行性复核

| 能力 | 可行性 | MVP 做法 | 主要边界 |
|---|:---:|---|---|
| Claim 候选抽取 | 高 | 分节 LLM structured output + exact span check + 人工确认 | 不能保证一次抽取完整 |
| Claim 原子化 | 中高 | empirical Claim 固定字段；用户可 split/merge | 理论 Claim 延后 |
| 学术检索 | 高 | 历史 corpus + arXiv metadata；混合检索 | Live API 可能限速或失败 |
| Claim routing | 中高 | paper abstract/section -> top 3 Claim | 多 Claim 影响仍需人工修正 |
| 条件对齐 | 中 | 固定 task/dataset/split/metric/comparator/scope 六类字段 | 未报告字段必须为 unknown |
| 支持/挑战判断 | 中 | evidence-first LLM + 条件规则 + abstain | 是最主要研究风险 |
| 影响量化 | 中高 | 使用 ImpactVector 与 ordinal change depth | 不显示未经校准概率 |
| 证据追溯 | 高 | snapshot + exact quote + locator + hash | PDF locator 质量依赖解析 |
| 长期记忆 | 高 | SQLite 当前表 + append-only audit events | 不需要专用 memory framework |
| 论文修改建议 | 高 | before/after PatchProposal；不直接写文件 | 仅 Discussion/Related Work 等低风险区域 |
| 撤稿监测 | 高 | DOI 调 Crossref production API | arXiv-only work 可能没有 DOI |
| 实时持续监测 | 高 | on-demand scan；定时任务后移 | Demo 用历史回放更稳定 |

### 3.1 最重要的可行性边界

MVP 可以可靠演示：

```text
“发现了一条待确认挑战；它命中 Claim C7；
两边证据在这里；dataset 相同但 compute budget 未知；
建议在 Discussion 增加边界说明。”
```

MVP 不应声称：

```text
“这篇论文以 87% 概率推翻了你的结论，系统已经自动修正全文。”
```

前者可审计、可实现；后者在没有校准数据、领域专家和完整实验条件时不可成立。

---

## 4. 最小技术架构

### 4.1 架构原则

- 单体应用，模块化代码；
- 显式 pipeline，不使用自由 Agent loop；
- 单一 LLM provider adapter，structured JSON；
- SQLite 是事实源；embedding 是可重建缓存；
- 所有模型输出先写 candidate；
- UI 只调用应用 service，不直接调用模型或修改数据库；
- Historical Replay 是默认主路径；外部 API 是 adapter。

### 4.2 架构图

```text
Streamlit UI
  ├── Case / Claim Review
  ├── Scan Run
  ├── Impact Workspace
  └── Ledger / Patch Review
          |
          v
Explicit Orchestrator
  ingest -> claim -> retrieve -> route -> compare -> impact -> review -> patch
          |
          ├── Trust Service
          │     span / citation / numeric / condition / release-state
          |
          ├── LLM Adapter
          │     structured generation only
          |
          ├── Search Adapters
          │     fixture / arXiv / optional S2 / optional Crossref
          |
          └── SQLite + local snapshots
                current tables + audit_events + model_runs
```

### 4.3 不需要真正的“多 Agent”

代码中可以保留工位概念，但它们只是确定性 workflow step：

```text
ClaimExtractor
SearchPlanner
EvidenceExtractor
ConditionComparator
ImpactAssessor
PatchGenerator
TrustVerifier
```

每个 step 有 Pydantic 输入输出 schema、超时、错误状态和重试上限。没有 Agent 有权直接修改 confirmed state。

---

## 5. 推荐技术栈

| 层 | 选择 | 原因 |
|---|---|---|
| 语言 | Python 3.12 | 科学 NLP、API、LLM 和快速 Demo 生态成熟 |
| UI | Streamlit | 一周内可完成多栏 Evidence Workspace，无需前后端分离 |
| 数据模型 | SQLAlchemy 2 + SQLite | 类型、关系、迁移路径清楚；单用户足够 |
| Schema | Pydantic | 所有 LLM 和 workflow step 使用强类型输出 |
| HTTP | httpx | 超时、重试和异步接口统一 |
| arXiv | Atom API + feedparser 或 XML parser | 官方 metadata 接口，适合小批量 on-demand scan |
| 全文 | LaTeX/Markdown parser；PDF 文本回退 | 优先保证准确 locator，不做 OCR |
| 检索 | SQLite FTS5 + embedding + NumPy cosine | 50-500 篇规模不需要 vector DB |
| LLM | 单 provider SDK + 自有 adapter | 便于后续替换模型，首版不引入额外路由框架 |
| 审计 | JSON payload + append-only `audit_events` | 简单、可回放、可检查 |
| 测试 | pytest + golden fixtures | 保护证据定位、状态 Gate 和完整 Demo 流程 |

### 5.1 建议目录

```text
app.py
radar/
  config.py
  db.py
  models.py
  schemas.py
  orchestrator.py
  parsers/
    latex.py
    markdown.py
    pdf_fallback.py
  adapters/
    fixture.py
    arxiv.py
    semantic_scholar.py
    crossref.py
  llm/
    base.py
    provider.py
    prompts/
  services/
    claim_service.py
    retrieval_service.py
    evidence_service.py
    condition_service.py
    impact_service.py
    trust_service.py
    review_service.py
    patch_service.py
  ui/
    case_page.py
    scan_page.py
    impact_page.py
    ledger_page.py
tests/
  fixtures/
  golden/
```

首版不需要 FastAPI。应用 service 与 UI 分离后，未来再增加 API 层不会重写核心逻辑。

---

## 6. 最小数据模型

只实现以下约 15 张表，不建立图数据库：

```text
research_cases
manuscript_versions
claims
claim_revisions
claim_surfaces
claim_source_links
sources
source_snapshots
scan_runs
watch_entities
impact_candidates
review_decisions
patch_proposals
audit_events
model_runs
```

Weekly Radar Summary、Claim Health 和 Evidence Pack 都由上述数据生成物化视图或查询结果，不单独建表。`model_runs` 建议保留独立表，便于调试成本和模型版本。

### 6.1 MVP Claim schema

```json
{
  "claim_id": "C-07",
  "revision": 1,
  "statement": "...",
  "claim_type": "empirical_result",
  "centrality": "core",
  "contract": {
    "task": "...",
    "dataset": "...",
    "split": "...",
    "metric": "...",
    "comparator": "...",
    "scope": "..."
  },
  "falsifiable_condition": "...",
  "source_locator": "sec-4.2:p3:s2",
  "source_quote": "...",
  "review_state": "confirmed"
}
```

### 6.2 MVP Impact schema

```json
{
  "claim_revision_id": "C-07-r1",
  "source_snapshot_id": "S-12-v1",
  "event_type": "paper",
  "stance": "challenges",
  "impact_mode": "boundary_condition",
  "strategic_flags": ["competitor"],
  "comparability": "partial",
  "condition_differences": [
    {"field": "dataset", "status": "match"},
    {"field": "compute_budget", "status": "unknown"}
  ],
  "evidence_own": {
    "quote": "...",
    "locator": "sec-4.2:p3:s2"
  },
  "evidence_new": {
    "quote": "...",
    "locator": "sec-5.1:p2:s1"
  },
  "change_depth": 2,
  "suggested_action": "add_boundary_discussion",
  "uncertainty_sources": ["compute_budget_unknown"],
  "review_state": "candidate"
}
```

MVP 不保存未经校准的 `0.87 confidence`。如果 UI 需要排序，使用规则生成 `critical / review / informative`，并明确它是 review priority，不是真实性概率。

---

## 7. 最小可信控制

v0.5 的 Trust Release Path 不能因 MVP 而删除，但可以压缩为三个 Gate 和六个检查。

### 7.1 三个 Gate

```text
G0 Claim Gate
  candidate Claim -> 用户确认 -> confirmed Claim

G1 Impact Gate
  grounded Impact -> 用户确认/修正/忽略 -> ledger event

G2 Patch Gate
  PatchProposal -> 用户批准/拒绝 -> 只导出，不自动覆盖原稿
```

### 7.2 六个必须自动化的检查

1. `source_resolved`：论文标识和版本存在；
2. `own_span_exact`：用户论文 quote 可在 snapshot 中找到；
3. `new_span_exact`：新论文 quote 可在 snapshot 中找到；
4. `condition_gate`：challenge 的必要字段没有 hard mismatch；
5. `citation_resolved`：Patch 新增引用有真实 DOI/arXiv/URL 对象；
6. `state_permission`：candidate 不能进入 confirmed context 或被 Patch 使用。

### 7.3 Release rule

```text
Impact Card 可进入人工队列：
  source_resolved
  AND own_span_exact
  AND new_span_exact

Impact Card 可显示 challenges：
  上述全部通过
  AND condition_gate != hard_mismatch

PatchProposal 可生成：
  impact.review_state == confirmed
  AND citation_resolved
```

失败时显示明确状态：`source_missing / span_failed / incompatible / uncertain / blocked`，不能让 LLM 用自然语言绕过。

---

## 8. 检索与外部接口策略

### 8.1 Demo 默认：Historical Fixture Adapter

准备一个固定 Case：

- 1 篇 own paper；
- 10-15 条人工确认 Claim；
- 20-50 篇 incoming papers；
- 5-8 个预先人工确认的 material-impact examples；
- 至少 10 个主题相似但不构成影响的 hard negatives；
- 至少 1 个条件不兼容的伪反证；
- 至少 1 个 competitor event；
- 至少 1 个撤稿或修正事件，并预先标注它影响的引用与 Claim。

这既是 Demo 数据，也是第一套 golden test。

### 8.2 Live arXiv Adapter

只做：

- title、abstract、authors、categories、published/updated、arXiv ID；
- 每次查询最多取 50-100 条；
- 请求间隔至少 3 秒；
- 单连接；
- 同一查询结果按天缓存；
- 保存 query 和 fetch time；
- UI 链接回 arXiv 原页面。

arXiv 官方要求 legacy API 不超过每三秒一次请求、单连接；元数据可使用，但 e-print 全文受各自版权/许可约束，不能默认在产品服务器重新分发。[arXiv API Terms](https://info.arxiv.org/help/api/tou.html)

### 8.3 Semantic Scholar 与 OpenAlex

首版选择一个作为 metadata/citation enrichment 即可，不同时构建两套完整依赖：

- Semantic Scholar 可提供论文、引用、SPECTER2 与 Recommendations；初始 API key 通常为 1 RPS，需缓存与超时降级。[Semantic Scholar API](https://www.semanticscholar.org/product/api)
- OpenAlex 适合作为开放 Work identity/graph 备选，但当前免费 API 有日额度，免费 snapshot 为季度更新；不应让 Demo 依赖其付费 change files。[OpenAlex Developers](https://developers.openalex.org/)

建议 MVP：arXiv + Historical Fixture 为必选，Semantic Scholar 为可选 enrichment，OpenAlex 延后。

### 8.4 Crossref

撤稿影响传播在 P0 通过 Historical Fixture 实现；P0.5 再接入 live Crossref production REST API / Retraction Watch 数据，不使用旧 Labs annotation。[Crossref Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)

---

## 9. 三个界面足够

### Screen 1：Case Setup / Claim Review

- 论文信息；
- Claim candidate 列表；
- source quote；
- empirical contract 字段；
- confirm / edit / split / reject；
- centrality 设置；
- competitor author/lab aliases 配置。

### Screen 2：Impact Workspace

页面顶部先显示 Weekly Radar Summary：本次扫描论文数、相关论文数、critical/review/informative 数，以及 supports/challenges/competitor/integrity 四类摘要。

```text
左：Impact Queue
  severity / event type / stance / competitor flag / affected Claim

中：Condition Delta
  task / dataset / split / metric / comparator / scope

右：Evidence Inspector
  own quote vs incoming quote
  exact locator / source link
```

操作只有：confirm / edit / dismiss。

### Screen 3：Ledger / Patch Review

- Claim 当前证据和影响历史；
- supports / challenges / integrity 分组；
- confirmed actions；
- before / after PatchProposal；
- evidence links；
- validator results；
- Discussion Evidence Pack 导出；
- approve export / reject。

不需要首页大屏、聊天页、关系网络图或复杂统计图。

---

## 10. 15 个工作日实施顺序

| 天 | 工作 | 验收 |
|---|---|---|
| D1 | 项目 scaffold、配置、SQLite schema、fixture loader | 应用启动，Case 可加载 |
| D2-D3 | `.tex/.md` parser、ManuscriptVersion、Claim candidate schema | 原文可定位到 section/paragraph/sentence |
| D4 | Claim extraction + G0 Review UI | 10-20 条 Claim 可 confirm/edit/reject |
| D5 | Historical corpus、SourceSnapshot、competitor/retraction fixtures | 20-50 篇论文、竞争事件和撤稿事件可重复加载 |
| D6 | FTS5 + embedding 检索、候选 cache | known relevant papers 进入 top-k |
| D7 | Claim routing | incoming paper 可路由到 top 1-3 Claim |
| D8 | Evidence extraction + exact span verifier | 双边 quote 全部能回查 |
| D9 | Condition comparator | 六类字段输出 match/mismatch/unknown |
| D10 | ImpactAssessor + paper/competitor/integrity impact + abstain | 3-7 张卡可生成，事件类型不与 stance 混淆 |
| D11 | Weekly Radar Summary + Impact Workspace + G1 | 五类场景都能进入 review 流程 |
| D12 | Ledger、Evidence Pack、audit events、状态隔离 | 支持/挑战/撤稿可按 Claim 回查，历史不丢失 |
| D13 | PatchProposal + citation/state checks + G2 | confirmed impact 可生成 before/after 建议 |
| D14 | golden tests、失败注入、缓存与成本统计 | 关键 Trust rules 全有自动测试 |
| D15 | Demo rehearsal、文案和视觉收尾 | 5-10 分钟完整流程无阻塞 |

Live arXiv、S2 和 Crossref 放在核心 historical replay 通过后接入。

---

## 11. 开工前准备的唯一数据资产

正式写代码前先准备一个 Golden Case 文件夹：

```text
golden_case/
  own_paper.tex
  claims_gold.json
  incoming/
    paper_01.txt
    ...
  sources.json
  watch_entities.json
  claim_source_links.json
  integrity_events.json
  impacts_gold.json
  hard_negatives.json
  expected_patches.json
```

最低数量：

- 10 条 confirmed Claims；
- 20 篇 incoming papers；
- 3 条 supports；
- 2 条 challenges；
- 2 条 boundary/method impacts；
- 1 条 competitor alert；
- 1 条 retraction -> revalidation 传播样本；
- 10 条 hard negatives；
- 2 个应当 abstain 的条件缺失样本。

如果没有这套 Golden Case，代码很容易“看起来能跑”，但无法判断升级后是否变差。

---

## 12. MVP 验收清单

### 功能

- [ ] 能载入一篇真实 `.tex` / `.md` 论文；
- [ ] 能生成并人工确认至少 10 条 Claim；
- [ ] 能运行固定 20-50 篇历史论文回放；
- [ ] 能生成 3-7 张 Impact Cards；
- [ ] 能 confirm / edit / dismiss；
- [ ] 能生成“本周 N 篇论文相关”的 Weekly Radar Summary；
- [ ] 能显示一条 competitor strategic alert；
- [ ] 能把一条 retraction event 传播到相关 Claim；
- [ ] 能查看 Claim Ledger；
- [ ] 能按 supports / challenges / integrity 查看 Evidence Pack；
- [ ] 能生成至少一份 PatchProposal；
- [ ] 能导出审计 JSON 或 Markdown。

### 可信性

- [ ] 每张可见影响卡都有 own/new 双边 exact quote；
- [ ] 每个 quote 都能回到固定 SourceSnapshot；
- [ ] hard mismatch 不得显示为 confirmed challenge；
- [ ] unknown 不得被模型自动补全；
- [ ] candidate impact 不得进入 PatchProposal；
- [ ] competitor flag 不得替代 supports/challenges 判断；
- [ ] retraction 只能自动提出 `revalidation_required`，未经确认不能改变正式 Claim Health；
- [ ] 新增引用必须能解析；
- [ ] 刷新、重启后 review state 与历史不丢失；
- [ ] 模型、prompt、schema 和输入 snapshot 可查。

### Demo 体验

- [ ] 用户在 10 分钟内完成 Claim -> Impact -> Decision -> Patch；
- [ ] Historical Replay 不依赖外部网络；
- [ ] API 失败时有明确错误和 fallback；
- [ ] 不出现“AI 推翻了你的论文”等过度表述；
- [ ] 主体页面最多三个，不用用户理解 Agent 架构。

### 初步质量目标

这些是 Demo gate，不是论文结论：

- Claim source-span faithfulness：人工抽检通过率目标 ≥90%；
- Golden Case material-impact recall@20：目标 ≥90%；
- 可见 Impact Card 双边 evidence locator：100%；
- high-risk challenge precision：目标 ≥85%，不足时提高 abstention；
- citation resolution：100%；
- PatchProposal 锁定数值被意外修改：0；
- 完整 demo flow 未捕获异常：0。

---

## 13. 主要风险与处理

| 风险 | 发生概率 | 影响 | MVP 处理 |
|---|:---:|:---:|---|
| PDF/LaTeX 解析不稳定 | 中 | 高 | P0 限定 `.tex/.md`；PDF 明确标记 fallback |
| Live API 限速或中断 | 中 | 中 | 默认 Historical Fixture；缓存；adapter fallback |
| LLM 生成错误 evidence | 中 | 高 | exact span lookup；失败即 blocked |
| 主题相似误判 challenge | 中高 | 高 | 六字段 condition gate；unknown；人工 G1 |
| Demo latency或成本过高 | 中 | 中 | 先检索/routing；只对 top 3-7 做全文判断；缓存 ModelRun |
| 用户私有论文泄露 | 低到中 | 高 | 本地保存；只发送必要段落；明确 provider 数据策略 |
| 未授权缓存全文 | 中 | 高 | 保存用户上传/许可内容；外部论文优先 metadata、摘要和链接；记录 license |
| Scope creep | 高 | 高 | 以 P0 清单和 D15 退出门冻结，不并入插件、团队和自动执行 |

---

## 14. 正式开工时冻结的 14 个决定

1. 单用户、单 Case、CS/AI。
2. 主 Claim 类型只做 `empirical_result`。
3. 主输入为 `.tex/.md`；PDF 是 fallback。
4. 先做 Golden Historical Replay，后接 live scan。
5. incoming corpus 控制在 20-50 篇，后续再扩大。
6. stance 使用 `supports / challenges / neutral / uncertain`。
7. 不显示未经校准的概率或“真理分”。
8. Impact 量化只用 condition coverage、centrality、change depth 和 severity rule。
9. 只生成 PatchProposal，不自动改原稿。
10. Patch 首版只处理 Related Work / Discussion / Limitation 等低风险文本。
11. 三个 Human Gates 保留。
12. SQLite + append-only audit；不引入 graph DB、vector DB 或 memory framework。
13. 单 LLM adapter + 显式 workflow；不做多 Agent 自由循环。
14. Historical Demo 必须覆盖周报、反证、竞争、撤稿和证据写作五个场景；通过验收后再接 arXiv/S2/Crossref live adapter 和定时调度。

---

## 15. 开工判断

当前没有阻止搭建的技术性 blocker。正式开工需要的前置输入只有：

```text
1 个 Golden Case
+ 1 个可用 LLM API
+ 已确认的 P0 范围
```

只要按本规格执行，第一版不会过度复杂，也不会牺牲最重要的学术可信性。它能够真实验证产品最关键的闭环：

> **Claim 是否能成为长期监测锚点，新论文是否能被映射为可审查的项目影响，以及确认后的影响是否能安全转成论文修改建议。**

---

*本规格是 v0.5 的 Demo 实施裁剪，不替代长期产品路线。外部接口与许可约束依据 2026-07-21 的官方文档核查；开发时应锁定依赖版本、缓存策略和 adapter contract。*
