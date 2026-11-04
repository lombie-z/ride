import { HEART, ride } from './ride';

// The hive's boost: a press of the rocket starts a short run of six circles, numbered as angel numbers from 111 up to 666,
// each with a ring closing on it, to be clicked as it lands on the heart's beat (components/rhythm-overlay.tsx draws them
// and takes the clicks). They stand at the points of a unicursal star, six points in one line, each one drawn on to as it's hit, the heart
// quickening. On 666 the star burns and the boost hits, as hard as the run was clean (ride.drive.pump). The first ever,
// the ride slows right down as its ring closes, and waits there for the click, showing what's wanted.

/** How long a ring takes to close (s), how far off its landing a click's perfect or still good, and the run's length. */
export const RHYTHM = { approach: 0.8, perfect: 0.11, good: 0.27, count: 6 };

export type Circle = { point: number; x: number; y: number; at: number; number: number };
export type Burst = { x: number; y: number; age: number; kind: 'perfect' | 'good' | 'miss'; number: number };

/** The star's points, in the order they land: round a hexagon (from the top, clockwise) by the unicursal star's one line. */
export const STAR_ORDER = [0, 2, 5, 3, 1, 4];

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
  /** How far through the run (circles landed, hit or not), and how many were hit. */
  landed: 0,
  hits: 0,
  /** When the next circle should land. */
  nextAt: 0,
  /** Which of the star's points were hit, in order. */
  drawn: [] as (boolean | undefined)[],
  circles: [] as Circle[],
  bursts: [] as Burst[],
  /** The flash as the boost hits (1 down to 0): 666 reached. */
  burn: 0,
};

/** The heart's period now: quicker with the pump, and through the run. */
export const heartPeriod = () => HEART.period - HEART.quicken * Math.max(ride.drive.pump, rhythm.active ? rhythm.landed / RHYTHM.count : 0);

function beatAfter(time: number) {
  const beat = heartPeriod();
  const toBeat = (1 - ride.drive.phase) * beat;
  const from = rhythm.clock + toBeat;
  return from + Math.ceil(Math.max(0, time - from) / beat) * beat;
}

function spawn() {
  const r = rhythm;
  const n = r.landed + r.circles.length;
  const point = STAR_ORDER[n];
  r.circles.push({ point, x: 0, y: 0, at: r.nextAt, number: (n + 1) * 111 });
  // (Closer and closer: the last few come quick.)
  r.nextAt = beatAfter(r.nextAt + 0.95 - 0.08 * n);
}

function stop() {
  rhythm.active = false;
  rhythm.teaching = false;
  rhythm.circles.length = 0;
}

/** The run's over, 666 landed: the boost, as hard as it was clean; nothing at all if none were hit. */
function finish() {
  const r = rhythm;
  const score = r.hits / RHYTHM.count;
  stop();
  if (!r.hits) return;
  r.burn = 1;
  const d = ride.drive;
  d.pump = Math.max(d.pump, 0.35 + 0.65 * score);
  d.speed += 55 * score;
}

function land(c: Circle, kind: Burst['kind']) {
  const r = rhythm;
  r.circles.splice(r.circles.indexOf(c), 1);
  r.drawn[r.landed] = kind !== 'miss';
  r.landed++;
  if (kind !== 'miss') r.hits++;
  r.bursts.push({ x: c.x, y: c.y, age: 0, kind, number: c.number });
  if (r.landed >= RHYTHM.count) finish();
}

function hit(c: Circle, off: number) {
  const r = rhythm;
  const teaching = r.teaching;
  land(c, off < RHYTHM.perfect || teaching ? 'perfect' : 'good');
  if (teaching) {
    r.teaching = false;
    r.taught = true;
    r.nextAt = beatAfter(r.clock + 0.95);
  }
}

/**
 * A press of the rocket or Space: starts a run if none's going and the last boost has mostly run out; otherwise, or a click
 * on a circle (`on`, already checked to be over it), hits the one landing next if it's near enough its time.
 */
export function pressRhythm(on?: Circle) {
  const r = rhythm;
  ride.drive.cruise = true;
  if (!r.active) {
    if (ride.drive.pump > 0.25) return;
    r.active = true;
    r.landed = 0;
    r.hits = 0;
    r.drawn.length = 0;
    r.teaching = !r.taught;
    r.nextAt = beatAfter(r.clock + RHYTHM.approach);
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
    r.slow = left < 0.02 ? 0 : Math.min(r.slow, Math.max(0.02, left / 0.6));
  } else r.slow = Math.min(1, r.slow + dt * 3.5);
  r.clock += dt * r.slow;
  r.burn = Math.max(0, r.burn - dt / 1.1);
  for (const b of r.bursts) b.age += dt;
  while (r.bursts.length && r.bursts[0].age > 0.6) r.bursts.shift();
  if (!r.active || r.teaching) return;
  for (const c of [...r.circles]) {
    if (r.clock - c.at <= RHYTHM.good) continue;
    land(c, 'miss');
    if (!r.active) return;
  }
  if (r.landed + r.circles.length < RHYTHM.count && r.clock >= r.nextAt - RHYTHM.approach) spawn();
}
