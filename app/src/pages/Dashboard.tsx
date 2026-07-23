import { useMemo } from 'react';
import { Reveal, SectionHead } from '../components/chrome';
import { useProject } from '../contexts/ProjectContext';
import { Spinner } from '../components/ui/spinner';
import type { PageKey } from '../App';

export default function Dashboard({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const { project, loading, error } = useProject();

  // ---- derived stats ----
  const claimStats = useMemo(() => {
    if (!project) return { valid: 0, disputed: 0, revalidate: 0, supported: 0, pending: 0 };
    return {
      confirmed: project.claims.filter((c) => c.confirmed === 'yes').length,
      pending: project.claims.filter((c) => c.confirmed === 'pending').length,
      disputed: project.claims.filter((c) => c.status === 'disputed').length,
      valid: project.claims.filter((c) => c.status === 'valid' || c.status === 'supported').length,
      revalidate: project.claims.filter((c) => c.status === 'revalidate').length,
    };
  }, [project]);

  const urgentActions = useMemo(() => {
    if (!project) return [];
    return project.actions.filter((a) => a.priority === 'P0' || a.priority === 'P1').slice(0, 5);
  }, [project]);

  const paperStats = useMemo(() => {
    if (!project) return { total: 0, compared: 0, impacted: 0, urgent: 0 };
    return {
      total: project.papers.length,
      compared: project.papers.length,
      impacted: project.papers.filter((p) => p.verdict !== 'none').length,
      urgent: project.papers.filter((p) => p.urgency === 'urgent').length,
    };
  }, [project]);

  // ----

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="size-8 text-neutral-400" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 text-sm">{error?.message ?? '未找到项目'}</p>
      </div>
    );
  }

  return (
    <div>
      <Reveal>
        <div className="kicker mb-2">Overview</div>
        <h1 className="display-lg mb-2">{project.name}</h1>
        <div className="flex items-center gap-3 text-sm text-neutral-400 mb-10">
          <span>{project.version}</span>
          <span>·</span>
          <span>{project.file}</span>
          <span>·</span>
          <span>上次扫描 {project.lastScan}</span>
        </div>
      </Reveal>

      {/* Key metrics */}
      <Reveal delay={60}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5 pb-8 hairline-b">
          <div className="card p-5 text-center">
            <div className="font-serif font-semibold text-2xl text-teal">{claimStats.confirmed}/{project.claimsTotal}</div>
            <div className="text-xs text-neutral-400 mt-1">已确认 Claim</div>
          </div>
          <div className="card p-5 text-center">
            <div className={`font-serif font-semibold text-2xl ${claimStats.disputed > 0 ? 'text-[#B42318]' : 'text-neutral-400'}`}>{claimStats.disputed}</div>
            <div className="text-xs text-neutral-400 mt-1">存在争议</div>
          </div>
          <div className="card p-5 text-center">
            <div className={`font-serif font-semibold text-2xl ${project.urgent > 0 ? 'text-[#B42318]' : 'text-neutral-400'}`}>{project.urgent}</div>
            <div className="text-xs text-neutral-400 mt-1">紧急影响</div>
          </div>
          <div className="card p-5 text-center">
            <div className="font-serif font-semibold text-2xl text-neutral-600">{paperStats.impacted}</div>
            <div className="text-xs text-neutral-400 mt-1">材料影响论文</div>
          </div>
        </div>
      </Reveal>

      {/* Urgent actions */}
      {urgentActions.length > 0 && (
        <Reveal delay={80}>
          <div className="mt-8">
            <SectionHead kicker="Actions" title="本周紧急行动" />
            <div className="card overflow-hidden">
              {urgentActions.map((a) => (
                <div key={a.id} className="px-6 py-4 hairline-b last:border-none flex items-start gap-4">
                  <span className={`mt-0.5 shrink-0 badge-dot ${a.priority === 'P0' ? 'badge-red' : 'badge-orange'}`}>
                    {a.priority}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-neutral-700">{a.title}</p>
                    {a.reason && (
                      <p className="text-xs text-neutral-400 mt-1 line-clamp-2">{a.reason}</p>
                    )}
                  </div>
                  <span className="text-xs text-neutral-400 shrink-0">{a.due}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 text-right">
              <button className="btn-ghost text-xs" onClick={() => onNavigate('actions')}>
                查看全部行动 →
              </button>
            </div>
          </div>
        </Reveal>
      )}

      {/* Scan summary + Quick links */}
      <Reveal delay={100}>
        <div className="mt-8 grid md:grid-cols-2 gap-6">
          {/* Recent scan */}
          <div className="card p-6">
            <div className="kicker mb-3">最近扫描</div>
            <p className="text-sm text-neutral-500">{project.lastScan}</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <div className="font-semibold text-lg">{paperStats.total}</div>
                <div className="text-xs text-neutral-400">发现论文</div>
              </div>
              <div>
                <div className="font-semibold text-lg">{paperStats.impacted}</div>
                <div className="text-xs text-neutral-400">材料影响</div>
              </div>
              <div>
                <div className="font-semibold text-lg">{paperStats.urgent}</div>
                <div className="text-xs text-neutral-400">紧急</div>
              </div>
              <div>
                <div className="font-semibold text-lg">{project.actions.length}</div>
                <div className="text-xs text-neutral-400">行动建议</div>
              </div>
            </div>
          </div>

          {/* Quick actions */}
          <div className="card p-6 flex flex-col gap-3">
            <div className="kicker mb-1">快捷操作</div>
            <button className="btn-teal w-full justify-start" onClick={() => onNavigate('radar')}>
              ◎ 扫描最新公开论文
            </button>
            <button className="btn-dark w-full justify-start" onClick={() => onNavigate('actions')}>
              → 查看本周行动 ({project.actions.length})
            </button>
            <button className="btn-ghost w-full justify-start" onClick={() => onNavigate('paper')}>
              📄 管理项目主张 ({project.claimsTotal})
            </button>
            <button className="btn-ghost w-full justify-start" onClick={() => onNavigate('improve')}>
              ✎ 改进工作台
            </button>
          </div>
        </div>
      </Reveal>

      {/* Topics */}
      {project.topics.length > 0 && (
        <Reveal delay={120}>
          <div className="mt-8">
            <SectionHead kicker="Topics" title="监控主题" />
            <div className="flex flex-wrap gap-2">
              {project.topics.map((t) => (
                <span key={t} className="chip font-mono !text-[11px]">{t}</span>
              ))}
            </div>
          </div>
        </Reveal>
      )}
    </div>
  );
}
