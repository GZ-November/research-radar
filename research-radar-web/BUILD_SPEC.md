# Research Radar — Web UI 重建规格

把现有 Streamlit 应用「Research Radar」（科研论文·文献影响监控 Agent）重建为独立 React 网站（纯前端，无后端，数据全部来自 `src/data/seed.json` 真实导出）。**保留现有 UI 的全部功能与内容，视觉全面重新设计**。

风格定位：**科研 · 简约 · 大气**。安静、专业、可信赖的学术工作台气质 — 大量留白、细发丝线分隔、克制而清晰的信息层级，深青色作为唯一强调色，杜绝营销感装饰。

## 0. 强制阅读（设计系统）

实现前必须按顺序阅读 Kimi Design Skill 参考文件（只读）：

1. `/Users/georgezhu/Library/Application Support/kimi-desktop/daimon-share/daimon/skills/kimi-design-skill/references/principles.md`
2. `/Users/georgezhu/Library/Application Support/kimi-desktop/daimon-share/daimon/skills/kimi-design-skill/references/tokens.json`
3. `.../references/components-web.md`（索引），然后 `.../references/web-best-practices.md`
4. `.../references/animation.md`（所有交互状态遵守）
5. 用到的组件如有对应 `references/components-web/*.md`（如 button、dialog、tabs、table、badge、toast），必须阅读并遵守其组件契约

设计决策要点（结合 tokens 与本产品气质）：
- 浅色模式。页面底色用 `color.background.groundPc.light` (#f9fbfc)，卡片/表面用 `#ffffff`，分隔用 `color.separator.s1.light`（发丝线，避免重投影）。
- 文字层级用 `color.labels.*`：primary rgba(0,0,0,.9) / secondary .6 / tertiary .45 / quaternary .3。
- **品牌强调色**：科研深青 `#0E7490`（teal-700），hover `#155E75`，软底色 `#F0FAFB`。作为语义化 accent 贯穿（主按钮、激活导航、链接、进度、证据块左边条）。记录为 token 缺口（tokens.json 无 teal accent，这是产品品牌色）。
- 状态色：danger `color.status.danger`、警告橙 `color.status.orange`、成功绿 `color.status.positiveGreen`、信息蓝 `color.status.kimiBlue`；浅色软底用 `color.others.lightRedBg/lightOrangeBg/lightGreenBg/kimiBlue10`。
- 字体：PingFang SC 系统栈（`-apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif`）；等宽 `ui-monospace, SFMono-Regular, Menlo, monospace`（用于 locator、版本号、模型名、DOI）。
- 字阶遵守 `typography.webUI.*`：页面大标题 largeTitleEmphasized(20/600)，节标题 t2Emphasized(16/500)，正文 b1/b2(15/14)，说明与标签 c1(12)，小标签 c2(10)。英文/数字展示可用 600–700 字重制造"大气"感，但不引入新字号体系之外的随意尺寸（页面 Hero 数字指标可用 28–32px 展示数值，属 reading/display 场景，记录为扩展）。
- 交互：遵守 animation.md；hover/pressed/focus/disabled/loading 状态齐全；focus-visible 用 kimiBlue。
- 深色侧边栏：`#0D1420` 底，文字 `rgba(255,255,255,.84)`，次级 `rgba(255,255,255,.56)`，分隔 `rgba(255,255,255,.08)`，激活项用 teal 左指示条 + `rgba(255,255,255,.06)` 底。

## 1. 技术约束

- 项目根：`/Users/georgezhu/Desktop/InkMind Agent DEMO/research-radar-web`（React+TS+Vite+Tailwind+shadcn/ui 已装好）。
- **纯前端**：不得请求任何后端/网络 API。全部数据 import 自 `src/data/seed.json`。交互（采用/不采用、确认 Claim、批准改写、添加监控、保存设置、开始/完成行动等）用 React state 实现，操作后 UI 即时更新即可（toast 反馈），刷新可重置，不要求持久化（可用 localStorage 更好）。
- 路由：用轻量 state 路由或 react-router（如安装）均可；6 个页面 + 项目切换。
- 文案：**所有 UI 文案必须逐字使用本规格中的中文原文**（这是产品内容的一部分）。
- 图标：优先 lucide-react；severity/priority 的 🔴🟠🔵⚪ 与 claim 的 ✓○↺ 语义保留（可用彩色圆点/图标实现，不强制 emoji）。
- 页面标题 `Research Radar`，favicon 可用 ⌖/🔭 语义。
- 构建必须 `npm run build` 通过（无 TS 错误）。

## 2. 数据（src/data/seed.json）

真实导出：`{ cases: Case[] }`，4 个项目（含 1 个 demo 示例项目 `is_demo`）。每个 case：

- `id, title, research_question, is_demo, settings(含 generated_search_queries.queries), created_at`
- `versions[]`: `version_no, file_name, source_type, is_current, created_at`
- `claims[]`: `stable_key, lifecycle_state, revisions[]`；revision: `revision_no, statement, claim_type, centrality(core/major/minor), contract{task,dataset,split,metric,comparator,scope}, falsifiable_condition, source_quote, source_locator, review_state, is_current_version, manuscript_version_id`
- `scans[]`（最多 5 条，新的在前）: `status, started_at, finished_at, queries[], stats{progress, search_queries, newest_publication, analysis_model, full_text_papers, integrity_flagged, crossref_enrich_failures, embedding_provider/model/degraded, scanned/routed/related...}, error_message`
- `latest_scan_id`；`impacts[]`（最近完成扫描的）: `stance, impact_mode, comparability, severity, suggested_action, review_state, trust_state, change_depth, event_type, strategic_flags, condition_differences[{field,own_value,incoming_value,status,explanation}], evidence_own{quote,locator}, evidence_new{quote,locator}, uncertainty[], claim_stable_key, claim_statement, source{title,authors[],published_at,url,doi,arxiv_id,venue,publication_type,pdf_url}, source_snapshot_abstract`
- `actions[]`: `action_type, priority, title, rationale, checklist[], due_label, status, advice_source, source_title, source_url, impact_candidate_id`
- `patches[]`: `target_locator, edit_class, before_text, after_text, citations, validations{impact_confirmed,before_text_exact,citations_resolved,citation_marker_safe,locked_numbers_unchanged,original_file_untouched}, approval_state`
- `watch_entities[]`: `entity_type(lab/author/org), canonical_name, aliases[]`
- `profile`: `{output{title,research_problem,central_thesis,contributions[],key_findings[],limitations[],watch_topics[],claim_profiles[{stable_key,role,claim_summary,contract,boundary_conditions[]}]}, model, created_at}` 或 null
- `model_runs[]`（最近 20）: `stage, provider, model, latency_ms, estimated_cost, validation, created_at`
- `audit_events[]`（最近 30）、`review_decisions[]`

设置为「已配置远程 API，模型 deepseek-v4-pro」的演示状态（不展示任何真实密钥；API Key 输入框显示掩码占位 `········8300` 之类的假掩码）。

## 3. 标签字典（逐字复用）

- SEVERITY: critical→紧急 / review→需审查 / informative→参考
- STANCE: supports→支持 / challenges→挑战 / neutral→中性 / uncertain→信息不足
- HEALTH（仅人工确认）: active→有效 / corroborated→已被支持 / contested→存在争议 / revalidation_required→需要重新验证
- ATTENTION（自动）: stable→稳定 / new_support→出现新的支持证据 / needs_review→需要审查 / disputed→存在争议 · 需要团队决策 / competitor_pressure→竞争压力 / revalidation_required→需要重新验证
- REVIEW_STATE: candidate→待确认 / confirmed→已确认 / edited→已修改确认 / dismissed→未采用 / informative→参考信息 / rejected→已拒绝 / superseded→已被新版本替代
- PRIORITY: critical→紧急 / high→高 / medium→中 / low→低
- COMPARABILITY: compatible→可比 / partial→部分可比 / incompatible→不可比 / unknown→未知
- ACTION_STATUS: proposed→待采用 / open→已采用 · 待开始 / in_progress→进行中 / done→已完成 / dismissed→已关闭
- SCAN_STATUS: pending→排队中 / running→扫描中 / cancel_requested→取消中 / completed→已完成 / failed→失败 / interrupted→已中断 / cancelled→已取消
- IMPACT_MODE: replication→独立复现 / boundary_condition→边界条件 / method_substitution→方法替代 / prior_art→在先工作 / research_integrity→研究完整性 / no_material_change→无材料性变化
- SUGGESTED_ACTION: cite→引用 / add_boundary_discussion→补边界讨论 / run_comparison→跑对比实验 / narrow_claim→收窄 Claim / team_review→团队评审 / revalidate→重新验证 / watch→继续观察 / no_action→无需行动
- TRUST_STATE: generated→已生成 / grounded→已定位 / verified→已核验 / blocked→未通过校验
- CONDITION_STATUS: match→一致 / compatible_alias→别名一致 / partial→部分一致 / mismatch→不一致 / unknown→未知
- CENTRALITY: core→核心 / major→重要 / minor→次要
- EDIT_CLASS: add_citation→补充引用 / add_boundary_discussion→补充边界讨论 / add_limitation→增加局限说明 / qualify_claim→收窄表述 / experiment_todo→实验待办
- APPROVAL_STATE: candidate→待审批 / approved→已批准 / rejected→已拒绝
- VALIDATION 六项: impact_confirmed→影响已经人工采用 / before_text_exact→改写前文本可在当前文稿中精确定位 / citations_resolved→所有引用来源均已登记 / citation_marker_safe→未引入新的数字编号引用标记 / locked_numbers_unchanged→原文数字在改写后保持不变 / original_file_untouched→原论文文件未被修改
- CONTRACT 字段: task→任务 / dataset→数据集 / split→数据划分 / metric→指标 / comparator→对比基线 / scope→适用范围
- PUBLICATION_TYPE: preprint→预印本 / journal_article→已发表版本 / conference_paper→会议论文 / other→公开论文
- ACTION_TYPE: team_decision→团队决策 / experiment→改实验 / data→补数据/条件 / writing→调整写作 / cite→引用/关注 / competitor_response→竞争响应 / revalidation→重新验证
- 徽章配色：critical 红；high/橙；medium 蓝；low 灰；supports/active/confirmed/edited 绿；challenges/revalidation_required 红；review/contested/candidate 橙；neutral/dismissed/rejected/superseded 灰；uncertain 黄；informative 蓝。

## 4. 全局外壳

**深色侧边栏**（固定 264px 左右宽）：
1. 品牌块：teal 渐变方块 logo 标记 `⌖` + `Research Radar` + 小字 `文献影响监控 Agent`。
2. 分组小标签 `项目`（10px/500/大写/字距 .12em/灰蓝 #71809A 类色）。
3. 项目选择器（下拉，demo 项目显示 `{title} · 示例`）；下方小字显示该项目 `research_question`。
4. 项目状态：待处理 pill — 有 pending（proposed/open/in_progress 行动计数）显示琥珀 pill `{N} 项待处理行动`，否则绿 pill `没有待处理行动`；再下方小字 `上次扫描：YYYY-MM-DD HH:MM` 或 `尚未扫描`。
5. 幽灵按钮 `＋ 创建或管理项目` → 跳「项目工作台」。
6. 分组小标签 `导航` + 6 项导航：`项目工作台 / 本周行动 / 文献雷达 / 改进工作台 / 我的论文 / 设置`（图标 + 文字，激活态 teal 左条）。
7. 底部可放 LLM 状态：已配置时安静显示 `分析模型：deepseek-v4-pro`（小字 + 绿点）。

**全局确认对话框**：所有破坏性操作（不采用影响、不处理行动、拒绝改写、重置 Demo）弹出居中 Dialog：标题 `操作确认`，粗体操作名 + 说明正文 + 主按钮（动态文案如 `确认不采用`）+ `取消`。用 shadcn AlertDialog 或 Dialog。

**通用组件**：
- PageHeader：页面大标题 + muted 副标题（见各页）。
- EmptyState：虚线边框卡片、居中图标 + 粗体标题 + muted 提示。
- Badge：胶囊小徽章（上述配色）。
- EvidenceBlock：粗体标签 + 引用块（3px teal 左边条、#F0FAFB 底、引文斜体或正常）+ 等宽小字 locator（无则 `未登记位置`）。
- SourceTraceability（溯源块，各处复用）：`**[标题](url)**`；小字 `发表载体：{venue} · 公开日期：{YYYY-MM-DD}`（venue 空或 arxiv → `arXiv 预印本`，否则 `{venue} · {类型标签}`；日期缺失 `日期未登记`）；小字 `作者：a, b, c`；链接行 `[查看原文](url) · [打开 PDF 全文](pdf_url) · [DOI: xxx](https://doi.org/...)`，无 DOI 显示 `DOI：未登记`。
- MetricCard：白卡 + 发丝边框，小标签 + 大数值。
- Toast：操作反馈（sonner）。
- 主内容区：max-width 约 1200px，充足 padding，背景 #f9fbfc。

**采用指引 callout**（render_impact_status 复刻）：徽章行（severity + stance + impact_mode(蓝) + review_state）+ 一条指引（success/info/warning 样式），按优先级：
- dismissed → `已选择不采用：相关自动行动已关闭；你仍可重新采用这项影响。`
- confirmed/edited → `已采用：这个判断已进入证据账本，相关行动已转为可执行。`
- trust=blocked → `暂不可采用：证据校验未通过，需要先补齐原文证据。`
- no_material_change → `无需改变：条件矩阵和精确证据已保存；当前不要求修改实验、数据或写作。`
- research_integrity 或 event_type=retraction → `建议采用（紧急）：用于重新验证引用和实验；采用后会打开重新验证行动。`
- challenges + compatible/partial → `建议采用：用于团队决策和条件匹配实验；不会自动改写你的 Claim。`
- supports + compatible/partial → `建议采用为支持证据：用于 Discussion 和证据账本；仍需你确认引用方式。`
- boundary/prior_art/incompatible → `建议部分采用：只用于补实验边界、Related Work 或 Limitations，不作为直接支持/反驳。`
- uncertain → `先核对再采用：先检查原文条件和精确证据，再决定是否打开行动。`
- 其他 → `建议作为背景采用：用于研究定位或后续观察，不会自动改变核心主张。`

**影响决策块**（render_impact_decision，文献雷达与本周行动共用）：textarea 占位 `决策备注（可选）`；Popover `修改判断（可选）` 内含 select `影响类型`（6 种 IMPACT_MODE，预选当前）与 `建议动作`（8 种 SUGGESTED_ACTION，预选当前）+ 小字 `不修改时"采用"会直接确认当前判断。`；按钮：主 `采用这项影响`（no_material_change 时为 `确认无需行动`；已 confirmed/edited 则禁用）与次 `不采用`（已 dismissed 禁用）。采用 → toast `已采用：影响进入证据账本，相关行动已打开`；trust=blocked 时错误提示 `这条影响的证据校验未通过，暂时不能采用；请先补齐原文证据。`；不采用 → 确认对话框（`不采用这项影响` / `不采用会关闭这项影响生成的相关行动；之后仍可重新采用。` / `确认不采用`）→ toast `已记录不采用，并关闭相关行动`。

## 5. 页面一：项目工作台（Home）

- Hero 横幅：深青渐变条（`#123A47 → #0E7490`），白字 `Research Radar` + 副标 `盯住公开文献对你论文的影响，把变化变成可执行的行动。`
- PageHeader：`你的研究项目` / `上传或同步你正在推进的论文；Radar、证据和行动会按项目长期积累。`
- Tabs：`我的项目` | `新建项目`。
- 我的项目：项目卡片列表（白卡 + 发丝边框 + hover 微浮起）：标题（t2Emphasized）、research_question（muted）、右侧主按钮 `打开项目`（切换当前项目并跳「本周行动」）；3 个指标 `当前版本`(vN) / `已确认 Claim` / `最近雷达`(日期或 `尚未扫描`)；小字 `当前文稿：{file_name}`。demo 项目前加分隔线 + 小标题 `示例项目` + 小字 `示例只用于体验产品，不限制你创建和切换自己的研究项目。`。空态 🗂️ `还没有研究项目` / `到"新建项目"上传第一篇论文，即可开始监控公开文献的影响。`
- 新建项目：说明 `支持 .tex、.md 或文本可提取的 .pdf；之后可以继续上传新版本。`；表单：`项目/论文标题`（占位 `例如：My retrieval robustness project`）、`核心研究问题`（占位 `这个项目希望回答什么？`）、文件上传 `当前文稿`（tex/md/pdf，前端只做文件名展示）；主提交 `创建项目并提取 Claim`。校验失败提示 `请填写项目标题、研究问题并选择当前文稿。`；成功后 toast 并跳「我的论文」（演示：不必真的新建，也可真的往 state 加）。
- 页脚分隔线上：`**工作流程** · 导入/同步文稿 → 确认项目 Claim → 搜索最新公开论文 → 采用有用影响 → 执行实验、数据和写作行动`

## 6. 页面二：本周行动（Action Center）

- PageHeader：`这个项目现在需要做什么？` / `所有判断和行动都属于项目《{title}》。`
- 无扫描空态：🔭 `还没有联网搜索结果` / `先搜索最新公开论文，系统才能给出行动建议。` + 主按钮 `开始搜索最新公开论文` → 文献雷达。
- 头条横幅（三选一）：有紧急 → 红色 `**需要马上处理：** {headline}`；有开放行动 → 橙色 `**本周建议：** {headline}`；否则绿色 `最新公开论文中没有发现需要改变实验、数据或写作的材料性影响。`（headline 取优先级最高开放行动的 title，无则自拟合理句）。
- 溯源小字（点连接）：`arXiv 最新优先 · 混合检索 · {analysis_model} 影响判断 · {full_text_papers} 篇公开 PDF 全文 · 最新论文日期 {newest_publication} · 搜索主题：q1 / q2`。
- 两个按钮：`重新搜索最新公开论文`（→文献雷达）、主按钮 `打开改进工作台`（→改进工作台）。
- 6 个指标卡：`紧急` `改实验` `补数据` `调整写作` `竞争预警` `重新验证`（按 actions 统计）。
- 4 Tabs：`你要做什么` | `有用论文` | `受影响的主张` | `写作证据`。

### Tab 你要做什么
- 空态 ✅ `本周没有开放行动` / `最新扫描没有发现需要执行的任务；可以重新扫描查看最新公开论文。` + 按钮 `重新扫描最新公开论文`。
- 行动 = Accordion 项，标题 `{优先级色点} {action_type 标签} · {title}`（critical 默认展开）：徽章行（priority + status）；小字 `建议期限：{due_label} · 关联 Claim：{stable_key 或 —}`；正文 rationale；advice_source=llm 时小字 `AI 建议 · 基于《{source_title}》`；`**触发来源**` + 溯源块；小字 `影响：{stance} / {impact_mode} · 可比性：{comparability} · 审查状态：{review_state}`；`**执行清单**`（checkbox 列表）；status=proposed 时 info `先在"有用论文"中采用对应影响，再开始执行这项行动。`；4 按钮：`开始`、主 `完成`（proposed 禁用）、`不处理`（确认对话框：`不处理这项行动` / `行动会被关闭；之后如需恢复，可在"有用论文"中重新采用对应影响。` / `确认不处理`）、`查看证据`（有 impact 时，跳文献雷达并选中该影响）。

### Tab 有用论文
- 小标题 `这次搜索中值得你决策或继续观察的论文`；说明小字 `"采用"表示接受 Agent 对这篇论文影响的判断，并打开相关行动；不会自动修改你的论文或 Claim。每项判断都保留原文、PDF、DOI 和精确证据。`
- 材料性影响论文（Accordion，candidate 默认展开）标题 `{source.title} · {venue} · {指引短名}`：溯源块 → 分隔 → 采用指引 callout → `**影响的 Claim：{stable_key}** — {claim_statement}` → 小字 `建议动作：{x} · 证据状态：{trust}` → 证据块 `这篇论文中的精确证据`(evidence_new) → 有 uncertainty 时 `**采用前需要注意**` 列表 → 决策块 → 按钮 `查看完整比较`（跳文献雷达）。
- 小节 `已深度比较 · 暂无材料性影响`：no_material_change 行（Accordion `{title} · {venue} · 无需改变`）：小字 `比较对象：{claim} · 总体可比性：{x} · 判断状态：{x}`；证据块 `用于判断的精确证据`；小字 `{model} 已完成双方全文比较；你可以打开条件矩阵，把判断改为 prior art、边界条件或方法替代。`；按钮 `查看条件矩阵并修正判断`。

### Tab 受影响的主张
- 按 stable_key 排序的 Claim 卡片列表：`**{色点} {stable_key} · {attention 标签}**`（disputed/revalidation_required 红，competitor_pressure/needs_review 橙，其余绿）+ 最新已确认 revision 的 statement。attention 由该 claim 的影响推导：有 disputed/challenges → `存在争议 · 需要团队决策`；有 competitor flag → `竞争压力`；有 candidate 待审 → `需要审查`；有新 supports → `出现新的支持证据`；否则 `稳定`。

### Tab 写作证据
- 4 指标：`支持证据` `反证` `边界/相关工作` `完整性风险`。
- 4 子 Tabs：`支持证据` | `反证` | `边界与 prior art` | `完整性`。条目 = 折叠项 `{claim} · {source_title} · {已确认|待确认}`：小字 `{stance} · {impact_mode} · 可比性：{x}` + 引文块 + locator 小字 + 小字 `发表载体：{venue} · 公开日期：{date 或 未登记}` + 链接 `[查看原文] · [PDF 全文] · [DOI: …]` 或 `DOI：未登记`。空 → 小字 `暂无记录。`
- `**建议写作动作**`：`- {priority} · {status} **{title}** — {rationale}` 列表。
- 下载按钮 `下载 Discussion Evidence Brief`（前端生成 markdown 文本下载，文件名 `discussion-evidence-brief.md`）。

## 7. 页面三：文献雷达（Impact Workspace）

- PageHeader：`搜索最新公开论文` / `系统根据你论文的全文画像和核心 Claim 自动搜索，不需要你自己写检索词。`
- 顶部说明块：小标题 `当前项目：{title}`；正文 `点击一次后，Agent 会完成：**arXiv 最新论文搜索 → 混合检索 → 公开 PDF 全文提取 → {model} 读取你的文稿和公开论文全文并逐项比较 → 生成项目行动**。`；小字 `自动搜索主题：q1 · q2 · …`（settings.generated_search_queries.queries，无则显示 `未运行 AI 全文画像：搜索主题由研究问题自动生成。到"我的论文"跑一次 AI 全文画像，搜索会更准。`）；配置小字 `分析模型：\`deepseek-v4-pro\`（远程 API，发送完整文稿与命中论文全文） · 向量：未启用（纯关键词检索） · 已确认核心 Claim：{n}`；0 条已确认 Claim 时警告 `请先到"我的论文"确认至少一条核心 Claim。` + 按钮 `去确认 Claim`。
- Collapsible `扫描范围`：两个数字输入 `最多搜索公开论文`（8–60，默认 32，步进 4）与 `最多深度比较`（1–10，默认 3）；小字 `结果按 arXiv 提交日期从新到旧；只深度分析与已确认 Claim 最相关的论文。每篇论文需要两次结构化判断，Demo 建议保持 3 篇。`
- 主 CTA（宽大主按钮）：`搜索最新公开论文并告诉我该做什么`。点击 → 演示扫描进行态：脉冲点 + `Agent 正在工作：联网搜索并逐篇比较公开论文` + 进度条（可用 setInterval 模拟阶段文案：`搜索 arXiv 最新论文…` → `混合检索相关论文…` → `提取公开 PDF 全文…` → `逐项比较已确认 Claim…` → `生成项目行动…`）+ 按钮 `取消扫描`（点击后小字 `已请求取消：扫描将在当前阶段结束后停止。`，随后停在 cancelled 态）；完成后 toast 并展示扫描摘要。已有扫描时显示 `已有扫描进行中，请等待完成或先取消。`
- 扫描状态信息（按 latest scan status）：failed → 错误 `最近一次扫描失败：{error}` + 按钮 `重试扫描`；interrupted → 警告 `上次扫描被中断（页面刷新或服务重启），结果可能不完整，可重新发起扫描。`；cancelled → info `上次扫描已取消，取消前完成的中途结果已保留。`；无扫描 → 空态 🛰️ `还没有联网扫描结果` / `点击上方按钮，Agent 会完成搜索、全文比较并生成项目行动。`
- 扫描摘要区：分隔 + 小标题 `最近一次真实扫描` + 小字 `最近一次扫描：YYYY-MM-DD HH:MM`；有撤稿时警告 `⚠️ {n} 篇文献被撤稿标记`；6 指标：`公开论文` `深度比较` `材料影响` `紧急` `竞争预警` `完整性`（从 stats/impacts 统计）；info 块含行动 headline + 主按钮 `查看我要做什么`（→本周行动）；零影响时 success `本次扫描没有需要审查的材料性影响。`
- 双栏工作区（左队列约 30% / 右详情 70%）：
  - 左：`影响队列` 列表项 `{severity 色点} {stable_key} · {stance} · {source title}`（选中态高亮）。
  - 右详情：`### {图标} {stable_key} — {claim_statement}`；小字 `证据状态：{trust 标签}`；采用指引 callout；有 competitor flag → 警告 `竞争团队提醒：这是战略标记，不代表 support 或 challenge。`；event_type=retraction → 错误 `该引用来源出现撤稿记录。确认后 Claim Health 才会变为"需要重新验证"。`
  - 3 Tabs：`比较矩阵` | `证据` | `决策`。
    - 比较矩阵：`总体可比性：**{标签}**`；非 compatible 时警告 `当前条件不是"可比"：程序禁止输出支持/挑战结论，只能作为信息不足、边界、在先工作或后续实验线索。`；表格列 **`字段 | 本方 | 公开论文 | 状态`**（缺失 —）；Collapsible `逐项比较说明`：每项 `{field} · {status} — {explanation}`。
    - 证据：`**可追溯来源**` + 溯源块 → 分隔 → 证据块 `你的文稿`(evidence_own) → 证据块 `公开论文`(evidence_new) → 小字 `两段引文均经过原文精确区间校验。`
    - 决策：`**为什么重要**`（用 rationale/abstract 合理呈现）；小字 `当前判断：{mode} · 建议动作：{action}（可在下方"修改判断"中调整）`；有 uncertainty → `**不确定因素**` 列表；no_material_change 时 info `当前判断为"无需改变"。你仍可以根据条件矩阵和原文证据，把它改为 在先工作、边界条件或方法替代，再采用相应动作。`；然后决策块。

## 8. 页面四：改进工作台（Ledger & Patch Review）

- PageHeader：`改进工作台` / `核对已采用影响，生成可审阅的最小改写；原论文文件永远不会被自动覆盖。`
- info 横幅：`工作流：① 在文献雷达核对条件矩阵和证据 → ② 采用或修正影响 → ③ AI 生成最小改写 → ④ 验证数字、引用和原文定位 → ⑤ 人工批准并下载。`
- Collapsed Collapsible `三个真实论文例子：影响应该怎样变成改进`：三个带 arXiv 链接的示例（Emergent Abilities vs Mirage → 补连续指标/收窄表述/limitation；TAP-RAG vs E-Agent → 跨设置 comparison/继续观察；Agentic RAG SoK → `prior_art + cite` Related Work 改写），用合理排版简述。
- 无 Claim 空态 🧾 `这个项目还没有 Claim` / `先到"我的论文"确认至少一条核心 Claim，再回来生成改写方案。` + 主按钮 `去确认 Claim`。
- Select `选择要改进的 Claim`（显示 stable_key）。
- Claim 账本区：小标题 `{stable_key} · {statement}`；一行 `Claim 状态 {health 徽章} ・ 当前 Radar 关注 {attention 徽章}`（两层状态：health 仅由人工确认推导、attention 自动）；health=active 时小字 `当前没有已人工确认的支持/挑战/完整性影响；待确认的判断不会改变本状态。`；3 Tabs（带计数）`支持证据 · {n}` | `挑战证据 · {n}` | `完整性 · {n}`：条目 `**{source_title}** · {mode} · {review_state}` + 引文块 + locator 小字；空 → `暂无人工确认记录。`；下载 `导出证据包（JSON）`（生成 JSON 下载，文件名 `evidence-pack-{stable_key}.json`）。
- 最小改写方案区：小标题 `最小改写方案`；无已采用影响时 info `先到"文献雷达"核对并采用一条材料性影响，才能生成改写方案。`；每条已采用影响 = 折叠项 `{source_title} · {mode} · {suggested_action}`：`[查看触发论文原文](url)` + 引文块 + 小字 `建议落点：{target} · 改进方式：{change} · 条件可比性：{x}` + 主按钮 `用 AI 生成最小改写方案`（演示：点击 loading 1–2 秒后若已有 patch 数据则展示，否则 toast `AI 改写失败：演示环境未连接分析模型`）。
- 每个 PatchProposal = 展开的卡片 `{edit_class 标签} · {approval_state 标签} · {target_locator}`：两栏 `**改写前**` / `**改写后**` 代码块（等宽、白底/浅灰底）；`**自动验证结果**` 六项 ✅/❌ 清单；按钮：主 `批准并允许导出`（有未通过项时错误 `这版改写未通过校验，不能批准。未通过项：…。请查看上方校验清单，修正后重新生成。`）与 `拒绝这版改写`（确认对话框 `拒绝这版改写` / `拒绝后该改写方案会标记为已拒绝；之后可以重新生成新的改写方案。` / `确认拒绝`）；approved 时下载按钮 `下载已批准改写`（`patch-{id}.md`）。
- 审计区（Collapsible `证据、模型运行与审计记录`）：小字 `共 {n} 条审计事件（仅最近 500 条）· 仅保存在本机` + 审计事件表格；`**模型运行与确定性阶段（最近 20 条）**` 表格列 **`阶段 | 提供方 | 模型 | 耗时(ms) | 估算成本 | 验证结果`**；下载 `导出审计记录（JSON）`（`research-radar-audit.json`）。
- demo 项目专属：按钮 `重置 Demo 决策`（确认对话框：`重置 Demo 决策` / `将删除并重建 Golden Demo 项目的全部扫描、影响和决策记录；你自己上传的项目不受影响。` / `确认重置`）→ toast。

## 9. 页面五：我的论文（Case Page）

- PageHeader：标题 = 项目名，副标 = research_question。
- 4 指标：`当前文稿`（文件名）`版本`（vN）`当前 Claim`（当前版本条数）`已确认`。
- 4 Tabs：`文稿与版本` | `项目主张` | `AI 全文画像` | `竞争监控`。

### Tab 文稿与版本
- 小标题 `同步当前论文`；小字 `上传新版本不会覆盖历史文件。系统会保留仍然存在的 Claim，把新增或改写结果放入待确认队列。`；文件上传 `上传新版本` + 主按钮 `同步为新版本`（演示：toast `已同步 v{n+1}：保留 x 条稳定 Claim，发现 y 条新候选。` 即可，不必真改数据）。
- `**版本历史**` 表格列 **`版本 | 文件 | 状态 | 导入时间`**（状态 `当前`/`历史`）。

### Tab 项目主张
- 空态 📝 `尚未找到实验类 Claim 候选` / `请检查文稿中的实验结论，或同步一个新版本文稿。`
- >20 条时：Select `按状态过滤`（`全部/待确认/已确认/历史记录`）+ 分页。
- 每条 Claim = Accordion `{图标} {stable_key} · {centrality 标签} · {statement}`（图标：当前+已确认 ✓绿 / 当前候选 ○ / 历史 ↺；首个当前候选默认展开）：小字 `状态：{review_state} · 来自 v{n} · {source_locator}`；历史项警告 `这条 Claim 未在当前版本中精确匹配，只保留为历史记录。`；引文块 source_quote；`**实验条件（Claim 合同）**` 两列表格 `字段 | 值`（空 —）；`**可证伪条件**` + 文本。
- 候选操作 4 按钮：主 `确认 Claim`、`拒绝`、`编辑`、`拆分`。编辑 → Dialog `编辑 Claim`：textarea（预填 statement）+ Select `重要程度`（核心/重要/次要）+ textarea `可证伪条件` + 主提交 `保存为已确认版本` + `取消`。拆分 → Dialog `拆分 Claim`：textarea `拆分（每行一条 Claim）` + 提交 `拆分为多条候选` + `取消`。（演示：操作后 toast + 本地 state 更新即可）

### Tab AI 全文画像
- 无已确认 Claim → info `先在"项目主张"中确认至少一条当前版本 Claim。`
- 主按钮 `用 deepseek-v4-pro 分析当前版本全文`；小字 `会把当前完整文稿和已确认 Claim 发送给 deepseek-v4-pro。`（演示：loading 后若已有 profile 则展示，否则 toast）
- 无 profile → info `当前版本尚未生成全文理解画像。`
- profile 展示：小标题 = profile.title；`**研究问题**`、`**核心论点**` 段落；两栏：`**主要贡献**` + `**关键发现**` 列表 | `**局限**` + `**每周监控主题**` 列表；`**已确认 Claim 画像**` 每条 Accordion `{stable_key} · {role} · {claim_summary}`：合同表格 + boundary_conditions 列表。

### Tab 竞争监控
- 每条 watch：`**{canonical_name}** · \`{类型}\``（lab→实验室/团队 / author→作者 / org→机构）+ `别名：a, b` + 按钮 `删除`（本地 state 删除）。
- 空 → info `当前项目尚未配置竞争对手别名。`
- 表单 `**添加监控对象**`：输入 `团队/作者名称`、Select `类型`、输入 `别名（用逗号分隔，可留空）`、主提交 `添加监控`；空名错误 `请填写团队/作者名称。`

## 10. 页面六：设置（Settings）

- PageHeader：`设置`；状态条：success `当前分析模型：\`deepseek-v4-pro\`（远程 API）`。
- 表单卡片：
  - 小标题 `分析模型`；Radio `模式`：`远程 API` / `本地 Ollama`（help `本地 Ollama 模式下文稿不出本机，配置后优先于远程 API。`）。
  - 远程：`Provider`（占位 `deepseek`）、`Base URL`（`https://api.deepseek.com`）、`模型名称`（`deepseek-chat`）、`API Key`（password，占位 `已保存 ····8300，留空表示不修改`，help `已保存 Key 时只显示后 4 位；留空表示不修改。`）。
  - 本地：`本地模型名称`（`qwen3:4b`）、`Ollama 地址`（`http://127.0.0.1:11434`，help `Docker 容器内访问宿主机 Ollama 时填 http://host.docker.internal:11434`）。
  - 小标题 `向量检索（可选）`；Select `向量模型 Provider`：`不启用` / `本地 Ollama` / `OpenAI-compatible API`（help `不启用时检索退化为纯关键词匹配，其他功能不受影响。`）；Ollama → `Embedding 模型`（`qwen3-embedding:0.6b`）+ `Ollama 地址`；OpenAI → `Embedding 模型`（`text-embedding-3-small`）、`Embedding Base URL`（`https://api.openai.com/v1`）、`Embedding API Key`（password）。
  - 小标题 `其他`：`Crossref 联系邮箱`（help `发送给 Crossref API 的联系地址（礼貌池），建议填真实邮箱。`）。
  - 主提交 `保存设置` → toast `设置已保存，立即生效。`
- 分隔 + 小字 `测试连接基于当前已保存的配置；失败不影响保存。` + 按钮 `测试连接`（loading `正在测试连接…` → 演示显示 `连接成功：远程服务可用，当前模型 \`deepseek-v4-pro\`。`）。

## 11. 品质要求

- 信息密度高但不拥挤：科研工作台的"大气"来自留白节奏与层级，不是大号元素堆砌。
- 所有列表/表格处理空态与长文本截断；长论文标题最多两行省略。
- 数字、日期、locator、模型名用等宽字体。
- hover/active/disabled/focus/loading 状态完整；Accordion/Tabs/Dialog 动效遵守 animation.md。
- 响应式：≥1280px 完整双栏；窄屏优雅降级（侧边栏可折叠为抽屉，双栏工作区变单栏）。
- 无 console 报错；`npm run build` 通过。

## 12. 实现说明（React 重建版，2026-07）

**Token 缺口记录**（tokens.json 中不存在、按 principles.md 记录的扩展）：

- 品牌深青 accent `#0E7490` / hover `#155E75` / 软底 `#F0FAFB` / 深色渐变端 `#123A47` —— 产品品牌色，tokens.json 无 teal accent，已在规格 §0 记录，实现为 Tailwind `radar` 色阶。
- Hero 数字指标 28px/600（MetricCard 大数值）—— reading/display 场景扩展，规格 §0 已记录；用等宽字体 + tabular-nums。
- 徽章文字色：tokens 的状态色（#ff3849 等）直接做白底文字对比度不足，徽章文字使用同色相加深色（如 `#c22e3a`、`#b06800`、`#0d7a35`、`#0f64cf`），底色与圆点仍用 token 原色（lightRedBg/lightOrangeBg/lightGreenBg/kimiBlue10/lightYellowBg）。属对比度原则优先于 token。
- 深色侧边栏 `#0D1420` 及 `rgba(255,255,255,.84/.56/.08/.06)`、分组灰蓝 `#71809A` —— 规格 §0 明确指定，tokens.json 无对应 sidebar token。
- 缓动 `cubic-bezier(0.23, 1, 0.32, 1)`（animation.md ease-out）注册为 Tailwind `ease-radar` 工具类。

**实现要点**：

- 路由：react-router v7 声明式路由（`/`、`/actions`、`/radar`、`/ledger`、`/case`、`/settings`），项目切换与跨页“查看证据”跳转通过 `src/store/AppStore.tsx` 全局 store；决策/行动状态/Claim 编辑/监控对象/设置持久化到 localStorage（key `research-radar-state-v1`）。
- 全局确认对话框：`useAppStore().confirm()` Promise 化，AlertDialog 360px 固定宽，标题 `操作确认`。
- 徽章/色点字典集中在 `src/lib/labels.ts`（全部中文文案逐字来自规格 §3）。
- 文件下载（Discussion Evidence Brief、证据包 JSON、审计 JSON、已批准改写 md）均为前端 Blob 生成。
- 扫描为前端模拟（setInterval 阶段文案 + 进度条 + 取消态），不产生网络请求。
