import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { ChevronDown, ClipboardList, Download, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/radar/Button'
import { Callout } from '@/components/radar/Callout'
import { StatusBadge } from '@/components/radar/StatusBadge'
import { EmptyState } from '@/components/radar/EmptyState'
import { QuoteBlock } from '@/components/radar/EvidenceBlock'
import { Mono, PageHeader, SectionTitle, SubNote } from '@/components/radar/Typography'
import { cn } from '@/lib/utils'
import { claimAttention, claimHealth, confirmedRevision, downloadText, fmtDateTime } from '@/lib/format'
import {
  APPROVAL_STATE,
  ATTENTION,
  COMPARABILITY,
  EDIT_CLASS,
  HEALTH,
  IMPACT_MODE,
  REVIEW_STATE,
  SUGGESTED_ACTION,
  VALIDATION_LABELS,
} from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import type { Impact, Patch } from '@/types'

const TARGET_HINT: Record<string, string> = {
  cite: 'Discussion / Related Work',
  add_boundary_discussion: '适用边界与 Limitations 段',
  run_comparison: '实验章节（新增对照）',
  narrow_claim: 'Claim 表述句',
  team_review: '团队评审记录',
  revalidate: '引用列表与实验设置',
  watch: '持续观察清单',
  no_action: '—',
}

// ————— Patch 卡片 —————
function PatchCard({ patch }: { patch: Patch }) {
  const { patchApproval, setPatchApproval, confirm } = useAppStore()
  const approval = patchApproval(patch.id, patch.approval_state)
  const failed = Object.entries(patch.validations).filter(([, v]) => !v).map(([k]) => k)

  const approve = () => {
    if (failed.length > 0) {
      toast.error(
        `这版改写未通过校验，不能批准。未通过项：${failed.map((k) => VALIDATION_LABELS[k]).join('；')}。请查看上方校验清单，修正后重新生成。`,
      )
      return
    }
    setPatchApproval(patch.id, 'approved')
    toast.success('改写已批准，可导出。')
  }

  const reject = async () => {
    const ok = await confirm({
      actionName: '拒绝这版改写',
      description: '拒绝后该改写方案会标记为已拒绝；之后可以重新生成新的改写方案。',
      confirmLabel: '确认拒绝',
      danger: true,
    })
    if (!ok) return
    setPatchApproval(patch.id, 'rejected')
    toast.success('这版改写已标记为已拒绝')
  }

  const download = () => {
    const md = [
      `# 已批准改写 ${patch.id}`,
      ``,
      `- 改进方式：${EDIT_CLASS[patch.edit_class]}`,
      `- 目标位置：\`${patch.target_locator}\``,
      ``,
      `## 改写前`,
      '```',
      patch.before_text,
      '```',
      ``,
      `## 改写后`,
      '```',
      patch.after_text,
      '```',
      ``,
    ].join('\n')
    downloadText(`patch-${patch.id}.md`, md)
    toast.success('已下载已批准改写')
  }

  return (
    <div className="rounded-[12px] border border-sep bg-white p-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge tone="teal" label={EDIT_CLASS[patch.edit_class]} />
        <StatusBadge k={approval} label={APPROVAL_STATE[approval]} />
        <Mono className="t-c1 text-lt">{patch.target_locator}</Mono>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="t-b2e text-lp">改写前</p>
          <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap rounded-[8px] border border-sep bg-black/[0.03] p-3 font-mono-radar t-c1 leading-[18px] text-ls">
            {patch.before_text}
          </pre>
        </div>
        <div>
          <p className="t-b2e text-lp">改写后</p>
          <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap rounded-[8px] border border-sep bg-white p-3 font-mono-radar t-c1 leading-[18px] text-lp">
            {patch.after_text}
          </pre>
        </div>
      </div>

      <p className="mt-3 t-b2e text-lp">自动验证结果</p>
      <ul className="mt-1.5 grid gap-1 sm:grid-cols-2">
        {Object.entries(patch.validations).map(([k, v]) => (
          <li key={k} className="flex items-start gap-1.5 t-c1 text-ls">
            <span aria-hidden>{v ? '✅' : '❌'}</span>
            {VALIDATION_LABELS[k] ?? k}
          </li>
        ))}
      </ul>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size={26} disabled={approval === 'approved'} onClick={approve}>
          批准并允许导出
        </Button>
        <Button variant="outline" size={26} disabled={approval === 'rejected'} onClick={reject}>
          拒绝这版改写
        </Button>
        {approval === 'approved' && (
          <Button variant="secondary" size={26} leftIcon={<Download />} onClick={download}>
            下载已批准改写
          </Button>
        )}
      </div>
    </div>
  )
}

// ————— 已采用影响 → 改写生成项 —————
function AdoptedImpactItem({ impact, patches }: { impact: Impact; patches: Patch[] }) {
  const [open, setOpen] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [showPatches, setShowPatches] = useState(false)
  const related = patches.filter((p) => p.impact_candidate_id === impact.id)

  const generate = () => {
    setGenerating(true)
    setTimeout(() => {
      setGenerating(false)
      if (related.length > 0) {
        setShowPatches(true)
        toast.success('已生成最小改写方案，请审阅。')
      } else {
        toast.error('AI 改写失败：演示环境未连接分析模型')
      }
    }, 1400)
  }

  return (
    <div className="rounded-[12px] border border-sep bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-black/[0.02]"
      >
        <ChevronDown className={cn('size-4 shrink-0 text-lt transition-transform duration-150', open && 'rotate-180')} />
        <span className="clamp-2 min-w-0 flex-1 t-b2e text-lp">
          {impact.source.title} · {IMPACT_MODE[impact.impact_mode]} · {SUGGESTED_ACTION[impact.suggested_action]}
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-sep px-4 py-3">
          {impact.source.url && (
            <a href={impact.source.url} target="_blank" rel="noreferrer" className="t-b2 text-radar hover:underline">
              查看触发论文原文
            </a>
          )}
          <QuoteBlock quote={impact.evidence_new?.quote} locator={impact.evidence_new?.locator} />
          <SubNote>
            建议落点：{TARGET_HINT[impact.suggested_action] ?? '—'} · 改进方式：
            {IMPACT_MODE[impact.impact_mode]} · 条件可比性：{COMPARABILITY[impact.comparability]}
          </SubNote>
          <div>
            <Button size={32} loading={generating} onClick={generate}>
              用 AI 生成最小改写方案
            </Button>
          </div>
          {(showPatches || related.length > 0) && (
            <div className="space-y-3">
              {related.map((p) => (
                <PatchCard key={p.id} patch={p} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ————— 页面 —————
export default function Ledger() {
  const { currentCase: c, impactState, resetDemo, confirm } = useAppStore()
  const navigate = useNavigate()
  const claims = useMemo(
    () =>
      [...c.claims]
        .filter((cl) => confirmedRevision(cl))
        .sort((a, b) => a.stable_key.localeCompare(b.stable_key)),
    [c.claims],
  )
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const claim = claims.find((cl) => cl.stable_key === selectedKey) ?? claims[0] ?? null
  const rev = claim ? confirmedRevision(claim) : null

  const adopted = claim
    ? c.impacts.filter(
        (i) =>
          i.claim_stable_key === claim.stable_key &&
          ['confirmed', 'edited'].includes(impactState(i)),
      )
    : []
  const supports = adopted.filter((i) => i.stance === 'supports')
  const challenges = adopted.filter((i) => i.stance === 'challenges')
  const integrity = adopted.filter(
    (i) => i.impact_mode === 'research_integrity' || i.event_type === 'retraction',
  )

  const health = claim ? claimHealth(claim.stable_key, c.impacts, impactState) : 'active'
  const attention = claim ? claimAttention(claim.stable_key, c.impacts, impactState) : 'stable'

  const exportEvidencePack = () => {
    if (!claim) return
    const pack = {
      claim_stable_key: claim.stable_key,
      statement: rev?.statement ?? null,
      health,
      attention,
      confirmed_impacts: adopted.map((i) => ({
        id: i.id,
        stance: i.stance,
        impact_mode: i.impact_mode,
        comparability: i.comparability,
        review_state: impactState(i),
        source: i.source,
        evidence_new: i.evidence_new,
        evidence_own: i.evidence_own,
      })),
    }
    downloadText(`evidence-pack-${claim.stable_key}.json`, JSON.stringify(pack, null, 2), 'application/json')
    toast.success('已导出证据包（JSON）')
  }

  const exportAudit = () => {
    downloadText(
      'research-radar-audit.json',
      JSON.stringify({ case_id: c.id, audit_events: c.audit_events }, null, 2),
      'application/json',
    )
    toast.success('已导出审计记录（JSON）')
  }

  const doResetDemo = async () => {
    const ok = await confirm({
      actionName: '重置 Demo 决策',
      description: '将删除并重建 Golden Demo 项目的全部扫描、影响和决策记录；你自己上传的项目不受影响。',
      confirmLabel: '确认重置',
      danger: true,
    })
    if (!ok) return
    resetDemo()
    toast.success('Demo 决策已重置')
  }

  const ledgerBucket = (list: Impact[]) =>
    list.length === 0 ? (
      <SubNote>暂无人工确认记录。</SubNote>
    ) : (
      <div className="space-y-3">
        {list.map((i) => (
          <div key={i.id} className="rounded-[10px] border border-sep bg-white p-3">
            <p className="t-b2 text-lp">
              <strong className="t-b2e">{i.source.title}</strong> · {IMPACT_MODE[i.impact_mode]} ·{' '}
              {REVIEW_STATE[impactState(i)]}
            </p>
            <div className="mt-2">
              <QuoteBlock quote={i.evidence_new?.quote} locator={i.evidence_new?.locator} />
            </div>
          </div>
        ))}
      </div>
    )

  return (
    <div className="space-y-6">
      <PageHeader
        title="改进工作台"
        subtitle="核对已采用影响，生成可审阅的最小改写；原论文文件永远不会被自动覆盖。"
      />

      <Callout kind="info">
        工作流：① 在文献雷达核对条件矩阵和证据 → ② 采用或修正影响 → ③ AI 生成最小改写 → ④
        验证数字、引用和原文定位 → ⑤ 人工批准并下载。
      </Callout>

      {/* 三个真实论文例子 */}
      <Collapsible>
        <CollapsibleTrigger className="group flex items-center gap-1 t-b2e text-lp hover:text-radar">
          <ChevronDown className="size-4 transition-transform duration-150 group-data-[state=open]:rotate-180" />
          三个真实论文例子：影响应该怎样变成改进
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-[12px] border border-sep bg-white p-4">
              <p className="t-b2e text-lp">
                <a href="https://arxiv.org/abs/2206.07682" target="_blank" rel="noreferrer" className="text-radar hover:underline">
                  Emergent Abilities
                </a>
                {' '}vs{' '}
                <a href="https://arxiv.org/abs/2304.15004" target="_blank" rel="noreferrer" className="text-radar hover:underline">
                  Mirage
                </a>
              </p>
              <p className="mt-1.5 t-c1 text-lt">
                挑战类影响：补连续指标评估、收窄“涌现”表述、在 Limitations 增加指标选择讨论。
              </p>
            </div>
            <div className="rounded-[12px] border border-sep bg-white p-4">
              <p className="t-b2e text-lp">TAP-RAG vs E-Agent</p>
              <p className="mt-1.5 t-c1 text-lt">
                条件不可比：跨设置补一个最小 head-to-head comparison，同时继续观察后续可比结果。
              </p>
            </div>
            <div className="rounded-[12px] border border-sep bg-white p-4">
              <p className="t-b2e text-lp">Agentic RAG SoK</p>
              <p className="mt-1.5 t-c1 text-lt">
                <Mono>prior_art + cite</Mono>：在 Related Work 增加一段定位改写，明确区分自身贡献边界。
              </p>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {claims.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="这个项目还没有 Claim"
          hint="先到“我的论文”确认至少一条核心 Claim，再回来生成改写方案。"
          action={{ label: '去确认 Claim', onClick: () => navigate('/case') }}
        />
      ) : (
        <>
          <div className="max-w-[320px]">
            <label htmlFor="claim-select" className="mb-1 block t-b2e text-lp">选择要改进的 Claim</label>
            <Select value={claim?.stable_key} onValueChange={setSelectedKey}>
              <SelectTrigger id="claim-select" className="h-9 rounded-[10px] border-sep font-mono-radar t-b2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {claims.map((cl) => (
                  <SelectItem key={cl.id} value={cl.stable_key} className="font-mono-radar">
                    {cl.stable_key}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {claim && (
            <>
              {/* Claim 账本区 */}
              <div className="rounded-[12px] border border-sep bg-white p-5">
                <SectionTitle>
                  <Mono>{claim.stable_key}</Mono> · {rev?.statement}
                </SectionTitle>
                <p className="mt-2 flex flex-wrap items-center gap-2 t-b2 text-ls">
                  Claim 状态 <StatusBadge k={health} label={HEALTH[health]} />
                  <span aria-hidden className="text-lq">・</span>
                  当前 Radar 关注 <StatusBadge k={attention} label={ATTENTION[attention]} />
                </p>
                {health === 'active' && (
                  <SubNote className="mt-1.5">
                    当前没有已人工确认的支持/挑战/完整性影响；待确认的判断不会改变本状态。
                  </SubNote>
                )}

                <Tabs defaultValue="supports" className="mt-4">
                  <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
                    <TabsTrigger value="supports" className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
                      支持证据 · {supports.length}
                    </TabsTrigger>
                    <TabsTrigger value="challenges" className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
                      挑战证据 · {challenges.length}
                    </TabsTrigger>
                    <TabsTrigger value="integrity" className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
                      完整性 · {integrity.length}
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="supports" className="mt-4">{ledgerBucket(supports)}</TabsContent>
                  <TabsContent value="challenges" className="mt-4">{ledgerBucket(challenges)}</TabsContent>
                  <TabsContent value="integrity" className="mt-4">{ledgerBucket(integrity)}</TabsContent>
                </Tabs>

                <div className="mt-4">
                  <Button variant="outline" size={26} leftIcon={<Download />} onClick={exportEvidencePack}>
                    导出证据包（JSON）
                  </Button>
                </div>
              </div>

              {/* 最小改写方案区 */}
              <div>
                <SectionTitle>最小改写方案</SectionTitle>
                {adopted.length === 0 ? (
                  <Callout kind="info" className="mt-2">
                    先到“文献雷达”核对并采用一条材料性影响，才能生成改写方案。
                  </Callout>
                ) : (
                  <div className="mt-3 space-y-3">
                    {adopted.map((i) => (
                      <AdoptedImpactItem key={i.id} impact={i} patches={c.patches} />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* 审计区 */}
      <Collapsible>
        <CollapsibleTrigger className="group flex items-center gap-1 t-b2e text-lp hover:text-radar">
          <ChevronDown className="size-4 transition-transform duration-150 group-data-[state=open]:rotate-180" />
          证据、模型运行与审计记录
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3 space-y-4">
          <div className="rounded-[12px] border border-sep bg-white p-4">
            <SubNote>
              共 <Mono>{c.audit_events.length}</Mono> 条审计事件（仅最近 500 条）· 仅保存在本机
            </SubNote>
            <div className="mt-3 max-h-72 overflow-auto rounded-[10px] border border-sep">
              <Table>
                <TableHeader>
                  <TableRow className="border-sep bg-black/[0.02] hover:bg-black/[0.02]">
                    <TableHead className="t-c1e text-ls">时间</TableHead>
                    <TableHead className="t-c1e text-ls">事件</TableHead>
                    <TableHead className="t-c1e text-ls">对象</TableHead>
                    <TableHead className="t-c1e text-ls">来源</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {c.audit_events.map((e, i) => (
                    <TableRow key={i} className="border-sep">
                      <TableCell className="whitespace-nowrap font-mono-radar t-c1 text-lt">
                        {fmtDateTime(e.created_at) ?? '—'}
                      </TableCell>
                      <TableCell className="font-mono-radar t-c1 text-lp">{e.event_type}</TableCell>
                      <TableCell className="t-c1 text-lt">
                        {e.object_type}
                        <span className="font-mono-radar"> · {e.object_id.slice(0, 8)}…</span>
                      </TableCell>
                      <TableCell className="t-c1 text-lt">{e.actor_type}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {c.model_runs.length > 0 && (
            <div className="rounded-[12px] border border-sep bg-white p-4">
              <p className="t-b2e text-lp">模型运行与确定性阶段（最近 20 条）</p>
              <div className="mt-3 max-h-72 overflow-auto rounded-[10px] border border-sep">
                <Table>
                  <TableHeader>
                    <TableRow className="border-sep bg-black/[0.02] hover:bg-black/[0.02]">
                      <TableHead className="t-c1e text-ls">阶段</TableHead>
                      <TableHead className="t-c1e text-ls">提供方</TableHead>
                      <TableHead className="t-c1e text-ls">模型</TableHead>
                      <TableHead className="t-c1e text-ls">耗时(ms)</TableHead>
                      <TableHead className="t-c1e text-ls">估算成本</TableHead>
                      <TableHead className="t-c1e text-ls">验证结果</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {c.model_runs.map((r, i) => (
                      <TableRow key={i} className="border-sep">
                        <TableCell className="font-mono-radar t-c1 text-lp">{r.stage}</TableCell>
                        <TableCell className="font-mono-radar t-c1 text-lt">{r.provider}</TableCell>
                        <TableCell className="font-mono-radar t-c1 text-lt">{r.model}</TableCell>
                        <TableCell className="font-mono-radar t-c1 tabular-nums text-lt">{r.latency_ms}</TableCell>
                        <TableCell className="font-mono-radar t-c1 tabular-nums text-lt">
                          {r.estimated_cost.toFixed(4)}
                        </TableCell>
                        <TableCell className="t-c1 text-lt">
                          {r.validation
                            ? Object.entries(r.validation)
                                .map(([k, v]) => `${k}:${v ? '✓' : '✗'}`)
                                .join(' ')
                            : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          <div>
            <Button variant="outline" size={26} leftIcon={<Download />} onClick={exportAudit}>
              导出审计记录（JSON）
            </Button>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {c.is_demo && (
        <>
          <Separator className="bg-sep" />
          <div>
            <Button variant="outline" danger leftIcon={<RotateCcw />} onClick={doResetDemo}>
              重置 Demo 决策
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
