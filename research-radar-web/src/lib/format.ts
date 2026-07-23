// 格式化与派生逻辑工具
import type {
  Case,
  Claim,
  Impact,
  RadarAction,
  ReviewState,
  Source,
} from '@/types'

// "2026-07-22 12:33:58.596348" 或 ISO → Date
export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null
  const norm = s.includes('T') ? s : s.replace(' ', 'T')
  const d = new Date(norm)
  return Number.isNaN(d.getTime()) ? null : d
}

function pad(n: number) {
  return String(n).padStart(2, '0')
}

export function fmtDate(s: string | null | undefined): string | null {
  const d = parseDate(s)
  if (!d) return null
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function fmtDateTime(s: string | null | undefined): string | null {
  const d = parseDate(s)
  if (!d) return null
  return `${fmtDate(s)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 客户端下载
export function downloadText(filename: string, content: string, mime = 'text/markdown') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 溯源载体行：venue 空或 arxiv → `arXiv 预印本`，否则 `{venue} · {类型标签}`
export function venueLine(source: Source, pubTypeLabel: (t: string | null) => string): string {
  const date = fmtDate(source.published_at) ?? '日期未登记'
  const venue = source.venue?.trim()
  const head = !venue || venue.toLowerCase() === 'arxiv'
    ? 'arXiv 预印本'
    : `${venue} · ${pubTypeLabel(source.publication_type)}`
  return `${head} · 公开日期：${date}`
}

// 最新确认 revision
export function confirmedRevision(claim: Claim) {
  const revs = [...claim.revisions].sort((a, b) => b.revision_no - a.revision_no)
  return revs.find((r) => r.review_state === 'confirmed' || r.review_state === 'edited') ?? null
}

export function currentRevision(claim: Claim) {
  const revs = [...claim.revisions].sort((a, b) => b.revision_no - a.revision_no)
  return revs[0] ?? null
}

export function currentVersion(c: Case) {
  return c.versions.find((v) => v.is_current) ?? c.versions[c.versions.length - 1] ?? null
}

export function latestScan(c: Case) {
  if (c.latest_scan_id) {
    const found = c.scans.find((s) => s.id === c.latest_scan_id)
    if (found) return found
  }
  return c.scans[0] ?? null
}

export function latestCompletedScan(c: Case) {
  return c.scans.find((s) => s.status === 'completed') ?? null
}

// Claim 自动 Radar 关注（attention）：由该 claim 的影响推导
export function claimAttention(claimKey: string, impacts: Impact[], stateOf: (i: Impact) => ReviewState): string {
  const mine = impacts.filter((i) => i.claim_stable_key === claimKey)
  const confirmed = mine.filter((i) => ['confirmed', 'edited'].includes(stateOf(i)))
  if (confirmed.some((i) => i.impact_mode === 'research_integrity' || i.event_type === 'retraction'))
    return 'revalidation_required'
  if (confirmed.some((i) => i.stance === 'challenges')) return 'disputed'
  if (mine.some((i) => i.strategic_flags.includes('competitor'))) return 'competitor_pressure'
  if (mine.some((i) => stateOf(i) === 'candidate')) return 'needs_review'
  if (confirmed.some((i) => i.stance === 'supports')) return 'new_support'
  return 'stable'
}

// Claim Health（仅人工确认推导）
export function claimHealth(claimKey: string, impacts: Impact[], stateOf: (i: Impact) => ReviewState): string {
  const mine = impacts.filter(
    (i) => i.claim_stable_key === claimKey && ['confirmed', 'edited'].includes(stateOf(i)),
  )
  if (mine.some((i) => i.impact_mode === 'research_integrity' || i.event_type === 'retraction'))
    return 'revalidation_required'
  if (mine.some((i) => i.stance === 'challenges')) return 'contested'
  if (mine.some((i) => i.stance === 'supports')) return 'corroborated'
  return 'active'
}

// 待处理行动数（proposed/open/in_progress）
export function pendingActionCount(actions: RadarAction[], statusOf: (a: RadarAction) => string): number {
  return actions.filter((a) => ['proposed', 'open', 'in_progress'].includes(statusOf(a))).length
}

const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

export function sortActions(actions: RadarAction[], statusOf: (a: RadarAction) => string) {
  return [...actions].sort((a, b) => {
    const sa = statusOf(a) === 'dismissed' ? 1 : 0
    const sb = statusOf(b) === 'dismissed' ? 1 : 0
    if (sa !== sb) return sa - sb
    return (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9)
  })
}

export const SEVERITY_ORDER: Record<string, number> = { critical: 0, review: 1, informative: 2 }

export function sortImpacts(impacts: Impact[]) {
  return [...impacts].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9),
  )
}
