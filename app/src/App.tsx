import React, { useState } from 'react';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import Actions from './pages/Actions';
import Radar from './pages/Radar';
import Improve from './pages/Improve';
import Paper from './pages/Paper';
import Settings from './pages/Settings';
import { ProjectProvider, useProject } from './contexts/ProjectContext';
import HomeView from './pages/HomeView';

export type PageKey = 'dashboard' | 'actions' | 'radar' | 'improve' | 'paper' | 'settings';
type View = 'home' | PageKey;

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

const ICONS: Record<string, React.ReactNode> = {
  home: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M3.5 10.5 12 3.5l8.5 7" />
      <path d="M5.5 9v11h13V9" />
      <path d="M9.5 20v-6h5v6" />
    </svg>
  ),
  dashboard: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <rect x="3" y="3" width="7" height="8" rx="1" />
      <rect x="13" y="3" width="7" height="4" rx="1" />
      <rect x="3" y="14" width="7" height="6" rx="1" />
      <rect x="13" y="10" width="7" height="10" rx="1" />
    </svg>
  ),
  actions: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M4 12h15" />
      <path d="M13.5 6.5 19 12l-5.5 5.5" />
    </svg>
  ),
  radar: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4" />
      <path d="M12 12 18.5 5.5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    </svg>
  ),
  improve: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M4 20l1.2-4.2L16.7 4.3a2 2 0 0 1 2.8 2.8L8 18.6 4 20z" />
      <path d="M14.5 6.5l3 3" />
    </svg>
  ),
  paper: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M7 3.5h6.5L18 8v12.5H7z" />
      <path d="M13.5 3.5V8H18" />
      <path d="M9.5 12h5M9.5 15.5h5" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M4 7h16M4 12h16M4 17h16" />
      <circle cx="9" cy="7" r="1.8" fill="#0B0E12" />
      <circle cx="15" cy="12" r="1.8" fill="#0B0E12" />
      <circle cx="8" cy="17" r="1.8" fill="#0B0E12" />
    </svg>
  ),
  back: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  ),
};

// Project-scoped nav items (shown when a project is selected)
const PROJECT_NAV: { key: PageKey; label: string }[] = [
  { key: 'dashboard', label: '项目概览' },
  { key: 'actions', label: '本周行动' },
  { key: 'radar', label: '文献雷达' },
  { key: 'improve', label: '改进' },
  { key: 'paper', label: '我的论文' },
];

export default function AppWrapper() {
  return (
    <ProjectProvider>
      <App />
    </ProjectProvider>
  );
}

function App() {
  const [entered, setEntered] = useState(false);
  const [view, setView] = useState<View>('home');
  const { project, projectId, caseList, switchProject, clearProject } = useProject();
  const today = new Intl.DateTimeFormat('en-CA').format(new Date());

  if (!entered) return <Landing onEnter={() => setEntered(true)} />;

  const go = (v: View) => {
    setView(v);
    window.scrollTo({ top: 0 });
  };

  const handleSelectProject = async (id: string) => {
    try {
      await switchProject(id);
      setView('dashboard');
    } catch {
      setView('home');
    }
  };

  const handleBackToHome = () => {
    clearProject();
    setView('home');
  };

  const hasProject = projectId !== '';
  const projectChip = caseList.find((c) => c.id === projectId);

  return (
    <div className="min-h-screen bg-paper flex">
      {/* dark narrow sidebar */}
      <aside className="fixed inset-y-0 left-0 w-[76px] md:w-[190px] bg-night text-white flex flex-col z-40">
        {/* Logo / branding */}
        <button
          onClick={handleBackToHome}
          className="flex items-center gap-3 px-5 py-6 border-b border-white/10 hover:bg-white/5 transition-colors duration-200"
          title="返回项目列表"
        >
          <span className="w-2 h-2 rounded-full bg-cyan-300 blink-soft shrink-0" />
          <span className="hidden md:block font-mono text-[10px] tracking-[0.24em] uppercase text-cyan-100/80 leading-tight text-left">
            Research
            <br />
            Radar
          </span>
        </button>

        {/* Current project indicator (when inside a project) */}
        {hasProject && projectChip && (
          <div className="px-5 py-4 border-b border-white/10 bg-white/[0.03]">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
              <span className="text-[10px] text-teal-300/70 tracking-wider uppercase">当前项目</span>
            </div>
            <div className="text-sm font-semibold text-white truncate leading-tight">{projectChip.short}</div>
            <div className="text-[11px] text-white/35 mt-0.5">{projectChip.version} · {projectChip.file}</div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 py-4">
          {!hasProject ? (
            <>
              {/* Home view: just project list + settings */}
              <NavButton active={view === 'home'} onClick={() => go('home')} icon={ICONS.home} label="项目列表" />
              <NavButton active={view === 'settings'} onClick={() => go('settings')} icon={ICONS.settings} label="设置" />
            </>
          ) : (
            <>
              {/* Project-scoped navigation */}
              {PROJECT_NAV.map((n) => (
                <NavButton
                  key={n.key}
                  active={view === n.key}
                  onClick={() => go(n.key)}
                  icon={ICONS[n.key]}
                  label={n.label}
                />
              ))}
              <div className="my-3 mx-4 border-t border-white/[0.08]" />
              <NavButton
                active={false}
                onClick={handleBackToHome}
                icon={ICONS.back}
                label="← 所有项目"
              />
              <NavButton
                active={view === 'settings'}
                onClick={() => go('settings')}
                icon={ICONS.settings}
                label="设置"
              />
            </>
          )}

          {/* Future: Agent hub (disabled for now) */}
          <div className="mt-4 mx-5 pt-3 border-t border-white/10">
            <button
              disabled
              className="w-full flex items-center gap-3 py-2 text-[12px] text-white/20 cursor-not-allowed"
              title="Agent 中心（即将推出）"
            >
              <span className="w-[17px] h-[17px] shrink-0 flex items-center justify-center opacity-30">
                <svg viewBox="0 0 24 24" {...stroke}>
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v4M12 19v4M4.2 4.2l2.8 2.8M17 17l2.8 2.8M1 12h4M19 12h4M4.2 19.8l2.8-2.8M17 7l2.8-2.8" />
                </svg>
              </span>
              <span className="hidden md:block tracking-wide">Agent 中心</span>
            </button>
          </div>
        </nav>

        <div className="hidden md:block px-5 py-5 border-t border-white/10">
          <div className="locator !text-white/30">DEMO BUILD</div>
          <div className="locator !text-white/30 mt-1">{today}</div>
        </div>
      </aside>

      {/* main */}
      <div className="flex-1 ml-[76px] md:ml-[190px] min-w-0">
        {/* top bar */}
        <header className="sticky top-0 z-30 bg-paper/90 backdrop-blur hairline-b">
          <div className="flex items-center justify-between gap-4 px-6 md:px-10 h-16">
            <div className="flex items-center gap-3 min-w-0">
              {/* Breadcrumb */}
              <div className="flex items-center gap-1.5 text-xs text-neutral-400">
                <button
                  onClick={handleBackToHome}
                  className="hover:text-neutral-600 transition-colors"
                >
                  所有项目
                </button>
                {hasProject && projectChip && (
                  <>
                    <span className="text-neutral-300">›</span>
                    <span className="text-ink font-medium">{projectChip.short} {projectChip.version}</span>
                  </>
                )}
                {!hasProject && view === 'settings' && (
                  <>
                    <span className="text-neutral-300">›</span>
                    <span className="text-ink font-medium">设置</span>
                  </>
                )}
              </div>

              {/* Project quick-switch chips (only when inside a project) */}
              {hasProject && caseList.length > 1 && (
                <div className="hidden md:flex items-center gap-1.5 ml-4 pl-4 border-l border-hairline">
                  {caseList.map((c) => (
                    <button
                      key={c.id}
                      onClick={async () => { await switchProject(c.id); setView('dashboard'); }}
                      className={`chip transition-all duration-200 text-[10px] ${
                        c.id === projectId
                          ? '!border-teal !text-teal !bg-teal-soft cursor-default'
                          : 'hover:border-neutral-400'
                      }`}
                    >
                      {c.short}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="hidden md:flex items-center gap-5 shrink-0">
              {hasProject && project && (
                <>
                  <span className="locator">上次扫描 {project.lastScan}</span>
                  {project.urgent > 0 && <span className="badge-red badge-dot">{project.urgent} 紧急</span>}
                </>
              )}
            </div>
          </div>
        </header>

        <main className="px-6 md:px-10 py-10 max-w-[1200px]">
          {view === 'home' && <HomeView onSelectProject={handleSelectProject} />}
          {view === 'dashboard' && hasProject && <Dashboard onNavigate={(p) => go(p)} />}
          {view === 'actions' && hasProject && <Actions />}
          {view === 'radar' && hasProject && <Radar />}
          {view === 'improve' && hasProject && <Improve />}
          {view === 'paper' && hasProject && <Paper />}
          {view === 'settings' && <Settings />}
        </main>

        <footer className="px-6 md:px-10 py-8 hairline-t flex items-center justify-between">
          <span className="locator">Research Radar · 演示数据</span>
          {hasProject && projectChip && (
            <span className="locator">{projectChip.file} · {projectChip.version}</span>
          )}
        </footer>
      </div>
    </div>
  );
}

/** Single nav-button in the sidebar. */
function NavButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-5 py-3 text-[13px] transition-all duration-200 border-l-2 ${
        active
          ? 'border-cyan-300 text-white bg-white/5'
          : 'border-transparent text-white/45 hover:text-white/85 hover:bg-white/[0.03]'
      }`}
    >
      <span className="w-[17px] h-[17px] shrink-0 flex items-center justify-center">{icon}</span>
      <span className="hidden md:block tracking-wide">{label}</span>
    </button>
  );
}
