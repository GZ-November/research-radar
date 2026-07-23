import { useEffect, useState } from 'react';
import RadarCanvas from '../components/RadarCanvas';

const STEPS = ['导入 / 同步文稿', '确认项目 Claim', '搜索最新公开论文', '采用有用影响', '执行实验、数据与写作行动'];

export default function Landing({ onEnter }: { onEnter: () => void }) {
  const [scrolled, setScrolled] = useState(0);
  useEffect(() => {
    const fn = () => setScrolled(Math.min(1, window.scrollY / (window.innerHeight * 0.8)));
    window.addEventListener('scroll', fn, { passive: true });
    return () => window.removeEventListener('scroll', fn);
  }, []);

  return (
    <div className="bg-night text-white min-h-screen relative overflow-x-hidden">
      {/* hero */}
      <section className="relative h-screen flex flex-col">
        <RadarCanvas className="absolute inset-0 w-full h-full" />
        <div className="absolute inset-0 bg-gradient-to-b from-night/30 via-transparent to-night" />

        <header className="relative z-10 flex items-center justify-between px-8 md:px-14 py-7">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-cyan-300 blink-soft" />
            <span className="font-mono text-[11px] tracking-[0.3em] uppercase text-cyan-100/70">Research Radar</span>
          </div>
          <button onClick={onEnter} className="font-mono text-[11px] tracking-[0.2em] uppercase text-white/60 hover:text-white transition-colors duration-300">
            进入工作台 →
          </button>
        </header>

        <div
          className="relative z-10 flex-1 flex flex-col items-center justify-center text-center px-6"
          style={{ transform: `translateY(${scrolled * -90}px)`, opacity: 1 - scrolled * 1.1 }}
        >
          <div className="kicker mb-7 !text-cyan-200/60">Literature Impact Monitor</div>
          <h1 className="display-xl">
            <span className="block tracking-[0.06em]">Research</span>
            <span className="block tracking-[0.06em] text-cyan-100">Radar</span>
          </h1>
          <p className="mt-8 font-serif text-lg md:text-xl text-white/65 tracking-wide">
            盯住公开文献对你论文的影响，把变化变成可执行的行动。
          </p>
          <button onClick={onEnter} className="mt-12 btn-teal !px-8 !py-3 !text-sm tracking-widest">
            进入工作台
          </button>
        </div>

        <div className="relative z-10 pb-8 flex justify-center">
          <div className="font-mono text-[10px] tracking-[0.3em] uppercase text-white/30">Scroll</div>
        </div>
      </section>

      {/* workflow strip */}
      <section className="relative border-t border-white/10 px-8 md:px-14 py-20 max-w-6xl mx-auto">
        <div className="kicker mb-10 !text-cyan-200/60">Workflow</div>
        <ol className="grid md:grid-cols-5 gap-8">
          {STEPS.map((s, i) => (
            <li key={s} className="group">
              <div className="font-serif text-3xl text-white/25 group-hover:text-cyan-200 transition-colors duration-300">
                {String(i + 1).padStart(2, '0')}
              </div>
              <div className="mt-3 text-sm text-white/70 leading-relaxed">{s}</div>
            </li>
          ))}
        </ol>
        <div className="mt-20 flex justify-center">
          <button onClick={onEnter} className="btn-ghost !border-white/20 !text-white/80 hover:!border-cyan-300 hover:!text-cyan-100">
            打开演示项目
          </button>
        </div>
      </section>
    </div>
  );
}
