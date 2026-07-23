import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './Button'

// 虚线边框卡片、居中图标 + 粗体标题 + muted 提示
export function EmptyState({
  icon: Icon,
  title,
  hint,
  action,
  className,
}: {
  icon: LucideIcon
  title: string
  hint?: string
  action?: { label: string; onClick: () => void; icon?: LucideIcon }
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed border-sep bg-white px-6 py-12 text-center',
        className,
      )}
    >
      <Icon className="size-8 text-lq" aria-hidden />
      <p className="mt-1 t-b1e text-lp">{title}</p>
      {hint ? <p className="max-w-md t-b2 text-ls">{hint}</p> : null}
      {action ? (
        <Button className="mt-3" size={44} onClick={action.onClick} leftIcon={action.icon ? <action.icon /> : undefined}>
          {action.label}
        </Button>
      ) : null}
    </div>
  )
}
