'use client';

import { useEffect, useRef } from 'react';
import { TRACE, trace } from '@/lib/trace';

// The chrome city's trail of light and its star (lib/trace.ts), on a canvas of its own over the scene: the motion blur would
// smear it, and it has to be followed. At half resolution, so it's thin but still sits with the pixels of the rest.

const PIXEL = 2;

type Mote = { x: number; y: number; vx: number; vy: number; age: number; life: number; hue: number; size: number };

export function TraceOverlay() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const move = (e: PointerEvent) => {
      trace.px = e.clientX;
      trace.py = e.clientY;
    };
    // (While it's being taught it can be let go of and taken up again, anywhere.)
    const down = (e: PointerEvent) => {
      trace.down = true;
      move(e);
    };
    const up = () => {
      if (trace.teaching) trace.down = false;
    };
    window.addEventListener('pointermove', move, { capture: true, passive: true });
    window.addEventListener('pointerdown', down, { capture: true, passive: true });
    window.addEventListener('pointerup', up, { capture: true, passive: true });
    return () => {
      window.removeEventListener('pointermove', move, { capture: true });
      window.removeEventListener('pointerdown', down, { capture: true });
      window.removeEventListener('pointerup', up, { capture: true });
    };
  }, []);

  useEffect(() => {
    let raf = 0;
    let dirty = false;
    let last = performance.now();
    const motes: Mote[] = [];
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
      const stamp = performance.now();
      const dt = Math.min(0.05, (stamp - last) / 1000);
      last = stamp;
      const busy = trace.active || trace.dying > 0 || motes.length > 0;
      if (!busy && !dirty) return;
      dirty = busy;
      g.clearRect(0, 0, w, h);
      if (!busy) return;
      const now = stamp / 1000;
      const fade = trace.active ? 1 : trace.dying;
      const built = Math.min(1, trace.held / TRACE.build);
      const list = trace.trail;
      g.globalCompositeOperation = 'lighter';
      g.lineCap = 'round';
      // The trail: a thin bright thread in a wide soft glow, its colours sliding along it, gone by its tail.
      const lost = trace.lost && !trace.active;
      for (let i = 1; i < list.length; i++) {
        const a = list[i - 1];
        const b = list[i];
        const life = 1 - b.age / TRACE.trail;
        if (life <= 0) continue;
        const hue = lost ? 350 : (now * 90 + i * 2.2) % 360;
        g.beginPath();
        g.moveTo(a.x / PIXEL, a.y / PIXEL);
        g.lineTo(b.x / PIXEL, b.y / PIXEL);
        g.strokeStyle = `hsla(${hue}, 100%, 65%, ${life * life * 0.09 * fade})`;
        g.lineWidth = 16 + 16 * built;
        g.stroke();
        g.strokeStyle = `hsla(${hue}, 100%, 72%, ${life * life * 0.32 * fade})`;
        g.lineWidth = 5;
        g.stroke();
        g.strokeStyle = `hsla(${hue}, 100%, 92%, ${life * fade})`;
        g.lineWidth = 1.2;
        g.stroke();
      }
      // Stardust, shed off the star and drifting down its trail, twinkling.
      if (trace.active) {
        const n = 1 + Math.floor(built * 3);
        for (let i = 0; i < n; i++) {
          motes.push({
            x: trace.x / PIXEL + (Math.random() - 0.5) * 8,
            y: trace.y / PIXEL + (Math.random() - 0.5) * 8,
            vx: (Math.random() - 0.5) * 34,
            vy: (Math.random() - 0.25) * 30,
            age: 0,
            life: 0.7 + Math.random() * 1.1,
            hue: (now * 90 + Math.random() * 120) % 360,
            size: 0.8 + Math.random() * 1.8,
          });
        }
      }
      for (let i = motes.length - 1; i >= 0; i--) {
        const m = motes[i];
        m.age += dt;
        if (m.age > m.life || motes.length > 320) {
          motes.splice(i, 1);
          continue;
        }
        m.x += m.vx * dt;
        m.y += m.vy * dt;
        m.vy += 14 * dt;
        const k = (1 - m.age / m.life) * (0.55 + 0.45 * Math.sin(now * 24 + m.hue));
        g.fillStyle = `hsla(${m.hue}, 100%, 84%, ${Math.max(0, k)})`;
        const s = m.size;
        g.fillRect(m.x - s / 2, m.y - s / 2, s, s);
        // (The bigger ones, a little cross.)
        if (s > 1.8) {
          g.fillRect(m.x - s * 1.6, m.y - 0.4, s * 3.2, 0.8);
          g.fillRect(m.x - 0.4, m.y - s * 1.6, 0.8, s * 3.2);
        }
      }
      // The star at its end: four long points in a wide coloured halo, long flares across it, swelling as it builds; red when
      // the pointer's off it (and, being taught, it waits).
      if (trace.active) {
        const x = trace.x / PIXEL;
        const y = trace.y / PIXEL;
        const pulse = 1 + 0.14 * Math.sin(now * 7);
        const R = (20 + 14 * built) * pulse;
        const turn = now * 0.9;
        const on = trace.on && trace.down;
        const hue = on ? (now * 90) % 360 : 350;
        const halo = g.createRadialGradient(x, y, 0, x, y, R * 4);
        halo.addColorStop(0, `hsla(${hue}, 100%, 82%, 0.85)`);
        halo.addColorStop(0.18, `hsla(${(hue + 40) % 360}, 100%, 66%, 0.34)`);
        halo.addColorStop(0.55, `hsla(${(hue + 90) % 360}, 100%, 60%, 0.08)`);
        halo.addColorStop(1, 'hsla(0, 0%, 0%, 0)');
        g.fillStyle = halo;
        g.fillRect(x - R * 4, y - R * 4, R * 8, R * 8);
        // Long thin flares, as through a lens.
        const flare = g.createLinearGradient(x - R * 5, y, x + R * 5, y);
        flare.addColorStop(0, 'hsla(0, 0%, 0%, 0)');
        flare.addColorStop(0.5, `hsla(${hue}, 100%, 90%, 0.9)`);
        flare.addColorStop(1, 'hsla(0, 0%, 0%, 0)');
        g.fillStyle = flare;
        g.fillRect(x - R * 5, y - 0.7, R * 10, 1.4);
        const star = (radius: number, waist: number, spin: number) => {
          g.beginPath();
          for (let i = 0; i < 8; i++) {
            const a = spin + (i * Math.PI) / 4;
            const r = i % 2 === 0 ? radius : radius * waist;
            if (i === 0) g.moveTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
            else g.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
          }
          g.closePath();
          g.fill();
        };
        g.fillStyle = `hsla(${(hue + 180) % 360}, 100%, 75%, 0.55)`;
        star(R * 0.72, 0.16, -turn + Math.PI / 4);
        g.fillStyle = on ? 'rgb(255, 252, 255)' : 'rgb(255, 120, 140)';
        star(R, 0.12, turn);
        // How far it's built: an arc closing round it.
        g.strokeStyle = `hsla(${hue}, 100%, 88%, 0.85)`;
        g.lineWidth = 1;
        g.beginPath();
        g.arc(x, y, R * 1.3, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * built);
        g.stroke();
        g.globalCompositeOperation = 'source-over';
        // Showing what's wanted: the words, pulsing.
        if (trace.teaching) {
          g.globalAlpha = 0.65 + 0.35 * Math.sin(now * 5);
          g.fillStyle = '#fff';
          g.font = 'bold 15px Georgia, "Times New Roman", serif';
          g.textAlign = 'center';
          g.fillText(on ? 'FOLLOW IT' : 'HOLD ON THE STAR', x, y + R + 22);
          g.globalAlpha = 1;
        }
      }
      g.globalCompositeOperation = 'source-over';
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full mix-blend-screen [image-rendering:pixelated]" />;
}
