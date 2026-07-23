import { useMemo, useRef, useState } from 'react'
import { CheckCircle2, Circle, FileText, History, Upload } from 'lucide-react'
import { toast } from 'sonner'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
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
import { EmptyState } from '@/components/radar/EmptyState'
import { MetricCard } from '@/components/radar/MetricCard'
import { QuoteBlock } from '@/components/radar/EvidenceBlock'
import { StatusBadge } from '@/components/radar/StatusBadge'
import { Mono, PageHeader, SectionTitle, SubNote } from '@/components/radar/Typography'
import { currentRevision, currentVersion, fmtDateTime } from '@/lib/format'
import { CENTRALITY, CONTRACT_LABELS, REVIEW_STATE, WATCH_ENTITY_TYPE } from '@/lib/labels'
import { useAppStore } from '@/store/AppStore'
import type { Centrality, Claim, ReviewState } from '@/types'

// ————— Tab 2 单条 Claim —————
function ClaimItem({ claim, isCurrentVersion }: { claim: Claim; isCurrentVersion: boolean }) {
  const { claimOverride, setClaimOverride } = useAppStore()
  const rev = currentRevision(claim)
  const [editOpen, setEditOpen] = useState(false)
  const [splitOpen, setSplitOpen] = useState(false)
  const [editStatement, setEditStatement] = useState('')
  const [editCentrality, setEditCentrality] = useState<Centrality>('major')
  const [editFalsifiable, setEditFalsifiable] = useState('')
  const [splitText, setSplitText] = useState('')

  if (!rev) return null
  const o = claimOverride(rev.id)
  const state: ReviewState = o?.review_state ?? rev.review_state
  const statement = o?.statement ?? rev.statement
  const centrality = o?.centrality ?? rev.centrality
  const falsifiable = o?.falsifiable_condition ?? rev.falsifiable_condition
  const versionNo = rev.revision_no
  const isCandidate = state === 'candidate'
  const isConfirmed = state === 'confirmed' || state === 'edited'
  const isHistory = !isCurrentVersion || state === 'superseded' || state === 'rejected'

  const openEdit = () => {
    setEditStatement(statement)
    setEditCentrality(centrality)
    setEditFalsifiable(falsifiable ?? '')
    setEditOpen(true)
  }

  const icon = isHistory ? (
    <History className="mt-0.5 size-4 shrink-0 text-lt" aria-label="历史" />
  ) : isConfirmed ? (
    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-kgreen" aria-label="已确认" />
  ) : (
    <Circle className="mt-0.5 size-4 shrink-0 text-lt" aria-label="候选" />
  )

  return (
    <>
      <AccordionItem value={rev.id} className="rounded-[12px] border border-sep bg-white px-4 data-[state=open]:shadow-[0_4px_16px_rgba(0,0,0,0.06)]">
        <AccordionTrigger className="py-3 hover:no-underline [&>svg]:text-lt">
          <span className="flex min-w-0 items-start gap-2 pr-3 text-left">
            {icon}
            <span className="min-w-0">
              <span className="t-b2e text-lp">
                <Mono>{claim.stable_key}</Mono> · {CENTRALITY[centrality]}
              </span>
              <span className="clamp-2 mt-0.5 block t-b2 font-normal text-ls">{statement}</span>
            </span>
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-4">
          <div className="space-y-3">
            <SubNote>
              状态：{REVIEW_STATE[state]} · 来自 <Mono>v{versionNo}</Mono> ·{' '}
              <Mono>{rev.source_locator ?? '未登记位置'}</Mono>
            </SubNote>
            {isHistory && (
              <Callout kind="warning">
                这条 Claim 未在当前版本中精确匹配，只保留为历史记录。
              </Callout>
            )}
            <QuoteBlock quote={rev.source_quote} locator={rev.source_locator} />
            <div>
              <p className="t-b2e text-lp">实验条件（Claim 合同）</p>
              <div className="mt-1.5 overflow-hidden rounded-[10px] border border-sep">
                <Table>
                  <TableBody>
                    {Object.entries(CONTRACT_LABELS).map(([k, label]) => (
                      <TableRow key={k} className="border-sep">
                        <TableCell className="w-28 bg-black/[0.02] t-c1e text-ls">{label}</TableCell>
                        <TableCell className="t-b2 text-lp">
                          {rev.contract[k as keyof typeof rev.contract] ?? '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
            <div>
              <p className="t-b2e text-lp">可证伪条件</p>
              <p className="mt-1 t-b2 text-ls">{falsifiable ?? '—'}</p>
            </div>
            {isCandidate && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size={26}
                  onClick={() => {
                    setClaimOverride(rev.id, { review_state: 'confirmed' })
                    toast.success(`已确认 ${claim.stable_key}`)
                  }}
                >
                  确认 Claim
                </Button>
                <Button
                  variant="outline"
                  size={26}
                  onClick={() => {
                    setClaimOverride(rev.id, { review_state: 'rejected' })
                    toast.success(`已拒绝 ${claim.stable_key}`)
                  }}
                >
                  拒绝
                </Button>
                <Button variant="outline" size={26} onClick={openEdit}>
                  编辑
                </Button>
                <Button variant="outline" size={26} onClick={() => { setSplitText(statement); setSplitOpen(true) }}>
                  拆分
                </Button>
              </div>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>

      {/* 编辑 Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="rounded-[16px] border-0 sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle className="t-t2e text-lp">编辑 Claim</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea
              value={editStatement}
              onChange={(e) => setEditStatement(e.target.value)}
              className="min-h-[88px] rounded-[10px] border-sep t-b2"
            />
            <div>
              <p className="mb-1 t-c1e text-ls">重要程度</p>
              <Select value={editCentrality} onValueChange={(v) => setEditCentrality(v as Centrality)}>
                <SelectTrigger className="h-8 w-40 rounded-[10px] border-sep t-b2">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="core">核心</SelectItem>
                  <SelectItem value="major">重要</SelectItem>
                  <SelectItem value="minor">次要</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <p className="mb-1 t-c1e text-ls">可证伪条件</p>
              <Textarea
                value={editFalsifiable}
                onChange={(e) => setEditFalsifiable(e.target.value)}
                className="min-h-[60px] rounded-[10px] border-sep t-b2"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="secondary" onClick={() => setEditOpen(false)}>取消</Button>
            <Button
              onClick={() => {
                setClaimOverride(rev.id, {
                  review_state: 'edited',
                  statement: editStatement.trim() || statement,
                  centrality: editCentrality,
                  falsifiable_condition: editFalsifiable.trim(),
                })
                setEditOpen(false)
                toast.success('已保存为已确认版本')
              }}
            >
              保存为已确认版本
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 拆分 Dialog */}
      <Dialog open={splitOpen} onOpenChange={setSplitOpen}>
        <DialogContent className="rounded-[16px] border-0 sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle className="t-t2e text-lp">拆分 Claim</DialogTitle>
          </DialogHeader>
          <div>
            <p className="mb-1 t-c1e text-ls">拆分（每行一条 Claim）</p>
            <Textarea
              value={splitText}
              onChange={(e) => setSplitText(e.target.value)}
              className="min-h-[120px] rounded-[10px] border-sep t-b2"
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="secondary" onClick={() => setSplitOpen(false)}>取消</Button>
            <Button
              onClick={() => {
                const n = splitText.split('\n').filter((l) => l.trim()).length
                setClaimOverride(rev.id, { review_state: 'edited' })
                setSplitOpen(false)
                toast.success(`已拆分为 ${Math.max(n, 1)} 条候选（演示）`)
              }}
            >
              拆分为多条候选
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ————— 页面 —————
export default function CasePage() {
  const { currentCase: c, claimOverride, watchEntities, addWatch, removeWatch } = useAppStore()
  const version = currentVersion(c)
  const [fileName, setFileName] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const revInfo = useMemo(
    () =>
      c.claims.map((cl) => {
        const rev = currentRevision(cl)
        const o = rev ? claimOverride(rev.id) : undefined
        const st = o?.review_state ?? rev?.review_state
        const isCurrent = rev?.manuscript_version_id === version?.id
        return { cl, rev, st, isCurrent }
      }),
    [c.claims, claimOverride, version],
  )
  const currentClaims = revInfo.filter((x) => x.isCurrent && x.st !== 'superseded')
  const confirmedCount = revInfo.filter((x) => x.st === 'confirmed' || x.st === 'edited').length

  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 10
  const filtered = revInfo.filter((x) => {
    if (filter === 'candidate') return x.st === 'candidate' && x.isCurrent
    if (filter === 'confirmed') return x.st === 'confirmed' || x.st === 'edited'
    if (filter === 'history') return !x.isCurrent || x.st === 'superseded' || x.st === 'rejected'
    return true
  })
  const paged = revInfo.length > 20 ? filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE) : filtered
  const firstCandidate = filtered.find((x) => x.st === 'candidate' && x.isCurrent)?.rev?.id

  // AI 画像
  const [profiling, setProfiling] = useState(false)
  const runProfile = () => {
    setProfiling(true)
    setTimeout(() => {
      setProfiling(false)
      if (!c.profile) toast.error('AI 画像生成失败：演示环境未连接分析模型')
    }, 1500)
  }

  // 竞争监控
  const watch = watchEntities(c.id)
  const [watchName, setWatchName] = useState('')
  const [watchType, setWatchType] = useState<'lab' | 'author' | 'org'>('lab')
  const [watchAliases, setWatchAliases] = useState('')
  const submitWatch = () => {
    if (!watchName.trim()) {
      toast.error('请填写团队/作者名称。')
      return
    }
    addWatch(c.id, {
      id: `watch-local-${Date.now()}`,
      case_id: c.id,
      entity_type: watchType,
      canonical_name: watchName.trim(),
      created_at: new Date().toISOString(),
      aliases: watchAliases.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    })
    setWatchName('')
    setWatchAliases('')
    toast.success('已添加监控对象')
  }

  const syncVersion = () => {
    if (!fileName) {
      toast.error('请先选择要上传的新版本文件。')
      return
    }
    toast.success(`已同步 v${(version?.version_no ?? 1) + 1}：保留 ${confirmedCount} 条稳定 Claim，发现 2 条新候选。`)
    setFileName('')
  }

  const profile = c.profile

  return (
    <div className="space-y-6">
      <PageHeader title={c.title} subtitle={c.research_question} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="当前文稿" value={<span className="block truncate text-[18px] leading-8">{version?.file_name ?? '—'}</span>} />
        <MetricCard label="版本" value={version ? `v${version.version_no}` : '—'} />
        <MetricCard label="当前 Claim" value={currentClaims.length} />
        <MetricCard label="已确认" value={confirmedCount} tone="green" />
      </div>

      <Tabs defaultValue="versions">
        <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
          {[
            ['versions', '文稿与版本'],
            ['claims', '项目主张'],
            ['profile', 'AI 全文画像'],
            ['watch', '竞争监控'],
          ].map(([v, l]) => (
            <TabsTrigger key={v} value={v} className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
              {l}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Tab 1 文稿与版本 */}
        <TabsContent value="versions" className="mt-4 space-y-6">
          <div className="rounded-[12px] border border-sep bg-white p-5">
            <SectionTitle>同步当前论文</SectionTitle>
            <SubNote className="mt-1">
              上传新版本不会覆盖历史文件。系统会保留仍然存在的 Claim，把新增或改写结果放入待确认队列。
            </SubNote>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                ref={fileRef}
                type="file"
                accept=".tex,.md,.pdf"
                className="hidden"
                onChange={(e) => setFileName(e.target.files?.[0]?.name ?? '')}
              />
              <Button variant="outline" leftIcon={<Upload />} onClick={() => fileRef.current?.click()}>
                上传新版本
              </Button>
              <Mono className="truncate t-c1 text-lt">{fileName || '未选择文件'}</Mono>
              <Button onClick={syncVersion}>同步为新版本</Button>
            </div>
          </div>

          <div>
            <p className="t-b2e text-lp">版本历史</p>
            <div className="mt-2 overflow-hidden rounded-[10px] border border-sep bg-white">
              <Table>
                <TableHeader>
                  <TableRow className="border-sep bg-black/[0.02] hover:bg-black/[0.02]">
                    <TableHead className="t-c1e text-ls">版本</TableHead>
                    <TableHead className="t-c1e text-ls">文件</TableHead>
                    <TableHead className="t-c1e text-ls">状态</TableHead>
                    <TableHead className="t-c1e text-ls">导入时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...c.versions]
                    .sort((a, b) => b.version_no - a.version_no)
                    .map((v) => (
                      <TableRow key={v.id} className="border-sep">
                        <TableCell className="font-mono-radar t-b2 text-lp">v{v.version_no}</TableCell>
                        <TableCell className="font-mono-radar t-b2 text-ls">{v.file_name}</TableCell>
                        <TableCell>
                          {v.is_current ? (
                            <StatusBadge tone="teal" label="当前" />
                          ) : (
                            <StatusBadge tone="gray" label="历史" />
                          )}
                        </TableCell>
                        <TableCell className="font-mono-radar t-c1 text-lt">
                          {fmtDateTime(v.created_at) ?? '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2 项目主张 */}
        <TabsContent value="claims" className="mt-4 space-y-3">
          {revInfo.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="尚未找到实验类 Claim 候选"
              hint="请检查文稿中的实验结论，或同步一个新版本文稿。"
            />
          ) : (
            <>
              {revInfo.length > 20 && (
                <div className="flex items-center gap-2">
                  <Select value={filter} onValueChange={(v) => { setFilter(v); setPage(0) }}>
                    <SelectTrigger className="h-8 w-40 rounded-[10px] border-sep t-b2">
                      <SelectValue placeholder="按状态过滤" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部</SelectItem>
                      <SelectItem value="candidate">待确认</SelectItem>
                      <SelectItem value="confirmed">已确认</SelectItem>
                      <SelectItem value="history">历史记录</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Accordion type="multiple" defaultValue={firstCandidate ? [firstCandidate] : []} className="space-y-2">
                {paged.map(({ cl, isCurrent }) => (
                  <ClaimItem key={cl.id} claim={cl} isCurrentVersion={isCurrent} />
                ))}
              </Accordion>
              {revInfo.length > 20 && filtered.length > PAGE_SIZE && (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size={26} disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                    上一页
                  </Button>
                  <SubNote>
                    第 <Mono>{page + 1}</Mono> / <Mono>{Math.ceil(filtered.length / PAGE_SIZE)}</Mono> 页
                  </SubNote>
                  <Button
                    variant="outline"
                    size={26}
                    disabled={(page + 1) * PAGE_SIZE >= filtered.length}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    下一页
                  </Button>
                </div>
              )}
            </>
          )}
        </TabsContent>

        {/* Tab 3 AI 全文画像 */}
        <TabsContent value="profile" className="mt-4 space-y-4">
          {confirmedCount === 0 ? (
            <Callout kind="info">先在“项目主张”中确认至少一条当前版本 Claim。</Callout>
          ) : (
            <div className="rounded-[12px] border border-sep bg-white p-5">
              <Button loading={profiling} onClick={runProfile}>
                用 deepseek-v4-pro 分析当前版本全文
              </Button>
              <SubNote className="mt-2">会把当前完整文稿和已确认 Claim 发送给 deepseek-v4-pro。</SubNote>
            </div>
          )}

          {!profile ? (
            <Callout kind="info">当前版本尚未生成全文理解画像。</Callout>
          ) : (
            <div className="space-y-5 rounded-[12px] border border-sep bg-white p-5">
              <SectionTitle>{profile.output.title}</SectionTitle>
              <div>
                <p className="t-b2e text-lp">研究问题</p>
                <p className="mt-1 t-b2 text-ls">{profile.output.research_problem ?? '—'}</p>
              </div>
              <div>
                <p className="t-b2e text-lp">核心论点</p>
                <p className="mt-1 t-b2 text-ls">{profile.output.central_thesis ?? '—'}</p>
              </div>
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-4">
                  <div>
                    <p className="t-b2e text-lp">主要贡献</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                      {profile.output.contributions.map((x, i) => <li key={i}>{x}</li>)}
                    </ul>
                  </div>
                  <div>
                    <p className="t-b2e text-lp">关键发现</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                      {profile.output.key_findings.map((x, i) => <li key={i}>{x}</li>)}
                    </ul>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <p className="t-b2e text-lp">局限</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                      {profile.output.limitations.map((x, i) => <li key={i}>{x}</li>)}
                    </ul>
                  </div>
                  <div>
                    <p className="t-b2e text-lp">每周监控主题</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 t-b2 text-ls">
                      {profile.output.watch_topics.map((x, i) => <li key={i}>{x}</li>)}
                    </ul>
                  </div>
                </div>
              </div>
              {profile.output.claim_profiles.length > 0 && (
                <div>
                  <p className="t-b2e text-lp">已确认 Claim 画像</p>
                  <Accordion type="multiple" className="mt-2 space-y-2">
                    {profile.output.claim_profiles.map((cp) => (
                      <AccordionItem key={cp.stable_key} value={cp.stable_key} className="rounded-[12px] border border-sep px-4">
                        <AccordionTrigger className="py-3 hover:no-underline [&>svg]:text-lt">
                          <span className="clamp-2 pr-3 text-left t-b2 text-lp">
                            <Mono>{cp.stable_key}</Mono> · {cp.role} · {cp.claim_summary}
                          </span>
                        </AccordionTrigger>
                        <AccordionContent className="pb-4">
                          <div className="space-y-3">
                            <div className="overflow-hidden rounded-[10px] border border-sep">
                              <Table>
                                <TableBody>
                                  {Object.entries(CONTRACT_LABELS).map(([k, label]) => (
                                    <TableRow key={k} className="border-sep">
                                      <TableCell className="w-28 bg-black/[0.02] t-c1e text-ls">{label}</TableCell>
                                      <TableCell className="t-b2 text-lp">
                                        {cp.contract[k as keyof typeof cp.contract] ?? '—'}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                            {cp.boundary_conditions.length > 0 && (
                              <div>
                                <p className="t-c1e text-ls">边界条件</p>
                                <ul className="mt-1 list-disc space-y-1 pl-5 t-c1 text-lt">
                                  {cp.boundary_conditions.map((b, i) => <li key={i}>{b}</li>)}
                                </ul>
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </div>
              )}
              <SubNote>
                画像模型：<Mono>{profile.model}</Mono> · 生成时间：<Mono>{fmtDateTime(profile.created_at) ?? '—'}</Mono>
              </SubNote>
            </div>
          )}
        </TabsContent>

        {/* Tab 4 竞争监控 */}
        <TabsContent value="watch" className="mt-4 space-y-4">
          {watch.length === 0 ? (
            <Callout kind="info">当前项目尚未配置竞争对手别名。</Callout>
          ) : (
            <div className="space-y-2">
              {watch.map((w) => (
                <div key={w.id} className="flex flex-wrap items-center gap-2 rounded-[12px] border border-sep bg-white px-4 py-3">
                  <p className="t-b2 text-lp">
                    <strong className="t-b2e">{w.canonical_name}</strong>{' '}
                    <Mono className="t-c1 text-lt">`{WATCH_ENTITY_TYPE[w.entity_type] ?? w.entity_type}`</Mono>
                  </p>
                  {w.aliases.length > 0 && (
                    <SubNote>别名：{w.aliases.join(', ')}</SubNote>
                  )}
                  <div className="flex-1" />
                  <Button
                    variant="outline"
                    size={26}
                    danger
                    onClick={() => {
                      removeWatch(c.id, w.id)
                      toast.success('已删除监控对象')
                    }}
                  >
                    删除
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="max-w-[520px] rounded-[12px] border border-sep bg-white p-5">
            <p className="t-b2e text-lp">添加监控对象</p>
            <div className="mt-3 space-y-3">
              <Input
                value={watchName}
                onChange={(e) => setWatchName(e.target.value)}
                placeholder="团队/作者名称"
                className="h-9 rounded-[10px] border-sep t-b2"
              />
              <Select value={watchType} onValueChange={(v) => setWatchType(v as 'lab' | 'author' | 'org')}>
                <SelectTrigger className="h-9 w-48 rounded-[10px] border-sep t-b2">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lab">实验室/团队</SelectItem>
                  <SelectItem value="author">作者</SelectItem>
                  <SelectItem value="org">机构</SelectItem>
                </SelectContent>
              </Select>
              <Input
                value={watchAliases}
                onChange={(e) => setWatchAliases(e.target.value)}
                placeholder="别名（用逗号分隔，可留空）"
                className="h-9 rounded-[10px] border-sep t-b2"
              />
              <Button onClick={submitWatch}>添加监控</Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
