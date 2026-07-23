import { cn } from '@/lib/utils'
import { DOT_COLOR, toneFor, type Tone } from '@/lib/labels'

// 徽章胶囊：spec §3 配色
const TONE_CLS: Record<Tone, string> = {
  red: 'bg-[rgba(255,77,77,0.1)] text-[#c22e3a]',
  orange: 'bg-[rgba(255,149,0,0.1)] text-[#b06800]',
  blue: 'bg-[rgba(23,131,255,0.1)] text-[#0f64cf]',
  green: 'bg-[rgba(22,196,86,0.1)] text-[#0d7a35]',
  yellow: 'bg-[rgba(255,200,0,0.2)] text-[#7a6200]',
  gray: 'bg-black/[0.05] text-ls',
  teal: 'bg-radar-soft text-radar',
}

export function StatusBadge({
  k,
  label,
  tone,
  className,
}: {
  k?: string
  label: string
  tone?: Tone
  className?: string
}) {
  const t = tone ?? (k ? toneFor(k) : 'gray')
  return (
    <span
      className={cn(
        'inline-flex w-fit shrink-0 items-center gap-1 whitespace-nowrap rounded-[4px] px-1.5 py-0.5 t-c1e',
        TONE_CLS[t],
        className,
      )}
    >
      {label}
    </span>
  )
}

export function Dot({ tone, className }: { tone: Tone; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('inline-block size-2 shrink-0 rounded-full', className)}
      style={{ backgroundColor: DOT_COLOR[tone] }}
    />
  )
}
