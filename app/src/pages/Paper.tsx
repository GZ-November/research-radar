import { useState } from 'react';
import { claimStatusMeta, type Project, type Claim, type VersionRec } from '../data/mock';
import { Reveal, Stat, Tabs, Quote, Empty } from '../components/chrome';
import {
  useApi,
  getCaseDetail,
  getProfile,
  analyzeProfile,
  getCompetitors,
  addCompetitor,
  removeCompetitor,
  confirmClaim,
  rejectClaim,
  editClaim,
  uploadManuscript,
} from '../api';

// ---------- local types ----------

interface CompetitorItem {
  id?: string;
  team: string;
  aliases: string[];
}

// ---------- constants ----------

const CONTRACT_LABELS: [string, keyof Claim['contract']][] = [
  ['任务', 'task'],
  ['数据集', 'dataset'],
  ['数据划分', 'split'],
  ['指标', 'metric'],
  ['对比基线', 'baseline'],
  ['适用范围', 'scope'],
];

// ---------- Paper page ----------

export default function Paper({ caseId }: { caseId: string }) {
  const [tab, setTab] = useState(0);

  // ---- data hooks ----

  const { data: project, loading: projectLoading, error: projectError } = useApi(
    () => getCaseDetail(caseId),
    [caseId],
  );

  const {
    data: profile,
    loading: profileLoading,
    error: profileError,
    refetch: refetchProfile,
  } = useApi(() => getProfile(caseId), [caseId]);

  const {
    data: competitors,
    loading: competitorsLoading,
    error: competitorsError,
    refetch: refetchCompetitors,
  } = useApi(() => getCompetitors(caseId), [caseId]);

  // ---- local state ----

  const [confirm, setConfirm] = useState<Record<string, 'yes' | 'no'>>({});
  const [synced, setSynced] = useState(false);
  const [team, setTeam] = useState('');
  const [alias, setAlias] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  // ---- derived values ----

  const confirmedCount = project
    ? project.claims.filter(
        (c) =>
          (confirm[c.id] ??
            (c.confirmed === 'yes'
              ? 'yes'
              : c.confirmed === 'pending'
                ? undefined
                : 'no')) === 'yes',
      ).length
    : 0;

  // ---- action handlers ----

  const handleConfirm = async (revId: string) => {
    try {
      setActionError(null);
      const updated = await confirmClaim(caseId, revId);
      setConfirm((m) => ({ ...m, [revId]: 'yes' }));
      // merge API response into confirm state
      if (updated.confirmed === 'yes') {
        setConfirm((m) => ({ ...m, [revId]: 'yes' }));
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '确认失败');
    }
  };

  const handleReject = async (revId: string) => {
    try {
      setActionError(null);
      const updated = await rejectClaim(caseId, revId);
      setConfirm((m) => ({ ...m, [revId]: 'no' }));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '拒绝失败');
    }
  };

  const handleEdit = async (revId: string, body: { statement?: string }) => {
    try {
      setActionError(null);
      await editClaim(caseId, revId, body);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : '编辑失败');
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setActionError(null);
      await uploadManuscript(caseId, file);
      setSynced(true);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '上传失败');
    }
  };

  const handleAddCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!team.trim()) return;
    try {
      setActionError(null);
      await addCompetitor(
        caseId,
        team.trim(),
        alias.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      );
      setTeam('');
      setAlias('');
      refetchCompetitors();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '添加监控失败');
    }
  };

  const handleRemoveCompetitor = async (item: CompetitorItem) => {
    const watchId = item.id ?? item.team;
    try {
      setActionError(null);
      await removeCompetitor(caseId, watchId);
      refetchCompetitors();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '移除监控失败');
    }
  };

  const handleReanalyze = async () => {
    try {
      setActionError(null);
      await analyzeProfile(caseId);
      refetchProfile();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '重新分析失败');
    }
  };

  // ---- loading / error states ----

  if (projectLoading) {
    return (
      <div className="py-20 text-center">
        <div className="font-serif italic text-neutral-300 text-3xl select-none">…</div>
        <div className="mt-3 text-sm text-neutral-400">加载中</div>
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="py-20 text-center">
        <div className="text-sm text-[#B42318]">
          {projectError?.message ?? '无法加载项目数据'}
        </div>
      </div>
    );
  }

  // ---- render ----

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">Manuscript</div>
        <h1 className="display-lg mb-8">我的论文</h1>
      </Reveal>

      {/* action-level error banner */}
      {actionError && (
        <div className="mb-6 card p-4 text-sm text-[#B42318] bg-red-50/60 border border-red-200 rounded-lg">
          {actionError}
          <button className="ml-3 underline text-neutral-500" onClick={() => setActionError(null)}>
            关闭
          </button>
        </div>
      )}

      <Reveal delay={60}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pb-8 hairline-b">
          <Stat
            value={<span className="font-mono text-2xl">{project.file}</span>}
            label="当前文稿"
          />
          <Stat value={project.version} label="版本" tone="teal" />
          <Stat value={project.claimsTotal} label="当前 Claim" />
          <Stat value={confirmedCount} label="已确认" tone="teal" />
        </div>
      </Reveal>

      <div className="mt-8">
        <Tabs
          tabs={['文稿与版本', '项目主张', 'AI 全文画像', '竞争监控']}
          active={tab}
          onChange={setTab}
        />

        {/* ================================================================ */}
        {/* Tab 0: 文稿与版本                                                   */}
        {/* ================================================================ */}
        {tab === 0 && (
          <div>
            <Reveal>
              <div className="card p-6 flex flex-col md:flex-row md:items-center gap-4 justify-between">
                <div>
                  <div className="font-medium text-sm">同步新版本</div>
                  <p className="text-xs text-neutral-400 mt-1">
                    上传后自动重新提取 Claim 并与当前账本比对
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <label className="btn-ghost cursor-pointer">
                    选择文件
                    <input
                      type="file"
                      accept=".tex,.md,.pdf"
                      className="hidden"
                      onChange={handleUpload}
                    />
                  </label>
                  {synced && (
                    <span className="badge-green badge-dot">
                      已同步 · 无新增 Claim
                    </span>
                  )}
                </div>
              </div>
            </Reveal>
            <Reveal delay={80}>
              <div className="card mt-5 overflow-x-auto">
                <table className="table-base min-w-[560px]">
                  <thead>
                    <tr>
                      <th>版本</th>
                      <th>日期</th>
                      <th>文件</th>
                      <th>Claim 数</th>
                      <th>备注</th>
                    </tr>
                  </thead>
                  <tbody>
                    {project.versions.map((v: VersionRec) => (
                      <tr key={v.v}>
                        <td className="font-mono text-[12px]">{v.v}</td>
                        <td className="locator">{v.date}</td>
                        <td className="font-mono text-[12px] text-neutral-500">
                          {v.file}
                        </td>
                        <td className="tabular">{v.claims}</td>
                        <td className="text-neutral-500">{v.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Reveal>
          </div>
        )}

        {/* ================================================================ */}
        {/* Tab 1: 项目主张                                                     */}
        {/* ================================================================ */}
        {tab === 1 && (
          <div className="grid gap-4">
            {project.claims.map((c: Claim, i: number) => {
              const st =
                confirm[c.id] ??
                (c.confirmed === 'yes'
                  ? 'yes'
                  : c.confirmed === 'pending'
                    ? undefined
                    : 'no');
              return (
                <Reveal key={c.id} delay={i * 50}>
                  <article className="card p-6">
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <span
                        className={`font-mono text-[13px] ${
                          st === 'yes'
                            ? 'text-[#067647]'
                            : st === 'no'
                              ? 'text-neutral-300'
                              : 'text-[#B54708]'
                        }`}
                      >
                        {st === 'yes'
                          ? '✓ 已确认'
                          : st === 'no'
                            ? '↺ 历史'
                            : '○ 待确认'}
                      </span>
                      <span className={claimStatusMeta[c.status].cls}>
                        {claimStatusMeta[c.status].label}
                      </span>
                      <span className="locator ml-auto">{c.id}</span>
                    </div>
                    <p className="font-medium text-[15px]">{c.text}</p>
                    <div className="mt-4">
                      <Quote loc={c.loc}>{c.quote}</Quote>
                    </div>
                    <div className="mt-5 overflow-x-auto">
                      <table className="table-base min-w-[520px]">
                        <tbody>
                          {CONTRACT_LABELS.map(([label, key]) => (
                            <tr key={key}>
                              <td className="w-24 text-neutral-400 text-xs whitespace-nowrap !py-2">
                                {label}
                              </td>
                              <td className="text-[13px] text-neutral-600 !py-2">
                                {c.contract[key]}
                              </td>
                            </tr>
                          ))}
                          <tr>
                            <td className="text-neutral-400 text-xs !py-2">
                              可证伪条件
                            </td>
                            <td className="text-[13px] text-[#B42318]/80 !py-2">
                              {c.falsifiable}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-4 pt-4 hairline-t flex flex-wrap gap-2">
                      {st !== 'yes' && (
                        <button
                          className="btn-teal"
                          onClick={() => handleConfirm(c.id)}
                        >
                          确认
                        </button>
                      )}
                      {st !== 'no' && (
                        <button
                          className="btn-quiet"
                          onClick={() => handleReject(c.id)}
                        >
                          拒绝
                        </button>
                      )}
                      <button
                        className="btn-ghost"
                        onClick={() => handleEdit(c.id, { statement: c.text })}
                      >
                        编辑
                      </button>
                      <button className="btn-ghost">拆分</button>
                    </div>
                  </article>
                </Reveal>
              );
            })}
          </div>
        )}

        {/* ================================================================ */}
        {/* Tab 2: AI 全文画像                                                  */}
        {/* ================================================================ */}
        {tab === 2 && (
          <div className="grid gap-4">
            {/* Full-text profile */}
            <Reveal>
              <section className="card p-7">
                <div className="flex items-center justify-between mb-4">
                  <div className="kicker">Full-text Profile</div>
                  <button className="btn-ghost text-xs" onClick={handleReanalyze}>
                    重新分析
                  </button>
                </div>
                {profileLoading && (
                  <div className="py-8 text-center text-sm text-neutral-400">
                    加载中…
                  </div>
                )}
                {profileError && (
                  <div className="py-8 text-center text-sm text-[#B42318]">
                    {profileError.message}
                  </div>
                )}
                {!profileLoading && !profileError && !profile && (
                  <Empty text="AI 全文画像尚未分析" />
                )}
                {profile && (
                  <dl className="grid md:grid-cols-2 gap-x-10 gap-y-6">
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">研究问题</dt>
                      <dd className="font-serif text-lg leading-snug">
                        {profile.question}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">核心论点</dt>
                      <dd className="text-sm text-neutral-600 leading-relaxed">
                        {profile.thesis}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">主要贡献</dt>
                      <dd>
                        <ul className="text-sm text-neutral-600 space-y-1">
                          {profile.contributions.map((x) => (
                            <li key={x}>· {x}</li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">关键发现</dt>
                      <dd>
                        <ul className="text-sm text-neutral-600 space-y-1">
                          {profile.findings.map((x) => (
                            <li key={x}>· {x}</li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">局限</dt>
                      <dd>
                        <ul className="text-sm text-neutral-500 space-y-1">
                          {profile.limits.map((x) => (
                            <li key={x}>· {x}</li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-neutral-400 mb-1.5">
                        每周监控主题
                      </dt>
                      <dd className="flex flex-wrap gap-2">
                        {project.topics.map((t: string) => (
                          <span key={t} className="chip font-mono !text-[11px]">
                            {t}
                          </span>
                        ))}
                      </dd>
                    </div>
                  </dl>
                )}
              </section>
            </Reveal>

            {/* Per-claim profile */}
            <Reveal delay={80}>
              <section className="card p-7">
                <div className="kicker mb-4">Per-Claim Profile</div>
                <div className="grid md:grid-cols-2 gap-4">
                  {project.claims.map((c: Claim) => (
                    <div
                      key={c.id}
                      className="border border-hairline rounded-md p-4 hover:border-neutral-300 transition-colors duration-200"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-mono text-[11px] text-neutral-400">
                          {c.id}
                        </span>
                        <span className={claimStatusMeta[c.status].cls}>
                          {claimStatusMeta[c.status].label}
                        </span>
                      </div>
                      <p className="text-[13px] text-neutral-600 leading-relaxed">
                        {c.text}
                      </p>
                      <p className="locator mt-2">
                        证据 {c.evidence.length} ·{' '}
                        {c.radarWatch ? 'Radar 关注中' : '常规监控'}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </Reveal>
          </div>
        )}

        {/* ================================================================ */}
        {/* Tab 3: 竞争监控                                                     */}
        {/* ================================================================ */}
        {tab === 3 && (
          <div className="grid gap-4">
            {competitorsLoading && (
              <div className="py-8 text-center text-sm text-neutral-400">
                加载中…
              </div>
            )}
            {competitorsError && (
              <div className="py-8 text-center text-sm text-[#B42318]">
                {competitorsError.message}
              </div>
            )}
            {!competitorsLoading &&
              !competitorsError &&
              competitors &&
              competitors.length === 0 && (
                <Empty text="尚未添加监控对象" />
              )}
            {competitors &&
              competitors.map((w: CompetitorItem, i: number) => (
                <Reveal key={w.team} delay={i * 60}>
                  <div className="card p-6 flex flex-col md:flex-row md:items-center gap-4">
                    <div className="flex-1">
                      <div className="font-medium text-[15px]">{w.team}</div>
                      <div className="flex flex-wrap gap-2 mt-2.5">
                        {w.aliases.map((a: string) => (
                          <span key={a} className="chip font-mono !text-[11px]">
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button
                      className="btn-quiet shrink-0"
                      onClick={() => handleRemoveCompetitor(w)}
                    >
                      移除
                    </button>
                  </div>
                </Reveal>
              ))}
            <Reveal delay={100}>
              <form
                className="card p-6 grid md:grid-cols-[1fr_1fr_auto] gap-4 items-end"
                onSubmit={handleAddCompetitor}
              >
                <label>
                  <span className="text-xs text-neutral-500">团队 / 实验室</span>
                  <input
                    className="input mt-1.5"
                    value={team}
                    onChange={(e) => setTeam(e.target.value)}
                    placeholder="例如：DeepMind Retrieval Team"
                  />
                </label>
                <label>
                  <span className="text-xs text-neutral-500">
                    作者别名（逗号分隔）
                  </span>
                  <input
                    className="input mt-1.5"
                    value={alias}
                    onChange={(e) => setAlias(e.target.value)}
                    placeholder="J. Smith, Jane Smith"
                  />
                </label>
                <button type="submit" className="btn-dark">
                  添加监控
                </button>
              </form>
            </Reveal>
          </div>
        )}
      </div>
    </div>
  );
}
