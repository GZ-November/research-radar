import type { Evidence } from '@/types'
import { Mono } from './Typography'

// 证据块：粗体标签 + 引用块（3px teal 左边条、#F0FAFB 底）+ 等宽小字 locator
export function EvidenceBlock({
  label,
  evidence,
}: {
  label: string
  evidence: Evidence | null | undefined
}) {
  return (
    <div>
      <p className="t-b2e text-lp">{label}</p>
      <div className="mt-1.5 rounded-r-[8px] border-l-[3px] border-radar bg-radar-soft px-3 py-2.5">
        {evidence?.quote ? (
          <p className="t-b2 whitespace-pre-wrap text-lp">{evidence.quote}</p>
        ) : (
          <p className="t-b2 text-lt">未登记原文引文</p>
        )}
      </div>
      <Mono className="mt-1 block t-c1 text-lt">{evidence?.locator || '未登记位置'}</Mono>
    </div>
  )
}

// 通用引文块（无标签版本，账本等处复用）
export function QuoteBlock({ quote, locator }: { quote: string | null | undefined; locator?: string | null }) {
  return (
    <div>
      <div className="rounded-r-[8px] border-l-[3px] border-radar bg-radar-soft px-3 py-2.5">
        {quote ? (
          <p className="t-b2 whitespace-pre-wrap text-lp">{quote}</p>
        ) : (
          <p className="t-b2 text-lt">未登记原文引文</p>
        )}
      </div>
      <Mono className="mt-1 block t-c1 text-lt">{locator || '未登记位置'}</Mono>
    </div>
  )
}
