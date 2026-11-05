'use client';

import { useEffect, useRef } from 'react';
import { lookFromParam, TRACE_LOOKS } from '@/components/trace-looks';
import { PIXEL, plate, type TraceFrame } from '@/components/trace-looks/shared';
import { ride } from '@/lib/ride';
import { TRACE, trace, traceReach } from '@/lib/trace';

// The chrome city's point and trail (lib/trace.ts), on a canvas of its own over the scene: the motion blur would smear it,
// and it has to be followed. At half resolution, so it's thin but still sits with the pixels of the rest. What it looks like
// is up to the look in use (components/trace-looks): this only runs it. `?trace=a|b|c|d` picks one, `t` cycles them in dev.

const LABEL_FOR = 1.6;

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
    trace.look = lookFromParam(new URLSearchParams(window.location.search).get('trace'));
    let raf = 0;
    let dirty = false;
    let last = performance.now();
    // (Dev: t, riding, shows the next look, and says which for a moment.)
    let labelUntil = 0;
    const key = (e: KeyboardEvent) => {
      if (e.key !== 't' || !ride.mounted) return;
      trace.look = (trace.look + 1) % TRACE_LOOKS.length;
      labelUntil = performance.now() / 1000 + LABEL_FOR;
    };
    const dev = process.env.NODE_ENV === 'development';
    if (dev) window.addEventListener('keydown', key);
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
      const now = stamp / 1000;
      const surge = ride.mount * ride.drive.surge;
      const running = trace.active || trace.dying > 0 || surge > 0.01 || now < labelUntil;
      if (!running && !dirty) return;
      g.clearRect(0, 0, w, h);
      const built = Math.min(1, trace.held / TRACE.build);
      const frame: TraceFrame = {
        w,
        h,
        dt,
        now,
        x: trace.x / PIXEL,
        y: trace.y / PIXEL,
        px: trace.px / PIXEL,
        py: trace.py / PIXEL,
        bx: ride.boostScreen.x / PIXEL,
        by: ride.boostScreen.y / PIXEL,
        reach: traceReach(built, trace.teaching) / PIXEL,
        speed: ride.drive.speed,
        surge,
        built,
        fade: trace.active ? 1 : trace.dying,
        active: trace.active,
        teaching: trace.teaching,
        on: trace.on && trace.down,
        lost: trace.lost && !trace.active,
        trail: trace.trail,
      };
      const left = TRACE_LOOKS[trace.look].draw(g, frame);
      dirty = running || left;
      if (now < labelUntil) plate(g, frame, [`TRACE ${TRACE_LOOKS[trace.look].id.toUpperCase()} ${TRACE_LOOKS[trace.look].name}`], w / 2 - 60, 22, '#ffffff');
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      if (dev) window.removeEventListener('keydown', key);
    };
  }, []);

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />;
}
