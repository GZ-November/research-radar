import { NavLink, useNavigate } from 'react-router'
import {
  FileText,
  LayoutDashboard,
  ListChecks,
  Plus,
  Radar,
  Settings,
  Wrench,
} from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { fmtDateTime, latestScan, pendingActionCount } from '@/lib/format'
import { useAppStore } from '@/store/AppStore'

const NAV = [
  { to: '/', label: '项目工作台', icon: LayoutDashboard, end: true },
  { to: '/actions', label: '本周行动', icon: ListChecks, end: false },
  { to: '/radar', label: '文献雷达', icon: Radar, end: false },
  { to: '/ledger', label: '改进工作台', icon: Wrench, end: false },
  { to: '/case', label: '我的论文', icon: FileText, end: false },
  { to: '/settings', label: '设置', icon: Settings, end: false },
]

function GroupLabel({ children }: { children: string }) {
  return (
    <p className="px-2 pt-5 pb-2 t-c2e uppercase tracking-[0.12em] text-side-group">{children}</p>
  )
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { cases, currentCase, setCurrentCase, actionStatus } = useAppStore()
  const navigate = useNavigate()

  const pending = pendingActionCount(currentCase.actions, actionStatus)
  const scan = latestScan(currentCase)
  const lastScanAt = fmtDateTime(scan?.finished_at ?? scan?.started_at)

  return (
    <div className="flex h-full flex-col bg-side text-side-text">
      {/* 品牌块 */}
      <div className="flex items-center gap-2.5 px-4 pt-5 pb-4">
        <div
          aria-hidden
          className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-gradient-to-br from-radar-deep to-radar text-[18px] font-semibold text-white"
        >
          ⌖
        </div>
        <div className="min-w-0">
          <p className="t-b2e tracking-wide text-white">Research Radar</p>
          <p className="t-c1 text-side-sub">文献影响监控 Agent</p>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <GroupLabel>项目</GroupLabel>
        <Select value={currentCase.id} onValueChange={(id) => { setCurrentCase(id) }}>
          <SelectTrigger className="h-9 w-full rounded-[10px] border-white/10 bg-white/[0.04] px-2.5 t-b2e text-side-text hover:bg-white/[0.07] focus:ring-1 focus:ring-kblue [&_svg]:text-side-sub">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="border-sep">
            {cases.map((c) => (
              <SelectItem key={c.id} value={c.id} className="t-b2">
                <span className="block max-w-[210px] truncate">
                  {c.is_demo ? `${c.title} · 示例` : c.title}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="clamp-2 mt-2 px-1 t-c1 leading-[18px] text-side-sub">
          {currentCase.research_question}
        </p>

        {/* 项目状态 pill */}
        <div className="mt-3 px-1">
          {pending > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[rgba(255,149,0,0.16)] px-2.5 py-1 t-c1e text-[#ffb84d]">
              <span className="size-1.5 rounded-full bg-korange" aria-hidden />
              {pending} 项待处理行动
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[rgba(22,196,86,0.16)] px-2.5 py-1 t-c1e text-[#4ade80]">
              <span className="size-1.5 rounded-full bg-kgreen" aria-hidden />
              没有待处理行动
            </span>
          )}
          <p className="mt-2 t-c1 text-side-sub">
            上次扫描：{lastScanAt ?? '尚未扫描'}
          </p>
        </div>

        <button
          onClick={() => { navigate('/'); onNavigate?.() }}
          className="mt-3 flex w-full items-center gap-1.5 rounded-[10px] px-2 py-2 t-b2 text-side-sub transition-colors duration-150 hover:bg-white/[0.06] hover:text-side-text"
        >
          <Plus className="size-4" aria-hidden />
          创建或管理项目
        </button>

        <GroupLabel>导航</GroupLabel>
        <nav className="space-y-0.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center gap-2.5 rounded-[8px] px-2.5 py-2 t-b2 transition-colors duration-150',
                  isActive
                    ? 'bg-side-active font-medium text-white'
                    : 'text-side-sub hover:bg-white/[0.04] hover:text-side-text',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span aria-hidden className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-radar" />
                  )}
                  <Icon className="size-[18px] shrink-0" aria-hidden />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* 底部 LLM 状态 */}
      <div className="border-t border-side-sep px-4 py-3">
        <p className="flex items-center gap-1.5 t-c1 text-side-sub">
          <span className="size-1.5 rounded-full bg-kgreen" aria-hidden />
          分析模型：<span className="font-mono-radar">deepseek-v4-pro</span>
        </p>
      </div>
    </div>
  )
}
