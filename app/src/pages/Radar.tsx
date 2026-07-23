import { useEffect, useMemo, useRef, useState } from 'react';
import { verdictMeta, matrixStatusMeta } from '../data/mock';
import {
  startScan,
  getScanStatus,
  cancelScan,
  confirmImpact,
  dismissImpact,
  getSettings,
  useApi,
} from '../api';
import { useProject } from '../contexts/ProjectContext';
import { Reveal, Stat, Tabs, Quote } from '../components/chrome';
import { Spinner } from '../components/ui/spinner';

const STAGES = ['搜索 arXiv', '混合检索', '提取 PDF 全文', '逐项比较', '生成行动'];

type ScanState = 'idle' | 'running' | 'done' | 'failed';

export default function Radar() {
  const { project, loading, error, refreshProject } = useProject();
  const [scan, setScan] = useState<ScanState>('idle');
  const [stage, setStage] = useState(0);
  const [progress, setProgress] = useState(0);
  const [sel, setSel] = useState(() => project?.papers[0]?.id ?? '');
  const [tab, setTab] = useState(0);
  const [decisions, setDecisions] = useState<Record<string, 'adopted' | 'rejected'>>(
    () => Object.fromEntries(
      (project?.papers ?? [])
        .filter((item) => item.reviewState === 'confirmed' || item.reviewState === 'dismissed')
        .map((item) => [item.id, item.reviewState === 'confirmed' ? 'adopted' : 'rejected']),
    ),
  );
  const [scanMessage, setScanMessage] = useState('');
  const [decisionError, setDecisionError] = useState('');
  const [savingDecision, setSavingDecision] = useState('');
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const scanIdRef = useRef<string | null>(null);

  // Scan configuration
  const [showConfig, setShowConfig] = useState(false);
  const [maxResults, setMaxResults] = useState(32);
  const [analysisLimit, setAnalysisLimit] = useState(3);
  const { data: settings } = useApi(() => getSettings(), []);

  const papers = useMemo(() => project?.papers ?? [], [project?.papers]);
  const paper = papers.find((p) => p.id === sel) ?? papers[0];

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const stopPolling = () => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };

  const poll = async (caseId: string, scanId: string) => {
    try {
      const status = await getScanStatus(caseId, scanId);
      const nextProgress = Math.max(0, Math.min(100, (status.progress.value ?? 0) * 100));
      setProgress(nextProgress);
      setStage(Math.min(STAGES.length - 1, Math.floor((nextProgress / 100) * STAGES.length)));
      setScanMessage(status.progress.message ?? '');

      if (status.status === 'completed') {
        stopPolling();
        setScan('done');
        setProgress(100);
        setStage(STAGES.length);
        await refreshProject();
      } else if (status.status === 'failed' || status.status === 'interrupted') {
        stopPolling();
        setScan('failed');
        setScanMessage(status.error_message || status.progress.message || '扫描失败');
      } else if (status.status === 'cancelled') {
        stopPolling();
        setScan('idle');
        setScanMessage('扫描已取消。');
        await refreshProject();
      }
    } catch (e) {
      stopPolling();
      setScan('failed');
      setScanMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const start = async () => {
    if (!project) return;
    stopPolling();
    setScan('running');
    setStage(0);
    setProgress(0);
    setScanMessage('正在启动扫描…');

    try {
      const res = await startScan(project.id, maxResults, analysisLimit);
      scanIdRef.current = res.scan_id;
      timer.current = setInterval(() => {
        void poll(project.id, res.scan_id);
      }, 1000);
      void poll(project.id, res.scan_id);
    } catch (e) {
      scanIdRef.current = null;
      setScan('failed');
      setScanMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const cancel = async () => {
    if (!project) return;
    stopPolling();
    if (scanIdRef.current) {
      try {
        await cancelScan(project.id, scanIdRef.current);
      } catch { /* best-effort */ }
      scanIdRef.current = null;
    }
    setScan('idle');
  };

  const decide = async (paperId: string, decision: 'adopted' | 'rejected') => {
    if (!project) return;
    setSavingDecision(paperId);
    setDecisionError('');
    try {
      if (decision === 'adopted') {
        await confirmImpact(project.id, paperId);
      } else {
        await dismissImpact(project.id, paperId);
      }
      setDecisions((current) => ({ ...current, [paperId]: decision }));
      await refreshProject();
    } catch (e) {
      setDecisionError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingDecision('');
    }
  };

  const summary = useMemo(
    () => [
      { v: 47, l: '公开论文' },
      { v: papers.length, l: '深度比较' },
      { v: papers.filter((p) => p.verdict !== 'none').length, l: '材料影响' },
      { v: papers.filter((p) => p.urgency === 'urgent').length, l: '紧急', tone: 'red' as const },
      { v: papers.filter((p) => p.verdict === 'none' && p.urgency === 'urgent').length, l: '竞争预警', tone: 'orange' as const },
      { v: papers.filter((p) => p.verdict === 'prior' || p.verdict === 'boundary').length, l: '完整性' },
    ],
    [papers],
  );

  const dotCls: Record<string, string> = {
    challenge: 'bg-[#B42318]',
    support: 'bg-[#067647]',
    boundary: 'bg-[#B54708]',
    prior: 'bg-[#175CD3]',
    none: 'bg-[#98A2B3]',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="size-8 text-neutral-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 text-sm">加载失败: {error.message}</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="card p-8 text-center">
        <p className="text-neutral-400 text-sm">未找到项目</p>
      </div>
    );
  }

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

      {/* scan control with config */}
      <Reveal delay={80}>
        <div className="card mt-8 p-7">
          {scan === 'idle' && (
            <div>
              <div className="flex flex-col md:flex-row md:items-center gap-5 justify-between">
                <p className="text-sm text-neutral-500">覆盖 arXiv 最新公开论文 · 全文比较 · 输出可执行行动</p>
                <div className="flex items-center gap-2">
                  <button
                    className="btn-ghost text-xs"
                    onClick={() => setShowConfig((s) => !s)}
                  >
                    {showConfig ? '收起配置' : '⚙ 搜索配置'}
                  </button>
                  <button className="btn-teal !px-6 !py-3" onClick={start}>
                    ◎ 搜索最新公开论文并告诉我该做什么
                  </button>
                </div>
              </div>

              {/* Config panel */}
              {showConfig && (
                <div className="mt-5 pt-5 hairline-t grid md:grid-cols-2 gap-4">
                  <label className="block">
                    <span className="text-xs text-neutral-500">搜索篇数上限</span>
                    <select
                      className="input mt-1.5"
                      value={maxResults}
                      onChange={(e) => setMaxResults(Number(e.target.value))}
                    >
                      <option value={16}>16 篇</option>
                      <option value={32}>32 篇</option>
                      <option value={50}>50 篇</option>
                      <option value={100}>100 篇</option>
                    </select>
                    <span className="text-[10px] text-neutral-400 mt-0.5 block">arXiv / OpenAlex 搜索结果上限</span>
                  </label>
                  <label className="block">
                    <span className="text-xs text-neutral-500">深度分析篇数</span>
                    <select
                      className="input mt-1.5"
                      value={analysisLimit}
                      onChange={(e) => setAnalysisLimit(Number(e.target.value))}
                    >
                      <option value={1}>1 篇</option>
                      <option value={3}>3 篇</option>
                      <option value={5}>5 篇</option>
                      <option value={7}>7 篇</option>
                      <option value={10}>10 篇</option>
                    </select>
                    <span className="text-[10px] text-neutral-400 mt-0.5 block">LLM 逐项比较与行动建议篇数</span>
                  </label>
                  <div className="md:col-span-2 text-xs text-neutral-400">
                    本次使用：{settings?.llm.model ?? '未配置模型'}。
                    模型切换统一在设置页完成，避免把其他提供商的模型名发送到当前接口。
                  </div>
                </div>
              )}
            </div>
          )}
          {scan === 'running' && (
            <div className="flex items-center gap-7">
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
                {scanMessage && <p className="mt-2 text-xs text-neutral-400">{scanMessage}</p>}
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
          {scan === 'failed' && (
            <div className="flex flex-col md:flex-row md:items-center gap-4 justify-between">
              <div>
                <span className="badge-red badge-dot">扫描失败</span>
                <p className="mt-2 text-xs text-red-700 break-words">{scanMessage}</p>
              </div>
              <button className="btn-ghost" onClick={() => setScan('idle')}>修改配置后重试</button>
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
              <span className="locator">{papers.length} 篇</span>
            </div>
            <ul>
              {papers.map((p) => (
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
        {paper && (
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
                          <button
                            className="btn-teal"
                            disabled={savingDecision === paper.id}
                            onClick={() => void decide(paper.id, 'adopted')}
                          >
                            {savingDecision === paper.id ? '保存中…' : '采用这项影响'}
                          </button>
                          <button
                            className="btn-quiet"
                            disabled={savingDecision === paper.id}
                            onClick={() => void decide(paper.id, 'rejected')}
                          >
                            不采用
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
                      {decisionError && <span className="text-xs text-red-600">{decisionError}</span>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </Reveal>
        )}
      </div>
    </div>
  );
}
