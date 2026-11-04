import { ride } from './ride';

// The chrome city's boost: a press of the rocket sends a thin trail of light out from it, a star at its end, wandering over
// the view; keep the pointer on the star and hold on, and the surge builds toward its full speed the longer it's kept up.
// Fall off it or let go, and it's over (components/trace-overlay.tsx draws it; components/ride-button.tsx feeds the pointer).
// The first ever, time slows nearly to a stop and the star only moves while it's being traced, waiting if it isn't.

export const TRACE = {
  /** How long it takes to build to full speed (s). */
  build: 11,
  /** How far off the star the pointer can be, as a share of the view's shorter side (and tighter once it's built). */
  reach: 0.1,
  tight: 0.075,
  /** How long off it before it's lost (s); and how long at the start to catch it. */
  grace: 0.28,
  start: 0.5,
  /** The trail's length (s). */
  trail: 2,
};

type Point = { x: number; y: number; age: number };

export const trace = {
  active: false,
  /** They've held on a while: no more showing what's wanted. */
  taught: false,
  /** Showing what's wanted: time slowed, the star waiting on the pointer. */
  teaching: false,
  /** How fast the ride's running (1 full speed): components/three/ride.tsx. */
  slow: 1,
  /** The press is held. */
  down: false,
  /** How fast the star's going along its way now: eased, so it gathers pace. */
  pace: 0,
  t: 0,
  /** Seconds on the star this go, and how long off it just now. */
  held: 0,
  off: 0,
  /** How far it's built (0 to 1): the surge's strength. */
  level: 0,
  /** The star and the pointer on the screen (CSS px). */
  x: 0,
  y: 0,
  px: 0,
  py: 0,
  on: true,
  /** Where it set out from, how far along its way it's wandered, and the way's own shape. */
  fromX: 0,
  fromY: 0,
  along: 0,
  shape: [0, 0, 0, 0],
  trail: [] as Point[],
  /** The trail dying away once it's over (1 down to 0); red if it was lost rather than let go. */
  dying: 0,
  lost: false,
};

export function startTrace(x: number, y: number, px = x, py = y) {
  const r = trace;
  if (r.active) return;
  Object.assign(r, {
    active: true,
    teaching: !r.taught,
    down: true,
    pace: 0,
    t: 0,
    held: 0,
    off: 0,
    level: 0,
    x,
    y,
    px,
    py,
    on: true,
    fromX: x,
    fromY: y,
    along: 0,
    dying: 0,
    lost: false,
  });
  r.shape = [0, 1, 2, 3].map(() => Math.random() * Math.PI * 2);
  r.trail.length = 0;
  ride.drive.cruise = true;
}

/** The press let go: over, unless it's still being taught: then it waits to be taken up again. */
export function releaseTrace() {
  if (trace.teaching) trace.down = false;
  else endTrace();
}

export function endTrace(lost = false) {
  const r = trace;
  if (!r.active) return;
  r.active = false;
  r.teaching = false;
  r.level = 0;
  r.dying = 1;
  r.lost = lost;
  ride.drive.shedding = true;
}

/** Runs it on: the star along its way, checked against the pointer. `allowed`: riding, in the chrome city, not pulled up. */
export function updateTrace(dt: number, allowed: boolean) {
  const r = trace;
  r.dying = Math.max(0, r.dying - dt / 0.55);
  // Time slows as it's taught, and comes back quickly enough after.
  r.slow += ((r.teaching ? 0.05 : 1) - r.slow) * Math.min(1, dt * (r.teaching ? 3 : 1.6));
  if (r.slow > 0.998) r.slow = 1;
  for (const p of r.trail) p.age += dt;
  while (r.trail.length && r.trail[0].age > TRACE.trail) r.trail.shift();
  if (!r.active) return;
  if (!allowed) {
    endTrace();
    return;
  }
  const built = Math.min(1, r.held / TRACE.build);
  const w = window.innerWidth;
  const h = window.innerHeight;
  const reach = Math.min(w, h) * (r.teaching ? 0.14 : TRACE.reach + (TRACE.tight - TRACE.reach) * built);
  r.on = Math.hypot(r.px - r.x, r.py - r.y) <= reach;
  // Being taught it only moves while it's being traced, and slowly.
  const traced = r.on && r.down;
  r.t += r.teaching ? (traced ? dt * 0.3 : 0) : dt;
  // (Quickening as it builds; a smooth wander over the upper part of the view, clear of the bike.)
  const pace = r.teaching ? (traced ? 0.11 : 0) : 0.5 + 0.55 * built;
  r.pace += (pace - r.pace) * Math.min(1, dt * (pace > r.pace ? 1.2 : 8));
  r.along += dt * r.pace;
  const a = r.along;
  const [p, q, s, u] = r.shape;
  const gx = (0.5 + 0.34 * Math.sin(a + p) + 0.08 * Math.sin(a * 2.3 + q)) * w;
  const gy = (0.4 + 0.24 * Math.sin(a * 1.37 + s) + 0.05 * Math.sin(a * 3.1 + u)) * h;
  // (It sets out from the button, easing onto its way.)
  const e = Math.min(1, r.t / 1.1);
  const out = e * e * (3 - 2 * e);
  r.x = r.fromX + (gx - r.fromX) * out;
  r.y = r.fromY + (gy - r.fromY) * out;
  r.trail.push({ x: r.x, y: r.y, age: 0 });
  if (r.teaching) {
    // (Held on for a few seconds, it's got it: time comes back.)
    if (traced) r.held += dt;
    if (r.held > 3.5) {
      r.teaching = false;
      r.taught = true;
    }
  } else if (r.on) {
    r.held += dt;
    r.off = 0;
  } else if (r.t > TRACE.start) {
    r.off += dt;
    if (r.off > TRACE.grace) {
      endTrace(true);
      return;
    }
  }
  r.level = Math.min(1, 0.1 + 0.9 * Math.min(1, r.held / TRACE.build) ** 1.2);
}
