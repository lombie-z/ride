import { Vector3 } from 'three';

// The course: the zones the ride runs through, one after another. The green city's endless street first, then each
// city in turn, placed where the last one's road leaves off: the chrome city a stretch down the street (lib/ride.ts
// TRANSITION_LEAD), each one after at the end of the one before's way out (its RoadOut). Every city carries its own
// road as data (art/build-city2.py and on: RoadPath, from where it takes over to the bike's spot in its plaza, and
// RoadOut, from there on out of it), so the whole ride is one line, measured as ride.drive.s.

/** What each zone's throttle does, beyond riding on: the button's feature there. */
export type Feature = 'start' | 'surge' | 'heartbeat' | 'slingshot';

export type ZoneDef = {
  id: 'green' | 'chrome' | 'hive' | 'desert';
  name: string;
  /** Its city (null: the green city, the landing's own, with the endless street). */
  city: string | null;
  /** Its node names' prefix in the city's glb (City2.RoadPath and so on). */
  prefix: string;
  bike: string;
  feature: Feature;
  /** Cruising speed there (m/s). */
  cruise: number;
  /** How much the feature adds at full strength, as a share of cruising. */
  boost: number;
};

export const ZONES: ZoneDef[] = [
  { id: 'green', name: 'Green city', city: null, prefix: 'City', bike: '/models/bike.glb', feature: 'start', cruise: 32, boost: 0 },
  { id: 'chrome', name: 'Chrome city', city: '/models/city2.glb', prefix: 'City2', bike: '/models/bike2.glb', feature: 'surge', cruise: 38, boost: 1.7 },
  { id: 'hive', name: 'Coral hive', city: '/models/city3.glb', prefix: 'City3', bike: '/models/bike3.glb', feature: 'heartbeat', cruise: 44, boost: 2.3 },
  { id: 'desert', name: 'Data desert', city: '/models/city4.glb', prefix: 'City4', bike: '/models/bike4.glb', feature: 'slingshot', cruise: 50, boost: 3.2 },
];

/** A road as data: its centreline every `step` metres in its city's frame (Blender's: x along the road in, y to its left). */
export type Path = { x: Float32Array; y: Float32Array; step: number; length: number };

export function makePath(points: number[][] | number[], step: number, length: number): Path {
  const flat = (points as (number | number[])[]).flat() as number[];
  const n = flat.length / 2;
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = flat[2 * i];
    y[i] = flat[2 * i + 1];
  }
  return { x, y, step, length };
}

function pointAt(p: Path, v: number): [number, number] {
  const { x, y, step } = p;
  const last = x.length - 1;
  const f = Math.min(Math.max(v / step, 0), last);
  const i = Math.min(Math.floor(f), last - 1);
  const t = f - i;
  return [x[i] + (x[i + 1] - x[i]) * t, y[i] + (y[i + 1] - y[i]) * t];
}

/** Where along a path u metres in is: its city's local x, y and heading (radians, anticlockwise from +x). */
export function pathAt(p: Path, u: number) {
  const [px, py] = pointAt(p, u);
  // (Heading from points a few metres either side, not the 2 m segment underfoot: that turned in steps, a jolt to the
  // bike, and the camera riding on it, every segment.)
  const [ax, ay] = pointAt(p, u - 4);
  const [bx, by] = pointAt(p, u + 4);
  return { x: px, y: py, heading: Math.atan2(by - ay, bx - ax) };
}

/** A zone's arrival shot, from its city's ArrivalCam: eye and look-at in its frame (three's axes), vertical FOV. */
export type Shot = { eye: [number, number, number]; look: [number, number, number]; fov: number };

/**
 * Each zone as it's placed on the course: its city loaded and ready to draw; placed, with where its road takes over
 * (`at`, as ride.drive.s), where its frame sits in the world (on the deck's level) and its turn about the vertical; its
 * road in and out, and its arrival shot.
 */
export type Leg = {
  ready: boolean;
  placed: boolean;
  at: number;
  origin: Vector3;
  yaw: number;
  in: Path | null;
  out: Path | null;
  /** Where its way out ends, in its frame (Blender's x, y), and the heading there: the next zone goes on from it. */
  end: { x: number; y: number; heading: number } | null;
  shot: Shot | null;
  /** Its sun's direction, in its frame (three's axes), from where its city's own sun stands (else its look's). */
  sun: Vector3 | null;
};

export const course = {
  legs: ZONES.map((): Leg => ({ ready: false, placed: false, at: 0, origin: new Vector3(), yaw: 0, in: null, out: null, end: null, shot: null, sun: null })),
};

/** A point in a zone's frame (Blender's x, y; on its deck) into the world. */
export function legToWorld(leg: Leg, x: number, y: number, out = new Vector3()) {
  const c = Math.cos(leg.yaw);
  const s = Math.sin(leg.yaw);
  // (Three's local x, -y as z, turned about +y by its yaw.)
  return out.set(leg.origin.x + x * c - y * s, leg.origin.y, leg.origin.z - x * s - y * c);
}

/** How long a zone's road in is (to the bike's spot in its plaza), and its way on out of it. */
export const inLength = (leg: Leg) => leg.in?.length ?? 0;
export const outLength = (leg: Leg) => leg.out?.length ?? 0;

/** The last zone placed whose road has taken over by `s` (0: still on the green city's street). */
export function legIndexAt(s: number) {
  let k = 0;
  for (let i = 1; i < course.legs.length; i++) if (course.legs[i].placed && s >= course.legs[i].at) k = i;
  return k;
}

/**
 * Where on the course `s` metres along it is, in a zone's road: which zone, its frame's x, y and heading. Null on the
 * green city's street (the bike works that out itself, from the street's line).
 */
export function courseLocal(s: number) {
  const k = legIndexAt(s);
  if (k === 0) return null;
  const leg = course.legs[k];
  const u = s - leg.at;
  const length = inLength(leg);
  if (u <= length || !leg.out) return { k, ...pathAt(leg.in as Path, u), u };
  return { k, ...pathAt(leg.out, u - length), u };
}

const world = new Vector3();
/** Where on the course `s` metres along it is in the world (on the deck's level), and the bike's heading there (about y). */
export function courseAt(s: number) {
  const p = courseLocal(s);
  if (!p) return null;
  const leg = course.legs[p.k];
  legToWorld(leg, p.x, p.y, world);
  return { k: p.k, x: world.x, z: world.z, yaw: leg.yaw + p.heading, u: p.u };
}

/** How sharply the course turns `s` metres along it (radians per metre, positive to the left), over a few metres either side. */
export function courseCurve(s: number) {
  const a = courseAt(s - 6);
  const b = courseAt(s + 6);
  if (!a || !b) return 0;
  const d = b.yaw - a.yaw;
  return Math.atan2(Math.sin(d), Math.cos(d)) / 12;
}

/** Puts zone `k` on the course at the end of the one before's way out (it must have been placed and loaded). */
export function placeAfter(k: number) {
  const prev = course.legs[k - 1];
  const leg = course.legs[k];
  if (!prev.placed || !prev.end) return false;
  leg.at = prev.at + inLength(prev) + outLength(prev);
  legToWorld(prev, prev.end.x, prev.end.y, leg.origin);
  leg.yaw = prev.yaw + prev.end.heading;
  leg.placed = true;
  return true;
}

/** Takes every zone back off the course (back at the landing). */
export function resetCourse() {
  for (const leg of course.legs) leg.placed = false;
}
