import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export type CalloutKind = 'info' | 'success' | 'warning' | 'error'

const KIND_CLS: Record<CalloutKind, { box: string; icon: typeof Info }> = {
  info: { box: 'bg-[rgba(23,131,255,0.1)] text-[#123a5c]', icon: Info },
  success: { box: 'bg-[rgba(22,196,86,0.1)] text-[#0d5426]', icon: CheckCircle2 },
  warning: { box: 'bg-[rgba(255,149,0,0.1)] text-[#6b3d00]', icon: AlertTriangle },
  error: { box: 'bg-[rgba(255,77,77,0.1)] text-[#8c1f28]', icon: XCircle },
}

export function Callout({
  kind = 'info',
  children,
  className,
}: {
  kind?: CalloutKind
  children: ReactNode
  className?: string
}) {
  const { box, icon: Icon } = KIND_CLS[kind]
  return (
    <div
      role={kind === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2 rounded-[10px] px-3 py-2.5 t-b2', box, className)}
    >
      <Icon className="mt-0.5 size-[18px] shrink-0 opacity-80" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
