import { HEART, ride } from './ride';

// The hive's boost: a press of the rocket starts circles coming, one every other beat of the heart, each with a ring
// closing on it, to be clicked as it lands (components/rhythm-overlay.tsx draws them and takes the clicks). Each one hit
// pumps the bike on a little more (ride.drive.pump, through ride.drive.taps). The first ever, the ride slows right down as
// its ring closes, and waits there for the click, showing what's wanted. A few missed in a row and they stop coming, until
// the next press.

/** How long a ring takes to close (s), how far off its landing a click's perfect or still good, misses before it stops. */
export const RHYTHM = { approach: 0.95, perfect: 0.11, good: 0.27, misses: 3 };

export type Circle = { x: number; y: number; at: number; number: number };
export type Burst = { x: number; y: number; age: number; kind: 'perfect' | 'good' | 'miss' };

export const rhythm = {
  active: false,
  /** The first circle's been hit: no more stopping to show how. */
  taught: false,
  /** Waiting on the first circle: the ride slowing down to a stop. */
  teaching: false,
  /** How fast the ride's running (1 full speed, 0 stopped). */
  slow: 1,
  /** The rhythm's own clock (s): it stops when the ride does. */
  clock: 0,
  next: 0,
  misses: 0,
  combo: 0,
  circles: [] as Circle[],
  bursts: [] as Burst[],
  last: { x: 0.5, y: 0.34 },
};

const period = () => HEART.period - HEART.quicken * ride.drive.pump;

function spawn() {
  const r = rhythm;
  // Near the last one, as a path round the upper screen: clear of the bike and its buttons.
  const a = Math.random() * Math.PI * 2;
  const d = 0.17 + Math.random() * 0.13;
  const x = Math.min(0.84, Math.max(0.16, r.last.x + Math.cos(a) * d));
  const y = Math.min(0.56, Math.max(0.14, r.last.y + Math.sin(a) * d * 1.3));
  r.last = { x, y };
  // (Landing on a beat: the first far enough off for its ring to close in time.)
  const beat = period();
  const toBeat = (1 - ride.drive.phase) * beat;
  const at = r.clock + toBeat + Math.ceil(Math.max(0, RHYTHM.approach - toBeat) / beat) * beat;
  r.circles.push({ x, y, at, number: r.combo + r.circles.length + 1 });
  r.next = r.clock + 2 * beat;
}

function stop() {
  rhythm.active = false;
  rhythm.teaching = false;
  rhythm.circles.length = 0;
}

function hit(c: Circle, off: number) {
  const r = rhythm;
  const kind = off < RHYTHM.perfect || r.teaching ? 'perfect' : 'good';
  ride.drive.taps += kind === 'perfect' ? 1.4 : 1;
  // (The first, a real kick: it's what the waiting was for.)
  if (r.teaching) ride.drive.taps += 1.2;
  r.bursts.push({ x: c.x, y: c.y, age: 0, kind });
  r.circles.splice(r.circles.indexOf(c), 1);
  r.combo++;
  r.misses = 0;
  if (r.teaching) {
    r.teaching = false;
    r.taught = true;
    r.next = r.clock + period();
  }
}

/**
 * A press of the rocket or Space: starts the circles if they've stopped; otherwise, or a click on a circle (`on`, already
 * checked to be over it), hits the one landing next if it's near enough its time.
 */
export function pressRhythm(on?: Circle) {
  const r = rhythm;
  ride.drive.cruise = true;
  if (!r.active) {
    r.active = true;
    r.misses = 0;
    r.combo = 0;
    r.teaching = !r.taught;
    spawn();
    return;
  }
  const c = on ?? r.circles[0];
  if (!c) return;
  const off = Math.abs(c.at - r.clock);
  if (off < RHYTHM.good || r.teaching) hit(c, off);
}

/** Runs the rhythm on (dt: the frame's real time). `allowed`: on the bike, riding, in the hive, not pulled up. */
export function updateRhythm(dt: number, allowed: boolean) {
  const r = rhythm;
  if (r.active && !allowed) stop();
  // Teaching: the ride eases down as the first ring closes, to a stop as it lands; then back up, quick, once it's hit.
  const first = r.circles[0];
  if (r.teaching && first) {
    const left = first.at - r.clock;
    r.slow = left < 0.02 ? 0 : Math.min(r.slow, Math.max(0.02, left / 0.75));
  } else r.slow = Math.min(1, r.slow + dt * 3.5);
  const step = dt * r.slow;
  r.clock += step;
  for (const b of r.bursts) b.age += dt;
  while (r.bursts.length && r.bursts[0].age > 0.6) r.bursts.shift();
  if (!r.active) return;
  if (!r.teaching) {
    for (let i = r.circles.length - 1; i >= 0; i--) {
      const c = r.circles[i];
      if (r.clock - c.at <= RHYTHM.good) continue;
      // Missed: it knocks some of the pump off.
      r.circles.splice(i, 1);
      r.bursts.push({ x: c.x, y: c.y, age: 0, kind: 'miss' });
      ride.drive.taps = -1;
      r.combo = 0;
      if (++r.misses >= RHYTHM.misses) {
        stop();
        return;
      }
    }
    if (r.clock >= r.next) spawn();
  }
}
