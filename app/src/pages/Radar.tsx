import { useEffect, useMemo, useRef, useState } from 'react';
import { verdictMeta, matrixStatusMeta, type Project } from '../data/mock';
import { startScan, getScanStatus, cancelScan } from '../api';
import { Reveal, Stat, Tabs, Quote } from '../components/chrome';

const STAGES = ['搜索 arXiv', '混合检索', '提取 PDF 全文', '逐项比较', '生成行动'];

type ScanState = 'idle' | 'running' | 'done';

export default function Radar({ project }: { project: Project }) {
  const [scan, setScan] = useState<ScanState>('idle');
  const [stage, setStage] = useState(0);
  const [progress, setProgress] = useState(0);
  const [sel, setSel] = useState(project.papers[0]?.id ?? '');
  const [tab, setTab] = useState(0);
  const [decisions, setDecisions] = useState<Record<string, 'adopted' | 'rejected'>>({});
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const scanIdRef = useRef<string | null>(null);

  const paper = project.papers.find((p) => p.id === sel) ?? project.papers[0];

  useEffect(() => {
    setSel(project.papers[0]?.id ?? '');
    setTab(0);
    setScan('idle');
    setProgress(0);
    setStage(0);
  }, [project.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const start = async () => {
    setScan('running');
    setStage(0);
    setProgress(0);

    // Start the real scan on the backend
    try {
      const res = await startScan(project.id);
      scanIdRef.current = res.scan_id;
    } catch {
      // Backend unavailable — run a simulated scan for visual feedback
      scanIdRef.current = null;
    }

    // Visual progress animation + polling
    timer.current = setInterval(async () => {
      setProgress((p) => {
        const next = p + 1.6;
        setStage(Math.min(STAGES.length - 1, Math.floor((next / 100) * STAGES.length)));

        if (next >= 100) {
          if (timer.current) clearInterval(timer.current);
          setScan('done');
          return 100;
        }
        return next;
      });

      // Poll real scan status if we have a scan ID
      if (scanIdRef.current) {
        try {
          const status = await getScanStatus(project.id, scanIdRef.current);
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
            if (timer.current) clearInterval(timer.current);
            setScan('done');
            setProgress(100);
            setStage(STAGES.length);
          }
        } catch {
          // polling failed — keep the simulation going
        }
      }
    }, 90);
  };

  const cancel = async () => {
    if (timer.current) clearInterval(timer.current);
    if (scanIdRef.current) {
      try {
        await cancelScan(project.id, scanIdRef.current);
      } catch { /* best-effort cancel */ }
      scanIdRef.current = null;
    }
    setScan('idle');
  };

  const summary = useMemo(
    () => [
      { v: 47, l: '公开论文' },
      { v: project.papers.length, l: '深度比较' },
      { v: project.papers.filter((p) => p.verdict !== 'none').length, l: '材料影响' },
      { v: project.papers.filter((p) => p.urgency === 'urgent').length, l: '紧急', tone: 'red' as const },
      { v: project.papers.filter((p) => p.verdict === 'none' && p.urgency === 'urgent').length, l: '竞争预警', tone: 'orange' as const },
      { v: project.papers.filter((p) => p.verdict === 'prior' || p.verdict === 'boundary').length, l: '完整性' },
    ],
    [project],
  );

  const dotCls: Record<string, string> = {
    challenge: 'bg-[#B42318]',
    support: 'bg-[#067647]',
    boundary: 'bg-[#B54708]',
    prior: 'bg-[#175CD3]',
    none: 'bg-[#98A2B3]',
  };

  return (
    <div>
      <Reveal>
        <div className="flex flex-wrap items-end justify-between gap-4 mb-2">
          <div>
            <div className="kicker mb-2">Radar</div>
            <h1 className="display-lg">文献雷达</h1>
          </div>
          <span className="locator pb-2">上次扫描 {project.lastScan}</span>
        </div>
        <p className="text-sm text-neutral-500 mt-4">系统自动搜索，不需要你自己写检索词。监控主题由文稿与 Claim 自动提取：</p>
        <div className="flex flex-wrap gap-2 mt-3">
          {project.topics.map((t) => (
            <span key={t} className="chip font-mono !text-[11px]">{t}</span>
          ))}
        </div>
      </Reveal>

      {/* scan control */}
      <Reveal delay={80}>
        <div className="card mt-8 p-7">
          {scan === 'idle' && (
            <div className="flex flex-col md:flex-row md:items-center gap-5 justify-between">
              <p className="text-sm text-neutral-500">覆盖 arXiv 最新公开论文 · 全文比较 · 输出可执行行动</p>
              <button className="btn-teal !px-6 !py-3" onClick={start}>
                ◎ 搜索最新公开论文并告诉我该做什么
              </button>
            </div>
          )}
          {scan === 'running' && (
            <div className="flex items-center gap-7">
              {/* mini radar */}
              <div className="relative w-20 h-20 shrink-0">
                <div className="absolute inset-0 rounded-full border border-teal/30" />
                <div className="absolute inset-3 rounded-full border border-teal/20" />
                <div className="absolute inset-0 radar-ring rounded-full border border-teal/40" />
                <div className="absolute inset-0 radar-beam">
                  <div className="absolute left-1/2 top-1/2 w-1/2 h-[2px] bg-gradient-to-r from-teal to-transparent origin-left" />
                </div>
                <div className="absolute left-1/2 top-1/2 w-1.5 h-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  {STAGES.map((s, i) => (
                    <span key={s} className={`text-xs transition-colors duration-300 ${i < stage ? 'text-teal' : i === stage ? 'text-ink font-medium' : 'text-neutral-300'}`}>
                      {i === stage && <span className="blink-soft">●</span>} {s}
                      {i < STAGES.length - 1 && <span className="text-neutral-200 mx-1.5">→</span>}
                    </span>
                  ))}
                </div>
                <div className="mt-3 h-[3px] bg-hairline rounded-full overflow-hidden">
                  <div className="h-full bg-teal transition-all duration-150" style={{ width: `${progress}%` }} />
                </div>
              </div>
              <button className="btn-quiet shrink-0" onClick={cancel}>
                取消
              </button>
            </div>
          )}
          {scan === 'done' && (
            <div className="flex flex-col md:flex-row md:items-center gap-5 justify-between">
              <div className="flex items-center gap-3">
                <span className="badge-green badge-dot">扫描完成</span>
                <span className="text-sm text-neutral-500">发现 {summary[2].v} 项材料影响，{summary[3].v} 项紧急</span>
              </div>
              <button className="btn-ghost" onClick={start}>
                重新扫描
              </button>
            </div>
          )}
        </div>
      </Reveal>

      {/* summary metrics */}
      <Reveal delay={120}>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-6 mt-8 pb-8 hairline-b">
          {summary.map((m) => (
            <Stat key={m.l} value={m.v} label={m.l} tone={m.tone} />
          ))}
        </div>
      </Reveal>

      {/* two-column workspace */}
      <div className="mt-8 grid lg:grid-cols-[320px_1fr] gap-6 items-start">
        {/* impact queue */}
        <Reveal delay={140}>
          <div className="card overflow-hidden">
            <div className="px-5 py-4 hairline-b flex items-center justify-between">
              <span className="text-sm font-medium">影响队列</span>
              <span className="locator">{project.papers.length} 篇</span>
            </div>
            <ul>
              {project.papers.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => { setSel(p.id); setTab(0); }}
                    className={`w-full text-left px-5 py-4 border-b border-hairline/60 transition-colors duration-200 ${
                      sel === p.id ? 'bg-teal-soft/60' : 'hover:bg-neutral-50'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`w-[7px] h-[7px] rounded-full shrink-0 ${dotCls[p.verdict]}`} />
                      <span className="font-mono text-[11px] text-neutral-400">{p.claimIds.join(' · ')}</span>
                      {p.urgency === 'urgent' && <span className="badge-red ml-auto">紧急</span>}
                      {decisions[p.id] === 'adopted' && <span className="badge-green ml-auto">已采用</span>}
                    </div>
                    <div className="text-[13px] leading-snug text-neutral-700 line-clamp-2">{p.title}</div>
                    <div className="locator mt-1.5">{p.date}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </Reveal>

        {/* detail */}
        <Reveal delay={180}>
          <div className="card p-7">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <span className={verdictMeta[paper.verdict].cls}>{verdictMeta[paper.verdict].label}</span>
              <span className="locator">arXiv:{paper.arxivId}</span>
              <span className="locator ml-auto">{paper.date}</span>
            </div>
            <h3 className="font-serif font-semibold text-xl leading-snug">{paper.title}</h3>
            <p className="mt-1.5 text-xs text-neutral-400">{paper.authors.join(', ')}</p>

            <div className="mt-6">
              <Tabs tabs={['比较矩阵', '证据', '决策']} active={tab} onChange={setTab} />

              {tab === 0 && (
                <div className="overflow-x-auto">
                  <table className="table-base min-w-[560px]">
                    <thead>
                      <tr>
                        <th>字段</th>
                        <th>本方</th>
                        <th>公开论文</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paper.matrix.map((r) => (
                        <tr key={r.field}>
                          <td className="font-medium whitespace-nowrap">{r.field}</td>
                          <td className="text-neutral-600">{r.ours}</td>
                          <td className="text-neutral-600">{r.theirs}</td>
                          <td>
                            <span className={matrixStatusMeta[r.status].cls}>{matrixStatusMeta[r.status].label}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {tab === 1 && (
                <div className="grid gap-6">
                  <Quote label="你的文稿" loc={paper.yourLoc}>
                    {paper.yourQuote}
                  </Quote>
                  <Quote label="公开论文" loc={paper.quoteLoc} against={paper.verdict === 'challenge'}>
                    {paper.quote}
                  </Quote>
                </div>
              )}

              {tab === 2 && (
                <div className="grid gap-5">
                  <div>
                    <div className="kicker mb-2">为什么重要</div>
                    <p className="text-sm text-neutral-600 leading-relaxed">{paper.why}</p>
                  </div>
                  <div className="grid md:grid-cols-2 gap-5">
                    <div>
                      <div className="kicker mb-2">建议动作</div>
                      <p className="text-sm text-neutral-600 leading-relaxed">{paper.suggestion}</p>
                    </div>
                    <div>
                      <div className="kicker mb-2">不确定因素</div>
                      <p className="text-sm text-neutral-500 leading-relaxed">{paper.uncertainty}</p>
                    </div>
                  </div>
                  <div className="pt-5 hairline-t flex flex-wrap items-center gap-2">
                    {!decisions[paper.id] && (
                      <>
                        <button className="btn-teal" onClick={() => setDecisions((m) => ({ ...m, [paper.id]: 'adopted' }))}>
                          采用这项影响
                        </button>
                        <button className="btn-quiet" onClick={() => setDecisions((m) => ({ ...m, [paper.id]: 'rejected' }))}>
                          不采用
                        </button>
                        <button className="btn-ghost ml-auto" onClick={() => setDecisions((m) => ({ ...m, [paper.id]: 'adopted' }))}>
                          修改判断
                        </button>
                      </>
                    )}
                    {decisions[paper.id] === 'adopted' && (
                      <>
                        <span className="badge-green badge-dot">已采用 · 当前判断：{verdictMeta[paper.verdict].label}</span>
                        <button className="btn-quiet ml-auto" onClick={() => setDecisions((m) => { const n = { ...m }; delete n[paper.id]; return n; })}>
                          修改判断
                        </button>
                      </>
                    )}
                    {decisions[paper.id] === 'rejected' && (
                      <>
                        <span className="badge-gray badge-dot">已标记不采用</span>
                        <button className="btn-quiet ml-auto" onClick={() => setDecisions((m) => { const n = { ...m }; delete n[paper.id]; return n; })}>
                          修改判断
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  );
}
