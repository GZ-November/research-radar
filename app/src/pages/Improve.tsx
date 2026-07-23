import { useState } from 'react';
import { getCaseDetail, getAudit, approvePatch, rejectPatch, useApi } from '../api';
import { type Project, type AuditRec, claimStatusMeta, verdictMeta } from '../data/mock';
import { Reveal, SectionHead } from '../components/chrome';
import { Spinner } from '../components/ui/spinner';

export default function Improve({ caseId }: { caseId: string }) {
  const { data: project, loading, error } = useApi(() => getCaseDetail(caseId), [caseId]);
  const { data: audit, loading: auditLoading, error: auditError } = useApi(() => getAudit(caseId), [caseId]);
  const [verdict, setVerdict] = useState<'none' | 'approved' | 'rejected'>('none');
  const [exported, setExported] = useState(false);
  const [patchSubmitting, setPatchSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="size-6 text-neutral-400" />
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

  const exportJSON = () => {
    const data = { project: project.name, exportedAt: new Date().toISOString(), claims: project.claims };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `evidence-pack-${project.id}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setExported(true);
  };

  const handleApprove = async () => {
    setPatchSubmitting(true);
    try {
      await approvePatch(caseId, rw.claimId);
      setVerdict('approved');
    } catch (e) {
      console.error(e);
    } finally {
      setPatchSubmitting(false);
    }
  };

  const handleReject = async () => {
    setPatchSubmitting(true);
    try {
      await rejectPatch(caseId, rw.claimId);
      setVerdict('rejected');
    } catch (e) {
      console.error(e);
    } finally {
      setPatchSubmitting(false);
    }
  };

  const rw = project.rewrite;
  const allOk = rw.checks.every((c) => c.ok);

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">Ledger</div>
        <h1 className="display-lg mb-10">改进工作台</h1>
      </Reveal>

      {/* claim ledger */}
      <Reveal delay={60}>
        <SectionHead
          kicker="Claims"
          title="Claim 账本"
          right={
            <button className="btn-ghost" onClick={exportJSON}>
              导出证据包 JSON
            </button>
          }
        />
        {exported && <p className="badge-green badge-dot mb-4">已导出 evidence-pack-{project.id}.json</p>}
        <div className="card overflow-x-auto">
          <table className="table-base min-w-[760px]">
            <thead>
              <tr>
                <th>Claim</th>
                <th>状态</th>
                <th>支持</th>
                <th>挑战</th>
                <th>完整性</th>
              </tr>
            </thead>
            <tbody>
              {project.claims.map((c) => (
                <tr key={c.id}>
                  <td className="max-w-[340px]">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-neutral-400 shrink-0">{c.id}</span>
                      {c.radarWatch && <span className="badge-teal">Radar 关注</span>}
                    </div>
                    <div className="mt-1.5 text-[13px] text-neutral-700 leading-relaxed">{c.text}</div>
                  </td>
                  <td>
                    <span className={claimStatusMeta[c.status].cls}>{claimStatusMeta[c.status].label}</span>
                  </td>
                  {(['support', 'challenge', 'completeness'] as const).map((k) => (
                    <td key={k} className="max-w-[190px]">
                      {c.evidence.filter((e) => e.kind === k).length === 0 && <span className="text-neutral-200">—</span>}
                      <ul className="space-y-1.5">
                        {c.evidence
                          .filter((e) => e.kind === k)
                          .map((e) => {
                            const pp = project.papers.find((p) => p.id === e.paperId);
                            return (
                              <li key={e.paperId} className="text-xs text-neutral-500 leading-snug">
                                {e.note}
                                {pp && <span className="locator block">arXiv:{pp.arxivId} · {verdictMeta[pp.verdict].label}</span>}
                              </li>
                            );
                          })}
                      </ul>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>

      {/* minimal rewrite */}
      <Reveal delay={100} className="mt-12">
        <SectionHead kicker="Rewrite" title="最小改写方案" right={<span className="locator">{rw.claimId} · {rw.loc}</span>} />
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-6">
            <div className="locator mb-3 uppercase">改写前</div>
            <p className="quote quote-against text-[13.5px]">{rw.before}</p>
          </div>
          <div className="card p-6">
            <div className="locator mb-3 uppercase">改写后</div>
            <p className="quote text-[13.5px]">{rw.after}</p>
          </div>
        </div>

        <div className="card mt-4 p-6">
          <div className="grid md:grid-cols-3 gap-x-8 gap-y-2.5">
            {rw.checks.map((c) => (
              <div key={c.label} className="flex items-center gap-2 text-[13px]">
                <span className={c.ok ? 'text-[#067647]' : 'text-[#B42318]'}>{c.ok ? '✓' : '✗'}</span>
                <span className={c.ok ? 'text-neutral-600' : 'text-[#B42318]'}>{c.label}</span>
              </div>
            ))}
          </div>
          <div className="mt-6 pt-5 hairline-t flex flex-wrap items-center gap-3">
            {verdict === 'none' && (
              <>
                <button
                  className="btn-teal"
                  disabled={!allOk || patchSubmitting}
                  onClick={handleApprove}
                  title={allOk ? '' : '存在未通过的验证项'}
                >
                  批准并允许导出
                </button>
                <button className="btn-quiet" disabled={patchSubmitting} onClick={handleReject}>
                  拒绝这版改写
                </button>
                {!allOk && <span className="text-xs text-[#B54708]">存在未通过的验证项，需先修正</span>}
              </>
            )}
            {verdict === 'approved' && <span className="badge-green badge-dot">已批准 · 可导出至文稿</span>}
            {verdict === 'rejected' && (
              <>
                <span className="badge-red badge-dot">已拒绝 · 已退回模型重生成</span>
                <button className="btn-quiet" onClick={() => setVerdict('none')}>撤销</button>
              </>
            )}
          </div>
        </div>
      </Reveal>

      {/* audit log — lab journal */}
      <Reveal delay={140} className="mt-12">
        <SectionHead kicker="Lab Log" title="审计记录与模型运行" />
        <div className="card p-7 citation-texture">
          {auditLoading ? (
            <div className="flex items-center justify-center py-8">
              <Spinner className="size-5 text-neutral-300" />
            </div>
          ) : auditError ? (
            <p className="text-red-500 text-sm text-center">加载审计记录失败: {auditError.message}</p>
          ) : !audit || audit.length === 0 ? (
            <p className="text-neutral-400 text-sm text-center py-8">暂无审计记录</p>
          ) : (
            <ol className="relative">
              <span className="absolute left-[5px] top-3 bottom-3 w-px bg-[#DDD9CF]" />
              {audit.map((a, i) => (
                <li key={a.stage} className="relative pl-9 py-3.5 first:pt-0 last:pb-0 group">
                  <span
                    className={`absolute left-0 top-[9px] w-[11px] h-[11px] rounded-full border-2 bg-white transition-transform duration-200 group-hover:scale-110 ${
                      a.result === 'pass' ? 'border-[#067647]' : a.result === 'warn' ? 'border-[#B54708]' : 'border-[#B42318]'
                    }`}
                  />
                  <div className="flex items-baseline gap-3 font-mono text-[12.5px] min-w-0">
                    <span className="text-neutral-300 shrink-0">{String(i + 1).padStart(2, '0')}</span>
                    <span className="text-ink shrink-0">{a.stage}</span>
                    <span className="flex-1 border-b border-dotted border-neutral-200 -translate-y-[3px] min-w-6" />
                    <span className="tabular text-neutral-400 shrink-0">{a.duration}</span>
                    <span className="tabular text-neutral-500 shrink-0 w-14 text-right">{a.cost}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 pl-9">
                    <span className="locator">
                      {a.provider} · {a.model}
                    </span>
                    {a.result === 'pass' && <span className="badge-green badge-dot">验证通过</span>}
                    {a.result === 'warn' && <span className="badge-orange badge-dot">验证警告</span>}
                    {a.result === 'fail' && <span className="badge-red badge-dot">验证失败</span>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </Reveal>
    </div>
  );
}
