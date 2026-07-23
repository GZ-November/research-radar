import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { FolderOpen, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/radar/Button'
import { EmptyState } from '@/components/radar/EmptyState'
import { PageHeader } from '@/components/radar/Typography'
import { Mono } from '@/components/radar/Typography'
import { currentRevision, currentVersion, fmtDate, latestCompletedScan } from '@/lib/format'
import { useAppStore } from '@/store/AppStore'
import type { Case } from '@/types'

function confirmedClaimCount(c: Case, overridden: (rid: string) => string | undefined): number {
  return c.claims.filter((cl) => {
    const rev = currentRevision(cl)
    if (!rev) return false
    const st = overridden(rev.id) ?? rev.review_state
    return st === 'confirmed' || st === 'edited'
  }).length
}

function ProjectCard({ c }: { c: Case }) {
  const { currentCaseId, setCurrentCase, claimOverride } = useAppStore()
  const navigate = useNavigate()
  const version = currentVersion(c)
  const scan = latestCompletedScan(c)
  const confirmed = confirmedClaimCount(c, (rid) => claimOverride(rid)?.review_state)

  return (
    <div className="rounded-[12px] border border-sep bg-white p-4 transition-[transform,box-shadow] duration-150 ease-radar hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.08)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="t-t2e text-lp">{c.title}</h3>
            {c.id === currentCaseId && (
              <span className="rounded-[4px] bg-radar-soft px-1.5 py-0.5 t-c1e text-radar">当前项目</span>
            )}
          </div>
          <p className="clamp-2 mt-1 t-b2 text-ls">{c.research_question}</p>
        </div>
        <Button
          onClick={() => {
            setCurrentCase(c.id)
            navigate('/actions')
          }}
        >
          打开项目
        </Button>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3 border-t border-sep pt-3">
        <div>
          <p className="t-c1 text-lt">当前版本</p>
          <Mono className="t-b2e text-lp">{version ? `v${version.version_no}` : '—'}</Mono>
        </div>
        <div>
          <p className="t-c1 text-lt">已确认 Claim</p>
          <Mono className="t-b2e text-lp">{confirmed}</Mono>
        </div>
        <div>
          <p className="t-c1 text-lt">最近雷达</p>
          <Mono className="t-b2e text-lp">
            {scan ? fmtDate(scan.finished_at ?? scan.started_at) ?? '—' : '尚未扫描'}
          </Mono>
        </div>
      </div>
      <p className="mt-2 t-c1 text-lt">
        当前文稿：<Mono>{version?.file_name ?? '—'}</Mono>
      </p>
    </div>
  )
}

export default function Home() {
  const { cases } = useAppStore()
  const navigate = useNavigate()
  const mine = useMemo(() => cases.filter((c) => !c.is_demo), [cases])
  const demos = useMemo(() => cases.filter((c) => c.is_demo), [cases])

  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [fileName, setFileName] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const submit = () => {
    if (!title.trim() || !question.trim() || !fileName) {
      toast.error('请填写项目标题、研究问题并选择当前文稿。')
      return
    }
    toast.success(`项目「${title.trim()}」已创建（演示），正在提取 Claim。`)
    setTitle('')
    setQuestion('')
    setFileName('')
    navigate('/case')
  }

  return (
    <div className="space-y-8">
      {/* Hero 横幅 */}
      <div className="rounded-[16px] bg-gradient-to-r from-radar-deep to-radar px-6 py-8 text-white sm:px-8">
        <p className="text-[26px] font-semibold leading-8 tracking-wide">Research Radar</p>
        <p className="mt-2 t-b1 text-white/80">
          盯住公开文献对你论文的影响，把变化变成可执行的行动。
        </p>
      </div>

      <PageHeader
        title="你的研究项目"
        subtitle="上传或同步你正在推进的论文；Radar、证据和行动会按项目长期积累。"
      />

      <Tabs defaultValue="mine">
        <TabsList className="h-9 rounded-[10px] bg-black/[0.05] p-1">
          <TabsTrigger value="mine" className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
            我的项目
          </TabsTrigger>
          <TabsTrigger value="new" className="rounded-[8px] px-3 t-b2e data-[state=active]:bg-white data-[state=active]:shadow-xs">
            新建项目
          </TabsTrigger>
        </TabsList>

        <TabsContent value="mine" className="mt-5 space-y-4">
          {mine.length === 0 && demos.length === 0 ? (
            <EmptyState
              icon={FolderOpen}
              title="还没有研究项目"
              hint="到“新建项目”上传第一篇论文，即可开始监控公开文献的影响。"
            />
          ) : (
            <>
              {mine.map((c) => (
                <ProjectCard key={c.id} c={c} />
              ))}
              {demos.length > 0 && (
                <>
                  <div className="border-t border-sep pt-5">
                    <p className="t-b2e text-ls">示例项目</p>
                    <p className="mt-0.5 t-c1 text-lt">
                      示例只用于体验产品，不限制你创建和切换自己的研究项目。
                    </p>
                  </div>
                  {demos.map((c) => (
                    <ProjectCard key={c.id} c={c} />
                  ))}
                </>
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="new" className="mt-5">
          <div className="max-w-[560px] rounded-[12px] border border-sep bg-white p-5">
            <p className="t-b2 text-ls">支持 .tex、.md 或文本可提取的 .pdf；之后可以继续上传新版本。</p>
            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="np-title" className="mb-1 block t-b2e text-lp">项目/论文标题</label>
                <Input
                  id="np-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如：My retrieval robustness project"
                  className="h-9 rounded-[10px] border-sep t-b2"
                />
              </div>
              <div>
                <label htmlFor="np-q" className="mb-1 block t-b2e text-lp">核心研究问题</label>
                <Textarea
                  id="np-q"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="这个项目希望回答什么？"
                  className="min-h-[72px] rounded-[10px] border-sep t-b2"
                />
              </div>
              <div>
                <span className="mb-1 block t-b2e text-lp">当前文稿</span>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".tex,.md,.pdf"
                  className="hidden"
                  onChange={(e) => setFileName(e.target.files?.[0]?.name ?? '')}
                />
                <div className="flex items-center gap-2">
                  <Button variant="outline" leftIcon={<Upload />} onClick={() => fileRef.current?.click()}>
                    选择文件
                  </Button>
                  <Mono className="truncate t-c1 text-lt">{fileName || '未选择文件（.tex / .md / .pdf）'}</Mono>
                </div>
              </div>
              <Button size={44} className="w-full" onClick={submit}>
                创建项目并提取 Claim
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <footer className="border-t border-sep pt-4 pb-2">
        <p className="t-c1 text-lt">
          <strong className="t-c1e text-ls">工作流程</strong>
          {' '}· 导入/同步文稿 → 确认项目 Claim → 搜索最新公开论文 → 采用有用影响 → 执行实验、数据和写作行动
        </p>
      </footer>
    </div>
  )
}
