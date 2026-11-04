'use client';

import { useEffect, useRef } from 'react';
import { type Circle, pressRhythm, RHYTHM, rhythm, STAR_ORDER } from '@/lib/rhythm';
import { ride } from '@/lib/ride';

// The hive's run of angel numbers (lib/rhythm.ts), on a canvas of its own over the scene: its motion blur would smear
// them, and they have to be read at a glance. At a quarter of the resolution, drawn up in chunky pixels to sit with the
// rest. A six-pointed star being drawn over the view in one line (unicursal, the occult one), point by point: each point an all-seeing wheel, its number in it, gold
// at 111 turning to blood by 666; when it's done the boost hits, and the star burns over the road for as long as it lasts.

const PIXEL = 4;
const MISS = '#ff2238';
const GOLD = [255, 190, 70];
const BLOOD = [255, 24, 40];
const FONT = 'Georgia, "Times New Roman", serif';

const mix = (t: number) => GOLD.map((a, i) => Math.round(a + (BLOOD[i] - a) * t));
const rgb = (c: number[], a = 1) => `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`;

/** The star's points on the screen: the six points over the upper middle, clear of the bike (as shares of the view). */
function point(i: number, w: number, h: number) {
  const r = Math.min(w * 0.3, h * 0.25);
  const a = -Math.PI / 2 + (i * Math.PI) / 3;
  return { x: (w / 2 + Math.cos(a) * r) / w, y: (h * 0.33 + Math.sin(a) * r) / h };
}

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
      const busy = rhythm.active || rhythm.bursts.length > 0 || rhythm.slow < 1 || rhythm.burn > 0 || ride.drive.pump > 0.01;
      if (!busy && !dirty) return;
      g.clearRect(0, 0, w, h);
      dirty = busy;
      const unit = Math.min(w, h);
      const r = unit * 0.085;
      const now = performance.now() / 1000;
      const landed = rhythm.landed;
      // The view darkens as the run goes on, toward red at the edges; to a stop, more.
      const dread = rhythm.active ? landed / RHYTHM.count : 0;
      if (rhythm.active || rhythm.slow < 1) {
        const v = g.createRadialGradient(w / 2, h * 0.42, unit * 0.2, w / 2, h * 0.42, Math.max(w, h) * 0.72);
        v.addColorStop(0, `rgba(10, 2, 2, ${0.12 + 0.3 * (1 - rhythm.slow)})`);
        v.addColorStop(1, `rgba(${40 + 90 * dread}, 2, 4, ${0.5 + 0.3 * dread})`);
        g.fillStyle = v;
        g.fillRect(0, 0, w, h);
      }
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      // The star, as far as it's been drawn: one line, from point to point.
      const at = (n: number) => {
        const p = point(STAR_ORDER[n], w, h);
        return { x: p.x * w, y: p.y * h };
      };
      if (rhythm.active && landed > 0) {
        g.strokeStyle = rgb(mix(dread), 0.9);
        g.lineWidth = 1.5;
        g.beginPath();
        for (let n = 0; n < landed; n++) {
          const p = at(n);
          if (n === 0) g.moveTo(p.x, p.y);
          else g.lineTo(p.x, p.y);
        }
        if (landed === RHYTHM.count) g.closePath();
        g.stroke();
      }
      // The boost: the finished star burning over the road for as long as it lasts, turning, beating with the heart, a
      // ring round it running out with it.
      const boost = ride.drive.pump;
      if (!rhythm.active && boost > 0.01) {
        const k = Math.min(1, boost * 5);
        const R = Math.min(w * 0.22, h * 0.25) * (1 + 0.07 * ride.drive.beat + 0.35 * rhythm.burn);
        const cx = w / 2;
        const cy = h * 0.34;
        const turn = now * 0.7;
        const star = () => {
          g.beginPath();
          for (const [i, n] of STAR_ORDER.entries()) {
            const a = turn + (n * Math.PI) / 3;
            if (i === 0) g.moveTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
            else g.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
          }
          g.closePath();
          g.stroke();
        };
        g.lineCap = 'round';
        g.strokeStyle = `rgba(255, 30, 40, ${0.4 * k})`;
        g.lineWidth = 5;
        star();
        g.strokeStyle = `rgba(255, ${Math.round(150 + 90 * ride.drive.beat)}, 90, ${k})`;
        g.lineWidth = 2;
        star();
        g.strokeStyle = `rgba(255, 60, 50, ${k})`;
        g.lineWidth = 2;
        g.beginPath();
        g.arc(cx, cy, R * 1.14, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(1, boost));
        g.stroke();
        g.lineCap = 'butt';
      }
      // A faint guide to where the star's going, once it's going.
      if (rhythm.active) {
        g.strokeStyle = rgb(mix(dread), 0.16);
        g.lineWidth = 1;
        g.beginPath();
        for (const [i, n] of STAR_ORDER.entries()) {
          const p = point(n, w, h);
          if (i === 0) g.moveTo(p.x * w, p.y * h);
          else g.lineTo(p.x * w, p.y * h);
        }
        g.closePath();
        g.stroke();
      }
      // The next to land last, on top.
      for (const c of [...rhythm.circles].reverse()) {
        const p = point(c.point, w, h);
        c.x = p.x;
        c.y = p.y;
        const x = p.x * w;
        const y = p.y * h;
        const left = (c.at - rhythm.clock) / RHYTHM.approach;
        const ink = mix((c.number / 111 - 1) / 5);
        g.globalAlpha = Math.min(1, Math.max(0, (1 - left) * 4));
        // Its wheel: a dark disc, a hot rim, ticks turning round it and eyes in the ring.
        g.fillStyle = 'rgba(6, 2, 2, 0.86)';
        g.beginPath();
        g.arc(x, y, r, 0, Math.PI * 2);
        g.fill();
        g.lineWidth = Math.max(1.5, r * 0.11);
        g.strokeStyle = rgb(ink);
        g.beginPath();
        g.arc(x, y, r, 0, Math.PI * 2);
        g.stroke();
        for (let i = 0; i < 6; i++) {
          const a = now * 0.9 + (i * Math.PI) / 3;
          const ex = x + Math.cos(a) * r;
          const ey = y + Math.sin(a) * r;
          g.fillStyle = '#fff4d8';
          g.beginPath();
          g.ellipse(ex, ey, r * 0.24, r * 0.15, a + Math.PI / 2, 0, Math.PI * 2);
          g.fill();
          g.fillStyle = '#100404';
          g.beginPath();
          g.arc(ex, ey, r * 0.1, 0, Math.PI * 2);
          g.fill();
        }
        // The ring closing on it: a broken halo, turning the other way.
        const ring = r * (1 + 1.9 * Math.max(0, left));
        g.lineWidth = Math.max(1.5, r * 0.09);
        g.strokeStyle = rgb(ink, 0.95);
        for (let i = 0; i < 3; i++) {
          const a = -now * 1.4 + (i * Math.PI * 2) / 3;
          g.beginPath();
          g.arc(x, y, ring, a, a + Math.PI * 0.52);
          g.stroke();
        }
        g.fillStyle = '#fff4d8';
        g.font = `bold ${Math.round(r * 0.72)}px ${FONT}`;
        g.fillText(String(c.number), x, y + 1);
        // Showing what's wanted: the word, pulsing.
        if (rhythm.teaching) {
          g.globalAlpha = 0.55 + 0.45 * Math.sin(now * 8);
          g.font = `bold ${Math.round(r * 0.62)}px ${FONT}`;
          g.fillText('CLICK', x, y + r * 1.85);
        }
        g.globalAlpha = 1;
      }
      for (const b of rhythm.bursts) {
        const x = b.x * w;
        const y = b.y * h;
        const t = b.age / 0.6;
        const ink = mix((b.number / 111 - 1) / 5);
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
          g.strokeStyle = b.kind === 'perfect' ? '#fff4d8' : rgb(ink);
          g.lineWidth = Math.max(1.5, r * 0.26 * (1 - t));
          g.beginPath();
          g.arc(x, y, r * (1 + 1.3 * t), 0, Math.PI * 2);
          g.stroke();
          g.fillStyle = rgb(ink);
          g.font = `bold ${Math.round(r * (0.72 + 0.5 * t))}px ${FONT}`;
          g.fillText(String(b.number), x, y + 1);
        }
      }
      g.globalAlpha = 1;
      // 666: the flash.
      if (rhythm.burn > 0) {
        const b = rhythm.burn;
        g.fillStyle = `rgba(255, ${Math.round(40 + 70 * b * b)}, ${Math.round(30 + 40 * b * b)}, ${0.75 * b * b})`;
        g.fillRect(0, 0, w, h);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />;
}
