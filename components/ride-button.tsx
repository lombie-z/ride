'use client';

import { useEffect, useRef, useState } from 'react';
import { ride } from '@/lib/ride';

// The hit area for the glowing button on the bike (drawn in the canvas, components/three/ride.tsx): a real, invisible
// <button> kept over it each frame, so it's clickable, focusable and announced. From the landing it covers the whole
// bike, and clicking gets on: the camera glides to the rider's eye and the page stops scrolling. On the bike it's the
// throttle: clicking it (or scrolling, swiping up, the up arrow) rides on, down the endless street; clicking again or
// scrolling back brakes, and scrolling back once stopped gets off (as does Escape).
export function RideButton() {
  const button = useRef<HTMLButtonElement>(null);
  const [mounted, setMounted] = useState(false);

  // Where the pointer is, for the button's glow.
  useEffect(() => {
    const move = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' || e.pointerType === 'pen') ride.pointer = { x: e.clientX, y: e.clientY };
    };
    const leave = () => {
      ride.pointer = null;
    };
    window.addEventListener('pointermove', move, { passive: true });
    document.documentElement.addEventListener('pointerleave', leave);
    return () => {
      window.removeEventListener('pointermove', move);
      document.documentElement.removeEventListener('pointerleave', leave);
    };
  }, []);

  // Keep the hit area on the button.
  useEffect(() => {
    let raf = 0;
    let label = '';
    const tick = () => {
      const el = button.current;
      if (el) {
        const { x, y, r, shown } = ride.screen;
        const pad = Math.max(22, r * 1.2);
        // From the landing, the whole bike (and at least a finger's width round the button); on it, just the button.
        const { x0, y0, x1, y1 } = ride.mounted ? { x0: x, y0: y, x1: x, y1: y } : ride.bike;
        const left = Math.min(x0, x - pad);
        const top = Math.min(y0, y - pad);
        el.style.transform = `translate(${left}px, ${top}px)`;
        el.style.width = `${Math.max(x1, x + pad) - left}px`;
        el.style.height = `${Math.max(y1, y + pad) - top}px`;
        el.style.visibility = shown ? 'visible' : 'hidden';
        const want = !ride.mounted ? 'Get on the bike' : ride.drive.cruise ? 'Slow down' : 'Ride on';
        if (want !== label) {
          label = want;
          el.setAttribute('aria-label', want);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // On the bike: no page scrolling; scroll and keys drive instead.
  useEffect(() => {
    ride.mounted = mounted;
    if (!mounted) return;
    const root = document.documentElement;
    root.style.overflow = 'hidden';
    const drive = ride.drive;
    const go = () => {
      // Each nudge forward adds a little boost on top of cruising.
      if (drive.cruise) drive.boost = Math.min(16, drive.boost + 1.5);
      drive.cruise = true;
    };
    const back = () => {
      if (drive.cruise || drive.speed > 1) drive.cruise = false;
      else setMounted(false);
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMounted(false);
      else if (e.key === 'ArrowUp' || e.key === 'w') go();
      else if (e.key === 'ArrowDown' || e.key === 's') back();
    };
    // (Wheels and trackpads fire many events per gesture: one gesture is one nudge.)
    let quiet = 0;
    const wheel = (e: WheelEvent) => {
      const now = performance.now();
      const fresh = now - quiet > 250;
      quiet = now;
      if (e.deltaY > 0) go();
      else if (e.deltaY < 0 && fresh) back();
    };
    let touchY: number | null = null;
    const touchStart = (e: TouchEvent) => {
      touchY = e.touches[0]?.clientY ?? null;
    };
    // (A finger dragged up the screen is scrolling down: ride on; dragged down is scrolling up.)
    const touchMove = (e: TouchEvent) => {
      if (touchY === null) return;
      const dy = (e.touches[0]?.clientY ?? touchY) - touchY;
      if (Math.abs(dy) < 40) return;
      touchY = null;
      if (dy < 0) go();
      else back();
    };
    window.addEventListener('keydown', key);
    window.addEventListener('wheel', wheel, { passive: true });
    window.addEventListener('touchstart', touchStart, { passive: true });
    window.addEventListener('touchmove', touchMove, { passive: true });
    return () => {
      root.style.overflow = '';
      window.removeEventListener('keydown', key);
      window.removeEventListener('wheel', wheel);
      window.removeEventListener('touchstart', touchStart);
      window.removeEventListener('touchmove', touchMove);
    };
  }, [mounted]);

  return (
    <div className="pointer-events-none fixed inset-0 z-[15] overflow-hidden">
      <button
        ref={button}
        type="button"
        aria-label="Get on the bike"
        onClick={() => {
          if (!mounted) setMounted(true);
          else ride.drive.cruise = !ride.drive.cruise;
        }}
        onFocus={() => {
          ride.focused = true;
        }}
        onBlur={() => {
          ride.focused = false;
        }}
        className="pointer-events-auto invisible absolute top-0 left-0 cursor-pointer outline-none"
      />
    </div>
  );
}
