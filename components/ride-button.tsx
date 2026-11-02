'use client';

import { useEffect, useRef, useState } from 'react';
import { ride } from '@/lib/ride';

// The hit area for the glowing button on the bike (drawn in the canvas, components/three/ride.tsx): a real, invisible
// <button> kept over the whole bike each frame, so it's clickable, focusable and announced. Clicking gets on the bike: the camera
// glides to the rider's eye and the page stops scrolling; scrolling (or swiping) back up gets off, as does Escape.
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
    const tick = () => {
      const el = button.current;
      if (el) {
        // Over the whole bike (and at least a finger's width round the button).
        const { x, y, r, shown } = ride.screen;
        const { x0, y0, x1, y1 } = ride.bike;
        const pad = Math.max(22, r * 1.2);
        const left = Math.min(x0, x - pad);
        const top = Math.min(y0, y - pad);
        el.style.transform = `translate(${left}px, ${top}px)`;
        el.style.width = `${Math.max(x1, x + pad) - left}px`;
        el.style.height = `${Math.max(y1, y + pad) - top}px`;
        el.style.visibility = shown ? 'visible' : 'hidden';
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // On the bike: no scrolling; scrolling or swiping back up gets off (and Escape, for the keyboard).
  useEffect(() => {
    ride.mounted = mounted;
    if (!mounted) return;
    const root = document.documentElement;
    root.style.overflow = 'hidden';
    const off = () => setMounted(false);
    const key = (e: KeyboardEvent) => e.key === 'Escape' && off();
    const wheel = (e: WheelEvent) => e.deltaY < 0 && off();
    let touchY: number | null = null;
    const touchStart = (e: TouchEvent) => {
      touchY = e.touches[0]?.clientY ?? null;
    };
    // (A finger dragged down the screen is scrolling up.)
    const touchMove = (e: TouchEvent) => touchY !== null && (e.touches[0]?.clientY ?? touchY) - touchY > 40 && off();
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
        onClick={() => setMounted(true)}
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
