import { useState, useRef } from 'react';
import { useProject } from '../contexts/ProjectContext';
import { createCase, deleteCase } from '../api';
import { Reveal, SectionHead } from '../components/chrome';

const FLOW = ['导入 / 同步文稿', '确认项目 Claim', '搜索最新公开论文', '采用有用影响', '执行实验、数据与写作行动'];

export default function HomeView({ onSelectProject }: { onSelectProject: (id: string) => Promise<void> }) {
  const { caseList, refreshCaseList, loading, error } = useProject();
  const [showForm, setShowForm] = useState(false);
  const [created, setCreated] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle');
  const [fileName, setFileName] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [operationError, setOperationError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleCreate = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const titleInput = form.elements.namedItem('title') as HTMLInputElement;
    const questionInput = form.elements.namedItem('question') as HTMLTextAreaElement;
    const fileInput = fileRef.current;

    if (!titleInput.value.trim() || !fileInput?.files?.[0]) return;

    setCreated('submitting');
    setOperationError('');
    try {
      await createCase(titleInput.value.trim(), questionInput.value.trim(), fileInput.files[0]);
      setCreated('done');
      await refreshCaseList();
      form.reset();
      setFileName('');
      setShowForm(false);
      setTimeout(() => setCreated('idle'), 2000);
    } catch (e) {
      setCreated('error');
      setOperationError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定要删除项目「${name}」吗？此操作不可撤销。`)) return;
    setDeleting(id);
    setOperationError('');
    try {
      await deleteCase(id);
      await refreshCaseList();
    } catch (e) {
      setOperationError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">Projects</div>
        <h1 className="display-lg mb-2">项目工作台</h1>
        <p className="text-sm text-neutral-500 mb-10">每个项目对应一篇论文，独立管理 Claim、文献扫描和行动项</p>
      </Reveal>

      {/* project cards */}
      {loading && caseList.length === 0 && (
        <div className="card p-10 text-center">
          <p className="text-neutral-400 text-sm">正在加载项目…</p>
        </div>
      )}
      {(error || operationError) && (
        <div className="mb-5 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {operationError || error?.message}
        </div>
      )}
      {caseList.length === 0 && (
        <div className={`card p-10 text-center ${loading ? 'hidden' : ''}`}>
          <p className="text-neutral-400 text-sm">暂无项目，点击下方按钮创建第一个项目</p>
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-5">
        {caseList.map((p, i) => (
          <Reveal key={p.id} delay={i * 90}>
            <article className="card card-hover p-7">
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
                  <div className={`font-serif font-semibold text-2xl tabular ${p.urgent ? 'text-[#B42318]' : ''}`}>
                    {p.urgent}
                  </div>
                  <div className="text-xs text-neutral-400 mt-1">紧急影响</div>
                </div>
                <div className="min-w-0">
                  <div className="locator truncate">{p.lastScan}</div>
                  <div className="text-xs text-neutral-400 mt-1">最近扫描</div>
                </div>
              </div>
              {/* topics */}
              {p.topics.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {p.topics.slice(0, 4).map((t) => (
                    <span key={t} className="chip font-mono !text-[10px]">{t}</span>
                  ))}
                  {p.topics.length > 4 && (
                    <span className="text-[10px] text-neutral-400">+{p.topics.length - 4}</span>
                  )}
                </div>
              )}
              <div className="mt-7 pt-5 hairline-t flex items-center justify-between">
                <span className="locator">{p.file}</span>
                <div className="flex items-center gap-2">
                  <button
                    className="btn-quiet !text-xs"
                    onClick={() => handleDelete(p.id, p.name)}
                    disabled={deleting === p.id}
                  >
                    {deleting === p.id ? '删除中…' : '删除'}
                  </button>
                  <button className="btn-dark" onClick={() => void onSelectProject(p.id)}>
                    进入项目
                  </button>
                </div>
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
          <form className="card p-7 grid gap-5" onSubmit={handleCreate}>
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
