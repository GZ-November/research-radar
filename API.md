# Research Radar — React 前端 API 接口规格

> 基于 `radar/services/` 现有公开方法整理。所有 endpoint 无需 auth（单用户本地应用），
> 请求/响应均为 JSON（文件上传除外）。本章案不包含 FastAPI 实现代码。

---

## 通用约定

- **Base URL**: `/api`
- **Content-Type**: `application/json`（文件上传用 `multipart/form-data`）
- **错误响应**: `{"detail": str}`, HTTP 4xx/5xx
- **case_id** / **manuscript_version_id** / **claim_id** 等主键均为 UUID 字符串
- 所有列表接口默认按 `created_at` 倒序排列

---

## 1. 项目管理

### `POST /api/cases`
创建研究案例（含文稿上传）。

- **请求**: `multipart/form-data`
  - `title`: str — 项目标题
  - `research_question`: str — 研究问题
  - `manuscript`: file — PDF / .tex / .md 文稿
- **响应 201**: `{case_id: str, manuscript_id: str, claims: [...]}`
  - `claims` 为自动提取的候选 Claim 列表（ClaimRevision 对象）
- **错误**:
  - 400 — 文稿文本提取不足（扫描件 PDF 无文本层）
  - 415 — 不支持的文件类型

### `GET /api/cases`
列出所有研究案例。

- **参数**: `?include_synthetic_demo=true|false` （默认 true）
- **响应 200**: `[{id, title, research_question, field, created_at, updated_at}, ...]`

### `GET /api/cases/{case_id}`
获取单个案例详情。

- **响应 200**: `{id, title, research_question, field, settings_json, created_at, updated_at}`
- **错误**: 404

### `POST /api/cases/{case_id}/manuscript`
同步新版本文稿（保留历史版本，自动 carry-over 已确认 Claim）。

- **请求**: `multipart/form-data`
  - `manuscript`: file
- **响应 200**:
  ```json
  {
    "manuscript_id": str,
    "version_no": int,
    "unchanged": bool,
    "carried_claims": int,
    "new_candidates": int,
    "previous_claims_not_found": int,
    "lost_claims": [{"claim_id": str, "stable_key": str, "statement": str}]
  }
  ```

### `DELETE /api/cases/{case_id}`
删除案例（含所有关联数据）。*未实现，需要新增 service 方法。*

---

## 2. 文稿版本

### `GET /api/cases/{case_id}/manuscripts`
列出案例所有文稿版本。

- **响应 200**: `[{id, version_no, file_name, source_type, is_current, created_at}, ...]`

### `GET /api/manuscripts/{manuscript_version_id}`
获取文稿版本全文及解析结构。

- **响应 200**: `{id, case_id, version_no, file_name, content_text, content_hash, sections, paragraphs, sentences}`

---

## 3. Claim 管理

### `GET /api/cases/{case_id}/claims`
列出案例所有 Claim（含最新 revision）。

- **参数**: `?review_state=candidate|confirmed|rejected|superseded`
- **响应 200**: `[{claim_id, stable_key, lifecycle_state, revision: {...}}, ...]`

### `POST /api/claims/{revision_id}/confirm`
确认候选 Claim（G0 通过）。

- **响应 200**: ClaimRevision 对象
- **错误**: 404 / 422（span 验证失败）

### `POST /api/claims/{revision_id}/reject`
拒绝候选 Claim。

- **响应 200**: ClaimRevision 对象

### `PUT /api/claims/{revision_id}`
编辑 Claim（创建新 revision，旧 revision → superseded）。

- **请求**:
  ```json
  {
    "statement": str,
    "centrality": "core" | "major" | "minor",
    "contract": {"task": str|null, "dataset": str|null, "split": str|null, "metric": str|null, "comparator": str|null, "scope": str|null},
    "falsifiable_condition": str
  }
  ```
- **响应 200**: 新 ClaimRevision 对象

### `POST /api/claims/{revision_id}/split`
拆分 Claim 为多个子 Claim。

- **请求**: `{"statements": [str, str, ...]}`
- **响应 200**: `[ClaimRevision, ...]`
- **错误**: 400 — 少于 2 个 statement

---

## 4. 扫描

### `POST /api/cases/{case_id}/scan`
启动一次文献雷达扫描。

- **请求**:
  ```json
  {
    "max_results": int,   // 默认 32
    "analysis_limit": int // 默认 3
  }
  ```
- **响应 202**: `{scan_id: str, status: "running"}`
- **错误**: 409 — 该案例已有活跃扫描
- **注意**: 返回的 `scan_id` 用于后续轮询

### `GET /api/scans/{scan_id}`
轮询扫描状态与进度。

- **响应 200**:
  ```json
  {
    "id": str,
    "case_id": str,
    "mode": str,
    "status": "running" | "completed" | "failed" | "cancelled" | "interrupted",
    "started_at": str,
    "finished_at": str | null,
    "stats": {
      "progress": {"value": 0.0-1.0, "message": str},
      "scanned_papers": int,
      "routed_pairs": int,
      "impact_candidates": int,
      "source_counts": {"arxiv": int, "openalex": int, "citation_graph": int},
      "hyde": bool,
      "source_failures": {"arxiv": str, ...},
      "newest_publication": str | null,
      "analysis_provider": str,
      "analysis_model": str
    },
    "error_message": str | null
  }
  ```

### `POST /api/scans/{scan_id}/cancel`
请求取消扫描（协作式，到达下一阶段边界时生效）。

- **响应 200**: `{"cancelled": true}`
- **响应 200**: `{"cancelled": false}` — 扫描已完成无法取消

### `GET /api/cases/{case_id}/scans`
列出案例所有扫描记录。

- **响应 200**: `[{id, mode, status, started_at, finished_at, ...}, ...]`

---

## 5. 影响判断 (Impact)

### `GET /api/scans/{scan_id}/impacts`
列出某次扫描的所有影响候选。

- **参数**: `?review_state=candidate|confirmed|edited|dismissed`
- **响应 200**: `[ImpactCandidate, ...]`
  - 每个 ImpactCandidate 包含：id, claim_revision_id, source_snapshot_id, stance, impact_mode, severity, comparability, suggested_action, strategic_flags, condition_differences, evidence_own, evidence_new, change_depth, review_state, trust_state

### `POST /api/impacts/{impact_id}/confirm`
确认影响（G1 通过，自动生成对应 Action）。

- **请求**: `{"reason": str|null}`
- **响应 200**: ImpactCandidate（含更新后的 review_state）

### `POST /api/impacts/{impact_id}/edit`
编辑影响字段后确认。

- **请求**:
  ```json
  {
    "payload": {
      "stance": str,
      "impact_mode": str,
      "comparability": str,
      "change_depth": int,
      "severity": str,
      "suggested_action": str
    },
    "reason": str|null
  }
  ```
- **响应 200**: ImpactCandidate

### `POST /api/impacts/{impact_id}/dismiss`
忽略影响。

- **请求**: `{"reason": str|null}`
- **响应 200**: ImpactCandidate

### `GET /api/impacts/{impact_id}/decisions`
查看影响的所有审核决策历史。

- **响应 200**: `[ReviewDecision, ...]`

### `GET /api/cases/{case_id}/impacts`
列出案例所有影响（跨扫描）。

- **响应 200**: `[ImpactCandidate, ...]`

---

## 6. 行动 (Action)

### `GET /api/cases/{case_id}/actions`
列出案例所有行动项。

- **参数**:
  - `?scan_run_id=str` — 按扫描筛选
  - `?include_closed=true|false` — 默认 false（仅活跃）
- **响应 200**: `[ActionItem, ...]`

### `PUT /api/actions/{action_id}/status`
更新行动状态。

- **请求**: `{"status": "proposed" | "open" | "in_progress" | "done" | "dismissed"}`
- **响应 200**: ActionItem
- **错误**: 400 — 无效状态 / 404

### `GET /api/claims/{claim_id}/attention`
获取 Claim 的关注状态（摘要信号）。

- **响应 200**: `{"state": "stable" | "new_support" | "needs_review" | "disputed" | "competitor_pressure" | "revalidation_required"}`

---

## 7. 补丁 (Patch)

### `POST /api/impacts/{impact_id}/patch`
为已确认的影响生成文稿修改建议。

- **响应 201**: PatchProposal 对象
  - 包含：edit_class, target_locator, before_text, after_text, citations, validations, approval_state
- **错误**: 400 — 影响未确认 / 无变更影响 / 404

### `POST /api/patches/{patch_id}/approve`
批准补丁。

- **响应 200**: PatchProposal（approval_state → "approved"）
- **错误**: 422 — 验证未通过

### `POST /api/patches/{patch_id}/reject`
拒绝补丁。

- **响应 200**: PatchProposal（approval_state → "rejected"）

### `GET /api/patches/{patch_id}/validate`
重新验证补丁。

- **响应 200**: `{"before_text_exact": bool, "citations_resolved": bool, "citation_marker_safe": bool, "locked_numbers_unchanged": bool, "original_file_untouched": bool}`

### `POST /api/patches/{patch_id}/export`
导出补丁为 Markdown。

- **响应 200**: `{"markdown": str}`

---

## 8. 审计导出

### `GET /api/cases/{case_id}/audit`
导出案例审计事件。

- **参数**: `?limit=500` — 默认 500，传 `0` 为全量
- **响应 200**: JSON 字符串（application/json）
  ```json
  [
    {
      "id": str,
      "event_type": str,
      "object_type": str,
      "object_id": str,
      "payload": {...},
      "actor_type": str,
      "actor_id": str,
      "created_at": str
    }
  ]
  ```

---

## 9. 报告

### `GET /api/scans/{scan_id}/summary`
获取扫描周报摘要。

- **响应 200**:
  ```json
  {
    "scanned_papers": int,
    "routed_papers": int,
    "related_papers": int,
    "critical": int,
    "review": int,
    "informative": int,
    "supports": int,
    "challenges": int,
    "competitor_alerts": int,
    "integrity_alerts": int
  }
  ```

### `GET /api/scans/{scan_id}/action-report`
获取扫描行动报告（自动同步 actions）。

- **响应 200**:
  ```json
  {
    "scan_run_id": str,
    "headline": str,
    "urgent": int,
    "open_actions": int,
    "counts_by_type": {"team_decision": int, "experiment": int, ...},
    "summary": {...},
    "actions": [{"id": str, "type": str, "priority": str, "title": str, "rationale": str, "checklist": [str], "due": str, "status": str}, ...]
  }
  ```

### `GET /api/cases/{case_id}/writing-brief`
获取文稿写作简报（证据分组 + 写作行动）。

- **响应 200**:
  ```json
  {
    "supports": [...],
    "challenges": [...],
    "boundary_and_prior_art": [...],
    "integrity": [...],
    "writing_actions": [...]
  }
  ```

### `POST /api/cases/{case_id}/writing-brief/export`
导出写作简报为 Markdown。

- **响应 200**: `{"markdown": str}`

### `GET /api/claims/{claim_id}/evidence-pack`
获取单个 Claim 的证据包。

- **响应 200**:
  ```json
  {
    "schema": "ResearchRadarEvidencePack.v1",
    "claim": {"id": str, "stable_key": str, "statement": str, "centrality": str, "contract": {...}, "health": str},
    "supports": [...],
    "challenges": [...],
    "integrity": [...],
    "safety_note": str
  }
  ```

---

## 10. 设置

### `GET /api/settings`
读取当前设置（敏感字段已脱敏）。

- **响应 200**:
  ```json
  {
    "llm_provider": str|null,
    "llm_model": str|null,
    "llm_base_url": str|null,
    "local_llm_model": str|null,
    "embedding_provider": str|null,
    "embedding_model": str|null,
    "llm_api_key": "masked_sk-••••abcd",
    "llm_configured": bool,
    "llm_mode": "local" | "remote" | null
  }
  ```

### `PUT /api/settings`
更新设置（写入 `data/settings.local.env`）。

- **请求**: `{"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-chat", ...}`
- **响应 200**: `{"saved": true, "path": "data/settings.local.env"}`
- **注意**: key 全部大写，与 `.env` 格式一致；空值表示取消设置

---

## 11. 文稿理解 (Manuscript Understanding)

### `POST /api/cases/{case_id}/analyze`
运行一次完整的文稿结构化理解（需已确认 Claim）。

- **响应 200**: `{model_run_id: str, profile: ManuscriptUnderstandingOutput}`
  - profile 包含：title, research_problem, central_thesis, contributions, methods, datasets, evaluation_protocol, key_findings, limitations, terminology, watch_topics, claim_profiles
- **错误**: 400 — 缺少已确认 Claim / 404

### `GET /api/cases/{case_id}/profile`
获取最近的文稿理解 profile（如有）。

- **响应 200**: ManuscriptUnderstandingOutput | `null`

---

## 12. 竞品监控 (Watch Entity)

### `POST /api/cases/{case_id}/watch`
添加竞品/团队监控别名。

- **请求**:
  ```json
  {
    "entity_type": str,
    "canonical_name": str,
    "aliases": [str]
  }
  ```
- **响应 201**: `{watch_id: str}`

### `DELETE /api/watch/{watch_id}`
移除监控。

- **响应 204**

---

## 附录 A: Service 层接入审查结果

| Service | Streamlit 依赖 | 返回值类型 | 参数来源 | FastAPI 兼容 |
|---------|---------------|-----------|---------|-------------|
| CaseService | ❌ 无 | ORM 对象 | 纯参数 | ⚠️ 需包装为 dict/Pydantic |
| ClaimService | ❌ 无 | ORM 对象 | 纯参数 | ⚠️ 需包装为 dict/Pydantic |
| ActionService | ❌ 无 | ORM 对象 | 纯参数 | ⚠️ 需包装为 dict/Pydantic |
| ImpactService | ❌ 无 | Pydantic/list | 纯参数 | ✅ 直接可用 |
| PatchService | ❌ 无 | ORM 对象 | 纯参数 | ⚠️ 需包装为 dict/Pydantic |
| ReviewService | ❌ 无 | ORM 对象 | 纯参数 | ⚠️ 需包装为 dict/Pydantic |
| ConditionService | ❌ 无 | Pydantic | 纯参数 | ✅ 直接可用 |
| EvidenceService | ❌ 无 | Pydantic | 纯参数 | ✅ 直接可用 |
| TrustService | ❌ 无 | Pydantic | 纯参数 | ✅ 直接可用 |
| LedgerService | ❌ 无 | dict | 纯参数 | ✅ 直接可用 |
| RetrievalService | ❌ 无 | list/dict | 纯参数 | ✅ 直接可用 |
| ReportService | ❌ 无 | dict/str | 纯参数 | ✅ 直接可用 |
| ManuscriptUnderstandingService | ❌ 无 | Pydantic | 纯参数 | ✅ 直接可用 |
| WeeklyRadarService | ❌ 无 | str/dict（扫描编排） | 纯参数 | ✅ 直接可用 |
| scan_runner 模块函数 | ❌ 无 | str/ScanRun | 纯参数 | ⚠️ 全局 threading 状态见附录 B |

**结论**: 没有 service 直接依赖 Streamlit。返回 ORM 对象的 service 需要增加一层 `to_dict()` 或 Pydantic response schema 包装；其余可直接用作 FastAPI 路由的返回值。

---

## 附录 B: 数据库并发注意事项（FastAPI 适配）

当前 `radar/db.py` 使用模块级全局变量：

```python
engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

**对 FastAPI 的影响**:

1. **SQLite + check_same_thread=False**: FastAPI 默认使用线程池处理请求，`check_same_thread=False` 允许多线程共享同一连接。但 SQLite 仍受限于单写锁——并发写请求会排队。对于 Research Radar 的单用户本地场景，这通常不是问题。

2. **sessionmaker 线程安全**: `SessionLocal` 是线程安全的（SQLAlchemy `sessionmaker` 内部管理连接池），每个请求调用 `SessionLocal()` 获取独立 Session 即可。

3. **推荐 FastAPI 集成模式**:
   ```python
   # 使用 FastAPI dependency injection 而非模块级 session_scope
   def get_db():
       db = SessionLocal()
       try:
           yield db
       finally:
           db.close()
   
   @app.get("/api/cases")
   def list_cases(db: Session = Depends(get_db)):
       ...
   ```
   或者保持现有 `session_scope` 模式，在路由中每次调用 `with session_scope(self.session_factory) as session:` 即可。

4. **scan_runner 全局状态**: `_active_by_case`、`_threads`、`_lock` 是进程级变量，在单进程 FastAPI（`uvicorn` 默认 1 worker）下可正常工作。如需多 worker，需将扫描状态迁移到数据库或 Redis。

5. **config.get_settings() 的 lru_cache**: 进程级缓存，每个 worker 独立缓存一份 Settings，安全。

6. **无需引入 scoped_session**: 当前 `session_scope` 上下文管理器模式已经实现了"每个业务操作一个 session"，在 FastAPI 下每种请求创建一个 session 即可。`scoped_session` 仅在需要跨函数隐式传递 session 时才需要（如 Flask 的 `g`），FastAPI 的 `Depends` 注入模式更清晰。
