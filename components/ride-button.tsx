'use client';

import { useEffect, useRef, useState } from 'react';
import { course, inLength, ZONES } from '@/lib/course';
import { music, startMusic, toggleMuted } from '@/lib/music';
import { pressRhythm } from '@/lib/rhythm';
import { featureHere, pressGhost, ride } from '@/lib/ride';
import { releaseTrace, startTrace, trace } from '@/lib/trace';

// The hit areas for the bike's controls (drawn in the canvas): real, invisible <button>s kept over them each frame, so
// they're clickable, focusable and announced. From the landing the first covers the whole bike, and clicking gets on: the
// camera glides to the rider's eye and the page stops scrolling. On the bike it's play and pause: clicking it (or
// scrolling, swiping up, the up arrow) rides on, down the endless street; clicking again or scrolling back brakes.
// The second's the boost button, the rocket on its pod (components/three/boost-pod.tsx), from the chrome city on, doing
// each zone's own thing (lib/course.ts ZONES), as does Space: in the chrome city pressing it sends out a point, with its
// trail, to keep the pointer on as it wanders, holding on: the surge builds the longer it's kept up (lib/trace.ts); in the hive, a press starts a run of circles, 111 to 666, to click on the heart's beat, for the boost (lib/rhythm.ts); in the desert, dragging
// it back, down the screen toward the rider (or holding Space), draws it back along its rail like a slingshot, and
// letting go launches the bike; in the core, a press phases it out for a few seconds of far greater speed. There's no getting off by scrolling (easy to do by accident while finding the controls):
// the way back is on the map, once in the chrome city (ride.request.back, from the map's green city,
// components/three/holomap.tsx).
/** The boost button's feature in the zone the bike's in. */
const feature = () => featureHere();

export function RideButton() {
  const button = useRef<HTMLButtonElement>(null);
  const boostButton = useRef<HTMLButtonElement>(null);
  const backButton = useRef<HTMLButtonElement>(null);
  const onButton = useRef<HTMLButtonElement>(null);
  const [mounted, setMounted] = useState(false);
  const [muted, setMuted] = useState(false);
  // (What was remembered: read once on the client, so the first render matches the server's.)
  useEffect(() => setMuted(music.muted), []);
  const flipSound = () => {
    toggleMuted();
    setMuted(music.muted);
  };
  // The slingshot: where the press began (null when not pressed) and whether it's become a drag.
  const press = useRef<{ x: number; y: number; dragging: boolean } | null>(null);

  const flipSoundRef = useRef(flipSound);
  flipSoundRef.current = flipSound;

  // Let go of a draw: far enough back, it launches (as hard as it was drawn); not, it just slides home.
  const letGo = (launch: boolean) => {
    const drive = ride.drive;
    if (press.current?.dragging && launch && drive.pull > 0.12) drive.release = drive.pull;
    drive.pull = 0;
    press.current = null;
    drive.boosting = false;
    releaseTrace();
  };

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
        const boost = boostButton.current;
        if (boost) {
          const b = ride.boostScreen;
          const hit = Math.max(24, b.r * 1.25);
          boost.style.transform = `translate(${b.x - hit}px, ${b.y - hit}px)`;
          boost.style.width = boost.style.height = `${hit * 2}px`;
          boost.style.visibility = b.shown ? 'visible' : 'hidden';
        }
        for (const [b, r] of [
          [backButton.current, ride.mapBack],
          [onButton.current, ride.mapOn],
        ] as const) {
          if (!b) continue;
          b.style.transform = `translate(${r.x}px, ${r.y}px)`;
          b.style.width = `${r.w}px`;
          b.style.height = `${r.h}px`;
          b.style.visibility = r.shown ? 'visible' : 'hidden';
        }
        const on = onButton.current;
        const next = ZONES[ride.zone + 1];
        if (on && next && on.dataset.zone !== next.id) {
          on.dataset.zone = next.id;
          on.setAttribute('aria-label', `Ride on to the next place`);
        }
        // The map's way back: ride back to the green city (the wash, back at the landing).
        if (ride.request.back) {
          ride.request.back = false;
          setMounted(false);
        }
        const want = !ride.mounted ? 'Get on the bike' : ride.drive.cruise ? 'Pause' : 'Ride on';
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
      drive.cruise = false;
    };
    // (Space, held, draws the slingshot back over a moment.)
    let drawing = 0;
    const key = (e: KeyboardEvent) => {
      if (process.env.NODE_ENV === 'development') {
        // (Dev: j jumps to a little short of the plaza ahead; n rides on from one, as the map's next place does.)
        const leg = course.legs[ride.zone];
        if (e.key === 'j' && ride.transition.placed && leg.in) ride.drive.s = Math.max(ride.drive.s, leg.at + inLength(leg) - 250);
        if (e.key === 'n') ride.request.on = true;
      }
      if (e.key === ' ') {
        // Space is the boost button's feature: it surges, keeps the circles' time, draws back.
        e.preventDefault();
        if (e.repeat) return;
        const f = feature();
        if (f === 'surge') {
          // (Followed with the pointer wherever it already is.)
          const b = ride.boostScreen;
          startTrace(b.x, b.y, ride.pointer?.x ?? b.x, ride.pointer?.y ?? b.y);
        } else if (f === 'heartbeat') pressRhythm();
        else if (f === 'ghost') pressGhost();
        else if (f === 'slingshot') {
          const from = performance.now();
          window.clearInterval(drawing);
          drawing = window.setInterval(() => {
            ride.drive.pull = Math.min(1, (performance.now() - from) / 900);
          }, 16);
        } else go();
      } else if (e.key === 'm') flipSoundRef.current();
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
      // (Not a drag on the boost button itself: that's the slingshot.)
      touchY = e.target === boostButton.current ? null : (e.touches[0]?.clientY ?? null);
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
    const keyUp = (e: KeyboardEvent) => {
      if (e.key !== ' ') return;
      ride.drive.boosting = false;
      releaseTrace();
      if (drawing) {
        window.clearInterval(drawing);
        drawing = 0;
        if (ride.drive.pull > 0.12) ride.drive.release = ride.drive.pull;
        ride.drive.pull = 0;
      }
    };
    window.addEventListener('keydown', key);
    window.addEventListener('keyup', keyUp);
    window.addEventListener('wheel', wheel, { passive: true });
    window.addEventListener('touchstart', touchStart, { passive: true });
    window.addEventListener('touchmove', touchMove, { passive: true });
    return () => {
      root.style.overflow = '';
      window.removeEventListener('keydown', key);
      window.removeEventListener('keyup', keyUp);
      window.clearInterval(drawing);
      ride.drive.boosting = false;
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
          if (!mounted) {
            setMounted(true);
            // (Browsers only let sound start from a press like this one.)
            startMusic();
          } else ride.drive.cruise = !ride.drive.cruise;
        }}
        onFocus={() => {
          ride.focused = true;
        }}
        onBlur={() => {
          ride.focused = false;
        }}
        className="pointer-events-auto invisible absolute top-0 left-0 cursor-pointer touch-none outline-none"
      />
      {/* Over the rocket on its pod: the boost. */}
      <button
        ref={boostButton}
        type="button"
        aria-label="Boost"
        onPointerDown={(e) => {
          press.current = { x: e.clientX, y: e.clientY, dragging: false };
          // (Kept on the button while it's dragged off it.)
          e.currentTarget.setPointerCapture(e.pointerId);
          const f = feature();
          if (f === 'surge') startTrace(e.clientX, e.clientY);
          else if (f === 'heartbeat') pressRhythm();
          else if (f === 'ghost') pressGhost();
        }}
        // Dragged back (down the screen, toward the rider): drawn back along its rail, the further the harder.
        onPointerMove={(e) => {
          trace.px = e.clientX;
          trace.py = e.clientY;
          const p = press.current;
          if (!p || feature() !== 'slingshot') return;
          const back = e.clientY - p.y;
          if (!p.dragging && back > 8 && back > Math.abs(e.clientX - p.x)) p.dragging = true;
          if (p.dragging) ride.drive.pull = Math.min(1, Math.max(0, back / Math.max(80, window.innerHeight * 0.16)));
        }}
        onPointerUp={() => letGo(true)}
        onPointerCancel={() => letGo(false)}
        onLostPointerCapture={() => {
          if (press.current) letGo(true);
        }}
        onKeyDown={(e) => {
          // (Enter on it, focused from the keyboard: a press. Space is handled for the whole ride.)
          if (e.key !== 'Enter' || e.repeat) return;
          const f = feature();
          if (f === 'heartbeat') pressRhythm();
          else if (f === 'ghost') pressGhost();
          else if (f === 'surge') ride.drive.boost = Math.min(16, ride.drive.boost + 8);
        }}
        className="pointer-events-auto invisible absolute top-0 left-0 cursor-pointer touch-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-[#ffd27a]"
      />
      {/* Sound on or off, while riding (or the m key). */}
      {mounted && (
        <button
          type="button"
          aria-label={muted ? 'Turn the music on' : 'Turn the music off'}
          aria-pressed={!muted}
          onClick={flipSound}
          className="pointer-events-auto absolute right-4 bottom-4 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full bg-black/55 text-[#9dff7a] outline-none backdrop-blur-sm focus-visible:ring-2 focus-visible:ring-[#7dff6a]"
        >
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5H4z" fill="currentColor" />
            {muted ? <path d="M16 9.5l5 5M21 9.5l-5 5" /> : <path d="M16 9a4.5 4.5 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" />}
          </svg>
        </button>
      )}
      {/* Over the map's green city: the way back. */}
      <button
        ref={backButton}
        type="button"
        aria-label="Ride back to the green city"
        onClick={() => {
          ride.request.back = true;
        }}
        onPointerEnter={() => {
          ride.mapBack.hover = 1;
        }}
        onPointerLeave={() => {
          ride.mapBack.hover = 0;
        }}
        onFocus={() => {
          ride.mapBack.hover = 1;
        }}
        onBlur={() => {
          ride.mapBack.hover = 0;
        }}
        className="pointer-events-auto invisible absolute top-0 left-0 cursor-pointer rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[#7dff6a]"
      />
      {/* Over the map's next place, in its fog: ride on there. */}
      <button
        ref={onButton}
        type="button"
        aria-label="Ride on to the next place"
        onClick={() => {
          ride.request.on = true;
        }}
        onPointerEnter={() => {
          ride.mapOn.hover = 1;
        }}
        onPointerLeave={() => {
          ride.mapOn.hover = 0;
        }}
        onFocus={() => {
          ride.mapOn.hover = 1;
        }}
        onBlur={() => {
          ride.mapOn.hover = 0;
        }}
        className="pointer-events-auto invisible absolute top-0 left-0 cursor-pointer rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[#ffd27a]"
      />
    </div>
  );
}
