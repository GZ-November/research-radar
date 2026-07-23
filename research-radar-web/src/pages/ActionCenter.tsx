import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { CheckCircle2, Download, Telescope } from 'lucide-react'
import { toast } from 'sonner'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/radar/Button'
import { Callout } from '@/components/radar/Callout'
import { Dot, StatusBadge } from '@/components/radar/StatusBadge'
import { EmptyState } from '@/components/radar/EmptyState'
import { EvidenceBlock, QuoteBlock } from '@/components/radar/EvidenceBlock'
import { ImpactDecisionBlock } from '@/components/radar/ImpactDecisionBlock'
import { ImpactStatusCallout } from '@/components/radar/ImpactStatusCallout'
import { MetricCard } from '@/components/radar/MetricCard'
import { SourceTraceability } from '@/components/radar/SourceTraceability'
import { Mono, PageHeader, SectionTitle, SubNote } from '@/components/radar/Typography'
import {
  claimAttention,
  confirmedRevision,
  downloadText,
  fmtDate,
  latestCompletedScan,
  sortActions,
  sortImpacts,
  venueLine,
} from '@/lib/format'
import {
  ACTION_STATUS,
  ACTION_TYPE,
  ATTENTION,
  COMPARABILITY,
  IMPACT_MODE,
  PUBLICATION_TYPE,
  PRIORITY,
  REVIEW_STATE,
  STANCE,
  SUGGESTED_ACTION,
  TRUST_STATE,
  toneFor,
} from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import type { Case, Claim, Impact, RadarAction } from '@/types'

function guidanceShort(impact: Impact, review: string): string {
  if (review === 'dismissed') return '已不采用'
  if (review === 'confirmed' || review === 'edited') return '已采用'
  if (impact.impact_mode === 'research_integrity' || impact.event_type === 'retraction') return '建议采用（紧急）'
  if (impact.impact_mode === 'no_material_change') return '无需改变'
  if (impact.stance === 'challenges' && ['compatible', 'partial'].includes(impact.comparability)) return '建议采用'
  if (impact.stance === 'supports' && ['compatible', 'partial'].includes(impact.comparability)) return '建议采用为支持证据'
  if (['boundary_condition', 'prior_art'].includes(impact.impact_mode) || impact.comparability === 'incompatible') return '建议部分采用'
  if (impact.stance === 'uncertain') return '先核对再采用'
  return '建议背景采用'
}

// ————— Tab 1：行动条目 —————
function ActionItem({ action, c }: { action: RadarAction; c: Case }) {
  const { actionStatus, setActionStatus, confirm, setFocusImpactId } = useAppStore()
  const navigate = useNavigate()
  const status = actionStatus(action)
  const impact = c.impacts.find((i) => i.id === action.impact_candidate_id) ?? null
  const claim = c.claims.find((cl) => cl.revisions.some((r) => r.id === action.claim_revision_id))
  const [checked, setChecked] = useState<Record<number, boolean>>({})

  const dismiss = async () => {
    const ok = await confirm({
      actionName: '不处理这项行动',
      description: '行动会被关闭；之后如需恢复，可在“有用论文”中重新采用对应影响。',
      confirmLabel: '确认不处理',
      danger: true,
    })
    if (!ok) return
    setActionStatus(action.id, 'dismissed')
    toast.success('行动已关闭')
  }

  return (
    <div className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusBadge k={action.priority} label={PRIORITY[action.priority]} />
        <StatusBadge k={status} label={ACTION_STATUS[status]} />
      </div>
      <SubNote className="mt-2">
        建议期限：<Mono>{action.due_label ?? '—'}</Mono> · 关联 Claim：
        <Mono>{claim?.stable_key ?? '—'}</Mono>
      </SubNote>
      <p className="mt-2 t-b2 text-lp">{action.rationale}</p>
      {action.advice_source === 'llm' && action.source_title ? (
        <SubNote className="mt-1.5">AI 建议 · 基于《{action.source_title}》</SubNote>
      ) : null}

      {impact && (
        <>
          <p className="mt-3 t-b2e text-lp">触发来源</p>
          <div className="mt-1.5">
            <SourceTraceability source={impact.source} />
          </div>
          <SubNote className="mt-2">
            影响：{STANCE[impact.stance]} / {IMPACT_MODE[impact.impact_mode]} · 可比性：
            {COMPARABILITY[impact.comparability]} · 审查状态：{REVIEW_STATE[impact.review_state]}
          </SubNote>
        </>
      )}

      {action.checklist.length > 0 && (
        <>
          <p className="mt-3 t-b2e text-lp">执行清单</p>
          <ul className="mt-1.5 space-y-1.5">
            {action.checklist.map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <Checkbox
                  id={`${action.id}-${i}`}
                  checked={!!checked[i]}
                  onCheckedChange={(v) => setChecked((s) => ({ ...s, [i]: v === true }))}
                  className="mt-0.5 border-sep data-[state=checked]:border-radar data-[state=checked]:bg-radar"
                />
                <label
                  htmlFor={`${action.id}-${i}`}
                  className={checked[i] ? 't-b2 text-lt line-through' : 't-b2 text-lp'}
                >
                  {item}
                </label>
              </li>
            ))}
          </ul>
        </>
      )}

      {status === 'proposed' && (
        <Callout kind="info" className="mt-3">
          先在“有用论文”中采用对应影响，再开始执行这项行动。
        </Callout>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size={26}
          disabled={status === 'proposed' || status === 'in_progress' || status === 'done' || status === 'dismissed'}
          onClick={() => {
            setActionStatus(action.id, 'in_progress')
            toast.success('行动已开始')
          }}
        >
          开始
        </Button>
        <Button
          size={26}
          disabled={status === 'proposed' || status === 'done' || status === 'dismissed'}
          onClick={() => {
            setActionStatus(action.id, 'done')
            toast.success('行动已完成')
          }}
        >
          完成
        </Button>
        <Button
          variant="outline"
          size={26}
          disabled={status === 'dismissed' || status === 'done'}
          onClick={dismiss}
        >
          不处理
        </Button>
        {impact && (
          <Button
            variant="outline"
            size={26}
            onClick={() => {
              setFocusImpactId(impact.id)
              navigate('/radar')
            }}
          >
            查看证据
          </Button>
        )}
      </div>
    </div>
  )
}

// ————— Tab 2：有用论文 —————
function UsefulPapers({ c }: { c: Case }) {
  const { impactState, setFocusImpactId } = useAppStore()
  const navigate = useNavigate()
  const material = sortImpacts(c.impacts.filter((i) => i.impact_mode !== 'no_material_change'))
  const noChange = c.impacts.filter((i) => i.impact_mode === 'no_material_change')
  const defaultOpen = material.filter((i) => impactState(i) === 'candidate').map((i) => i.id)

  return (
    <div className="space-y-5">
      <div>
        <SectionTitle>这次搜索中值得你决策或继续观察的论文</SectionTitle>
        <SubNote className="mt-1 max-w-3xl">
          “采用”表示接受 Agent 对这篇论文影响的判断，并打开相关行动；不会自动修改你的论文或
          Claim。每项判断都保留原文、PDF、DOI 和精确证据。
        </SubNote>
      </div>

      {material.length > 0 ? (
        <Accordion type="multiple" defaultValue={defaultOpen} className="space-y-2">
          {material.map((imp) => (
            <AccordionItem
              key={imp.id}
              value={imp.id}
              className="rounded-[12px] border border-sep bg-white px-4 data-[state=open]:shadow-[0_4px_16px_rgba(0,0,0,0.06)]"
            >
              <AccordionTrigger className="py-3 hover:no-underline [&>svg]:text-lt">
                <span className="clamp-2 pr-3 text-left t-b2e text-lp">
                  {imp.source.title} · {imp.source.venue ?? 'arXiv'} · {guidanceShort(imp, impactState(imp))}
                </span>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <div className="space-y-4">
                  <SourceTraceability source={imp.source} />
                  <Separator className="bg-sep" />
                  <ImpactStatusCallout impact={imp} />
                  <p className="t-b2 text-lp">
                    <strong className="t-b2e">影响的 Claim：<Mono>{imp.claim_stable_key}</Mono></strong>
                    {' '}— {imp.claim_statement}
                  </p>
                  <SubNote>
                    建议动作：{SUGGESTED_ACTION[imp.suggested_action]} · 证据状态：
                    {TRUST_STATE[imp.trust_state]}
                  </SubNote>
                  <EvidenceBlock label="这篇论文中的精确证据" evidence={imp.evidence_new} />
                  {imp.uncertainty.length > 0 && (
                    <div>
                      <p className="t-b2e text-lp">采用前需要注意</p>
                      <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                        {imp.uncertainty.map((u, i) => (
                          <li key={i}>{u}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <ImpactDecisionBlock impact={imp} />
                  <div>
                    <Button
                      variant="outline"
                      size={26}
                      onClick={() => {
                        setFocusImpactId(imp.id)
                        navigate('/radar')
                      }}
                    >
                      查看完整比较
                    </Button>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      ) : (
        <SubNote>暂无记录。</SubNote>
      )}

      {noChange.length > 0 && (
        <div>
          <SectionTitle className="t-b1e">已深度比较 · 暂无材料性影响</SectionTitle>
          <Accordion type="multiple" className="mt-2 space-y-2">
            {noChange.map((imp) => {
              const scan = c.scans.find((s) => s.id === imp.scan_run_id)
              const model = scan?.stats.analysis_model ?? 'deepseek-v4-pro'
              return (
                <AccordionItem
                  key={imp.id}
                  value={imp.id}
                  className="rounded-[12px] border border-sep bg-white px-4"
                >
                  <AccordionTrigger className="py-3 hover:no-underline [&>svg]:text-lt">
                    <span className="clamp-2 pr-3 text-left t-b2 text-ls">
                      {imp.source.title} · {imp.source.venue ?? 'arXiv'} · 无需改变
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="pb-4">
                    <div className="space-y-3">
                      <SubNote>
                        比较对象：<Mono>{imp.claim_stable_key}</Mono> · 总体可比性：
                        {COMPARABILITY[imp.comparability]} · 判断状态：{REVIEW_STATE[impactState(imp)]}
                      </SubNote>
                      <EvidenceBlock label="用于判断的精确证据" evidence={imp.evidence_new} />
                      <SubNote>
                        <Mono>{model}</Mono> 已完成双方全文比较；你可以打开条件矩阵，把判断改为 prior
                        art、边界条件或方法替代。
                      </SubNote>
                      <Button
                        variant="outline"
                        size={26}
                        onClick={() => {
                          setFocusImpactId(imp.id)
                          navigate('/radar')
                        }}
                      >
                        查看条件矩阵并修正判断
                      </Button>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              )
            })}
          </Accordion>
        </div>
      )}
    </div>
  )
}

// ————— Tab 3：受影响的主张 —————
function AffectedClaims({ c }: { c: Case }) {
  const { impactState } = useAppStore()
  const claims = [...c.claims].sort((a, b) => a.stable_key.localeCompare(b.stable_key))
  if (claims.length === 0) return <SubNote>暂无记录。</SubNote>
  return (
    <div className="space-y-2">
      {claims.map((cl: Claim) => {
        const attention = claimAttention(cl.stable_key, c.impacts, impactState)
        const dotTone =
          attention === 'disputed' || attention === 'revalidation_required'
            ? 'red'
            : attention === 'competitor_pressure' || attention === 'needs_review'
              ? 'orange'
              : 'green'
        const rev = confirmedRevision(cl)
        return (
          <div key={cl.id} className="rounded-[12px] border border-sep bg-white p-4">
            <p className="t-b2e text-lp">
              <Dot tone={dotTone} className="mr-2" />
              <Mono>{cl.stable_key}</Mono> · {ATTENTION[attention]}
            </p>
            {rev ? (
              <p className="mt-1.5 t-b2 text-ls">{rev.statement}</p>
            ) : (
              <p className="mt-1.5 t-b2 text-lt">尚无已确认表述。</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ————— Tab 4：写作证据 —————
function WritingEvidence({ c }: { c: Case }) {
  const { impactState } = useAppStore()
  const buckets = useMemo(() => {
    const supports = c.impacts.filter((i) => i.stance === 'supports')
    const challenges = c.impacts.filter((i) => i.stance === 'challenges')
    const boundary = c.impacts.filter((i) =>
      ['boundary_condition', 'prior_art', 'method_substitution'].includes(i.impact_mode),
    )
    const integrity = c.impacts.filter(
      (i) => i.impact_mode === 'research_integrity' || i.event_type === 'retraction',
    )
    return { supports, challenges, boundary, integrity }
  }, [c.impacts])

  const writingActions = sortActions(
    c.actions.filter((a) => ['writing', 'cite'].includes(a.action_type)),
    () => '',
  )

  const entry = (imp: Impact) => (
    <AccordionItem
      key={imp.id}
      value={imp.id}
      className="rounded-[12px] border border-sep bg-white px-4"
    >
      <AccordionTrigger className="py-3 hover:no-underline [&>svg]:text-lt">
        <span className="clamp-2 pr-3 text-left t-b2 text-lp">
          <Mono>{imp.claim_stable_key}</Mono> · {imp.source.title} ·{' '}
          {['confirmed', 'edited'].includes(impactState(imp)) ? '已确认' : '待确认'}
        </span>
      </AccordionTrigger>
      <AccordionContent className="pb-4">
        <div className="space-y-2">
          <SubNote>
            {STANCE[imp.stance]} · {IMPACT_MODE[imp.impact_mode]} · 可比性：
            {COMPARABILITY[imp.comparability]}
          </SubNote>
          <QuoteBlock quote={imp.evidence_new?.quote} locator={imp.evidence_new?.locator} />
          <SubNote>
            发表载体：
            {venueLine(imp.source, (t) => (t ? PUBLICATION_TYPE[t] ?? '公开论文' : '公开论文'))}
          </SubNote>
          <p className="flex flex-wrap items-center gap-x-1.5 t-c1 text-lt">
            {imp.source.url && (
              <a href={imp.source.url} target="_blank" rel="noreferrer" className="text-radar hover:underline">
                查看原文
              </a>
            )}
            {imp.source.pdf_url && (
              <>
                <span aria-hidden>·</span>
                <a href={imp.source.pdf_url} target="_blank" rel="noreferrer" className="text-radar hover:underline">
                  PDF 全文
                </a>
              </>
            )}
            <span aria-hidden>·</span>
            {imp.source.doi ? (
              <a
                href={`https://doi.org/${imp.source.doi}`}
                target="_blank"
                rel="noreferrer"
                className="font-mono-radar text-radar hover:underline"
              >
                DOI: {imp.source.doi}
              </a>
            ) : (
              <span>DOI：未登记</span>
            )}
          </p>
        </div>
      </AccordionContent>
    </AccordionItem>
  )

  const bucket = (list: Impact[]) =>
    list.length === 0 ? (
      <SubNote>暂无记录。</SubNote>
    ) : (
      <Accordion type="multiple" className="space-y-2">
        {list.map(entry)}
      </Accordion>
    )

  const downloadBrief = () => {
    const lines: string[] = [
      `# Discussion Evidence Brief`,
      ``,
      `项目：${c.title}`,
      `生成时间：${fmtDate(new Date().toISOString()) ?? ''}`,
      ``,
      `## 支持证据`,
      ...buckets.supports.map(
        (i) => `- **${i.source.title}**（${IMPACT_MODE[i.impact_mode]} / ${COMPARABILITY[i.comparability]}）\n  > ${(i.evidence_new?.quote ?? '').replace(/\n/g, ' ')}\n  位置：${i.evidence_new?.locator ?? '未登记位置'} · ${i.source.url ?? ''}`,
      ),
      ``,
      `## 反证`,
      ...buckets.challenges.map(
        (i) => `- **${i.source.title}**（${IMPACT_MODE[i.impact_mode]} / ${COMPARABILITY[i.comparability]}）\n  > ${(i.evidence_new?.quote ?? '').replace(/\n/g, ' ')}\n  位置：${i.evidence_new?.locator ?? '未登记位置'} · ${i.source.url ?? ''}`,
      ),
      ``,
      `## 边界与 prior art`,
      ...buckets.boundary.map((i) => `- **${i.source.title}**（${IMPACT_MODE[i.impact_mode]}）· ${i.source.url ?? ''}`),
      ``,
      `## 完整性风险`,
      ...buckets.integrity.map((i) => `- **${i.source.title}** · ${i.source.url ?? ''}`),
      ``,
    ]
    downloadText('discussion-evidence-brief.md', lines.join('\n'))
    toast.success('已下载 Discussion Evidence Brief')
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="支持证据" value={buckets.supports.length} tone="green" />
        <MetricCard label="反证" value={buckets.challenges.length} tone="red" />
        <MetricCard label="边界/相关工作" value={buckets.boundary.length} tone="blue" />
        <MetricCard label="完整性风险" value={buckets.integrity.length} tone="orange" />
      </div>

      <Tabs defaultValue="supports">
        <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
          {[
            ['supports', '支持证据'],
            ['challenges', '反证'],
            ['boundary', '边界与 prior art'],
            ['integrity', '完整性'],
          ].map(([v, l]) => (
            <TabsTrigger key={v} value={v} className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
              {l}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="supports" className="mt-4">{bucket(buckets.supports)}</TabsContent>
        <TabsContent value="challenges" className="mt-4">{bucket(buckets.challenges)}</TabsContent>
        <TabsContent value="boundary" className="mt-4">{bucket(buckets.boundary)}</TabsContent>
        <TabsContent value="integrity" className="mt-4">{bucket(buckets.integrity)}</TabsContent>
      </Tabs>

      <div>
        <p className="t-b2e text-lp">建议写作动作</p>
        {writingActions.length === 0 ? (
          <SubNote className="mt-1">暂无记录。</SubNote>
        ) : (
          <ul className="mt-1.5 space-y-1.5">
            {writingActions.map((a) => (
              <li key={a.id} className="t-b2 text-ls">
                - {PRIORITY[a.priority]} · {a.title} — <span className="text-lt">{a.rationale}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <Button variant="outline" leftIcon={<Download />} onClick={downloadBrief}>
          下载 Discussion Evidence Brief
        </Button>
      </div>
    </div>
  )
}

// ————— 页面 —————
export default function ActionCenter() {
  const { currentCase: c, actionStatus } = useAppStore()
  const navigate = useNavigate()
  const scan = latestCompletedScan(c)

  const openActions = useMemo(
    () => c.actions.filter((a) => ['proposed', 'open', 'in_progress'].includes(actionStatus(a))),
    [c.actions, actionStatus],
  )
  const critical = openActions.find((a) => a.priority === 'critical')
  const headlineAction = critical ?? openActions[0]

  const stats = scan?.stats ?? {}
  const queries = c.settings.generated_search_queries?.queries ?? stats.search_queries ?? []

  const metric = (pred: (a: RadarAction) => boolean) =>
    c.actions.filter((a) => actionStatus(a) !== 'dismissed' && pred(a)).length

  if (!scan) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="这个项目现在需要做什么？"
          subtitle={`所有判断和行动都属于项目《${c.title}》。`}
        />
        <EmptyState
          icon={Telescope}
          title="还没有联网搜索结果"
          hint="先搜索最新公开论文，系统才能给出行动建议。"
          action={{ label: '开始搜索最新公开论文', onClick: () => navigate('/radar') }}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="这个项目现在需要做什么？"
        subtitle={`所有判断和行动都属于项目《${c.title}》。`}
      />

      {/* 头条横幅 */}
      {critical ? (
        <Callout kind="error">
          <strong className="t-b2e">需要马上处理：</strong>
          {critical.title}
        </Callout>
      ) : headlineAction ? (
        <Callout kind="warning">
          <strong className="t-b2e">本周建议：</strong>
          {headlineAction.title}
        </Callout>
      ) : (
        <Callout kind="success">
          最新公开论文中没有发现需要改变实验、数据或写作的材料性影响。
        </Callout>
      )}

      {/* 溯源小字 */}
      <SubNote>
        arXiv 最新优先 · 混合检索 · <Mono>{stats.analysis_model ?? 'deepseek-v4-pro'}</Mono> 影响判断 ·{' '}
        <Mono>{stats.full_text_papers ?? '—'}</Mono> 篇公开 PDF 全文 · 最新论文日期{' '}
        <Mono>{fmtDate(stats.newest_publication) ?? '—'}</Mono>
        {queries.length > 0 && <> · 搜索主题：{queries.slice(0, 2).join(' / ')}</>}
      </SubNote>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => navigate('/radar')}>
          重新搜索最新公开论文
        </Button>
        <Button onClick={() => navigate('/ledger')}>打开改进工作台</Button>
      </div>

      {/* 6 指标卡 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="紧急" value={metric((a) => a.priority === 'critical')} tone="red" />
        <MetricCard label="改实验" value={metric((a) => a.action_type === 'experiment')} />
        <MetricCard label="补数据" value={metric((a) => a.action_type === 'data')} />
        <MetricCard label="调整写作" value={metric((a) => a.action_type === 'writing')} />
        <MetricCard label="竞争预警" value={metric((a) => a.action_type === 'competitor_response')} tone="orange" />
        <MetricCard label="重新验证" value={metric((a) => a.action_type === 'revalidation')} tone="blue" />
      </div>

      <Tabs defaultValue="todo">
        <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
          {[
            ['todo', '你要做什么'],
            ['papers', '有用论文'],
            ['claims', '受影响的主张'],
            ['evidence', '写作证据'],
          ].map(([v, l]) => (
            <TabsTrigger key={v} value={v} className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
              {l}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="todo" className="mt-4">
          {openActions.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="本周没有开放行动"
              hint="最新扫描没有发现需要执行的任务；可以重新扫描查看最新公开论文。"
              action={{ label: '重新扫描最新公开论文', onClick: () => navigate('/radar') }}
            />
          ) : (
            <Accordion
              type="multiple"
              defaultValue={sortActions(openActions, actionStatus)
                .filter((a) => a.priority === 'critical')
                .map((a) => a.id)}
              className="space-y-2"
            >
              {sortActions(openActions, actionStatus).map((a) => (
                <AccordionItem
                  key={a.id}
                  value={a.id}
                  className="rounded-[12px] border border-sep bg-white data-[state=open]:shadow-[0_4px_16px_rgba(0,0,0,0.06)]"
                >
                  <AccordionTrigger className="px-4 py-3 hover:no-underline [&>svg]:text-lt">
                    <span className="flex min-w-0 items-center gap-2 pr-3 text-left t-b2e text-lp">
                      <Dot tone={toneFor(a.priority)} />
                      <span className="shrink-0 text-ls">{ACTION_TYPE[a.action_type]}</span>
                      <span className="clamp-2">· {a.title}</span>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <ActionItem action={a} c={c} />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </TabsContent>

        <TabsContent value="papers" className="mt-4">
          <UsefulPapers c={c} />
        </TabsContent>
        <TabsContent value="claims" className="mt-4">
          <AffectedClaims c={c} />
        </TabsContent>
        <TabsContent value="evidence" className="mt-4">
          <WritingEvidence c={c} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
