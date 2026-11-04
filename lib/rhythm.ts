import { HEART, ride } from './ride';

// The hive's boost: a press of the rocket starts a short run of six circles, numbered as angel numbers from 111 up to 666,
// each with a ring closing on it, to be clicked as it lands on the heart's beat (components/rhythm-overlay.tsx draws them
// and takes the clicks). They stand at the points of a sigil, a different one each run, six points in one line, each drawn
// on to as it's hit, the heart quickening. On 666 the boost hits, as hard as the run was clean (ride.drive.pump), and eyes
// open in every corner of the view and stare in; miss, and they open too. The first ever, the ride slows right down as
// its ring closes, and waits there for the click, showing what's wanted.

/** How long a ring takes to close (s), how far off its landing a click's perfect or still good, and the run's length. */
export const RHYTHM = { approach: 0.8, perfect: 0.11, good: 0.27, count: 6 };

export type Circle = { point: number; x: number; y: number; at: number; number: number };
export type Burst = { x: number; y: number; age: number; kind: 'perfect' | 'good' | 'miss'; number: number };

/** A point round a circle of radius 1, by angle (degrees clockwise from the top). */
const round = (deg: number): [number, number] => [Math.sin((deg * Math.PI) / 180), -Math.cos((deg * Math.PI) / 180)];
/**
 * The sigils: six points each in the order they land, in units of its radius (x right, y down; x is stretched a little on
 * the screen), and whether the last joins back up to the first. Far enough apart for the circles not to overlap.
 */
export const SIGILS: { points: [number, number][]; closed: boolean }[] = [
  // The unicursal star.
  { points: [0, 120, 300, 180, 60, 240].map(round), closed: true },
  // The pentacle, its point down, ending in its heart.
  { points: [...[180, 324, 108, 252, 36].map(round), [0, 0]], closed: false },
  // The triangle, its point down.
  {
    points: [round(180), [-0.43, 0.25], round(300), [0, -0.5], round(60), [0.43, 0.25]],
    closed: true,
  },
  // The spiral, winding in.
  {
    points: [
      [-1.1, 0.1],
      [-0.5, -0.95],
      [0.75, -0.8],
      [1.1, 0.35],
      [0.05, 0.95],
      [0, 0],
    ],
    closed: false,
  },
  // The bow: two loops, crossing.
  {
    points: [
      [0.5, -0.75],
      [1.4, 0],
      [0.5, 0.75],
      [-0.5, -0.75],
      [-1.4, 0],
      [-0.5, 0.75],
    ],
    closed: true,
  },
  // The bolt.
  {
    points: [
      [-0.9, -1],
      [0.45, -0.8],
      [-0.4, -0.15],
      [0.95, 0.05],
      [-0.15, 0.6],
      [0.65, 1],
    ],
    closed: false,
  },
  // The eye.
  {
    points: [
      [-1.4, 0],
      [-0.55, -0.72],
      [0.55, -0.72],
      [1.4, 0],
      [0.55, 0.72],
      [-0.55, 0.72],
    ],
    closed: true,
  },
  // The crown.
  {
    points: [
      [-1.25, 0.85],
      [-1.15, -0.65],
      [-0.4, 0.15],
      [0, -1],
      [0.4, 0.15],
      [1.15, -0.65],
    ],
    closed: false,
  },
];

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
  /** Which sigil this run's drawing. */
  sigil: 0,
  /** Which of its points were hit, in order. */
  drawn: [] as (boolean | undefined)[],
  circles: [] as Circle[],
  bursts: [] as Burst[],
  /** The flash as the boost hits (1 down to 0): 666 reached. */
  burn: 0,
  /** How hard the eyes in the corners are glaring over what's been got wrong (0 to 1, dying away). */
  glare: 0,
  /** Seconds since the boost button's eye (components/three/boost-pod.tsx) began its last blink; when it next does anyway. */
  blink: 9,
  blinkAt: 3,
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
  r.circles.push({ point: n, x: 0, y: 0, at: r.nextAt, number: (n + 1) * 111 });
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
  d.speed += 110 * score;
}

function land(c: Circle, kind: Burst['kind']) {
  const r = rhythm;
  r.circles.splice(r.circles.indexOf(c), 1);
  r.drawn[r.landed] = kind !== 'miss';
  r.landed++;
  if (kind !== 'miss') r.hits++;
  else r.glare = Math.min(1, r.glare + 0.45);
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
  r.blink = 0;
  if (!r.active) {
    if (ride.drive.pump > 0.25) return;
    r.active = true;
    r.landed = 0;
    r.hits = 0;
    r.drawn.length = 0;
    // (Never the same sigil twice running.)
    r.sigil = (r.sigil + 1 + Math.floor(Math.random() * (SIGILS.length - 1))) % SIGILS.length;
    r.teaching = !r.taught;
    r.nextAt = beatAfter(r.clock + RHYTHM.approach);
    spawn();
    return;
  }
  const c = on ?? r.circles[0];
  if (!c) return;
  const off = Math.abs(c.at - r.clock);
  if (off < RHYTHM.good || r.teaching) hit(c, off);
  // (Clicked at the wrong moment: they saw that.)
  else r.glare = Math.min(1, r.glare + 0.25);
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
  // (Slowly through the run, so a run of misses mounts up; then away.)
  r.glare = Math.max(0, r.glare - dt * (r.active ? 0.1 : 0.32));
  r.blink += dt;
  r.blinkAt -= dt;
  if (r.blinkAt <= 0) {
    r.blink = 0;
    r.blinkAt = 2.5 + Math.random() * 5;
  }
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
