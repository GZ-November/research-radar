import { useState, useRef } from 'react';
import { projects, type Project } from '../data/mock';
import { getCases, createCase, useApi, type CaseSummary } from '../api';
import { Reveal, SectionHead } from '../components/chrome';

const FLOW = ['导入 / 同步文稿', '确认项目 Claim', '搜索最新公开论文', '采用有用影响', '执行实验、数据与写作行动'];

export default function Dashboard({ project, onOpen }: { project: Project; onOpen: () => void }) {
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle');
  const [fileName, setFileName] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Try loading case list from API; fall back to mock
  const { data: apiCases } = useApi<CaseSummary[]>(() => getCases(), []);
  const displayCases: CaseSummary[] = apiCases ?? projects.map((p) => ({
    id: p.id,
    name: p.name,
    short: p.short,
    question: p.question,
    version: p.version,
    file: p.file,
    claimsConfirmed: p.claimsConfirmed,
    claimsTotal: p.claimsTotal,
    lastScan: p.lastScan,
    urgent: p.urgent,
    topics: p.topics,
  }));

  const handleCreate = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const titleInput = form.elements.namedItem('title') as HTMLInputElement;
    const questionInput = form.elements.namedItem('question') as HTMLTextAreaElement;
    const fileInput = fileRef.current;

    if (!titleInput.value.trim() || !fileInput?.files?.[0]) return;

    setCreated('submitting');
    try {
      await createCase(titleInput.value.trim(), questionInput.value.trim(), fileInput.files[0]);
      setCreated('done');
      // Reload cases list after a short delay
      setTimeout(() => window.location.reload(), 1500);
    } catch {
      setCreated('error');
    }
  };

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">Projects</div>
        <h1 className="display-lg mb-10">项目工作台</h1>
      </Reveal>

      {/* project cards */}
      <div className="grid md:grid-cols-2 gap-5">
        {displayCases.map((p, i) => (
          <Reveal key={p.id} delay={i * 90}>
            <article className={`card card-hover p-7 ${p.id === project.id ? 'ring-1 ring-teal/40' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-serif font-semibold text-xl leading-snug">{p.name}</h3>
                <span className="locator shrink-0 mt-1">{p.version}</span>
              </div>
              <p className="mt-3 text-sm text-neutral-500 leading-relaxed">{p.question}</p>
              <div className="mt-6 flex items-center gap-8">
                <div>
                  <div className="font-serif font-semibold text-2xl tabular">
                    {p.claimsConfirmed}
                    <span className="text-neutral-300 text-lg">/{p.claimsTotal}</span>
                  </div>
                  <div className="text-xs text-neutral-400 mt-1">已确认 Claim</div>
                </div>
                <div>
                  <div className={`font-serif font-semibold text-2xl tabular ${p.urgent ? 'text-[#B42318]' : ''}`}>{p.urgent}</div>
                  <div className="text-xs text-neutral-400 mt-1">紧急影响</div>
                </div>
                <div className="min-w-0">
                  <div className="locator truncate">{p.lastScan}</div>
                  <div className="text-xs text-neutral-400 mt-1">最近扫描</div>
                </div>
              </div>
              <div className="mt-7 pt-5 hairline-t flex items-center justify-between">
                <span className="locator">{p.file}</span>
                <button className="btn-dark" onClick={onOpen}>
                  打开项目
                </button>
              </div>
            </article>
          </Reveal>
        ))}
      </div>

      {/* new project */}
      <Reveal delay={120} className="mt-10">
        <SectionHead
          kicker="New"
          title="新建项目"
          right={
            <button className="btn-ghost" onClick={() => setShowForm((s) => !s)}>
              {showForm ? '收起' : '＋ 新建项目'}
            </button>
          }
        />
        {showForm && (
          <form
            className="card p-7 grid gap-5"
            onSubmit={handleCreate}
          >
            <div className="grid md:grid-cols-2 gap-5">
              <label className="block">
                <span className="text-xs text-neutral-500 tracking-wide">项目标题</span>
                <input name="title" className="input mt-1.5" placeholder="例如：Tool-R1 工具调用强化学习" />
              </label>
              <label className="block">
                <span className="text-xs text-neutral-500 tracking-wide">上传文稿</span>
                <label className="input mt-1.5 flex items-center justify-between cursor-pointer text-neutral-400">
                  <span className="truncate">{fileName || '.tex / .md / .pdf'}</span>
                  <span className="locator">浏览</span>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".tex,.md,.pdf"
                    className="hidden"
                    onChange={(e) => setFileName(e.target.files?.[0]?.name ?? '')}
                  />
                </label>
              </label>
            </div>
            <label className="block">
              <span className="text-xs text-neutral-500 tracking-wide">核心研究问题</span>
              <textarea name="question" className="input mt-1.5 h-20 resize-none" placeholder="一句话说明这个项目要回答什么" />
            </label>
            <div className="flex items-center gap-4">
              <button type="submit" className="btn-teal" disabled={created === 'submitting'}>
                {created === 'submitting' ? '创建中…' : '创建项目并提取 Claim'}
              </button>
              {created === 'done' && <span className="badge-green badge-dot">已创建 · Claim 提取任务已排队</span>}
              {created === 'error' && <span className="badge-red badge-dot">创建失败，请重试</span>}
            </div>
          </form>
        )}
      </Reveal>

      {/* workflow footer */}
      <Reveal delay={160} className="mt-16">
        <div className="hairline-t pt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
          {FLOW.map((f, i) => (
            <div key={f} className="flex items-center gap-6">
              <div className="flex items-center gap-2.5">
                <span className="font-serif italic text-neutral-300 text-lg">{String(i + 1).padStart(2, '0')}</span>
                <span className="text-sm text-neutral-500">{f}</span>
              </div>
              {i < FLOW.length - 1 && <span className="text-neutral-300 hidden md:inline">→</span>}
            </div>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
