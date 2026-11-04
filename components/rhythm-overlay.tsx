'use client';

import { UnifrakturCook } from 'next/font/google';
import { useEffect, useRef } from 'react';
import { type Circle, pressRhythm, RHYTHM, rhythm, SIGILS } from '@/lib/rhythm';
import { ride } from '@/lib/ride';

// The hive's run of angel numbers (lib/rhythm.ts), on a canvas of its own over the scene: its motion blur would smear
// them, and they have to be read at a glance. At a quarter of the resolution, drawn up in chunky pixels to sit with the
// rest. A sigil being drawn over the view in one line, a different one each run, point by point: each point an all-seeing
// wheel, its number in it, gold at 111 turning to blood by 666. When it's done the boost hits, and for as long as it lasts
// groups of eyes hold open in every corner of the view, in shadow, staring in, closing as it runs out. Miss, and they open
// then too, blood-red.

const PIXEL = 4;
// The lettering's blackletter, on a finer canvas over the rest: at a quarter of the resolution it would turn to mush.
const blackletter = UnifrakturCook({ subsets: ['latin'], weight: '700' });
const TEXT_SCALE = 2;
const MISS = '#ff2238';
const GOLD = [255, 190, 70];
const BLOOD = [255, 24, 40];

const mix = (t: number) => GOLD.map((a, i) => Math.round(a + (BLOOD[i] - a) * t));
const rgb = (c: number[], a = 1) => `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`;

/** A point of this run's sigil on the screen: over the upper middle, clear of the bike (as shares of the view). */
function point(i: number, w: number, h: number) {
  const R = Math.min(w * 0.3, h * 0.25);
  const [ux, uy] = SIGILS[rhythm.sigil].points[i];
  const edge = w / 2 - Math.min(w, h) * 0.11;
  return { x: (w / 2 + Math.max(-edge, Math.min(edge, ux * R * 1.25))) / w, y: (h * 0.33 + uy * R) / h };
}

/** The sigil's line through its points, as far as `n` of them. */
function sigilPath(g: CanvasRenderingContext2D, n: number, w: number, h: number) {
  g.beginPath();
  for (let i = 0; i < n; i++) {
    const p = point(i, w, h);
    if (i === 0) g.moveTo(p.x * w, p.y * h);
    else g.lineTo(p.x * w, p.y * h);
  }
  if (n === RHYTHM.count && SIGILS[rhythm.sigil].closed) g.closePath();
}

type Eye = { corner: number; x: number; y: number; size: number; tilt: number; delay: number; seed: number };
/** The eyes in the corners: bunched round each, biggest in it, as shares of the view's shorter side from that corner. */
const EYES: Eye[] = (() => {
  const list: Eye[] = [];
  const hash = (i: number) => {
    const h = Math.sin(i * 127.1 + 3.7) * 43758.5453;
    return h - Math.floor(h);
  };
  for (let corner = 0; corner < 4; corner++) {
    const placed: Eye[] = [];
    // (Out from the corner on a fan, biggest nearest it; a spot's tried till it's clear of those already there.)
    for (let i = 0; placed.length < 11 && i < 90; i++) {
      const n = corner * 100 + i;
      const order = placed.length;
      const d = 0.09 + 0.1 * Math.sqrt(order) + 0.05 * hash(n);
      const a = 0.04 + hash(n + 3) * (Math.PI * 0.5 - 0.08);
      const size = (0.095 - 0.0058 * order) * (0.85 + 0.3 * hash(n + 7));
      const x = Math.cos(a) * d * 1.3;
      const y = Math.sin(a) * d;
      if (placed.some((e) => Math.hypot((e.x - x) * 0.72, e.y - y) < (e.size + size) * 0.8)) continue;
      placed.push({ corner, x, y, size, tilt: (hash(n + 11) - 0.5) * 0.7, delay: order / 11, seed: hash(n + 23) });
    }
    list.push(...placed);
  }
  return list;
})();

/** One eye, `open` (0 to 1), its pupil turned to (lookX, lookY) on the screen. `rage`: bloodshot, the pupil pinned. */
function drawEye(g: CanvasRenderingContext2D, x: number, y: number, size: number, tilt: number, open: number, lookX: number, lookY: number, rage: number) {
  const lid = size * 0.62 * open;
  g.save();
  g.translate(x, y);
  g.rotate(tilt);
  // Its own shadow round it.
  g.fillStyle = `rgba(0, 0, 0, ${0.55 * Math.min(1, open * 2)})`;
  g.beginPath();
  g.ellipse(0, 0, size * 1.32, size * 0.92, 0, 0, Math.PI * 2);
  g.fill();
  const almond = () => {
    g.beginPath();
    g.moveTo(-size, 0);
    g.quadraticCurveTo(0, -lid * 2, size, 0);
    g.quadraticCurveTo(0, lid * 2, -size, 0);
    g.closePath();
  };
  almond();
  g.fillStyle = rage > 0.5 ? '#f2c9b4' : '#f0e4c0';
  g.fill();
  g.save();
  g.clip();
  // Turned in: the iris pushed toward where it's looking.
  const dx = lookX - x;
  const dy = lookY - y;
  const dist = Math.hypot(dx, dy) || 1;
  const c = Math.cos(-tilt);
  const s = Math.sin(-tilt);
  const ix = ((dx * c - dy * s) / dist) * size * 0.42;
  const iy = ((dx * s + dy * c) / dist) * size * 0.3;
  const iris = size * 0.52;
  g.fillStyle = rage > 0.5 ? '#c10f1c' : '#d98a1a';
  g.beginPath();
  g.arc(ix, iy, iris, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = '#080203';
  g.beginPath();
  g.arc(ix, iy, iris * (0.62 - 0.26 * rage), 0, Math.PI * 2);
  g.fill();
  g.fillStyle = 'rgba(255, 245, 225, 0.9)';
  g.fillRect(ix - iris * 0.42, iy - iris * 0.5, Math.max(1, iris * 0.26), Math.max(1, iris * 0.26));
  g.restore();
  almond();
  g.lineWidth = Math.max(1, size * 0.14);
  g.strokeStyle = '#0c0204';
  g.stroke();
  g.restore();
}

export function RhythmOverlay() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const lettering = useRef<HTMLCanvasElement>(null);

  // (A canvas won't wait for a font: fetched ahead, so the first run isn't in a fallback.)
  useEffect(() => {
    document.fonts.load(`700 40px ${blackletter.style.fontFamily}`, '123456CLICK').catch(() => {});
  }, []);

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
    // How far the corners' eyes are open: eased, so they open and close rather than snap.
    let staring = 0;
    let last = performance.now();
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const el = canvas.current;
      const g = el?.getContext('2d');
      const textEl = lettering.current;
      const text = textEl?.getContext('2d');
      if (!el || !g || !textEl || !text) return;
      const w = Math.ceil(window.innerWidth / PIXEL);
      const h = Math.ceil(window.innerHeight / PIXEL);
      if (el.width !== w || el.height !== h) {
        el.width = w;
        el.height = h;
        textEl.width = w * TEXT_SCALE;
        textEl.height = h * TEXT_SCALE;
      }
      const stamp = performance.now();
      const dt = Math.min(0.05, (stamp - last) / 1000);
      last = stamp;
      // Open for the boost (shutting as it runs out) or over what's been missed, whichever's more.
      const wide = Math.max(Math.min(1, ride.drive.pump / 0.3), rhythm.glare > 0.01 ? 0.4 + 0.6 * rhythm.glare : 0);
      staring += (wide - staring) * Math.min(1, dt * (wide > staring ? 7 : 3));
      if (staring < 0.004) staring = 0;
      const busy = rhythm.active || rhythm.bursts.length > 0 || rhythm.slow < 1 || rhythm.burn > 0 || ride.drive.pump > 0.01 || staring > 0;
      if (!busy && !dirty) return;
      g.clearRect(0, 0, w, h);
      text.clearRect(0, 0, textEl.width, textEl.height);
      dirty = busy;
      /** Lettering, in this canvas's units: dark round its edge, so it reads over whatever's behind it. */
      const label = (words: string, x: number, y: number, size: number, ink: string, alpha: number) => {
        text.globalAlpha = alpha;
        text.font = `700 ${Math.round(size * TEXT_SCALE)}px ${blackletter.style.fontFamily}`;
        text.lineWidth = size * TEXT_SCALE * 0.14;
        text.strokeStyle = 'rgba(8, 1, 2, 0.9)';
        text.strokeText(words, x * TEXT_SCALE, y * TEXT_SCALE);
        text.fillStyle = ink;
        text.fillText(words, x * TEXT_SCALE, y * TEXT_SCALE);
      };
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
      text.textAlign = 'center';
      text.textBaseline = 'middle';
      text.lineJoin = 'round';
      // The sigil, as far as it's been drawn, and a faint guide to where it's going.
      if (rhythm.active) {
        g.strokeStyle = rgb(mix(dread), 0.16);
        g.lineWidth = 1;
        sigilPath(g, RHYTHM.count, w, h);
        g.stroke();
        if (landed > 0) {
          g.strokeStyle = rgb(mix(dread), 0.9);
          g.lineWidth = 1.5;
          sigilPath(g, landed, w, h);
          g.stroke();
        }
      }
      // The eyes: groups in all four corners, in their shadow, opening from the corner in, staring at the middle of the view.
      if (staring > 0) {
        // (Always red, boost or miss.)
        const rage = 1;
        const beat = ride.drive.beat;
        for (let corner = 0; corner < 4; corner++) {
          const cx = corner % 3 === 0 ? 0 : w;
          const cy = corner < 2 ? 0 : h;
          const dark = g.createRadialGradient(cx, cy, 0, cx, cy, unit * (0.62 + 0.04 * beat));
          dark.addColorStop(0, `rgba(0, 0, 0, ${0.96 * Math.min(1, staring * 1.6)})`);
          dark.addColorStop(0.55, `rgba(2, 0, 0, ${0.8 * Math.min(1, staring * 1.6)})`);
          dark.addColorStop(1, 'rgba(0, 0, 0, 0)');
          g.fillStyle = dark;
          g.fillRect(0, 0, w, h);
        }
        const lookX = w / 2;
        const lookY = h * 0.46;
        for (const e of EYES) {
          const open = Math.min(1, Math.max(0, (staring * 1.45 - e.delay * 0.45) / 0.55));
          if (open <= 0.02) continue;
          // (Each blinks now and then, on its own.)
          const f = (now * (0.13 + 0.16 * e.seed) + e.seed * 7) % 1;
          const blink = f < 0.025 ? Math.abs(f / 0.0125 - 1) : 1;
          const x = (e.corner % 3 === 0 ? e.x : 1 * (w / unit) - e.x) * unit;
          const y = (e.corner < 2 ? e.y : h / unit - e.y) * unit;
          drawEye(g, x, y, e.size * unit * (1 + 0.05 * beat), e.tilt, open * open * (3 - 2 * open) * blink, lookX, lookY, rage);
        }
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
        label(String(c.number), x, y + 0.5, r * 0.9, '#fff4d8', g.globalAlpha);
        // Showing what's wanted: the word, pulsing.
        if (rhythm.teaching) label('CLICK', x, y + r * 2.05, r * 1.05, '#fff4d8', 0.55 + 0.45 * Math.sin(now * 8));
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
          label(String(b.number), x, y + 0.5, r * (0.9 + 0.5 * t), rgb(ink), 1 - t);
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

  return (
    <>
      <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
      <canvas ref={lettering} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
    </>
  );
}
