import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { type Project, type CaseSummary, getCases, getCaseDetail } from '../api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentEntry {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
}

interface ProjectContextValue {
  /** Current active project (full detail).  null while loading / unselected. */
  project: Project | null;
  /** Current project id.  Empty string when no project is selected. */
  projectId: string;
  /** True while the project detail is loading. */
  loading: boolean;
  /** Error from the last fetch, if any. */
  error: Error | null;
  /** All available projects (lightweight list). */
  caseList: CaseSummary[];
  /** Switch to a different project. */
  switchProject: (id: string) => Promise<void>;
  /** Leave the current project and return to the project list. */
  clearProject: () => void;
  /** Refresh the current project from the API. */
  refreshProject: () => Promise<void>;
  /** Refresh the case list. */
  refreshCaseList: () => Promise<void>;
  /** Currently enabled agents for this project (reserved for future use). */
  agents: AgentEntry[];
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projectId, setProjectId] = useState('');
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [caseList, setCaseList] = useState<CaseSummary[]>([]);
  const [agents] = useState<AgentEntry[]>([]);  // reserved for future Agent hub

  // ---- internal helpers ----

  // ---- public actions ----

  const switchProject = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const p = await getCaseDetail(id);
      setProject(p);
      setProjectId(id);
    } catch (e) {
      const nextError = e instanceof Error ? e : new Error(String(e));
      setProject(null);
      setProjectId('');
      setError(nextError);
      throw nextError;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearProject = useCallback(() => {
    setProjectId('');
    setProject(null);
    setError(null);
  }, []);

  const refreshProject = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const p = await getCaseDetail(projectId);
      setProject(p);
    } catch (e) {
      const nextError = e instanceof Error ? e : new Error(String(e));
      setError(nextError);
      throw nextError;
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const refreshCaseList = useCallback(async () => {
    try {
      const cases = await getCases();
      setCaseList(cases);
      setError(null);
    } catch (e) {
      const nextError = e instanceof Error ? e : new Error(String(e));
      setCaseList([]);
      setError(nextError);
      throw nextError;
    }
  }, []);

  // ---- initial load ----

  useEffect(() => {
    void refreshCaseList().catch(() => undefined);
  }, [refreshCaseList]);

  // ---- context value ----

  const value = useMemo<ProjectContextValue>(() => ({
    project, projectId, loading, error, caseList, switchProject, clearProject,
    refreshProject, refreshCaseList, agents,
  }), [
    agents, caseList, clearProject, error, loading, project, projectId,
    refreshCaseList, refreshProject, switchProject,
  ]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used within ProjectProvider');
  return ctx;
}

/** Convenience hook: returns projectId (for pages that only need the id). */
export function useProjectId(): string {
  return useProject().projectId;
}
