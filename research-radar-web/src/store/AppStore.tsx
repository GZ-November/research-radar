import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import seed from '@/data/seed.json'
import type {
  ActionStatus,
  ApprovalState,
  Case,
  Impact,
  ImpactMode,
  RadarAction,
  ReviewState,
  Seed,
  SuggestedAction,
  WatchEntity,
} from '@/types'

const DATA = seed as unknown as Seed

export interface ImpactDecision {
  review_state: Extract<ReviewState, 'confirmed' | 'edited' | 'dismissed'>
  note?: string
  impact_mode?: ImpactMode
  suggested_action?: SuggestedAction
}

export interface ClaimOverride {
  review_state?: ReviewState
  statement?: string
  centrality?: 'core' | 'major' | 'minor'
  falsifiable_condition?: string
}

export interface SettingsState {
  mode: 'remote' | 'local'
  provider: string
  baseUrl: string
  modelName: string
  apiKey: string
  localModel: string
  ollamaUrl: string
  embedProvider: 'off' | 'ollama' | 'openai'
  embedModel: string
  embedOllamaUrl: string
  embedOpenaiModel: string
  embedOpenaiBase: string
  embedOpenaiKey: string
  crossrefEmail: string
}

const DEFAULT_SETTINGS: SettingsState = {
  mode: 'remote',
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  modelName: 'deepseek-chat',
  apiKey: '',
  localModel: 'qwen3:4b',
  ollamaUrl: 'http://127.0.0.1:11434',
  embedProvider: 'off',
  embedModel: 'qwen3-embedding:0.6b',
  embedOllamaUrl: 'http://127.0.0.1:11434',
  embedOpenaiModel: 'text-embedding-3-small',
  embedOpenaiBase: 'https://api.openai.com/v1',
  embedOpenaiKey: '',
  crossrefEmail: '',
}

interface PersistedState {
  currentCaseId: string
  impactDecisions: Record<string, ImpactDecision>
  actionStatuses: Record<string, ActionStatus>
  claimOverrides: Record<string, ClaimOverride>
  patchApprovals: Record<string, ApprovalState>
  addedWatch: Record<string, WatchEntity[]>
  removedWatch: Record<string, string[]>
  settings: SettingsState
}

interface ConfirmRequest {
  title: string
  actionName: string
  description: string
  confirmLabel: string
  danger?: boolean
}

interface AppStore {
  cases: Case[]
  currentCase: Case
  currentCaseId: string
  setCurrentCase: (id: string) => void

  impactState: (i: Impact) => ReviewState
  decideImpact: (impact: Impact, decision: ImpactDecision) => void
  impactDecisions: Record<string, ImpactDecision>

  actionStatus: (a: RadarAction) => ActionStatus
  setActionStatus: (id: string, status: ActionStatus) => void

  claimOverride: (revisionId: string) => ClaimOverride | undefined
  setClaimOverride: (revisionId: string, o: ClaimOverride) => void

  patchApproval: (id: string, fallback: ApprovalState) => ApprovalState
  setPatchApproval: (id: string, s: ApprovalState) => void

  watchEntities: (caseId: string) => WatchEntity[]
  addWatch: (caseId: string, e: WatchEntity) => void
  removeWatch: (caseId: string, id: string) => void

  resetDemo: () => void

  settings: SettingsState
  saveSettings: (s: SettingsState) => void

  focusImpactId: string | null
  setFocusImpactId: (id: string | null) => void

  confirm: (req: Omit<ConfirmRequest, 'title'>) => Promise<boolean>
  confirmState: (ConfirmRequest & { resolve: (v: boolean) => void }) | null
  resolveConfirm: (v: boolean) => void
}

const Ctx = createContext<AppStore | null>(null)

const LS_KEY = 'research-radar-state-v1'

function loadPersisted(): PersistedState {
  const base: PersistedState = {
    currentCaseId: DATA.cases[0]?.id ?? '',
    impactDecisions: {},
    actionStatuses: {},
    claimOverrides: {},
    patchApprovals: {},
    addedWatch: {},
    removedWatch: {},
    settings: DEFAULT_SETTINGS,
  }
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return base
    const parsed = JSON.parse(raw) as Partial<PersistedState>
    return { ...base, ...parsed, settings: { ...DEFAULT_SETTINGS, ...(parsed.settings ?? {}) } }
  } catch {
    return base
  }
}

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PersistedState>(loadPersisted)
  const [focusImpactId, setFocusImpactId] = useState<string | null>(null)
  const [confirmState, setConfirmState] = useState<
    (ConfirmRequest & { resolve: (v: boolean) => void }) | null
  >(null)
  const confirmOpen = useRef(false)

  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(state))
    } catch {
      // 存储失败时忽略（演示环境）
    }
  }, [state])

  const currentCase = useMemo(
    () => DATA.cases.find((c) => c.id === state.currentCaseId) ?? DATA.cases[0],
    [state.currentCaseId],
  )

  const setCurrentCase = useCallback((id: string) => {
    setState((s) => ({ ...s, currentCaseId: id }))
    setFocusImpactId(null)
  }, [])

  const impactState = useCallback(
    (i: Impact): ReviewState => state.impactDecisions[i.id]?.review_state ?? i.review_state,
    [state.impactDecisions],
  )

  const decideImpact = useCallback((impact: Impact, decision: ImpactDecision) => {
    setState((s) => {
      const actionStatuses = { ...s.actionStatuses }
      // 采用 → 相关行动转为可执行（open）；不采用 → 关闭相关行动
      for (const c of DATA.cases) {
        for (const a of c.actions) {
          if (a.impact_candidate_id !== impact.id) continue
          if (decision.review_state === 'dismissed') {
            actionStatuses[a.id] = 'dismissed'
          } else {
            const cur = actionStatuses[a.id] ?? a.status
            if (cur === 'proposed' || cur === 'dismissed') actionStatuses[a.id] = 'open'
          }
        }
      }
      return {
        ...s,
        impactDecisions: { ...s.impactDecisions, [impact.id]: decision },
        actionStatuses,
      }
    })
  }, [])

  const actionStatus = useCallback(
    (a: RadarAction): ActionStatus => state.actionStatuses[a.id] ?? a.status,
    [state.actionStatuses],
  )

  const setActionStatus = useCallback((id: string, status: ActionStatus) => {
    setState((s) => ({ ...s, actionStatuses: { ...s.actionStatuses, [id]: status } }))
  }, [])

  const claimOverride = useCallback(
    (revisionId: string) => state.claimOverrides[revisionId],
    [state.claimOverrides],
  )

  const setClaimOverride = useCallback((revisionId: string, o: ClaimOverride) => {
    setState((s) => ({
      ...s,
      claimOverrides: {
        ...s.claimOverrides,
        [revisionId]: { ...s.claimOverrides[revisionId], ...o },
      },
    }))
  }, [])

  const patchApproval = useCallback(
    (id: string, fallback: ApprovalState): ApprovalState => state.patchApprovals[id] ?? fallback,
    [state.patchApprovals],
  )

  const setPatchApproval = useCallback((id: string, st: ApprovalState) => {
    setState((s) => ({ ...s, patchApprovals: { ...s.patchApprovals, [id]: st } }))
  }, [])

  const watchEntities = useCallback(
    (caseId: string): WatchEntity[] => {
      const c = DATA.cases.find((x) => x.id === caseId)
      const removed = new Set(state.removedWatch[caseId] ?? [])
      const base = (c?.watch_entities ?? []).filter((w) => !removed.has(w.id))
      return [...base, ...(state.addedWatch[caseId] ?? [])]
    },
    [state.addedWatch, state.removedWatch],
  )

  const addWatch = useCallback((caseId: string, e: WatchEntity) => {
    setState((s) => ({
      ...s,
      addedWatch: { ...s.addedWatch, [caseId]: [...(s.addedWatch[caseId] ?? []), e] },
    }))
  }, [])

  const removeWatch = useCallback((caseId: string, id: string) => {
    setState((s) => {
      const added = (s.addedWatch[caseId] ?? []).filter((w) => w.id !== id)
      return {
        ...s,
        addedWatch: { ...s.addedWatch, [caseId]: added },
        removedWatch: {
          ...s.removedWatch,
          [caseId]: [...(s.removedWatch[caseId] ?? []), id],
        },
      }
    })
  }, [])

  const resetDemo = useCallback(() => {
    const demo = DATA.cases.find((c) => c.is_demo)
    if (!demo) return
    const impactIds = new Set(demo.impacts.map((i) => i.id))
    const actionIds = new Set(demo.actions.map((a) => a.id))
    setState((s) => ({
      ...s,
      impactDecisions: Object.fromEntries(
        Object.entries(s.impactDecisions).filter(([k]) => !impactIds.has(k)),
      ),
      actionStatuses: Object.fromEntries(
        Object.entries(s.actionStatuses).filter(([k]) => !actionIds.has(k)),
      ),
      patchApprovals: Object.fromEntries(
        Object.entries(s.patchApprovals).filter(
          ([k]) => !demo.patches.some((p) => p.id === k),
        ),
      ),
    }))
  }, [])

  const saveSettings = useCallback((settings: SettingsState) => {
    setState((s) => ({ ...s, settings }))
  }, [])

  const confirm = useCallback((req: Omit<ConfirmRequest, 'title'>) => {
    return new Promise<boolean>((resolve) => {
      // 不叠加对话框：已有打开的确认时直接替换内容
      confirmOpen.current = true
      setConfirmState({ title: '操作确认', ...req, resolve })
    })
  }, [])

  const resolveConfirm = useCallback((v: boolean) => {
    setConfirmState((cur) => {
      cur?.resolve(v)
      return null
    })
    confirmOpen.current = false
  }, [])

  const value: AppStore = {
    cases: DATA.cases,
    currentCase,
    currentCaseId: currentCase.id,
    setCurrentCase,
    impactState,
    decideImpact,
    impactDecisions: state.impactDecisions,
    actionStatus,
    setActionStatus,
    claimOverride,
    setClaimOverride,
    patchApproval,
    setPatchApproval,
    watchEntities,
    addWatch,
    removeWatch,
    resetDemo,
    settings: state.settings,
    saveSettings,
    focusImpactId,
    setFocusImpactId,
    confirm,
    confirmState,
    resolveConfirm,
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAppStore(): AppStore {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAppStore must be used within AppStoreProvider')
  return v
}
