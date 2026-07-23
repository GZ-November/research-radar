import { useMemo, useState } from 'react';
import { verdictMeta, claimStatusMeta, kindMeta, matrixStatusMeta } from '../data/mock';
import { Reveal, Stat, Tabs, Quote, Priority, Empty } from '../components/chrome';
import { Spinner } from '../components/ui/spinner';
import { useProjectId } from '../contexts/ProjectContext';
import {
  getActions,
  getImpacts,
  getClaims,
  confirmImpact,
  dismissImpact,
  updateActionStatus,
  useApi,
} from '../api';

type ActionState = 'todo' | 'doing' | 'done' | 'dismissed';

function persistedActionState(status: string | undefined): ActionState {
  if (status === 'in_progress') return 'doing';
  if (status === 'done') return 'done';
  if (status === 'dismissed') return 'dismissed';
  return 'todo';
}

export default function Actions() {
  const caseId = useProjectId();
  // ---- data fetching ----
  const { data: actions, loading: actionsLoading, refetch: refetchActions } = useApi(
    () => getActions(caseId),
    [caseId],
  );
  const { data: papers, loading: papersLoading, refetch: refetchImpacts } = useApi(
    () => getImpacts(caseId),
    [caseId],
  );
  const { data: claims, loading: claimsLoading } = useApi(
    () => getClaims(caseId),
    [caseId],
  );

  const loading = actionsLoading || papersLoading || claimsLoading;

  // ---- local UI state ----
  const [tab, setTab] = useState(0);
  const [states, setStates] = useState<Record<string, ActionState>>({});
  const [decisions, setDecisions] = useState<Record<string, 'adopted' | 'rejected'>>({});
  const [expandedActionId, setExpandedActionId] = useState<string | null>(null);
  const [expandedImpactId, setExpandedImpactId] = useState<string | null>(null);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);
  const [operationError, setOperationError] = useState('');

  // ---- derived ----
  const p0 = useMemo(() => {
    if (!actions) return undefined;
    return actions.find(
      (a) =>
        a.priority === 'P0'
        && (states[a.id] ?? persistedActionState(a.status)) !== 'done',
    );
  }, [actions, states]);

  const useful = (papers ?? []).filter((p) => p.verdict !== 'none');
  const affected = (claims ?? []).filter((c) => c.status === 'disputed' || c.status === 'revalidate');

  const setA = (id: string, s: ActionState) => setStates((m) => ({ ...m, [id]: s }));

  const persistAction = async (
    id: string,
    previous: ActionState,
    next: ActionState,
    apiStatus: string,
  ) => {
    setOperationError('');
    setA(id, next);
    try {
      await updateActionStatus(caseId, id, apiStatus);
      refetchActions();
    } catch (e) {
      setA(id, previous);
      setOperationError(e instanceof Error ? e.message : String(e));
    }
  };

  const persistImpact = async (id: string, decision: 'adopted' | 'rejected') => {
    setOperationError('');
    try {
      if (decision === 'adopted') await confirmImpact(caseId, id);
      else await dismissImpact(caseId, id);
      setDecisions((current) => ({ ...current, [id]: decision }));
      refetchImpacts();
    } catch (e) {
      setOperationError(e instanceof Error ? e.message : String(e));
    }
  };

  // ---- metrics (computed from loaded actions) ----
  const list = actions ?? [];
  const metrics = [
    { v: list.filter((a) => a.priority === 'P0').length, l: '紧急', tone: 'red' as const },
    { v: list.filter((a) => a.kind === 'experiment').length, l: '改实验' },
    { v: list.filter((a) => a.kind === 'data').length, l: '补数据' },
    { v: list.filter((a) => a.kind === 'writing').length, l: '调整写作' },
    { v: list.filter((a) => a.kind === 'competitive').length, l: '竞争预警', tone: 'orange' as const },
    { v: list.filter((a) => a.kind === 'revalidate').length, l: '重新验证' },
  ];

  // ---- helpers ----
  const scrollTo = (id: string) => {
    setTimeout(() => {
      document.getElementById(`action-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
  };

  const findPaper = (id: string) => (papers ?? []).find((p) => p.id === id);

  // ---- loading state ----
  if (loading) {
    return (
      <div>
        <Reveal>
          <div className="kicker mb-2">This Week</div>
          <h1 className="display-lg mb-8">本周行动</h1>
        </Reveal>
        <div className="flex items-center justify-center py-20">
          <Spinner className="size-8 text-neutral-400" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">This Week</div>
        <h1 className="display-lg mb-8">本周行动</h1>
      </Reveal>

      {/* headline banner */}
      <Reveal delay={60}>
        <div className="rounded-lg bg-night text-white p-7 md:p-9 flex flex-col md:flex-row md:items-center gap-6 justify-between">
          <div>
            <div className="kicker !text-cyan-200/60 mb-3">需要马上处理</div>
            <p className="font-serif text-xl md:text-2xl leading-snug max-w-2xl">
              {p0 ? p0.title : '本周没有 P0 事项，保持监控即可。'}
            </p>
          </div>
          {p0 && (
            <button
              className="btn-teal shrink-0"
              onClick={() => {
                setExpandedActionId(p0.id);
                setTab(0);
                scrollTo(p0.id);
              }}
            >
              查看执行清单
            </button>
          )}
        </div>
      </Reveal>

      {/* metrics */}
      <Reveal delay={100}>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-6 mt-10 pb-8 hairline-b">
          {metrics.map((m) => (
            <Stat key={m.l} value={m.v} label={m.l} tone={m.tone} />
          ))}
        </div>
      </Reveal>

      <div className="mt-8">
        {operationError && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {operationError}
          </div>
        )}
        <Tabs tabs={['你要做什么', '文献判断', '受影响的主张']} active={tab} onChange={setTab} />

        {/* tab 0 — actions */}
        {tab === 0 && (
          <div className="grid gap-4">
            {list.length === 0 && <Empty text="暂无扫描结果，去文献雷达搜一下" />}
            {list.map((a, i) => {
              const st = states[a.id] ?? persistedActionState(a.status);
              const src = findPaper(a.sourcePaperId);
              const isExpanded = expandedActionId === a.id;
              if (st === 'dismissed') return null;
              return (
                <Reveal key={a.id} delay={i * 60}>
                  <article id={`action-${a.id}`} className={`card p-6 ${st === 'done' ? 'opacity-55' : ''}`}>
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <Priority p={a.priority} />
                      <span className="badge-gray">{kindMeta[a.kind]}</span>
                      <span className="locator">建议期限 · {a.due}</span>
                      <span className="locator ml-auto">{a.claimId}</span>
                    </div>
                    <h3 className={`font-medium text-[15px] leading-relaxed ${st === 'done' ? 'line-through' : ''}`}>
                      {a.title}
                    </h3>
                    {a.reason && (
                      <p className="mt-2 text-[13px] text-neutral-500 leading-relaxed">{a.reason}</p>
                    )}
                    {src && (
                      <p className="mt-2 text-xs text-neutral-400">
                        触发来源：<span className="font-mono">arXiv:{src.arxivId}</span> · {src.title.slice(0, 64)}…
                      </p>
                    )}
                    {isExpanded && (
                      <ul className="mt-4 grid md:grid-cols-2 gap-x-8 gap-y-1.5">
                        {a.checklist.map((c) => (
                          <li key={c} className="text-[13px] text-neutral-500 flex gap-2">
                            <span className={st === 'done' ? 'text-teal' : 'text-neutral-300'}>
                              {st === 'done' ? '✓' : '□'}
                            </span>
                            {c}
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="mt-5 pt-4 hairline-t flex flex-wrap gap-2">
                      {st === 'todo' && (
                        <button
                          className="btn-dark"
                          onClick={() => void persistAction(a.id, st, 'doing', 'in_progress')}
                        >
                          开始
                        </button>
                      )}
                      {st !== 'done' && (
                        <button
                          className="btn-teal"
                          onClick={() => void persistAction(a.id, st, 'done', 'done')}
                        >
                          完成
                        </button>
                      )}
                      {st !== 'done' && (
                        <button
                          className="btn-quiet"
                          onClick={() => void persistAction(a.id, st, 'dismissed', 'dismissed')}
                        >
                          不处理
                        </button>
                      )}
                      {st === 'done' && <span className="badge-green badge-dot">已完成</span>}
                    </div>
                  </article>
                </Reveal>
              );
            })}
          </div>
        )}

        {/* tab 1 — 文献判断 (merged papers + evidence) */}
        {tab === 1 && (
          <div className="grid gap-4">
            {useful.length === 0 && <Empty text="暂无文献判断结果" />}
            {useful.map((p, i) => {
              const d = decisions[p.id]
                ?? (p.reviewState === 'confirmed'
                  ? 'adopted'
                  : p.reviewState === 'dismissed'
                    ? 'rejected'
                    : undefined);
              const isExpanded = expandedImpactId === p.id;
              return (
                <Reveal key={p.id} delay={i * 60}>
                  <article className="card p-6">
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <span className={verdictMeta[p.verdict].cls}>{verdictMeta[p.verdict].label}</span>
                      <span className="locator">arXiv:{p.arxivId} · {p.date}</span>
                      <span className="locator ml-auto">{p.claimIds.join(' · ')}</span>
                    </div>
                    <button
                      className="text-left w-full"
                      onClick={() =>
                        setExpandedImpactId((prev) => (prev === p.id ? null : p.id))
                      }
                    >
                      <h3 className="font-medium text-[15px] leading-relaxed hover:text-teal transition-colors">
                        {p.title}
                      </h3>
                    </button>
                    <p className="mt-1 text-xs text-neutral-400">{p.authors.join(', ')}</p>
                    <div className="mt-4">
                      <Quote loc={p.quoteLoc} against={p.verdict === 'challenge'} label="证据引文">
                        {p.quote}
                      </Quote>
                    </div>

                    {/* expand/collapse section */}
                    {isExpanded && (
                      <div className="mt-5 pt-5 hairline-t">
                        {/* matrix table */}
                        {p.matrix.length > 0 && (
                          <div className="mb-5">
                            <div className="locator mb-2 uppercase">条件对比</div>
                            <div className="overflow-x-auto">
                              <table className="table-base min-w-[500px] text-[13px]">
                                <thead>
                                  <tr>
                                    <th>维度</th>
                                    <th>我们的</th>
                                    <th>他们的</th>
                                    <th>状态</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.matrix.map((row) => (
                                    <tr key={row.field}>
                                      <td className="text-neutral-600">{row.field}</td>
                                      <td className="text-neutral-600">{row.ours}</td>
                                      <td className="text-neutral-600">{row.theirs}</td>
                                      <td>
                                        <span className={matrixStatusMeta[row.status].cls}>
                                          {matrixStatusMeta[row.status].label}
                                        </span>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {p.why && (
                          <div className="mb-3">
                            <div className="locator mb-1 uppercase">分析</div>
                            <p className="text-[13px] text-neutral-600 leading-relaxed">{p.why}</p>
                          </div>
                        )}
                        {p.suggestion && (
                          <div className="mb-3">
                            <div className="locator mb-1 uppercase">建议</div>
                            <p className="text-[13px] text-neutral-600 leading-relaxed">{p.suggestion}</p>
                          </div>
                        )}
                        {p.uncertainty && (
                          <div>
                            <div className="locator mb-1 uppercase">不确定性</div>
                            <p className="text-[13px] text-neutral-600 leading-relaxed">{p.uncertainty}</p>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="mt-5 pt-4 hairline-t flex flex-wrap items-center gap-2">
                      {!d && (
                        <>
                          <button
                            className="btn-teal"
                            onClick={() => void persistImpact(p.id, 'adopted')}
                          >
                            采用这项影响
                          </button>
                          <button
                            className="btn-quiet"
                            onClick={() => void persistImpact(p.id, 'rejected')}
                          >
                            不采用
                          </button>
                        </>
                      )}
                      {d === 'adopted' && <span className="badge-green badge-dot">已采用 · 已生成写作证据</span>}
                      {d === 'rejected' && <span className="badge-gray badge-dot">已标记不采用</span>}
                      <span className="locator ml-auto">arxiv.org/abs/{p.arxivId}</span>
                    </div>
                  </article>
                </Reveal>
              );
            })}
          </div>
        )}

        {/* tab 2 — affected claims */}
        {tab === 2 && (
          <div className="grid gap-4">
            {affected.length === 0 && <Empty text="本周没有受影响的主张" />}
            {affected.map((c, i) => {
              const isExpanded = expandedClaimId === c.id;
              return (
                <Reveal key={c.id} delay={i * 60}>
                  <article className="card p-6">
                    <div className="flex flex-col md:flex-row md:items-center gap-5">
                      <button
                        className="font-serif italic text-2xl text-neutral-300 shrink-0 w-14 text-left hover:text-teal transition-colors"
                        onClick={() =>
                          setExpandedClaimId((prev) => (prev === c.id ? null : c.id))
                        }
                      >
                        {c.id}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <span className={claimStatusMeta[c.status].cls}>
                            {claimStatusMeta[c.status].label}
                          </span>
                          {c.radarWatch && <span className="badge-teal badge-dot">Radar 关注</span>}
                        </div>
                        <p className="font-medium text-[15px]">{c.text}</p>
                        <p className="mt-2 text-xs text-neutral-400">证伪条件：{c.falsifiable}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="num-display text-[#B42318]">
                          {c.evidence.filter((e) => e.kind === 'challenge').length}
                        </div>
                        <div className="text-xs text-neutral-400 mt-1">挑战证据</div>
                      </div>
                    </div>

                    {/* expand/collapse section */}
                    {isExpanded && (
                      <div className="mt-5 pt-5 hairline-t">
                        {/* contract details */}
                        <div className="mb-4">
                          <div className="locator mb-2 uppercase">约定细则</div>
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-[13px]">
                            {Object.entries(c.contract).map(([key, val]) => (
                              <div key={key}>
                                <span className="text-neutral-400">{key}</span>
                                <p className="text-neutral-700 mt-0.5">{val || '—'}</p>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* falsifiable condition */}
                        <div className="mb-4">
                          <div className="locator mb-1 uppercase">证伪条件</div>
                          <p className="text-[13px] text-neutral-600">{c.falsifiable}</p>
                        </div>

                        {/* evidence chain */}
                        <div>
                          <div className="locator mb-2 uppercase">证据链</div>
                          {c.evidence.length === 0 && (
                            <p className="text-[13px] text-neutral-300">—</p>
                          )}
                          <ul className="space-y-2">
                            {c.evidence.map((e) => {
                              const pp = findPaper(e.paperId);
                              return (
                                <li key={e.paperId} className="text-[13px] text-neutral-600 leading-relaxed">
                                  <span className="font-mono text-neutral-400">
                                    {e.kind === 'challenge' ? '⚠' : e.kind === 'support' ? '✓' : '○'}
                                  </span>{' '}
                                  {e.note}
                                  {pp && (
                                    <span className="locator block mt-0.5">
                                      arXiv:{pp.arxivId} · {pp.title.slice(0, 48)}…
                                    </span>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      </div>
                    )}
                  </article>
                </Reveal>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
