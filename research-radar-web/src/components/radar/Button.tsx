import { Loader2 } from 'lucide-react'
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

// Kimi Web Button 契约：variants primary/secondary/outline，sizes 26/32/44，danger，loading
type Variant = 'primary' | 'secondary' | 'outline' | 'ghost'
type Size = 26 | 32 | 44

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  danger?: boolean
  loading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const SIZE_CLS: Record<Size, string> = {
  26: 'h-[26px] min-w-[52px] rounded-[8px] px-2 t-c1e gap-0.5 [&_svg]:size-4',
  32: 'h-8 min-w-[62px] rounded-[10px] px-2.5 t-b2e gap-1 [&_svg]:size-[18px]',
  44: 'h-11 min-w-[72px] rounded-[12px] px-3.5 t-t2e gap-1.5 [&_svg]:size-5',
}

const VARIANT_CLS: Record<Variant, string> = {
  // 品牌深青主按钮
  primary: 'bg-radar text-white hover:bg-radar-hover',
  // fills.f1 / hover fills.f2
  secondary: 'bg-black/[0.03] text-lp hover:bg-black/[0.05]',
  // 0.5px 发丝描边
  outline: 'bg-white border border-sep text-lp hover:bg-black/[0.03]',
  ghost: 'bg-transparent text-lp hover:bg-black/[0.05]',
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  {
    variant = 'primary',
    size = 32,
    danger = false,
    loading = false,
    disabled,
    leftIcon,
    rightIcon,
    className,
    children,
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading
  return (
    <button
      ref={ref}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap outline-none',
        'transition-[background-color,color,transform,opacity] duration-150 ease-radar',
        'active:scale-[0.97]',
        'disabled:pointer-events-none disabled:text-lq',
        variant === 'secondary' || variant === 'outline' || variant === 'ghost'
          ? 'disabled:bg-black/[0.03] disabled:hover:bg-black/[0.03]'
          : '',
        SIZE_CLS[size],
        danger
          ? variant === 'primary'
            ? 'bg-kred text-white hover:bg-[#f73647]'
            : cn(VARIANT_CLS[variant], 'text-[#d63040]')
          : VARIANT_CLS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className="animate-spin" aria-hidden />
      ) : (
        leftIcon ?? null
      )}
      {children}
      {rightIcon ?? null}
    </button>
  )
})
