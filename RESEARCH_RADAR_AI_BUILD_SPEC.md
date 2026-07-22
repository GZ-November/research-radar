# Research Radar — AI Vibe Coding Master Spec

> 版本：Build v1.0  
> 日期：2026-07-21  
> 状态：**唯一开工规格 / Single Source of Truth**  
> 目标：把本文直接交给 Coding Agent，按里程碑完成一个可运行的 Research Radar MVP Demo。

---

## 0. 给 Coding Agent 的总指令

你正在实现一个单用户、本地运行的 Research Radar MVP。请完整阅读本文，但每次只实现当前里程碑。

执行规则：

1. 本文是功能、架构和验收的唯一来源；旧文档只作背景，不扩大本文范围。
2. 优先做能运行的纵向闭环，不先搭建复杂基础设施。
3. 每个里程碑完成后运行测试，并报告：修改文件、运行命令、测试结果、剩余问题。
4. 未经用户要求，不增加团队权限、邮件、插件、GraphRAG、多 Agent、自动实验或生产部署。
5. LLM 输出永远是 candidate，不得直接修改 confirmed state 或用户论文。
6. 所有 supports/challenges 必须有双方可回查原文证据。
7. 信息不足时输出 uncertain，不允许模型自行补全论文未报告的条件。
8. 优先使用简单、可替换、可测试的代码；不要为了“未来扩展”提前增加服务、队列或数据库。
9. 保留用户已有文件和修改；不得执行破坏性操作。
10. 如果实现细节存在歧义，选择能满足验收标准的最简单方案，并在结果中说明假设。

正式开工命令：

```text
Read RESEARCH_RADAR_AI_BUILD_SPEC.md completely.
Implement Milestone 0 only.
Do not implement later milestones yet.
Run the required checks and report the result.
```

---

## 1. 产品定义

### 1.1 一句话

> Research Radar 持续监测新研究，指出它影响了用户项目里的哪条主张、影响成立的条件，以及用户应该改实验、改表述还是补讨论。

### 1.2 目标用户

首个用户：

```text
正在推进一篇 CS/AI 论文或研究项目的高年级博士生 / Research Lead
```

用户已有：

- 一篇 LaTeX 或 Markdown 文稿；
- 10-20 条可识别的项目 Claim；
- 需要持续跟踪的研究主题；
- 对 prior art、竞争工作、反向结果和撤稿的真实焦虑。

### 1.3 核心任务

> 当一篇新论文出现时，帮助用户在 10 分钟内判断：它是否实质影响项目、影响哪条 Claim、为什么，以及是否需要采取行动。

### 1.4 产品不是

- 普通论文推荐器；
- Chat with PDF；
- 自动生成整篇论文的 AI Writer；
- 自动裁决科学真假的系统；
- 无人监管的科研 Agent；
- 自动实验执行平台。

---

## 2. 必须覆盖的五个使用场景

| 场景 | MVP 行为 | 安全语义 |
|---|---|---|
| 每周查看新论文 | 每次 ScanRun 生成 Weekly Radar Summary | MVP 按钮触发；真实 cron/邮件后移 |
| 新论文挑战核心主张 | 自动生成 candidate challenge 和行动建议 | 用户确认后 Claim Health 才显示 contested |
| 竞争对手发布相同方法 | 命中配置的作者/实验室 alias，添加 competitor flag | competitor 只是战略标记，不替代 stance |
| 引用论文被撤稿 | retraction event 沿 claim-source link 传播 | 自动建议 revalidation，用户确认后生效 |
| 写论文时查看证据 | Claim Ledger 汇总 supports/challenges/integrity | 可生成 Evidence Pack 和 PatchProposal |

五场景共用同一条数据主线：

```text
ResearchEvent
  -> affected Claim
  -> evidence + conditions
  -> candidate Impact
  -> human ReviewDecision
  -> Claim Ledger / Action / PatchProposal
```

---

## 3. MVP 成功标准

### 3.1 一句话验收

> 给定一篇用户论文和 20-50 篇历史候选论文，系统在 5-10 分钟内帮助用户处理 3-7 张 Impact Cards，并把确认结果保存为证据账本和论文修改建议。

### 3.2 首次价值

Demo Case 打开后 30 秒内看到第一张 Impact Card：

```text
我的 Claim
+ 自己论文的原文
+ 新论文的相关证据
+ dataset / metric / baseline / scope 差异
+ 支持、挑战或信息不足
+ 建议动作
```

### 3.3 初步质量目标

这些是 Demo gate，不是正式论文结论：

- Claim source-span faithfulness：人工抽检目标 ≥90%；
- Golden Case material-impact Recall@20：目标 ≥90%；
- 所有可见 Impact Card 双边 evidence locator：100%；
- high-risk challenge precision：目标 ≥85%，不足时提高 abstention；
- citation resolution：100%；
- PatchProposal 意外修改锁定数字：0；
- 完整 Demo flow 未捕获异常：0。

---

## 4. 范围冻结

### 4.1 P0 必须实现

1. 单用户、本地运行；
2. 一个 active Research Case；
3. Explore Demo Case；
4. `.tex` / `.md` 论文导入；
5. PDF 仅作文本 fallback；
6. Claim candidates 抽取；
7. Claim confirm / edit / split / reject；
8. empirical ClaimContract；
9. Golden Historical Replay；
10. 20-50 篇 incoming papers；
11. 简化混合检索；
12. paper -> top Claims routing；
13. 双边 evidence extraction；
14. 六字段 condition comparison；
15. stance / impact mode / severity / action；
16. Impact Cards；
17. confirm / edit / dismiss；
18. Weekly Radar Summary；
19. competitor fixture/alias flag；
20. retraction fixture propagation；
21. Claim Ledger；
22. Discussion Evidence Pack；
23. PatchProposal；
24. candidate/confirmed 隔离；
25. audit events 和 model runs；
26. Golden tests。

### 4.2 P0.5 可选

只有 P0 验收通过后才做：

- 按钮式 live arXiv scan；
- Semantic Scholar metadata/citation enrichment；
- Crossref live retraction check；
- Coverage Receipt；
- Markdown diff export。

### 4.3 明确不做

- cron 定时任务；
- 邮件、飞书、钉钉；
- 团队账号、RBAC、评论；
- Obsidian、Zotero、Overleaf 插件；
- DOCX tracked changes；
- 独立代码和数据集监测；
- 自动实验或代码执行；
- 自动应用论文修改；
- 多 Agent 自由循环；
- Graph DB、GraphRAG；
- vector database；
- 在线训练或自动微调；
- 未经校准的概率/真理分；
- 全学科 Claim schema；
- OCR-first ingestion；
- 完整论文 benchmark。

---

## 5. 用户体验

### 5.1 两个入口

```text
Explore Demo Case
  直接进入预置 Weekly Radar 和 Impact Cards

Create My Case
  上传 .tex/.md -> 确认前 5 条核心 Claim -> Historical Scan
```

默认演示使用 Explore Demo Case。

### 5.2 三个页面

#### Page 1：Case Setup / Claim Review

显示：

- Case 标题和研究问题；
- 文稿信息；
- Claim candidate 列表；
- 每条 Claim 的原文、定位和 empirical 条件；
- centrality：core / major / minor；
- competitor author/lab aliases。

操作：

```text
confirm
edit
split
reject
```

#### Page 2：Weekly Radar / Impact Workspace

顶部 Weekly Radar Summary：

- scanned papers；
- related papers；
- critical / review / informative；
- supports；
- challenges；
- competitor alerts；
- integrity alerts。

三栏工作区：

```text
左栏：Impact Queue
  severity / event type / stance / affected Claim

中栏：Condition Delta
  task / dataset / split / metric / comparator / scope

右栏：Evidence Inspector
  own evidence vs incoming evidence
  exact locator / source link / uncertainty
```

操作：

```text
confirm
edit
dismiss
```

#### Page 3：Claim Ledger / Evidence Pack / Patch Review

显示：

- Claim 当前版本；
- supports / challenges / integrity 分组；
- confirmed decisions；
- suggested actions；
- before / after PatchProposal；
- evidence links；
- validator results；
- audit details。

操作：

```text
approve export
reject patch
export Evidence Pack
```

### 5.3 用户文案

| 内部字段 | UI 文案 |
|---|---|
| ClaimContract | Project Claim / 实验条件 |
| ImpactCandidate | 待确认影响 |
| comparability | 这些结果能否直接比较？ |
| uncertain/abstain | 信息不足，暂不判断 |
| competitor flag | 竞争团队提醒 |
| revalidation_required | 需要重新验证 |
| PatchProposal | 论文修改建议 |
| Trust Envelope | 判断依据与运行记录 |

禁止文案：

```text
AI 推翻了你的论文
系统证明你的结论错误
87% 概率为真
已自动修正论文
```

推荐文案：

```text
检测到一条待确认挑战
这些实验条件部分可比
建议增加适用边界讨论
该引用来源已出现撤稿记录，建议重新验证
```

---

## 6. 最小技术架构

### 6.1 原则

- 单体 Streamlit 应用；
- 显式 orchestrator；
- 模块化 service；
- 单 LLM adapter；
- SQLite 是事实源；
- embedding 是可重建缓存；
- fixture 是默认数据源；
- 外部接口必须可失败降级；
- 不使用自由 ReAct 或多 Agent loop。

### 6.2 架构图

```text
Streamlit UI
  ├── Case / Claim Review
  ├── Weekly Radar / Impact Workspace
  └── Ledger / Patch Review
          |
          v
Explicit Orchestrator
  ingest
    -> claim
    -> retrieve
    -> route
    -> evidence
    -> compare
    -> impact
    -> review
    -> patch
          |
          ├── TrustService
          ├── LLMClient
          ├── SearchAdapter
          └── SQLite + local snapshots
```

### 6.3 工位不是自治 Agent

```text
ClaimExtractor
SearchPlanner
EvidenceExtractor
ConditionComparator
ImpactAssessor
PatchGenerator
TrustVerifier
```

每个工位必须有：

- Pydantic 输入；
- Pydantic 输出；
- 显式错误；
- 超时；
- 最多有限重试；
- ModelRun 记录。

---

## 7. 固定技术栈

| 层 | 选择 |
|---|---|
| Language | Python 3.12 |
| UI | Streamlit |
| ORM | SQLAlchemy 2 |
| Database | SQLite |
| Schemas | Pydantic |
| HTTP | httpx |
| arXiv parsing | feedparser 或标准 XML parser |
| LaTeX parsing | pylatexenc + 简单 section parser |
| Markdown parsing | Python Markdown/text parser |
| PDF fallback | pypdf；不做 OCR |
| Lexical retrieval | SQLite FTS5 |
| Dense retrieval | EmbeddingClient + NumPy cosine；可降级 lexical-only |
| LLM | 单 provider adapter；必须支持 JSON/structured response |
| Configuration | `.env` + typed settings |
| Testing | pytest |

首版不需要 FastAPI、Celery、Redis、Postgres、Docker 或云部署。

### 7.1 环境变量

```text
APP_ENV=development
DATABASE_URL=sqlite:///data/research_radar.db
LLM_PROVIDER=
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=
EMBEDDING_PROVIDER=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
DATA_DIR=data
FIXTURE_CASE_DIR=tests/fixtures/golden_case
```

必须提供 `.env.example`；不得提交真实密钥。

---

## 8. 项目目录

```text
app.py
pyproject.toml
.env.example
.gitignore
README.md

radar/
  __init__.py
  config.py
  db.py
  models.py
  schemas.py
  orchestrator.py

  parsers/
    __init__.py
    base.py
    latex.py
    markdown.py
    pdf_fallback.py

  adapters/
    __init__.py
    base.py
    fixture.py
    arxiv.py
    semantic_scholar.py
    crossref.py

  llm/
    __init__.py
    base.py
    mock.py
    provider.py
    prompts/
      claim_extraction.txt
      impact_assessment.txt
      patch_generation.txt

  services/
    __init__.py
    case_service.py
    claim_service.py
    retrieval_service.py
    evidence_service.py
    condition_service.py
    impact_service.py
    trust_service.py
    review_service.py
    ledger_service.py
    report_service.py
    patch_service.py

  ui/
    __init__.py
    home.py
    case_page.py
    impact_page.py
    ledger_page.py
    components.py

data/
  .gitkeep
  snapshots/

tests/
  conftest.py
  fixtures/
    golden_case/
  golden/
  test_claims.py
  test_retrieval.py
  test_conditions.py
  test_trust.py
  test_reviews.py
  test_patches.py
  test_demo_flow.py
```

尚未实现的 optional adapter 可以先提供清晰的 `NotImplementedError` 或不创建文件；不要制造假实现。

---

## 9. 数据模型

使用 UUID 字符串主键和 UTC 时间。JSON 字段在 SQLite 中存 JSON-compatible dict/list。

### 9.1 ResearchCase

```text
id
title
research_question
field                     # 固定 cs_ai
settings_json
created_at
updated_at
```

### 9.2 ManuscriptVersion

```text
id
case_id
version_no
file_name
source_type               # tex / md / pdf / fixture
content_text
content_hash
is_current
created_at
```

### 9.3 Claim

稳定 Claim identity：

```text
id
case_id
stable_key
lifecycle_state           # active / resolved / deprecated
created_at
```

### 9.4 ClaimRevision

```text
id
claim_id
manuscript_version_id
revision_no
statement
claim_type                # MVP: empirical_result
centrality                # core / major / minor
contract_json
falsifiable_condition
source_quote
source_locator
review_state              # candidate / confirmed / rejected / superseded
supersedes_id
created_at
```

### 9.5 ClaimSurface

```text
id
claim_revision_id
manuscript_version_id
section
locator
quote
surface_role              # abstract / intro / result / discussion / conclusion
created_at
```

### 9.6 Source

```text
id
external_id
title
authors_json
published_at
url
doi
arxiv_id
license
integrity_state           # normal / concern / retracted / corrected
created_at
```

### 9.7 SourceSnapshot

```text
id
source_id
version_label
title
abstract
content_text
content_hash
event_time
observed_at
created_at
```

### 9.8 ClaimSourceLink

```text
id
claim_revision_id
source_id
relation_type             # cited_by_claim / supports / challenges
source_locator
review_state
created_at
```

### 9.9 WatchEntity

```text
id
case_id
entity_type               # author / lab / institution
canonical_name
aliases_json
created_at
```

### 9.10 ScanRun

```text
id
case_id
mode                      # fixture / live
status                    # pending / running / completed / failed
started_at
finished_at
query_json
stats_json
error_message
created_at
```

### 9.11 ImpactCandidate

```text
id
scan_run_id
claim_revision_id
source_snapshot_id
event_type                # paper / correction / retraction
stance                    # supports / challenges / neutral / uncertain
impact_mode               # replication / boundary_condition / method_substitution / prior_art / research_integrity / no_material_change
strategic_flags_json      # e.g. [competitor]
comparability             # compatible / partial / incompatible / unknown
condition_differences_json
evidence_own_json
evidence_new_json
change_depth              # 0-4
severity                  # critical / review / informative
suggested_action
uncertainty_json
review_state              # candidate / confirmed / edited / dismissed
trust_state               # generated / grounded / verified / blocked
created_at
```

### 9.12 ReviewDecision

```text
id
impact_candidate_id
decision                  # confirm / edit / dismiss
edited_payload_json
reason
actor                     # MVP: local_user
created_at
```

### 9.13 PatchProposal

```text
id
case_id
manuscript_version_id
impact_candidate_id
target_locator
edit_class                # add_citation / add_boundary_discussion / add_limitation / qualify_claim / experiment_todo
before_text
after_text
citations_json
evidence_refs_json
validations_json
approval_state            # candidate / approved / rejected
created_at
```

### 9.14 AuditEvent

```text
id
case_id
event_type
object_type
object_id
payload_json
actor_type                # human / model / system
actor_id
created_at
```

### 9.15 ModelRun

```text
id
stage
provider
model
prompt_hash
schema_version
input_refs_json
raw_response
parsed_output_json
validation_json
input_tokens
output_tokens
estimated_cost
latency_ms
created_at
```

### 9.16 派生视图，不单独建表

```text
Current Claims
Claim Health
Weekly Radar Summary
Claim Evidence Pack
```

Claim Health 规则：

```text
revalidation_required:
  confirmed research_integrity impact exists

contested:
  confirmed challenge exists for active Claim

corroborated:
  confirmed support exists and no unresolved challenge

active:
  otherwise
```

Claim Health 是派生视图，不由 LLM 直接写入。

---

## 10. Pydantic 核心契约

### 10.1 EvidenceSpan

```python
class EvidenceSpan(BaseModel):
    quote: str
    locator: str
    source_snapshot_id: str | None = None
```

### 10.2 EmpiricalClaimContract

```python
class EmpiricalClaimContract(BaseModel):
    task: str | None = None
    dataset: str | None = None
    split: str | None = None
    metric: str | None = None
    comparator: str | None = None
    scope: str | None = None
```

### 10.3 ClaimCandidateOutput

```python
class ClaimCandidateOutput(BaseModel):
    statement: str
    claim_type: Literal["empirical_result"]
    centrality_suggestion: Literal["core", "major", "minor"]
    contract: EmpiricalClaimContract
    falsifiable_condition: str
    source_quote: str
    source_locator: str
```

### 10.4 ConditionDifference

```python
class ConditionDifference(BaseModel):
    field: Literal["task", "dataset", "split", "metric", "comparator", "scope"]
    own_value: str | None
    incoming_value: str | None
    status: Literal["match", "compatible_alias", "partial", "mismatch", "unknown"]
    explanation: str
```

### 10.5 ImpactAssessmentOutput

```python
class ImpactAssessmentOutput(BaseModel):
    stance: Literal["supports", "challenges", "neutral", "uncertain"]
    impact_mode: Literal[
        "replication",
        "boundary_condition",
        "method_substitution",
        "prior_art",
        "research_integrity",
        "no_material_change",
    ]
    comparability: Literal["compatible", "partial", "incompatible", "unknown"]
    condition_differences: list[ConditionDifference]
    evidence_own: EvidenceSpan
    evidence_new: EvidenceSpan
    change_depth: Literal[0, 1, 2, 3, 4]
    suggested_action: Literal[
        "cite",
        "add_boundary_discussion",
        "run_comparison",
        "narrow_claim",
        "team_review",
        "revalidate",
        "watch",
        "no_action",
    ]
    uncertainty_sources: list[str]
```

### 10.6 PatchProposalOutput

```python
class PatchProposalOutput(BaseModel):
    edit_class: Literal[
        "add_citation",
        "add_boundary_discussion",
        "add_limitation",
        "qualify_claim",
        "experiment_todo",
    ]
    target_locator: str
    before_text: str
    after_text: str
    citation_source_ids: list[str]
    assertions_added: list[str]
    assertions_weakened_or_removed: list[str]
    rationale: str
```

---

## 11. Service 接口

保持函数简单、可测试。

### 11.1 Parser

```python
class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...
```

`ParsedDocument` 至少包含：

```text
full_text
sections[]
paragraphs[]
sentences[]
stable locators
content_hash
```

### 11.2 LLMClient

```python
class LLMClient(Protocol):
    def generate_structured(
        self,
        *,
        stage: str,
        prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel: ...
```

实现：

- `MockLLMClient`：读取 Golden Case；
- 一个真实 provider adapter；
- provider 失败时明确报错，不伪造结果。

### 11.3 SearchAdapter

```python
class SearchAdapter(Protocol):
    def search(self, case_id: str, watch_query: WatchQuery) -> list[SourceRecord]: ...
```

实现顺序：

1. `FixtureSearchAdapter`；
2. `ArxivSearchAdapter`；
3. optional S2/Crossref。

### 11.4 核心 services

```python
CaseService.create_case(...)
CaseService.load_demo_case(...)

ClaimService.extract_candidates(manuscript_version_id)
ClaimService.confirm_candidate(...)
ClaimService.edit_candidate(...)

RetrievalService.rank_sources(claim_revisions, source_snapshots)
RetrievalService.route_claims(source_snapshot, claims, top_k=3)

EvidenceService.extract_relevant_evidence(claim_revision, source_snapshot)

ConditionService.compare(claim_contract, incoming_result) -> list[ConditionDifference]

ImpactService.assess(claim_revision, source_snapshot, condition_differences)

TrustService.verify_impact(impact_output, snapshots) -> TrustResult

ReviewService.confirm_impact(...)
ReviewService.edit_impact(...)
ReviewService.dismiss_impact(...)

LedgerService.get_claim_ledger(claim_id)
LedgerService.get_claim_health(claim_id)

ReportService.get_weekly_summary(scan_run_id)
ReportService.get_evidence_pack(claim_id)

PatchService.generate_patch(confirmed_impact_id)
PatchService.validate_patch(patch_id)
```

---

## 12. LLM 任务契约

### 12.1 Claim Extraction

输入：

- 一个文稿 section；
- section locator；
- 只允许 empirical Claim；
- `ClaimCandidateOutput` schema。

系统指令必须包含：

```text
Extract only claims explicitly supported by the supplied section.
Do not use outside knowledge.
Do not strengthen modality.
Every claim must include an exact verbatim source_quote.
If the task/dataset/metric/comparator is not stated, return null.
Do not infer missing experimental settings.
```

程序验证：

- `source_quote in manuscript_snapshot.content_text`；
- statement 非空；
- quote 非空；
- contract 字段类型正确。

验证失败：candidate blocked，不进入 Claim Review。

### 12.2 Impact Assessment

输入：

- confirmed ClaimRevision；
- own evidence；
- incoming source relevant text；
- programmatic condition comparison；
- `ImpactAssessmentOutput` schema。

系统指令必须包含：

```text
Judge the effect of the incoming evidence on the specified project claim.
Use only the supplied evidence.
Do not judge topic similarity as scientific contradiction.
If required conditions are unknown or incompatible, use uncertain or neutral.
Use challenges only when evidence direction conflicts and conditions are compatible or explicitly partially compatible.
Both evidence quotes must be exact verbatim text.
Competitor status is not a stance.
```

程序验证：

- own quote exact；
- incoming quote exact；
- hard mismatch 时 stance 不得为 challenges；
- evidence 不完整时 trust_state=blocked；
- unknown condition 不得被输出文本伪装为已知。

### 12.3 Patch Generation

输入：

- confirmed Impact；
- confirmed ClaimRevision；
- target ClaimSurface；
- allowed citation sources；
- 原段落；
- `PatchProposalOutput` schema。

系统指令必须包含：

```text
Generate the smallest possible manuscript edit.
Use only confirmed impacts and supplied citations.
Do not invent experiments, results, numbers, citations, or execution claims.
Do not change locked numerical values.
Prefer adding a boundary discussion, limitation, or citation.
Return before/after text and list every assertion added or weakened.
```

程序验证：

- impact 已 confirmed；
- before_text 可在 ManuscriptVersion 中找到；
- 新增 citation 可解析；
- 锁定数字没有改变；
- Patch 只生成 candidate，不写原文件。

---

## 13. Condition Comparison

MVP 只比较六个字段：

```text
task
dataset
split
metric
comparator
scope
```

每个字段输出：

```text
match
compatible_alias
partial
mismatch
unknown
```

规则优先级：

1. exact string/normalized string；
2. curated alias；
3. LLM 建议 alias，但标记需要确认；
4. 未报告就是 unknown；
5. 不得把 unknown 自动转换为 match。

整体 comparability：

```text
incompatible:
  任一 blocking field 为 mismatch

unknown:
  多个 required field 为 unknown，无法判断

partial:
  存在 partial/unknown，但没有 blocking mismatch

compatible:
  required fields 均 match/compatible_alias
```

MVP 不将 comparability 伪装成真实性概率。

---

## 14. Impact 语义

### 14.1 Stance

```text
supports
challenges
neutral
uncertain
```

### 14.2 Impact Mode

```text
replication
boundary_condition
method_substitution
prior_art
research_integrity
no_material_change
```

### 14.3 Strategic Flag

```text
competitor
```

`competitor` 不允许放入 stance。

### 14.4 Change Depth

| 级别 | 含义 |
|---|---|
| 0 | 无需行动 |
| 1 | 补引用或背景 |
| 2 | 增加讨论、局限或边界 |
| 3 | 收窄 Claim 或补实验 |
| 4 | 核心方法或论文主线需要团队讨论 |

### 14.5 Severity Rule

```text
critical:
  core Claim + confirmed-compatible challenge
  OR confirmed retraction of a key cited source

review:
  partial challenge
  OR competitor event
  OR change_depth >= 2

informative:
  support
  OR citation/background
  OR watch/no_action
```

Severity 是 review priority，不是真实性概率。

---

## 15. Trust Invariants

必须编码为硬规则和测试：

```text
T1 No source, no assertion.
T2 No exact evidence, no impact.
T3 No condition alignment, no contradiction.
T4 No execution receipt, no execution claim.
T5 No human confirmation, no semantic memory.
T6 No validated and approved diff, no manuscript mutation.
```

### 15.1 三个 Human Gates

```text
G0 Claim Gate
  candidate -> confirmed Claim

G1 Impact Gate
  candidate -> confirmed/edited/dismissed Impact

G2 Patch Gate
  candidate -> approved/rejected Patch export
```

### 15.2 Impact Release Rule

```text
可进入用户 review queue：
  source_resolved
  AND own_span_exact
  AND new_span_exact

可显示 challenges：
  上述通过
  AND condition_gate != hard_mismatch

可生成 PatchProposal：
  impact.review_state in [confirmed, edited]
  AND citations_resolved
```

### 15.3 明确错误状态

```text
source_missing
span_failed
condition_incompatible
condition_unknown
relation_uncertain
citation_failed
state_blocked
patch_validation_failed
```

不要用自然语言掩盖失败。

---

## 16. Golden Case

代码开始前必须准备：

```text
tests/fixtures/golden_case/
  case.json
  own_paper.tex
  manuscript.json
  claims_gold.json
  claim_surfaces.json
  watch_entities.json
  claim_source_links.json
  sources.json
  incoming/
    paper_01.txt
    paper_02.txt
    ...
  impacts_gold.json
  integrity_events.json
  hard_negatives.json
  expected_patches.json
```

最低内容：

- 1 个真实或授权使用的 CS/AI Case；
- 10 条 confirmed empirical Claims；
- 20 篇 incoming papers；
- 3 条 supports；
- 2 条 challenges；
- 2 条 boundary/method impacts；
- 1 条 competitor alert；
- 1 条 retraction -> revalidation 传播样本；
- 10 条 hard negatives；
- 2 个应当 uncertain/abstain 的条件缺失样本；
- 3 个 expected patches。

Golden Case 同时用于：

- Demo；
- MockLLMClient；
- UI 开发；
- 回归测试；
- product pilot。

---

## 17. 外部接口规则

### 17.1 Historical Fixture

P0 必须在完全离线情况下完成 Demo。任何 live API 失败都不能破坏 Golden Demo。

### 17.2 arXiv P0.5

实现约束：

- 单连接；
- 请求间隔至少 3 秒；
- 每次 50-100 条；
- 同一 query 按天缓存；
- 保存 query、fetch time 和返回 ID；
- UI 链接回 arXiv；
- 不默认重新分发无授权全文；
- 记录 license/metadata provenance。

### 17.3 Semantic Scholar P0.5

- optional enrichment；
- 缓存；
- 超时/429 明确降级；
- 不作为 Golden Demo 依赖。

### 17.4 Crossref P0.5

- 使用 production API；
- 按 DOI 检查 correction/retraction；
- 结果先生成 candidate integrity impact；
- 用户确认后更新 Claim Health。

---

## 18. 开发顺序

严格按里程碑执行。

Vibe Coding 使用方法：

- 每次新会话只指定一个 Milestone；
- 要求 Coding Agent 先读完整文档，但只实现当前 Milestone；
- 当前 Milestone 的测试没有通过，不进入下一阶段；
- 完成 M1 后先亲自走一遍 5 分钟 Demo，再决定是否继续 M2；
- Coding Agent 提议扩大技术栈或范围时，以本文 P0 和非目标为准拒绝扩张。

### Milestone 0：项目骨架

目标：应用、数据库和测试能启动。

实现：

- `pyproject.toml`；
- `.env.example`；
- `.gitignore`；
- 基础目录；
- typed settings；
- SQLAlchemy engine/session；
- 空 Streamlit 页面；
- pytest smoke test；
- README 启动命令。

验收：

```text
python imports succeed
database initializes
pytest passes
streamlit app starts
```

不要实现业务逻辑。

### Milestone 1：Golden Walking Skeleton

目标：三天内看到完整产品价值，不调用真实 LLM。

实现：

- Golden Case loader；
- 三个页面；
- Weekly Summary；
- gold Impact Queue；
- Evidence Inspector；
- confirm/edit/dismiss；
- Claim Ledger 更新；
- gold PatchProposal；
- audit event。

验收：

```text
Weekly Summary
-> open Impact
-> inspect evidence
-> confirm
-> Ledger changes
-> PatchProposal appears
```

这一阶段是最高优先级。

### Milestone 2：数据库持久化与状态 Gate

实现：

- 15 个核心 ORM model；
- fixture 导入数据库；
- current Claim queries；
- ReviewDecision；
- Claim Health 派生规则；
- candidate/confirmed isolation；
- app restart persistence。

验收：

- 重启后数据和决定不丢失；
- candidate 不进入 Ledger confirmed evidence；
- Claim Health 只由 confirmed decisions 计算。

### Milestone 3：真实文稿导入和 Claim Review

实现：

- `.tex` parser；
- `.md` parser；
- PDF fallback；
- stable locator；
- content hash；
- Claim extraction LLM contract；
- exact quote validator；
- Claim confirm/edit/split/reject UI。

验收：

- 一篇真实 `.tex/.md` 可导入；
- 至少 10 条 candidates；
- 所有可 review Claim 都能 exact locate；
- 前 5 条 Claim 可在 10 分钟内确认。

### Milestone 4：Retrieval 与 Claim Routing

实现：

- Source/Snapshot fixture；
- SQLite FTS5；
- optional EmbeddingClient；
- paper ranking；
- paper -> top 3 Claim routing；
- competitor alias flag；
- retrieval reasons。

验收：

- Golden relevant papers 进入 Recall@20 目标；
- hard negatives 不全部挤入 top results；
- competitor 只添加 flag，不改变 stance。

### Milestone 5：Evidence、Condition 与 Impact Engine

实现：

- relevant evidence extraction；
- exact span verifier；
- six-field condition comparison；
- impact LLM contract；
- hard mismatch rule；
- uncertain；
- severity/action policy；
- ModelRun。

验收：

- 3-7 张真实 candidate cards；
- 双边 evidence 100% 可定位；
- hard mismatch 不输出 challenge；
- unknown 不自动补齐；
- LLM 失败显示错误状态。

### Milestone 6：Retraction、Evidence Pack 与 Patch

实现：

- fixture retraction propagation；
- claim-source links；
- research_integrity impact；
- Evidence Pack；
- Patch LLM contract；
- citation/state/numeric checks；
- G2 approve/reject；
- export only。

验收：

- retraction 找到正确 Claim；
- 未确认 integrity event 不改 Claim Health；
- confirmed impact 生成最小 patch；
- candidate impact 不能生成 patch；
- 原文文件没有被自动覆盖。

### Milestone 7：产品 QA

实现：

- Golden regression tests；
- failure injection；
- loading/error/empty states；
- UI copy；
- latency/cost display；
- demo reset；
- audit export。

验收：

- 5 分钟脚本可完整运行；
- 所有 Trust tests 通过；
- 无未捕获异常；
- 3 名用户中至少 2 名认为核心闭环有用。

### Milestone 8：可选 Live Adapters

只有 Milestone 7 通过后做：

- arXiv；
- optional S2；
- optional Crossref；
- cache/retry/rate-limit；
- fallback to fixture。

---

## 19. 测试要求

### 19.1 Unit Tests

```text
test_source_quote_exact_match
test_source_quote_failure_blocks_candidate
test_claim_confirmation_required
test_condition_match
test_condition_unknown_not_inferred
test_hard_mismatch_blocks_challenge
test_competitor_flag_does_not_change_stance
test_retraction_propagates_to_linked_claim
test_retraction_requires_confirmation_for_health_change
test_candidate_cannot_generate_patch
test_confirmed_impact_can_generate_patch
test_patch_does_not_change_locked_numbers
test_claim_health_is_derived
```

### 19.2 Golden Tests

```text
golden claims match expected minimum
golden retrieval Recall@20
golden impacts contain expected Claim IDs
golden hard negative remains no_material/uncertain
golden retraction reaches expected Claim
golden patch uses expected source
```

### 19.3 End-to-End Test

```text
load Demo Case
create ScanRun
open challenge Impact
confirm Impact
verify Ledger
generate PatchProposal
approve export
verify AuditEvents
```

---

## 20. 五分钟 Demo 脚本

```text
00:00  打开 Explore Demo Case
00:20  Weekly Radar：3 篇相关、1 critical、1 competitor、1 support
00:40  打开核心 Claim challenge
01:10  查看 own/new 双边 evidence
01:40  展开 condition delta，看到一个 unknown 条件
02:10  将动作改为 add_boundary_discussion
02:40  Confirm
03:00  Claim Ledger 出现 confirmed challenge
03:30  打开 competitor alert，说明它不是 stance
04:00  打开 retraction event，展示 Claim 影响传播
04:30  生成 Evidence Pack 和 PatchProposal
05:00  查看 validator/audit 信息
```

---

## 21. Definition of Done

### 功能

- [ ] Demo Case 可一键载入；
- [ ] 自己的 `.tex/.md` 可导入；
- [ ] 至少 10 条 Claim 可 review；
- [ ] Historical Scan 可运行；
- [ ] 3-7 张 Impact Cards 可处理；
- [ ] Weekly Summary 覆盖五个场景；
- [ ] confirm/edit/dismiss 可持久化；
- [ ] Claim Ledger 可查看；
- [ ] Evidence Pack 可导出；
- [ ] PatchProposal 可生成和审批；
- [ ] Audit 可查看或导出。

### 可信

- [ ] 所有可见 Impact 有双边 exact evidence；
- [ ] hard mismatch 不显示 challenge；
- [ ] unknown 不被自动补全；
- [ ] competitor 不替代 stance；
- [ ] retraction 未确认不改变正式 Claim Health；
- [ ] candidate 不进入 confirmed memory；
- [ ] candidate 不生成 Patch；
- [ ] citation 可解析；
- [ ] Patch 不修改锁定数字；
- [ ] 原稿不被自动覆盖。

### 产品

- [ ] 30 秒内看到 Demo Impact Card；
- [ ] 单卡两分钟内完成 review；
- [ ] 5-10 分钟完成完整流程；
- [ ] 用户无需理解 Agent、Graph 或 Trust Envelope；
- [ ] 3 名目标用户中至少 2 名认为比摘要更支持项目决策。

---

## 22. 隐私、许可与安全

- 用户论文默认只保存在本地；
- 只将当前任务需要的段落发送给 LLM；
- `.env` 和数据库不提交公共仓库；
- raw model response 可能包含私有文本，UI 提供本地清理说明；
- 外部论文优先保存 metadata、用户授权内容和必要 evidence snapshot；
- 保存 license/provenance；
- arXiv/S2/Crossref 失败时明确降级；
- 不把模型输出描述为科学事实；
- 不自动修改原稿；
- 不声称执行过没有真实回执的实验。

---

## 23. Coding Agent 每阶段回复模板

完成一个里程碑后，按此格式回复：

```text
Milestone completed:

Outcome:
  用户现在可以做什么。

Files changed:
  文件列表和用途。

Commands run:
  安装、启动、测试命令。

Verification:
  通过的测试和手工检查。

Known limitations:
  当前阶段明确未实现的内容。

Next milestone:
  下一步目标；不要自动开始，等待用户确认。
```

---

## 24. 最终开工顺序摘要

```text
M0 骨架
  -> M1 Golden UI 纵向闭环
  -> M2 持久化与 Gate
  -> M3 文稿与 Claim
  -> M4 Retrieval / Routing
  -> M5 Evidence / Condition / Impact
  -> M6 Retraction / Pack / Patch
  -> M7 Product QA
  -> M8 Optional Live APIs
```

最重要的顺序原则：

> **先证明用户愿意基于 Impact Card 作出决定，再完善自动化；先用 Golden Case 做出产品，再让模型替换人工 gold 数据。**

---

## 25. 开工确认

当前没有产品或技术 blocker。开发目标、范围、架构、数据、流程、可信规则和验收标准已经冻结。

将本文交给 Coding Agent，并发送：

```text
Read RESEARCH_RADAR_AI_BUILD_SPEC.md completely.
Implement Milestone 0 only.
Do not implement later milestones.
Run tests and report using the required template.
```

即可开始。
