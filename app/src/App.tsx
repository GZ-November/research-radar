import React, { useState } from 'react';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import Actions from './pages/Actions';
import Radar from './pages/Radar';
import Improve from './pages/Improve';
import Paper from './pages/Paper';
import Settings from './pages/Settings';
import { projects, type Project } from './data/mock';
import { getCases, getCaseDetail, getMockProjects, getMockProject, useApi, type CaseSummary } from './api';

export type PageKey = 'dashboard' | 'actions' | 'radar' | 'improve' | 'paper' | 'settings';

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

const ICONS: Record<PageKey, React.ReactNode> = {
  dashboard: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M3.5 10.5 12 3.5l8.5 7" />
      <path d="M5.5 9v11h13V9" />
      <path d="M9.5 20v-6h5v6" />
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
};

const NAV: { key: PageKey; label: string }[] = [
  { key: 'dashboard', label: '工作台' },
  { key: 'actions', label: '本周行动' },
  { key: 'radar', label: '文献雷达' },
  { key: 'improve', label: '改进' },
  { key: 'paper', label: '我的论文' },
  { key: 'settings', label: '设置' },
];

/** Attempt to load a project from the API; fall back to mock if unavailable. */
async function loadProject(caseId: string): Promise<Project> {
  try {
    return await getCaseDetail(caseId);
  } catch {
    const fallback = getMockProject(caseId);
    if (fallback) return fallback;
    // If not found in mock either, use the first mock project
    return getMockProjects()[0];
  }
}

export default function App() {
  const [entered, setEntered] = useState(false);
  const [page, setPage] = useState<PageKey>('dashboard');
  const [projectId, setProjectId] = useState(projects[0].id);

  // Active project — starts from mock, may be replaced by API data
  const [project, setProject] = useState<Project>(projects[0]);
  // Whether we're showing the full mock list (API unavailable) or API list
  const [caseList, setCaseList] = useState<CaseSummary[] | null>(null);

  // Try loading case list from API on mount
  useApi<CaseSummary[]>(
    async () => {
      const cases = await getCases();
      setCaseList(cases);
      // Also load the first project from API
      if (cases.length > 0) {
        const detail = await loadProject(cases[0].id);
        setProject(detail);
        setProjectId(detail.id);
      }
      return cases;
    },
    [],
  );

  const displayProjects: CaseSummary[] = caseList ?? projects.map((p) => ({
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

  if (!entered) return <Landing onEnter={() => setEntered(true)} />;

  const go = (k: PageKey) => {
    setPage(k);
    window.scrollTo({ top: 0 });
  };

  const switchProject = async (id: string) => {
    setProjectId(id);
    // Try to load from API; fall back to mock
    const p = await loadProject(id);
    setProject(p);
  };

  return (
    <div className="min-h-screen bg-paper flex">
      {/* dark narrow sidebar */}
      <aside className="fixed inset-y-0 left-0 w-[76px] md:w-[190px] bg-night text-white flex flex-col z-40">
        <button
          onClick={() => setEntered(false)}
          className="flex items-center gap-3 px-5 py-6 border-b border-white/10 hover:bg-white/5 transition-colors duration-200"
          title="返回首屏"
        >
          <span className="w-2 h-2 rounded-full bg-cyan-300 blink-soft shrink-0" />
          <span className="hidden md:block font-mono text-[10px] tracking-[0.24em] uppercase text-cyan-100/80 leading-tight text-left">
            Research
            <br />
            Radar
          </span>
        </button>
        <nav className="flex-1 py-4">
          {NAV.map((n) => (
            <button
              key={n.key}
              onClick={() => go(n.key)}
              className={`w-full flex items-center gap-3 px-5 py-3 text-[13px] transition-all duration-200 border-l-2 ${
                page === n.key
                  ? 'border-cyan-300 text-white bg-white/5'
                  : 'border-transparent text-white/45 hover:text-white/85 hover:bg-white/[0.03]'
              }`}
            >
              <span className="w-[17px] h-[17px] shrink-0 flex items-center justify-center">{ICONS[n.key]}</span>
              <span className="hidden md:block tracking-wide">{n.label}</span>
            </button>
          ))}
        </nav>
        <div className="hidden md:block px-5 py-5 border-t border-white/10">
          <div className="locator !text-white/30">DEMO BUILD</div>
          <div className="locator !text-white/30 mt-1">2026-07-23</div>
        </div>
      </aside>

      {/* main */}
      <div className="flex-1 ml-[76px] md:ml-[190px] min-w-0">
        {/* top bar */}
        <header className="sticky top-0 z-30 bg-paper/90 backdrop-blur hairline-b">
          <div className="flex items-center justify-between gap-4 px-6 md:px-10 h-16">
            <div className="flex items-center gap-3 min-w-0">
              {displayProjects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => switchProject(p.id)}
                  className={`chip transition-all duration-200 ${
                    p.id === projectId ? '!border-teal !text-teal !bg-teal-soft' : 'hover:border-neutral-400'
                  }`}
                >
                  {p.short} · {p.version}
                </button>
              ))}
            </div>
            <div className="hidden md:flex items-center gap-5 shrink-0">
              <span className="locator">上次扫描 {project.lastScan}</span>
              {project.urgent > 0 && <span className="badge-red badge-dot">{project.urgent} 紧急</span>}
            </div>
          </div>
        </header>

        <main className="px-6 md:px-10 py-10 max-w-[1200px]">
          {page === 'dashboard' && <Dashboard project={project} onOpen={() => go('actions')} />}
          {page === 'actions' && <Actions caseId={projectId} />}
          {page === 'radar' && <Radar project={project} />}
          {page === 'improve' && <Improve caseId={projectId} />}
          {page === 'paper' && <PaperPage project={project} />}
          {page === 'settings' && <Settings />}
        </main>

        <footer className="px-6 md:px-10 py-8 hairline-t flex items-center justify-between">
          <span className="locator">Research Radar · 演示数据</span>
          <span className="locator">{project.file} · {project.version}</span>
        </footer>
      </div>
    </div>
  );
}

// alias to avoid name clash with type import
function PaperPage({ project }: { project: Project }) {
  return <Paper caseId={project.id} />;
}
