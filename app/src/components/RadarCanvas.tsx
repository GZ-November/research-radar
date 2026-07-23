import { useEffect, useRef } from 'react';

/**
 * Generative hero visual: a radar beam sweeping slowly over a "literature
 * star map" — paper titles drifting as tiny labels among star points.
 */
const TITLES = [
  'RobustRAG', 'SAGE', 'REAR', 'MM-Navigator', 'Voyager-2', 'WebVoyager-X',
  'Self-RAG', 'RAG-Fusion', 'Budget-Aware', 'Perturbation Meta-Analysis',
  'Scaling Memory', 'Agentic Retrieval', 'FreshQA', 'BEIR', 'WebArena',
  'Tool-Use Verification', 'Episodic Memory', 'Dense Retrieval',
];

interface Star {
  x: number;
  y: number;
  r: number;
  tw: number;
  label?: string;
}

export default function RadarCanvas({ className = '' }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    let w = 0;
    let h = 0;
    let stars: Star[] = [];
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // deterministic-ish star field
      stars = [];
      const n = Math.floor((w * h) / 16000);
      let seed = 42;
      const rnd = () => {
        seed = (seed * 16807) % 2147483647;
        return seed / 2147483647;
      };
      for (let i = 0; i < n; i++) {
        stars.push({
          x: rnd() * w,
          y: rnd() * h,
          r: 0.6 + rnd() * 1.4,
          tw: rnd() * Math.PI * 2,
          label: i % 9 === 0 && TITLES.length ? TITLES[(i / 9) % TITLES.length | 0] : undefined,
        });
      }
    };
    resize();
    window.addEventListener('resize', resize);

    const CX = () => w * 0.5;
    const CY = () => h * 0.62;
    const R = () => Math.max(w, h) * 0.55;

    const t0 = performance.now();
    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      ctx.clearRect(0, 0, w, h);

      // faint concentric rings
      ctx.strokeStyle = 'rgba(148, 197, 210, 0.07)';
      ctx.lineWidth = 1;
      for (let i = 1; i <= 4; i++) {
        ctx.beginPath();
        ctx.arc(CX(), CY(), (R() * i) / 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      // stars
      for (const s of stars) {
        const a = 0.25 + 0.55 * (0.5 + 0.5 * Math.sin(t * 1.4 + s.tw));
        ctx.fillStyle = `rgba(214, 231, 236, ${a})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
        if (s.label) {
          ctx.fillStyle = `rgba(148, 197, 210, ${a * 0.5})`;
          ctx.font = '10px "IBM Plex Mono", monospace';
          ctx.fillText(s.label, s.x + 6, s.y + 3);
        }
      }

      // sweeping beam
      const angle = t * 0.28;
      const grad = ctx.createConicGradient
        ? (() => {
            const g = ctx.createConicGradient(angle, CX(), CY());
            g.addColorStop(0, 'rgba(45, 212, 235, 0.20)');
            g.addColorStop(0.06, 'rgba(45, 212, 235, 0.05)');
            g.addColorStop(0.12, 'rgba(45, 212, 235, 0)');
            g.addColorStop(1, 'rgba(45, 212, 235, 0)');
            return g;
          })()
        : null;
      if (grad) {
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(CX(), CY());
        ctx.arc(CX(), CY(), R(), 0, Math.PI * 2);
        ctx.fill();
      }
      // beam leading edge
      ctx.strokeStyle = 'rgba(103, 232, 249, 0.5)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(CX(), CY());
      ctx.lineTo(CX() + Math.cos(angle) * R(), CY() + Math.sin(angle) * R());
      ctx.stroke();

      // center glow
      const rg = ctx.createRadialGradient(CX(), CY(), 0, CX(), CY(), 90);
      rg.addColorStop(0, 'rgba(45, 212, 235, 0.10)');
      rg.addColorStop(1, 'rgba(45, 212, 235, 0)');
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.arc(CX(), CY(), 90, 0, Math.PI * 2);
      ctx.fill();

      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf.current);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
