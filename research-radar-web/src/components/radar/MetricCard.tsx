import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

// 白卡 + 发丝边框，小标签 + 大数值（Hero 数字指标 28–32px，reading/display 扩展）
export function MetricCard({
  label,
  value,
  tone = 'default',
  sub,
  className,
}: {
  label: string
  value: ReactNode
  tone?: 'default' | 'red' | 'orange' | 'green' | 'blue' | 'teal'
  sub?: ReactNode
  className?: string
}) {
  const toneCls: Record<string, string> = {
    default: 'text-lp',
    red: 'text-[#c22e3a]',
    orange: 'text-[#b06800]',
    green: 'text-[#0d7a35]',
    blue: 'text-[#0f64cf]',
    teal: 'text-radar',
  }
  return (
    <div
      className={cn(
        'rounded-[12px] border border-sep bg-white px-4 py-3',
        'transition-shadow duration-150 ease-radar hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)]',
        className,
      )}
    >
      <p className="t-c1 text-lt">{label}</p>
      <p className={cn('mt-1 font-mono-radar text-[28px] font-semibold leading-8 tabular-nums', toneCls[tone])}>
        {value}
      </p>
      {sub ? <p className="mt-0.5 t-c1 text-lt">{sub}</p> : null}
    </div>
  )
}
