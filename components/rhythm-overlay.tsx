'use client';

import { useEffect, useRef } from 'react';
import { type Circle, pressRhythm, RHYTHM, rhythm } from '@/lib/rhythm';

// The hive's circles (lib/rhythm.ts), on a canvas of their own over the scene: its motion blur would smear them, and
// they have to be read at a glance. At a quarter of the resolution, drawn up in chunky pixels to sit with the rest.

const PIXEL = 4;
const INK = '#ffb02e';
const HOT = '#fff4d8';
const MISS = '#ff2238';

export function RhythmOverlay() {
  const canvas = useRef<HTMLCanvasElement>(null);

  // A click on a circle, wherever it is: nothing else is under them.
  useEffect(() => {
    const down = (e: PointerEvent) => {
      if (!rhythm.active) return;
      const radius = Math.min(window.innerWidth, window.innerHeight) * 0.085;
      let best: Circle | null = null;
      for (const c of rhythm.circles) {
        const d = Math.hypot(e.clientX - c.x * window.innerWidth, e.clientY - c.y * window.innerHeight);
        if (d < radius * 1.5 && (!best || c.at < best.at)) best = c;
      }
      if (best) pressRhythm(best);
    };
    window.addEventListener('pointerdown', down, { capture: true, passive: true });
    return () => window.removeEventListener('pointerdown', down, { capture: true });
  }, []);

  useEffect(() => {
    let raf = 0;
    let dirty = false;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const el = canvas.current;
      const g = el?.getContext('2d');
      if (!el || !g) return;
      const w = Math.ceil(window.innerWidth / PIXEL);
      const h = Math.ceil(window.innerHeight / PIXEL);
      if (el.width !== w || el.height !== h) {
        el.width = w;
        el.height = h;
      }
      const busy = rhythm.active || rhythm.bursts.length > 0 || rhythm.slow < 1;
      if (!busy && !dirty) return;
      g.clearRect(0, 0, w, h);
      dirty = busy;
      const unit = Math.min(w, h);
      const r = unit * 0.085;
      // The ride slowing to a stop: the scene dims behind the circle waiting on a click.
      if (rhythm.slow < 1) {
        g.fillStyle = `rgba(4, 2, 2, ${0.5 * (1 - rhythm.slow)})`;
        g.fillRect(0, 0, w, h);
      }
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      const beat = 0.5 + 0.5 * Math.sin(performance.now() / 120);
      // (Latest first, so the next to land is on top.)
      for (const c of [...rhythm.circles].reverse()) {
        const x = c.x * w;
        const y = c.y * h;
        const left = (c.at - rhythm.clock) / RHYTHM.approach;
        const shown = Math.min(1, (1 - left) * 4);
        g.globalAlpha = Math.max(0, shown);
        g.fillStyle = 'rgba(10, 5, 2, 0.72)';
        g.beginPath();
        g.arc(x, y, r, 0, Math.PI * 2);
        g.fill();
        g.lineWidth = Math.max(2, r * 0.16);
        g.strokeStyle = HOT;
        g.beginPath();
        g.arc(x, y, r, 0, Math.PI * 2);
        g.stroke();
        // The ring closing on it.
        g.lineWidth = Math.max(1.5, r * 0.11);
        g.strokeStyle = INK;
        g.beginPath();
        g.arc(x, y, r * (1 + 2.3 * Math.max(0, left)), 0, Math.PI * 2);
        g.stroke();
        g.fillStyle = HOT;
        g.font = `bold ${Math.round(r * 0.95)}px ui-monospace, Menlo, monospace`;
        g.fillText(String(c.number), x, y + 1);
        // Showing what's wanted: pulsing rings out from it, and the word.
        if (rhythm.teaching) {
          g.strokeStyle = INK;
          g.lineWidth = 1.5;
          g.globalAlpha = 0.35 + 0.65 * beat;
          g.beginPath();
          g.arc(x, y, r * (1.25 + 0.2 * beat), 0, Math.PI * 2);
          g.stroke();
          g.globalAlpha = 1;
          g.fillStyle = HOT;
          g.font = `bold ${Math.round(r * 0.7)}px ui-monospace, Menlo, monospace`;
          g.fillText('CLICK!', x, y + r * 1.95);
        }
      }
      g.globalAlpha = 1;
      for (const b of rhythm.bursts) {
        const x = b.x * w;
        const y = b.y * h;
        const t = b.age / 0.6;
        g.globalAlpha = 1 - t;
        if (b.kind === 'miss') {
          g.strokeStyle = MISS;
          g.lineWidth = Math.max(2, r * 0.2);
          const k = r * 0.55;
          g.beginPath();
          g.moveTo(x - k, y - k);
          g.lineTo(x + k, y + k);
          g.moveTo(x + k, y - k);
          g.lineTo(x - k, y + k);
          g.stroke();
        } else {
          g.strokeStyle = b.kind === 'perfect' ? HOT : INK;
          g.lineWidth = Math.max(1.5, r * 0.28 * (1 - t));
          g.beginPath();
          g.arc(x, y, r * (1 + 1.5 * t), 0, Math.PI * 2);
          g.stroke();
          if (t < 0.25) {
            g.fillStyle = HOT;
            g.beginPath();
            g.arc(x, y, r * (1 - t * 2), 0, Math.PI * 2);
            g.fill();
          }
        }
      }
      g.globalAlpha = 1;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />;
}
