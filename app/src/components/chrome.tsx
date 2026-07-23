import { useEffect, useRef, useState, type ReactNode } from 'react';

/* ---------- scroll reveal ---------- */
export function Reveal({ children, delay = 0, className = '' }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ob = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          ob.disconnect();
        }
      },
      { threshold: 0.08 },
    );
    ob.observe(el);
    return () => ob.disconnect();
  }, []);
  return (
    <div ref={ref} className={`reveal ${inView ? 'in' : ''} ${className}`} style={{ ['--reveal-delay' as string]: `${delay}ms` }}>
      {children}
    </div>
  );
}

/* ---------- section heading ---------- */
export function SectionHead({ kicker, title, right }: { kicker?: string; title: string; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-6">
      <div>
        {kicker && <div className="kicker mb-2">{kicker}</div>}
        <h2 className="display-md">{title}</h2>
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/* ---------- stat ---------- */
export function Stat({ value, label, tone = 'ink' }: { value: ReactNode; label: string; tone?: 'ink' | 'red' | 'teal' | 'orange' }) {
  const color = tone === 'red' ? 'text-[#B42318]' : tone === 'orange' ? 'text-[#B54708]' : tone === 'teal' ? 'text-teal' : 'text-ink';
  return (
    <div>
      <div className={`num-display ${color}`}>{value}</div>
      <div className="mt-1.5 text-xs text-neutral-500 tracking-wide">{label}</div>
    </div>
  );
}

/* ---------- quote block with locator ---------- */
export function Quote({ children, loc, against = false, label }: { children: ReactNode; loc?: string; against?: boolean; label?: string }) {
  return (
    <figure>
      {label && <div className="locator mb-1.5 uppercase">{label}</div>}
      <blockquote className={`quote ${against ? 'quote-against' : ''}`}>{children}</blockquote>
      {loc && <figcaption className="locator mt-1.5 pl-4">{loc}</figcaption>}
    </figure>
  );
}

/* ---------- underline tabs ---------- */
export function Tabs({ tabs, active, onChange }: { tabs: string[]; active: number; onChange: (i: number) => void }) {
  return (
    <div className="flex flex-wrap hairline-b mb-6">
      {tabs.map((t, i) => (
        <button key={t} className={`tab-btn ${i === active ? 'active' : ''}`} onClick={() => onChange(i)}>
          {t}
        </button>
      ))}
    </div>
  );
}

/* ---------- tiny progress ring / dot ---------- */
export function Dot({ cls }: { cls: string }) {
  return <span className={`inline-block w-[7px] h-[7px] rounded-full ${cls}`} />;
}

/* ---------- empty state ---------- */
export function Empty({ text }: { text: string }) {
  return (
    <div className="citation-texture rounded-lg border border-dashed border-hairline py-14 text-center">
      <div className="font-serif italic text-neutral-300 text-3xl select-none">§ ¶ †</div>
      <div className="mt-3 text-sm text-neutral-400">{text}</div>
    </div>
  );
}

/* ---------- priority badge ---------- */
export function Priority({ p }: { p: 'P0' | 'P1' | 'P2' }) {
  const cls = p === 'P0' ? 'badge-red' : p === 'P1' ? 'badge-orange' : 'badge-gray';
  return <span className={`${cls} font-mono`}>{p}</span>;
}
