'use client';

import { UnifrakturCook } from 'next/font/google';
import { useEffect, useRef } from 'react';
import { lookFromParam, RHYTHM_LOOKS } from '@/components/rhythm-looks';
import { clamp, PIXEL, type RhythmFrame, type Stare, TEXT_SCALE } from '@/components/rhythm-looks/shared';
import { type Circle, pressRhythm, RHYTHM, rhythm, SIGILS } from '@/lib/rhythm';
import { ride } from '@/lib/ride';

// The hive's run of angel numbers (lib/rhythm.ts), on a canvas of its own over the scene: its motion blur would smear
// them, and they have to be read at a glance. At a quarter of the resolution, drawn up in chunky pixels to sit with the
// rest. What the circles, the sigil and the eyes look like is up to the look in use (components/rhythm-looks); this runs it,
// takes the clicks and says where the eyes are: when a run's done the boost hits, and for as long as it lasts groups of eyes
// hold open in every corner of the view, in shadow, staring in, closing as it runs out. Miss, and they open then too, blood-red.
// `?rhythm=a|b|c|d` picks a look, `y` cycles them in dev.

// The lettering's blackletter, on a finer canvas over the rest: at a quarter of the resolution it would turn to mush.
const blackletter = UnifrakturCook({ subsets: ['latin'], weight: '700' });
const LABEL_FOR = 1.6;

/** A point of this run's sigil on the screen: over the upper middle, clear of the bike (as shares of the view). */
function point(i: number, w: number, h: number) {
  const R = Math.min(w * 0.3, h * 0.25);
  const [ux, uy] = SIGILS[rhythm.sigil].points[i];
  const edge = w / 2 - Math.min(w, h) * 0.11;
  return { x: (w / 2 + Math.max(-edge, Math.min(edge, ux * R * 1.25))) / w, y: (h * 0.33 + uy * R) / h };
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
    let look = lookFromParam(new URLSearchParams(window.location.search).get('rhythm'));
    let raf = 0;
    let dirty = false;
    // How far the corners' eyes are open: eased, so they open and close rather than snap.
    let staring = 0;
    let last = performance.now();
    let gloom = 0;
    let fade = 0;
    let run = 0;
    let was = false;
    // (Dev: y, riding, shows the next look, and says which for a moment.)
    let labelUntil = 0;
    const key = (e: KeyboardEvent) => {
      if (e.key !== 'y' || !ride.mounted) return;
      look = (look + 1) % RHYTHM_LOOKS.length;
      labelUntil = performance.now() / 1000 + LABEL_FOR;
    };
    const dev = process.env.NODE_ENV === 'development';
    if (dev) {
      window.addEventListener('keydown', key);
      (window as unknown as { __rhythmLook?: (i: number) => void }).__rhythmLook = (i) => {
        look = i;
      };
    }
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
      const now = stamp / 1000;
      // Open for the boost (shutting as it runs out) or over what's been missed, whichever's more.
      const wide = Math.max(Math.min(1, ride.drive.pump / 0.3), rhythm.glare > 0.01 ? 0.4 + 0.6 * rhythm.glare : 0);
      staring += (wide - staring) * Math.min(1, dt * (wide > staring ? 7 : 3));
      if (staring < 0.004) staring = 0;
      const running =
        rhythm.active || rhythm.bursts.length > 0 || rhythm.slow < 1 || rhythm.burn > 0 || ride.drive.pump > 0.01 || staring > 0 || now < labelUntil;
      if (!running && !dirty) return;
      g.clearRect(0, 0, w, h);
      text.clearRect(0, 0, textEl.width, textEl.height);
      /** Lettering, in this canvas's units: dark round its edge, so it reads over whatever's behind it. */
      const label = (words: string, x: number, y: number, size: number, ink: string, alpha: number) => {
        text.globalAlpha = clamp(alpha);
        text.font = `700 ${Math.round(size * TEXT_SCALE)}px ${blackletter.style.fontFamily}`;
        text.lineWidth = size * TEXT_SCALE * 0.14;
        text.strokeStyle = 'rgba(8, 1, 2, 0.9)';
        text.strokeText(words, x * TEXT_SCALE, y * TEXT_SCALE);
        text.fillStyle = ink;
        text.fillText(words, x * TEXT_SCALE, y * TEXT_SCALE);
      };
      text.textAlign = 'center';
      text.textBaseline = 'middle';
      text.lineJoin = 'round';
      const unit = Math.min(w, h);
      const r = unit * 0.085;
      if (rhythm.active && !was) run++;
      was = rhythm.active;
      // (The dread goes by what's landed; the run's end lets it go.)
      gloom += ((rhythm.active ? rhythm.landed / RHYTHM.count : 0) - gloom) * Math.min(1, dt * (rhythm.active ? 5 : 2));
      fade = rhythm.active ? 1 : Math.max(0, fade - dt / 1.1);
      const points = Array.from({ length: RHYTHM.count }, (_, i) => {
        const p = point(i, w, h);
        return { x: p.x * w, y: p.y * h };
      });
      // (Where they stand, in shares of the view, is what a click's checked against.)
      const circles = rhythm.circles.map((c) => {
        const p = point(c.point, w, h);
        c.x = p.x;
        c.y = p.y;
        return { point: c.point, number: c.number, x: p.x * w, y: p.y * h, left: (c.at - rhythm.clock) / RHYTHM.approach };
      });
      const frame: RhythmFrame = {
        w,
        h,
        unit,
        r,
        u: r / (180 * 0.085),
        dt,
        now,
        beat: ride.drive.beat,
        active: rhythm.active,
        teaching: rhythm.teaching,
        slow: rhythm.slow,
        burn: rhythm.burn,
        landed: rhythm.landed,
        gloom,
        fade,
        run,
        points,
        closed: SIGILS[rhythm.sigil].closed,
        drawn: rhythm.drawn,
        circles,
        bursts: rhythm.bursts,
        pointer: ride.pointer ? { x: ride.pointer.x / PIXEL, y: ride.pointer.y / PIXEL } : null,
        label,
      };
      const current = RHYTHM_LOOKS[look];
      const leftUnder = current.under(g, frame);
      // The eyes: groups in all four corners, in their shadow, opening from the corner in, staring at the middle of the view.
      if (staring > 0) {
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
        const stares: Stare[] = [];
        for (const e of EYES) {
          const open = Math.min(1, Math.max(0, (staring * 1.45 - e.delay * 0.45) / 0.55));
          if (open <= 0.02) continue;
          // (Each blinks now and then, on its own.)
          const f = (now * (0.13 + 0.16 * e.seed) + e.seed * 7) % 1;
          const blink = f < 0.025 ? Math.abs(f / 0.0125 - 1) : 1;
          const x = (e.corner % 3 === 0 ? e.x : 1 * (w / unit) - e.x) * unit;
          const y = (e.corner < 2 ? e.y : h / unit - e.y) * unit;
          stares.push({
            x,
            y,
            size: e.size * unit * (1 + 0.05 * beat),
            tilt: e.tilt,
            open: open * open * (3 - 2 * open) * blink,
            lookX: w / 2,
            lookY: h * 0.46,
            seed: e.seed,
          });
        }
        current.stare(g, frame, stares);
      }
      const leftOver = current.over(g, frame);
      dirty = running || leftUnder || leftOver;
      if (now < labelUntil) label(`Rhythm ${current.id.toUpperCase()} ${current.name}`, w / 2, h * 0.08, unit * 0.075, '#fff4d8', 1);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      if (dev) window.removeEventListener('keydown', key);
    };
  }, []);

  return (
    <>
      <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
      <canvas ref={lettering} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
    </>
  );
}
