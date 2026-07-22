# Research Radar v0.7：产品开工审查

> 日期：2026-07-21  
> 技术路线：[`v0.5`](./research_radar_MVP研究与技术路线_v0.5.md)  
> Demo 规格：[`v0.6`](./research_radar_MVP_Demo开工规格_v0.6.md)  
> 审查目标：从产品而非技术完整性的角度，判断是否可以开始写代码。
>
> **唯一实施入口**：后续交给 Coding Agent 的自包含开发规格统一使用 [`RESEARCH_RADAR_AI_BUILD_SPEC.md`](./RESEARCH_RADAR_AI_BUILD_SPEC.md)。

---

## 0. 最终结论

### 产品结论：GO，可以开始写代码

但这个 GO 有明确边界：

```text
GO：用于验证核心价值的单用户 CS/AI Research Case Demo

NOT YET：可无人值守、可多团队购买、覆盖所有研究领域的正式产品
```

当前产品已经具备开工所需的五个条件：

1. **用户明确**：有一篇正在推进的论文、需要长期跟踪相关研究的 CS/AI 博士生或 Research Lead；
2. **问题明确**：现有论文提醒无法回答“这篇新论文是否要求我改实验、改主张或改写作”；
3. **价值单位明确**：不是推荐一篇论文，而是确认一条“外部证据对项目 Claim 的可行动影响”；
4. **使用闭环明确**：Weekly Radar -> Impact Review -> Decision -> Ledger -> Patch；
5. **安全边界明确**：LLM 产生候选，人确认后才能进入项目记忆和论文修改建议。

最大的剩余风险不是“能否把系统写出来”，而是：

> **用户是否认为 Impact Card 比论文摘要更能帮助他作出项目决策。**

因此，第一周代码必须优先验证 Impact Card，而不是优先完成所有解析器、数据源和后台能力。

---

## 1. 产品定位审查

### 1.1 产品定位成立

当前一句话定位建议固定为：

> **Research Radar 持续监测新研究，指出它影响了你项目里的哪条主张、影响成立的条件，以及你应该改实验、改表述还是补讨论。**

这个定位比“学术搜索 Agent”“AI 论文助手”或“论文雷达”更具体，因为它同时定义了：

- 输入：用户自己的研究项目与 Claim；
- 外部变化：新论文、竞争工作、撤稿；
- 核心处理：条件化影响判断；
- 输出：项目动作和论文修改建议。

### 1.2 真正的差异点成立

Scite 已覆盖支持/反对型 citation context，Litmaps 已覆盖论文监测。因此产品不能只卖“支持/反证”和“每周提醒”。当前差异点已经足够清晰：

```text
公开论文/主题集合条件化
        -> 用户私有 Research Case / Claim 条件化

告诉你论文相关
        -> 告诉你影响哪条主张、为什么、接下来做什么

一次搜索结果
        -> 可持续更新的决策和论文修改历史
```

### 1.3 产品边界合理

首版只做 CS/AI empirical Claim 是正确选择：

- benchmark、dataset、metric、baseline 相对结构化；
- arXiv 新工作到达快；
- 用户本人能判断影响是否真实；
- 可以在不依赖医院、实验室和企业私有系统的情况下演示。

首版不应把自己包装为全学科科学真理判断器。

---

## 2. 用户与购买者审查

### 2.1 首个用户画像已经足够具体

```text
高年级 CS/AI 博士生或 Research Lead
  - 有正在写的论文或项目说明
  - 有 10-20 条可识别的项目主张
  - 每周需要跟踪 arXiv / conference 新论文
  - 面临 prior art、竞争路线和实验边界变化
```

这个用户能同时提供自己的文稿、确认 Claim、判断系统是否有用，适合作为首个 pilot user。

### 2.2 用户与长期买方不同，但不阻止 Demo

- 使用者：博士生、Postdoc、Research Lead；
- 长期买方：PI、实验室、企业研究团队、机构；
- MVP 首先验证使用价值，不需要现在完成团队采购、权限或机构部署。

后续商业化验证必须回答：PI 是否愿意为团队统一的 Claim Ledger、竞争雷达和研究完整性提醒付费。但这不是开始写 Demo 的前置条件。

---

## 3. 核心用户任务审查

### 3.1 核心 Job-to-be-Done 成立

> 当一篇新论文出现时，帮我在 10 分钟内判断：它是否实质影响我的项目，影响哪条主张，为什么，以及我是否需要采取行动。

这个任务有明确触发时刻、输入、决策和完成标准，可以被真实用户测试。

### 3.2 五个使用场景应看作一个闭环，而不是五套功能

| 场景 | 在闭环中的位置 | 产品对象复用 |
|---|---|---|
| 每周雷达报告 | 入口 | ScanRun + Impact Summary |
| 核心主张被挑战 | 高风险影响 | Impact Card + Claim Health |
| 竞争对手预警 | 战略附加信息 | strategic flag + Watch Entity |
| 引用论文被撤稿 | 研究完整性影响 | integrity event + claim-source link |
| 写作时查看支持和反证 | 价值沉淀 | Claim Ledger + Evidence Pack + Patch |

它们不需要五套独立后台。共同的数据主线是：

```text
ResearchEvent
  -> affected Claim
  -> evidence and conditions
  -> review decision
  -> action / patch / ledger
```

这使五场景进入 MVP 后仍然可控。

---

## 4. 首次价值审查

### 4.1 当前最大的产品风险：首次使用成本偏高

如果新用户必须先上传论文、等待解析、审查 20 条 Claim、配置检索规则，可能 20-30 分钟后才看到价值。这对 Demo 不利。

因此产品需要两个入口：

```text
入口 A：Explore Demo Case
  立即打开预置 Case 的 3 张 Impact Cards
  用于展示价值和测试核心体验

入口 B：Create My Case
  上传论文 -> 确认前 5 条核心 Claim -> 第一次扫描
  用于验证真实 onboarding
```

Demo 演示必须从入口 A 开始，不从上传文件或空白聊天框开始。

### 4.2 首个 Wow Moment 已经明确

用户打开一张 challenge 卡后，在一个页面里看到：

```text
我的 Claim C7
+ 自己论文的原文
+ 新论文的反向证据
+ dataset / metric / budget 的条件差异
+ “建议增加边界讨论，而不是直接认定结论错误”
```

如果这个时刻不能让用户觉得“这比论文摘要更接近我的真实决策”，其他功能没有继续扩张的意义。

### 4.3 Time to Value 目标

| 模式 | 目标 |
|---|---|
| Demo Case | 30 秒内看到第一张 Impact Card |
| 自己的 Case | 10 分钟内确认前 5 条 Claim 并看到候选影响 |
| 单张影响 review | 2 分钟内完成 confirm/edit/dismiss |

---

## 5. 信息架构与交互审查

### 5.1 三个页面足够

1. **Case Setup / Claim Review**；
2. **Weekly Radar / Impact Workspace**；
3. **Claim Ledger / Evidence Pack / Patch Review**。

Weekly Summary 放在 Impact Workspace 顶部，不增加独立大屏。

### 5.2 用户不应被迫理解内部技术术语

| 内部术语 | 用户界面文案 |
|---|---|
| ClaimContract | Project Claim / 条件 |
| ImpactHypothesis | 待确认影响 |
| comparability coverage | 这些结果能否直接比较？ |
| strategic_flag=competitor | 竞争团队提醒 |
| abstain | 信息不足，暂不判断 |
| revalidation_required | 需要重新验证 |
| PatchProposal | 论文修改建议 |
| Trust Envelope | 判断依据与运行记录 |

技术结构保留在系统内，界面只展示用户作决策所需的信息。

### 5.3 Impact Card 应按动作排序

默认顺序：

```text
Critical
  核心 Claim 的高可比挑战、关键引用撤稿

Review
  部分可比挑战、竞争工作、需要补实验或收窄表述

Informative
  支持证据、背景引用、新方法线索
```

不能只按论文发布时间或模型相似度排序。

---

## 6. 功能范围审查

### 6.1 P0 功能没有方向性遗漏

当前 P0 已覆盖：

- Case 与文稿；
- Claim review；
- Historical Scan；
- Claim routing；
- 条件对齐；
- Impact Card；
- Weekly Summary；
- competition flag；
- retraction propagation；
- confirm/edit/dismiss；
- Claim Ledger；
- Evidence Pack；
- PatchProposal；
- 审计和可信 Gate。

从产品故事看已经完整，不需要再增加新功能后才开工。

### 6.2 但代码第一版不能同时“深做”全部 P0

P0 中有三类能力：

| 类型 | 功能 | 第一版实现深度 |
|---|---|---|
| 核心价值 | Claim -> Impact -> Decision -> Ledger -> Patch | 必须真实跑通 |
| 场景视图 | Weekly Summary、competition、retraction | 使用 fixture 和简单规则证明可扩展 |
| 基础设施 | live API、调度、实体消歧、团队权限 | 暂不实现或只做 adapter interface |

因此竞争预警和撤稿在 Demo 中是同一 Impact Pipeline 的不同 event type，不应分别开发成大型子系统。

### 6.3 继续禁止进入首版的能力

- 自动应用论文修改；
- 自动改变正式 Claim 状态；
- 多 Agent 自由循环；
- Graph DB / GraphRAG；
- 全学科 Schema；
- 真实团队权限；
- 邮件和插件；
- 独立代码/数据集监测；
- 自动实验执行；
- 未经校准的真实性概率。

---

## 7. 产品指标审查

### 7.1 Demo 不能只用模型指标验收

模型准确率重要，但产品是否成立需要同时看四层指标：

| 层 | 指标 |
|---|---|
| 发现 | Golden Case material-impact Recall@20 |
| 可信 | high-risk challenge precision、证据定位通过率、abstain |
| 决策 | Impact Card confirm + meaningful edit 比例、单卡 review 时间 |
| 行动 | cite/discuss/experiment/patch 被接受的比例 |

### 7.2 建议的首轮产品 Gate

对 3-5 位目标用户测试后：

- 80% 以上用户无需解释就能理解 Impact Card；
- 单卡 review 中位时间低于 2 分钟；
- 至少 50% Impact Cards 被 confirm 或产生实质 edit；
- 每位用户至少有一条影响导致 cite/discuss/run comparison/narrow claim；
- 所有可见 Impact Card 都有可回查双边 evidence；
- 用户认为它比“标题 + 摘要 + 相似度”更支持项目决策。

这些是继续产品化的 Gate，不是需要在写第一行代码前证明的条件。

---

## 8. 正确的开发顺序：先做 Walking Skeleton

v0.6 的技术模块保持不变，但从产品风险看，开发顺序应调整。

### Phase A：三天内做出价值闭环

全部使用 Golden Case 和人工 gold 数据：

```text
Weekly Summary
  -> Impact Queue
  -> Evidence Inspector
  -> confirm/edit/dismiss
  -> Claim Ledger
  -> PatchProposal
```

目标：先让用户体验并评价产品，不等待真实 LLM pipeline。

### Phase B：替换为真实 Impact Engine

- Claim routing；
- evidence extraction；
- condition comparison；
- stance / impact mode；
- exact span Trust Gate；
- abstention。

目标：用模型输出逐步替换 gold Impact Cards。

### Phase C：增加自己的 Case onboarding

- `.tex/.md` ingestion；
- Claim extraction；
- Claim review；
- centrality 与条件编辑；
- WatchSpec 生成。

目标：用户可以从自己的论文进入同一闭环。

### Phase D：证明五场景扩展性

- weekly summary；
- competitor fixture；
- retraction fixture；
- Evidence Pack；
- patch export。

### Phase E：最后接 live adapters

- arXiv；
- optional Semantic Scholar；
- optional Crossref；
- caching、rate limit 和 fallback。

这种顺序能在第 3 天发现“Impact Card 产品体验是否成立”，而不是第 10 天才第一次看到核心页面。

---

## 9. 第一个 Demo 的五分钟脚本

```text
00:00  打开预置 Research Case
00:20  Weekly Radar：3 篇相关，1 条 critical，1 条 competitor，1 条 support
00:40  打开核心 Claim challenge
01:10  对照双方 evidence
01:40  展开 condition delta，看到 compute budget 未知
02:10  将动作从 narrow claim 改为 add boundary discussion
02:40  Confirm
03:00  Claim Ledger 出现 confirmed challenge
03:30  打开 competitor alert，说明它是战略标记而非学术反证
04:00  打开 retraction event，展示对引用 Claim 的影响传播
04:30  生成 Discussion Evidence Pack 和 PatchProposal
05:00  展示审计与回滚依据
```

这个脚本已经可以同时表达用户价值、技术差异和可信边界。

---

## 10. 开工前只需冻结的产品资产

不需要继续写更多战略文档。开始编码前准备：

1. **一个 Golden Case**：真实 CS/AI 论文与 10 条 Claim；
2. **五张核心 Impact Cards**：support、challenge、boundary、competitor、retraction；
3. **三张 PatchProposal**：补引用、边界讨论、重新验证；
4. **一份五分钟 Demo script**；
5. **一套 UI 文案**：避免“推翻”“自动真理”等表述；
6. **一个隐私决定**：用户论文发送给哪个模型、保存什么、如何删除。

这些资产可以在开发 D1-D2 同时完成，不构成继续等待的 blocker。

---

## 11. Week 1 产品退出门

第一周结束时，不以“完成了多少后端模块”为标准，而要求：

- 用户能从 Weekly Summary 进入一张 Impact Card；
- 不看说明文档也知道 Claim、证据差异和建议动作；
- 能完成 confirm/edit/dismiss；
- 确认后 Ledger 发生可见变化；
- 能看到一份由该确认生成的 PatchProposal；
- 整个流程不出现聊天式长答案；
- 3 名目标用户中至少 2 名认为这个闭环值得继续使用。

若这个 Gate 不通过，优先修改对象、文案和交互，不扩大检索源或增加 Agent。

---

## 12. 最终 Go / No-Go 清单

| 审查项 | 结论 |
|---|:---:|
| 用户问题是否真实 | GO |
| 目标用户是否足够具体 | GO |
| 相对现有论文搜索是否有差异 | GO |
| 是否有明确首次价值 | GO |
| 五个场景是否共用一套对象 | GO |
| Demo 是否能在 2-3 周内完成 | GO |
| 技术风险是否有人工与规则兜底 | GO |
| 是否需要先完成实时监控和团队系统 | NO |
| 是否需要继续扩充功能再开工 | NO |
| 是否可以开始写代码 | **YES** |

---

## 13. 开工命令

产品侧建议正式冻结：

```text
Build target:
  单用户 CS/AI Research Case Demo

First vertical slice:
  Weekly Summary
  -> Impact Card
  -> Evidence Review
  -> Decision
  -> Ledger
  -> PatchProposal

Default data:
  Golden Historical Case

Success:
  用户在 5-10 分钟内作出一项有证据的项目决定
```

**审查结论：可以从现在开始写代码。**

---

*产品开工后的第一目标不是“把路线图实现完”，而是证明用户愿意基于一张可追溯 Impact Card 改变项目动作。*
