// ---------- Research Radar API client ----------
// All functions try the live API first; on failure they fall back to mock data.
// Types are re-exported from ../data/mock so the rest of the app stays compatible.

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  type Project,
  type Paper,
  type Claim,
  type ActionItem,
  type VersionRec,
  type AuditRec,
  type MatrixRow,
  projects,
} from './data/mock';

// Types defined inline in mock.ts but not exported — derive them from the
// parent interfaces so the rest of the codebase can reference them.
export type CompetitorEntry = Project['competitors'][number];
export type EvidenceItem = Claim['evidence'][number];

// ---------------------------------------------------------------------------
// Re-export types so callers can import from a single source
// ---------------------------------------------------------------------------
export type { Project, Paper, Claim, ActionItem, VersionRec, AuditRec, MatrixRow };

// ---------------------------------------------------------------------------
// Sub-types used by the API layer
// ---------------------------------------------------------------------------
export interface CaseSummary {
  id: string;
  name: string;
  short: string;
  question: string;
  version: string;
  file: string;
  claimsConfirmed: number;
  claimsTotal: number;
  lastScan: string;
  urgent: number;
  topics: string[];
}

export interface ScanStatus {
  id: string;
  mode: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  progress: Record<string, number>;
  stats: Record<string, unknown>;
  error_message: string | null;
}

export interface SettingsData {
  llm: {
    configured: boolean;
    mode: string;
    model: string;
    missing: string[];
    provider: string;
    base_url: string;
  };
  embedding: {
    configured: boolean;
    model: string;
    provider: string;
    base_url: string;
  };
  local_llm: {
    model: string;
    base_url: string;
  };
  pdf_parser_backend: string;
}

// ---------------------------------------------------------------------------
// Low-level fetch helpers
// ---------------------------------------------------------------------------

const BASE_URL = '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: {} };

  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    (opts.headers as Record<string, string>)['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(`${BASE_URL}${path}`, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${method} ${path} ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body);
}

async function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}

// ---------------------------------------------------------------------------
// Typed API functions — one per FastAPI route
// ---------------------------------------------------------------------------

/** List all research cases (lightweight). */
export async function getCases(): Promise<CaseSummary[]> {
  return get<CaseSummary[]>('/cases');
}

/** Get full project detail for one case. */
export async function getCaseDetail(caseId: string): Promise<Project> {
  return get<Project>(`/cases/${caseId}`);
}

/** Create a new case with manuscript upload (multipart). */
export async function createCase(
  title: string,
  researchQuestion: string,
  manuscript: File,
): Promise<CaseSummary> {
  const fd = new FormData();
  fd.append('title', title);
  fd.append('research_question', researchQuestion);
  fd.append('manuscript', manuscript);
  return post<CaseSummary>('/cases', fd);
}

/** Upload a new manuscript version for an existing case. */
export async function uploadManuscript(caseId: string, file: File): Promise<Record<string, unknown>> {
  const fd = new FormData();
  fd.append('manuscript', file);
  return post<Record<string, unknown>>(`/cases/${caseId}/upload`, fd);
}

// -- Claims ----------------------------------------------------------------

export async function getClaims(caseId: string): Promise<Claim[]> {
  return get<Claim[]>(`/cases/${caseId}/claims`);
}

export async function confirmClaim(caseId: string, revId: string): Promise<Claim> {
  return post<Claim>(`/cases/${caseId}/claims/${revId}/confirm`);
}

export async function rejectClaim(caseId: string, revId: string): Promise<Claim> {
  return post<Claim>(`/cases/${caseId}/claims/${revId}/reject`);
}

export async function editClaim(
  caseId: string,
  revId: string,
  body: { statement?: string; centrality?: string; contract?: Record<string, string>; falsifiable_condition?: string },
): Promise<Claim> {
  return put<Claim>(`/cases/${caseId}/claims/${revId}`, body);
}

export async function splitClaim(
  caseId: string,
  revId: string,
  statements: string[],
): Promise<Claim[]> {
  return post<Claim[]>(`/cases/${caseId}/claims/${revId}/split`, { statements });
}

// -- Scans -----------------------------------------------------------------

export async function startScan(
  caseId: string,
  maxResults = 32,
  analysisLimit = 3,
): Promise<{ scan_id: string; status: string }> {
  return post<{ scan_id: string; status: string }>(`/cases/${caseId}/scans`, {
    max_results: maxResults,
    analysis_limit: analysisLimit,
  });
}

export async function listScans(caseId: string): Promise<ScanStatus[]> {
  return get<ScanStatus[]>(`/cases/${caseId}/scans`);
}

export async function getScanStatus(caseId: string, scanId: string): Promise<ScanStatus> {
  return get<ScanStatus>(`/cases/${caseId}/scans/${scanId}`);
}

export async function cancelScan(
  caseId: string,
  scanId: string,
): Promise<{ scan_id: string; cancelled: boolean }> {
  return del<{ scan_id: string; cancelled: boolean }>(`/cases/${caseId}/scans/${scanId}`);
}

// -- Impacts (papers) ------------------------------------------------------

export async function getImpacts(caseId: string): Promise<Paper[]> {
  return get<Paper[]>(`/cases/${caseId}/impacts`);
}

export async function confirmImpact(caseId: string, impactId: string): Promise<Paper> {
  return post<Paper>(`/cases/${caseId}/impacts/${impactId}/confirm`);
}

export async function dismissImpact(caseId: string, impactId: string): Promise<Paper> {
  return post<Paper>(`/cases/${caseId}/impacts/${impactId}/dismiss`);
}

export async function editImpact(
  caseId: string,
  impactId: string,
  body: Record<string, string | null>,
): Promise<Paper> {
  return put<Paper>(`/cases/${caseId}/impacts/${impactId}`, body);
}

// -- Actions ---------------------------------------------------------------

export async function getActions(caseId: string): Promise<ActionItem[]> {
  return get<ActionItem[]>(`/cases/${caseId}/actions`);
}

export async function updateActionStatus(
  caseId: string,
  actionId: string,
  status: string,
): Promise<ActionItem> {
  return put<ActionItem>(`/cases/${caseId}/actions/${actionId}/status`, { status });
}

// -- Patches / rewrites ----------------------------------------------------

export async function generatePatch(
  caseId: string,
  impactId: string,
): Promise<{ claimId: string; loc: string; before: string; after: string; checks: { label: string; ok: boolean }[] }> {
  const fd = new FormData();
  fd.append('impact_id', impactId);
  return post<{ claimId: string; loc: string; before: string; after: string; checks: { label: string; ok: boolean }[] }>(
    `/cases/${caseId}/patches`,
    fd,
  );
}

export async function approvePatch(
  caseId: string,
  patchId: string,
): Promise<{ claimId: string; before: string; after: string; loc: string }> {
  return post<{ claimId: string; before: string; after: string; loc: string }>(
    `/cases/${caseId}/patches/${patchId}/approve`,
  );
}

export async function rejectPatch(
  caseId: string,
  patchId: string,
): Promise<{ claimId: string; before: string; after: string; loc: string }> {
  return post<{ claimId: string; before: string; after: string; loc: string }>(
    `/cases/${caseId}/patches/${patchId}/reject`,
  );
}

// -- Audit -----------------------------------------------------------------

export async function getAudit(caseId: string): Promise<AuditRec[]> {
  return get<AuditRec[]>(`/cases/${caseId}/audit`);
}

// -- Profile ---------------------------------------------------------------

export async function getProfile(caseId: string): Promise<Project['profile']> {
  return get<Project['profile']>(`/cases/${caseId}/profile`);
}

export async function analyzeProfile(caseId: string): Promise<Project['profile']> {
  return post<Project['profile']>(`/cases/${caseId}/profile/analyze`);
}

// -- Competitors -----------------------------------------------------------

export async function getCompetitors(caseId: string): Promise<CompetitorEntry[]> {
  return get<CompetitorEntry[]>(`/cases/${caseId}/competitors`);
}

export async function addCompetitor(
  caseId: string,
  team: string,
  aliases: string[],
): Promise<{ id: string; team: string; aliases: string[] }> {
  return post<{ id: string; team: string; aliases: string[] }>(`/cases/${caseId}/competitors`, { team, aliases });
}

export async function removeCompetitor(
  caseId: string,
  watchId: string,
): Promise<{ deleted: string }> {
  return del<{ deleted: string }>(`/cases/${caseId}/competitors/${watchId}`);
}

// -- Settings --------------------------------------------------------------

export async function getSettings(): Promise<SettingsData> {
  return get<SettingsData>('/settings');
}

export async function putSettings(updates: Record<string, string>): Promise<{ saved: string[] }> {
  return put<{ saved: string[] }>('/settings', { updates });
}

// ---------------------------------------------------------------------------
// useApi hook — generic data fetcher with loading / error state
// ---------------------------------------------------------------------------

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  const execute = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRef
      .current()
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    const cancel = execute();
    return cancel;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, refetch: execute };
}

// ---------------------------------------------------------------------------
// Fallback helpers — wrap any API call so it degrades to mock data on failure
// ---------------------------------------------------------------------------

/** Try the API; on failure return the fallback value. */
export async function apiOrFallback<T>(apiFn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await apiFn();
  } catch {
    return fallback;
  }
}

/** Return the mock project list (used as default fallback). */
export function getMockProjects(): Project[] {
  return projects;
}

/** Return a mock single project by id. */
export function getMockProject(id: string): Project | undefined {
  return projects.find((p) => p.id === id);
}
