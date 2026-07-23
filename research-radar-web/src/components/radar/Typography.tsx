import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-3', className)}>
      <div className="min-w-0">
        <h1 className="t-largeTitle text-lp">{title}</h1>
        {subtitle ? <p className="mt-1 t-b2 text-ls">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function SectionTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn('t-t2e text-lp', className)}>{children}</h2>
}

export function SubNote({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('t-c1 text-lt', className)}>{children}</p>
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('font-mono-radar', className)}>{children}</span>
}
