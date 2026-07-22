# Research Radar Agent 验证报告

> **过期说明（2026-07-22）**：本报告记录的是 2026-07-21 的验证状态，此后系统经过一轮大改造（统一 LLM factory 本地/远程切换、后台扫描任务、数据库迁移机制、Crossref 诚信检查入管线等），测试数与部分结论已过时，仅作历史参考，现状以 README 和 `scripts/verify_live_stack.py` 为准。

验证日期：2026-07-21

## 结论

当前版本已经收缩为 **单论文可用 Demo**：主界面固定绑定 RARE，不再展示 Golden Case 或多 Case选择；系统真实搜索最新 arXiv 公开论文、提取命中 PDF 全文，并由本地 Qwen3 生成实验与写作行动。

不建议现阶段直接作为无人值守生产系统运行；RARE 论文仍需先人工确认 3–5 条核心 Claim，且线上检索目前以 arXiv 元数据和摘要为证据来源。

## 验证结果

| 模块 | 结果 | 说明 |
| --- | --- | --- |
| Python 自动化测试 | 通过 | 48/48 |
| Python 编译检查 | 通过 | `radar`、`app.py`、`scripts` |
| 依赖一致性 | 通过 | `pip check` 无冲突 |
| Ollama | 通过 | 本机服务可用，版本 0.32.1 |
| Qwen Embedding | 通过 | `qwen3-embedding:0.6b`，1024 维 |
| 本地 Qwen 判断 | 通过 | `qwen3:4b`，Ollama structured output |
| 混合检索 | 通过 | 55% lexical + 45% semantic；失败时可降级 |
| DeepSeek | 通过 | `deepseek-v4-pro` 真实结构化调用成功 |
| arXiv | 通过 | 真实 API 返回论文，Atom 解析正常 |
| PDF/Claim 抽取 | 通过 | RARE PDF 解析 67,931 字符，12/12 引文精确命中 |
| G0 Claim Gate | 通过 | 0 条 confirmed 时 Weekly Scan 被正确禁用 |
| Weekly Radar | 通过 | Scan、路由、影响分析、trust、review 状态完整 |
| 单论文工作区 | 通过 | 只显示 RARE；Golden Case 不进入 UI |
| Action Center | 通过 | 最新真实扫描生成 1 个实验和 3 个写作行动 |
| 自动 Claim 风险 | 通过 | C1/C4 Disputed、C3 竞争压力、C9 需要重新验证 |
| 行动状态流转 | 通过 | 浏览器实测 `open → in_progress`，随后重置 Demo |
| 写作证据工作台 | 通过 | 支持 2、反证 3、边界/prior art 1、完整性 1，可下载 Brief |
| Claim Ledger | 通过 | confirmed challenge 正确将 Claim Health 变为 Contested |
| Patch | 通过 | 生成、五项校验、批准、下载入口均正常 |
| 原文件保护 | 通过 | Patch 为 export-only，原稿哈希保持不变 |
| UI | 通过 | 本周行动、搜索最新论文、我的论文全页实测 |
| Reset Demo | 通过 | 只重建 Golden Demo，不影响上传的 RARE Case |

## 真实全栈闭环结果

初始工程验证使用完全合成、非敏感的临时论文文本，并在隔离数据库中执行：

`Scan → Qwen 混合检索 → DeepSeek IncomingResult → DeepSeek ImpactAssessment → Trust → Confirm → Ledger → Patch → Validate → Approve → Export`

- 扫描论文：1
- 路由配对：1
- 影响候选：1
- Embedding 降级：false
- 最终 stance：`uncertain`
- comparability：`unknown`
- trust：`verified`
- Ledger health：`active`
- Patch 五项校验：全部 true
- 原始文件未改动：true
- DeepSeek 两次模型调用延迟约 12.4 秒与 30.3 秒
- 审计事件：5

`comparability=unknown` 时结果被强制收敛为 `uncertain`，证明安全规则确实生效，而不是只存在于提示词中。

## 本轮发现并修复的问题

1. 恢复 Ollama Embedding 环境配置，并把 `.env` 权限收紧为仅当前用户可读写。
2. 修复 arXiv Atom 解析调用，并将检索表达式改为显式字段化 AND 查询。
3. 在 Claim 路由前加入 Qwen source-level 排序，降低 arXiv 宽匹配噪音。
4. 增加硬性 stance 防线：`unknown` / `incompatible` 可比性不能输出 `supports` 或 `challenges`。
5. 增加相应回归测试，完整测试数达到 44。
6. 修复长 Claim 被错误当作整句检索词的问题，改为关键词与精确句子级证据提取，并兼容 arXiv 摘要丢失句间空格的情况。
7. 增加确定性 Decision Engine，把 verified impacts 转成六类项目动作，并支持状态流转和审计。
8. 将 Golden Demo 重建为完整决策场景，覆盖直接反证、竞争预警、撤稿、边界条件和支持证据。
9. 增加双层状态：candidate 立即影响 Current Radar Attention；正式 Claim Health 仍只由人工确认改变。

## 当前数据状态

| Case | Claims | Confirmed | Candidates |
| --- | ---: | ---: | ---: |
| RARE: Retrieval-Aware Robustness Evaluation | 12 | 5 | 7 |
| RadarNet: Robust Retrieval Under Domain Shift | 10 | 10 | 0 |

RARE 最新真实扫描搜索 15 篇 arXiv 公开论文，深度比较最高相关的 3 篇并成功解析 3 篇公开 PDF 全文；生成 3 条 verified candidate impacts、1 个实验动作、3 个写作动作、0 个失败。检索自动排除了 RARE 自己，所有影响均只关联核心 Claim C2。

## RARE 全文理解

在用户明确授权后，完整 RARE 原稿已由 DeepSeek 分析并保存为结构化全文画像：

- 输入 tokens：19,140
- 输出 tokens：2,681
- 延迟：43.4 秒
- 覆盖 confirmed Claims：C1、C2、C5、C10、C11
- 产物：研究问题、中心论点、贡献、方法、数据集、实验协议、关键发现、限制、监控主题，以及每条 Claim 的 contract、边界条件与证伪测试

全文画像已接入 Weekly Radar，并在 Case & Claims 页面提供可视化入口。

## 已知边界

- RARE 的 5 条核心 Claim 已确认；其完整原稿已按用户明确授权发送给 DeepSeek 生成全文画像。
- arXiv 线上证据目前主要是标题、作者、摘要和元数据，尚未自动下载并解析每篇命中的全文 PDF。
- `ModelRun` 已记录 token 和 latency，但尚未实现 DeepSeek 费用估算，因此 estimated cost 仍为 0。
- Weekly Radar 当前是页面按钮触发，尚未接入 cron、邮件或消息通知。

## 复查命令

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q radar app.py scripts
.venv/bin/python -m pip check
.venv/bin/python scripts/verify_live_stack.py
.venv/bin/streamlit run app.py
```
