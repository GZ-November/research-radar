import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { Satellite, ShieldAlert, Swords } from 'lucide-react'
import { toast } from 'sonner'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
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
import { Dot, StatusBadge } from '@/components/radar/StatusBadge'
import { EmptyState } from '@/components/radar/EmptyState'
import { EvidenceBlock } from '@/components/radar/EvidenceBlock'
import { ImpactDecisionBlock } from '@/components/radar/ImpactDecisionBlock'
import { ImpactStatusCallout } from '@/components/radar/ImpactStatusCallout'
import { MetricCard } from '@/components/radar/MetricCard'
import { SourceTraceability } from '@/components/radar/SourceTraceability'
import { Mono, PageHeader, SectionTitle, SubNote } from '@/components/radar/Typography'
import { cn } from '@/lib/utils'
import { fmtDateTime, latestCompletedScan, latestScan, sortImpacts, currentRevision } from '@/lib/format'
import {
  COMPARABILITY,
  CONDITION_STATUS,
  CONTRACT_LABELS,
  SEVERITY,
  SUGGESTED_ACTION,
  IMPACT_MODE,
  TRUST_STATE,
  toneFor,
} from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import type { Impact } from '@/types'

const STAGES = [
  '搜索 arXiv 最新论文…',
  '混合检索相关论文…',
  '提取公开 PDF 全文…',
  '逐项比较已确认 Claim…',
  '生成项目行动…',
]

// ————— 右侧详情 —————
function ImpactDetail({ impact }: { impact: Impact }) {
  const [matrixOpen, setMatrixOpen] = useState(false)
  const competitor = impact.strategic_flags.includes('competitor')
  const retraction = impact.event_type === 'retraction'

  return (
    <div className="space-y-4">
      <div>
        <h3 className="flex items-start gap-2 t-t2e text-lp">
          <Dot tone={toneFor(impact.severity)} className="mt-2" />
          <span>
            <Mono>{impact.claim_stable_key}</Mono> — {impact.claim_statement}
          </span>
        </h3>
        <SubNote className="mt-1.5">证据状态：{TRUST_STATE[impact.trust_state]}</SubNote>
      </div>

      <ImpactStatusCallout impact={impact} />

      {competitor && (
        <Callout kind="warning">竞争团队提醒：这是战略标记，不代表 support 或 challenge。</Callout>
      )}
      {retraction && (
        <Callout kind="error">
          该引用来源出现撤稿记录。确认后 Claim Health 才会变为“需要重新验证”。
        </Callout>
      )}

      <Tabs defaultValue="matrix">
        <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
          {[
            ['matrix', '比较矩阵'],
            ['evidence', '证据'],
            ['decision', '决策'],
          ].map(([v, l]) => (
            <TabsTrigger key={v} value={v} className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
              {l}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="matrix" className="mt-4 space-y-3">
          <p className="t-b2 text-lp">
            总体可比性：<strong className="t-b2e">{COMPARABILITY[impact.comparability]}</strong>
          </p>
          {impact.comparability !== 'compatible' && (
            <Callout kind="warning">
              当前条件不是“可比”：程序禁止输出支持/挑战结论，只能作为信息不足、边界、在先工作或后续实验线索。
            </Callout>
          )}
          <div className="overflow-hidden rounded-[10px] border border-sep">
            <Table>
              <TableHeader>
                <TableRow className="border-sep bg-black/[0.02] hover:bg-black/[0.02]">
                  <TableHead className="t-c1e text-ls">字段</TableHead>
                  <TableHead className="t-c1e text-ls">本方</TableHead>
                  <TableHead className="t-c1e text-ls">公开论文</TableHead>
                  <TableHead className="t-c1e text-ls">状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {impact.condition_differences.map((cd) => (
                  <TableRow key={cd.field} className="border-sep">
                    <TableCell className="t-b2e text-lp">
                      {CONTRACT_LABELS[cd.field] ?? cd.field}
                    </TableCell>
                    <TableCell className="max-w-[220px] t-b2 text-ls">
                      <span className="clamp-2">{cd.own_value ?? '—'}</span>
                    </TableCell>
                    <TableCell className="max-w-[220px] t-b2 text-ls">
                      <span className="clamp-2">{cd.incoming_value ?? '—'}</span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge k={cd.status} label={CONDITION_STATUS[cd.status]} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Collapsible open={matrixOpen} onOpenChange={setMatrixOpen}>
            <CollapsibleTrigger className="flex items-center gap-1 t-b2e text-radar hover:underline">
              <ChevronDown className={cn('size-4 transition-transform duration-150', matrixOpen && 'rotate-180')} />
              逐项比较说明
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2 space-y-1.5">
              {impact.condition_differences.map((cd) => (
                <p key={cd.field} className="t-c1 text-lt">
                  {CONTRACT_LABELS[cd.field] ?? cd.field} · {CONDITION_STATUS[cd.status]} —{' '}
                  {cd.explanation ?? '—'}
                </p>
              ))}
            </CollapsibleContent>
          </Collapsible>
        </TabsContent>

        <TabsContent value="evidence" className="mt-4 space-y-4">
          <div>
            <p className="t-b2e text-lp">可追溯来源</p>
            <div className="mt-1.5">
              <SourceTraceability source={impact.source} />
            </div>
          </div>
          <Separator className="bg-sep" />
          <EvidenceBlock label="你的文稿" evidence={impact.evidence_own} />
          <EvidenceBlock label="公开论文" evidence={impact.evidence_new} />
          <SubNote>两段引文均经过原文精确区间校验。</SubNote>
        </TabsContent>

        <TabsContent value="decision" className="mt-4 space-y-4">
          <div>
            <p className="t-b2e text-lp">为什么重要</p>
            <p className="mt-1.5 t-b2 text-ls">
              {impact.source_snapshot_abstract ??
                `该公开论文与 Claim ${impact.claim_stable_key} 的条件矩阵已完成逐项比较，请结合左侧证据判断是否采纳。`}
            </p>
          </div>
          <SubNote>
            当前判断：{IMPACT_MODE[impact.impact_mode]} · 建议动作：
            {SUGGESTED_ACTION[impact.suggested_action]}（可在下方“修改判断”中调整）
          </SubNote>
          {impact.uncertainty.length > 0 && (
            <div>
              <p className="t-b2e text-lp">不确定因素</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                {impact.uncertainty.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </div>
          )}
          {impact.impact_mode === 'no_material_change' && (
            <Callout kind="info">
              当前判断为“无需改变”。你仍可以根据条件矩阵和原文证据，把它改为
              在先工作、边界条件或方法替代，再采用相应动作。
            </Callout>
          )}
          <ImpactDecisionBlock impact={impact} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ————— 页面 —————
export default function ImpactWorkspace() {
  const { currentCase: c, focusImpactId, setFocusImpactId } = useAppStore()
  const navigate = useNavigate()

  const confirmedClaims = c.claims.filter((cl) => {
    const r = currentRevision(cl)
    return r && (r.review_state === 'confirmed' || r.review_state === 'edited')
  })
  const queries = c.settings.generated_search_queries?.queries ?? []
  const scan = latestScan(c)
  const completedScan = latestCompletedScan(c)

  const impacts = useMemo(() => {
    const list = completedScan
      ? c.impacts.filter((i) => i.scan_run_id === completedScan.id)
      : c.impacts
    return sortImpacts(list.length > 0 ? list : c.impacts)
  }, [c.impacts, completedScan])

  const [selectedId, setSelectedId] = useState<string | null>(focusImpactId ?? impacts[0]?.id ?? null)
  useEffect(() => {
    if (focusImpactId && impacts.some((i) => i.id === focusImpactId)) {
      setSelectedId(focusImpactId)
      setFocusImpactId(null)
    }
  }, [focusImpactId, impacts, setFocusImpactId])

  const selected = impacts.find((i) => i.id === selectedId) ?? impacts[0] ?? null
  const detailRef = useRef<HTMLDivElement>(null)

  // 扫描范围
  const [maxPapers, setMaxPapers] = useState(32)
  const [maxCompare, setMaxCompare] = useState(3)

  // 模拟扫描
  const [sim, setSim] = useState<'idle' | 'running' | 'cancel_req' | 'cancelled' | 'done'>('idle')
  const [stage, setStage] = useState(0)
  useEffect(() => {
    if (sim !== 'running' && sim !== 'cancel_req') return
    if (sim === 'cancel_req') {
      const t = setTimeout(() => setSim('cancelled'), 1200)
      return () => clearTimeout(t)
    }
    const t = setInterval(() => {
      setStage((s) => {
        if (s >= STAGES.length - 1) {
          clearInterval(t)
          setSim('done')
          toast.success('扫描完成：已生成项目行动（演示）。')
          return s
        }
        return s + 1
      })
    }, 1400)
    return () => clearInterval(t)
  }, [sim])

  const startScan = () => {
    setStage(0)
    setSim('running')
  }

  const stats = completedScan?.stats ?? {}
  const material = impacts.filter((i) => i.impact_mode !== 'no_material_change')
  const criticalCount = impacts.filter((i) => i.severity === 'critical').length
  const competitorCount = impacts.filter((i) => i.strategic_flags.includes('competitor')).length
  const integrityCount = impacts.filter(
    (i) => i.impact_mode === 'research_integrity' || i.event_type === 'retraction',
  ).length
  const retractionCount = impacts.filter((i) => i.event_type === 'retraction').length
  const headline = c.actions.find((a) => a.priority === 'critical')?.title ?? material[0]?.source.title

  const running = sim === 'running' || sim === 'cancel_req'

  return (
    <div className="space-y-6">
      <PageHeader
        title="搜索最新公开论文"
        subtitle="系统根据你论文的全文画像和核心 Claim 自动搜索，不需要你自己写检索词。"
      />

      {/* 顶部说明块 */}
      <div className="rounded-[12px] border border-sep bg-white p-5">
        <SectionTitle>当前项目：{c.title}</SectionTitle>
        <p className="mt-2 t-b2 text-ls">
          点击一次后，Agent 会完成：<strong className="t-b2e text-lp">arXiv 最新论文搜索 → 混合检索 →
          公开 PDF 全文提取 → <Mono>deepseek-v4-pro</Mono> 读取你的文稿和公开论文全文并逐项比较 →
          生成项目行动</strong>。
        </p>
        <SubNote className="mt-2">
          {queries.length > 0 ? (
            <>自动搜索主题：{queries.join(' · ')}</>
          ) : (
            <>未运行 AI 全文画像：搜索主题由研究问题自动生成。到“我的论文”跑一次 AI 全文画像，搜索会更准。</>
          )}
        </SubNote>
        <SubNote className="mt-1">
          分析模型：<Mono>deepseek-v4-pro</Mono>（远程 API，发送完整文稿与命中论文全文） ·
          向量：未启用（纯关键词检索） · 已确认核心 Claim：<Mono>{confirmedClaims.length}</Mono>
        </SubNote>
        {confirmedClaims.length === 0 && (
          <Callout kind="warning" className="mt-3">
            <span className="flex flex-wrap items-center gap-2">
              请先到“我的论文”确认至少一条核心 Claim。
              <Button size={26} variant="secondary" onClick={() => navigate('/case')}>
                去确认 Claim
              </Button>
            </span>
          </Callout>
        )}
      </div>

      {/* 扫描范围 */}
      <Collapsible>
        <CollapsibleTrigger className="group flex items-center gap-1 t-b2e text-lp hover:text-radar">
          <ChevronDown className="size-4 transition-transform duration-150 group-data-[state=open]:rotate-180" />
          扫描范围
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3">
          <div className="flex flex-wrap items-end gap-4 rounded-[12px] border border-sep bg-white p-4">
            <div>
              <label htmlFor="max-papers" className="mb-1 block t-c1e text-ls">最多搜索公开论文</label>
              <input
                id="max-papers"
                type="number"
                min={8}
                max={60}
                step={4}
                value={maxPapers}
                onChange={(e) => setMaxPapers(Number(e.target.value))}
                className="h-8 w-28 rounded-[10px] border border-sep px-2 font-mono-radar t-b2 outline-none focus-visible:ring-2 focus-visible:ring-kblue"
              />
            </div>
            <div>
              <label htmlFor="max-compare" className="mb-1 block t-c1e text-ls">最多深度比较</label>
              <input
                id="max-compare"
                type="number"
                min={1}
                max={10}
                value={maxCompare}
                onChange={(e) => setMaxCompare(Number(e.target.value))}
                className="h-8 w-28 rounded-[10px] border border-sep px-2 font-mono-radar t-b2 outline-none focus-visible:ring-2 focus-visible:ring-kblue"
              />
            </div>
            <SubNote className="max-w-md pb-1.5">
              结果按 arXiv 提交日期从新到旧；只深度分析与已确认 Claim 最相关的论文。每篇论文需要两次结构化判断，Demo 建议保持 3 篇。
            </SubNote>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* 主 CTA + 扫描进行态 */}
      <div className="space-y-3">
        <Button
          size={44}
          className="w-full sm:w-auto sm:min-w-[320px]"
          disabled={running || confirmedClaims.length === 0}
          onClick={startScan}
        >
          搜索最新公开论文并告诉我该做什么
        </Button>

        {running && (
          <div className="rounded-[12px] border border-sep bg-white p-4">
            <p className="flex items-center gap-2 t-b2e text-lp">
              <span className="radar-pulse-dot inline-block size-2 rounded-full bg-radar" aria-hidden />
              Agent 正在工作：联网搜索并逐篇比较公开论文
            </p>
            <Progress
              value={((stage + 1) / STAGES.length) * 100}
              className="mt-3 h-1.5 bg-black/[0.06] [&>div]:bg-radar"
            />
            <SubNote className="mt-2">{STAGES[stage]}</SubNote>
            {sim === 'cancel_req' ? (
              <SubNote className="mt-2">已请求取消：扫描将在当前阶段结束后停止。</SubNote>
            ) : (
              <Button variant="outline" size={26} className="mt-3" onClick={() => setSim('cancel_req')}>
                取消扫描
              </Button>
            )}
          </div>
        )}
        {sim === 'cancelled' && (
          <Callout kind="info">上次扫描已取消，取消前完成的中途结果已保留。</Callout>
        )}
        {sim === 'done' && !completedScan && (
          <Callout kind="success">本次扫描没有需要审查的材料性影响。</Callout>
        )}
      </div>

      {/* 扫描状态信息 */}
      {!running && sim !== 'cancelled' && (
        <>
          {scan?.status === 'failed' && (
            <Callout kind="error">
              <span className="flex flex-wrap items-center gap-2">
                最近一次扫描失败：{scan.error_message ?? '未知错误'}
                <Button size={26} variant="secondary" onClick={startScan}>重试扫描</Button>
              </span>
            </Callout>
          )}
          {scan?.status === 'interrupted' && (
            <Callout kind="warning">
              上次扫描被中断（页面刷新或服务重启），结果可能不完整，可重新发起扫描。
            </Callout>
          )}
          {scan?.status === 'cancelled' && (
            <Callout kind="info">上次扫描已取消，取消前完成的中途结果已保留。</Callout>
          )}
          {!scan && (
            <EmptyState
              icon={Satellite}
              title="还没有联网扫描结果"
              hint="点击上方按钮，Agent 会完成搜索、全文比较并生成项目行动。"
            />
          )}
        </>
      )}

      {/* 扫描摘要区 */}
      {completedScan && (
        <div className="space-y-4 border-t border-sep pt-6">
          <div>
            <SectionTitle>最近一次真实扫描</SectionTitle>
            <SubNote className="mt-1">
              最近一次扫描：<Mono>{fmtDateTime(completedScan.finished_at ?? completedScan.started_at) ?? '—'}</Mono>
            </SubNote>
          </div>
          {retractionCount > 0 && (
            <Callout kind="warning">⚠️ {retractionCount} 篇文献被撤稿标记</Callout>
          )}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="公开论文" value={stats.scanned_papers ?? impacts.length} />
            <MetricCard label="深度比较" value={stats.routed_pairs ?? impacts.length} />
            <MetricCard label="材料影响" value={material.length} />
            <MetricCard label="紧急" value={criticalCount} tone="red" />
            <MetricCard label="竞争预警" value={competitorCount} tone="orange" />
            <MetricCard label="完整性" value={integrityCount} tone="blue" />
          </div>
          {material.length > 0 ? (
            <Callout kind="info">
              <span className="flex flex-wrap items-center gap-2">
                {headline ?? '本次扫描有需要审查的材料性影响。'}
                <Button size={26} onClick={() => navigate('/actions')}>查看我要做什么</Button>
              </span>
            </Callout>
          ) : (
            <Callout kind="success">本次扫描没有需要审查的材料性影响。</Callout>
          )}
        </div>
      )}

      {/* 双栏工作区 */}
      {impacts.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[30%_1fr]">
          <div className="overflow-hidden rounded-[12px] border border-sep bg-white">
            <p className="border-b border-sep px-4 py-2.5 t-b2e text-lp">影响队列</p>
            <div className="max-h-[560px] overflow-y-auto">
              {impacts.map((imp) => (
                <button
                  key={imp.id}
                  onClick={() => {
                    setSelectedId(imp.id)
                    detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  }}
                  className={cn(
                    'flex w-full items-start gap-2 border-b border-sep px-4 py-3 text-left transition-colors duration-150 last:border-0',
                    selected?.id === imp.id ? 'bg-radar-soft' : 'hover:bg-black/[0.03]',
                  )}
                >
                  <Dot tone={toneFor(imp.severity)} className="mt-1.5" />
                  <span className="min-w-0">
                    <span className="block t-b2e text-lp">
                      <Mono>{imp.claim_stable_key}</Mono> · {SEVERITY[imp.severity]}
                    </span>
                    <span className="clamp-2 mt-0.5 block t-c1 text-lt">{imp.source.title}</span>
                  </span>
                  {imp.strategic_flags.includes('competitor') && (
                    <Swords className="ml-auto mt-1 size-4 shrink-0 text-korange" aria-label="竞争标记" />
                  )}
                  {imp.event_type === 'retraction' && (
                    <ShieldAlert className="ml-auto mt-1 size-4 shrink-0 text-kred" aria-label="撤稿" />
                  )}
                </button>
              ))}
            </div>
          </div>
          <div ref={detailRef} className="scroll-mt-6 rounded-[12px] border border-sep bg-white p-5">
            {selected ? (
              <ImpactDetail impact={selected} />
            ) : (
              <SubNote>从左侧队列选择一项影响查看详情。</SubNote>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
