import type { Source } from '@/types'
import { PUBLICATION_TYPE } from '@/lib/labels'
import { venueLine } from '@/lib/format'

// 溯源块（各处复用）：标题链接 + 载体行 + 作者 + 链接行
export function SourceTraceability({ source }: { source: Source }) {
  const pubLabel = (t: string | null) => (t ? PUBLICATION_TYPE[t] ?? '公开论文' : '公开论文')
  const links: React.ReactNode[] = []
  if (source.url) {
    links.push(
      <a key="url" href={source.url} target="_blank" rel="noreferrer" className="text-radar hover:underline">
        查看原文
      </a>,
    )
  }
  if (source.pdf_url) {
    links.push(
      <a key="pdf" href={source.pdf_url} target="_blank" rel="noreferrer" className="text-radar hover:underline">
        打开 PDF 全文
      </a>,
    )
  }
  return (
    <div className="min-w-0">
      {source.url ? (
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="clamp-2 t-b2e text-lp hover:text-radar hover:underline"
        >
          {source.title}
        </a>
      ) : (
        <p className="clamp-2 t-b2e text-lp">{source.title}</p>
      )}
      <p className="mt-1 t-c1 text-lt">发表载体：{venueLine(source, pubLabel)}</p>
      {source.authors.length > 0 ? (
        <p className="mt-0.5 t-c1 text-lt">作者：{source.authors.join(', ')}</p>
      ) : null}
      <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 t-c1 text-lt">
        {links.map((el, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden>·</span>}
            {el}
          </span>
        ))}
        {source.doi ? (
          <span className="flex items-center gap-1.5">
            {(links.length > 0) && <span aria-hidden>·</span>}
            <a
              href={`https://doi.org/${source.doi}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono-radar text-radar hover:underline"
            >
              DOI: {source.doi}
            </a>
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            {links.length > 0 && <span aria-hidden>·</span>}
            <span>DOI：未登记</span>
          </span>
        )}
      </p>
    </div>
  )
}
