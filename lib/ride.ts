import { type Object3D, Vector3 } from 'three';
import { course, type Feature, inLength, makePath, type Path, pathAt, ZONES } from './course';

/**
 * The ride button on the bike and getting on: shared per-frame state, written by components/three/ride.tsx (and the
 * pointer by components/ride-button.tsx), read by the camera and the DOM hit area.
 */
export const ride = {
  /** Seconds since the camera settled on the landing (0 while it's elsewhere): the streaks and the button run off it. */
  since: 0,
  /** 0 until the streaks have converged between the handlebars, then 1 once the button is lit. */
  appear: 0,
  /** The streaks have lit the button: it stays lit from then on (no replay on coming back to the landing). */
  activated: false,
  /** How close the pointer is to the button: 0 far off, 1 on it (or focused from the keyboard). */
  near: 0,
  /** The pointer in CSS px (null with no pointer yet, or on touch). */
  pointer: null as { x: number; y: number } | null,
  /** The keyboard focus is on the button. */
  focused: false,
  /** The button on screen, CSS px: its centre and radius; shown when it's in view and lit. */
  screen: { x: 0, y: 0, r: 0, shown: false },
  /** The whole bike's box on screen, CSS px: all of it is the click target. */
  bike: { x0: 0, y0: 0, x1: 0, y1: 0 },
  /** The rider's view is wanted; how far the camera has got there (0 at the landing, 1 on the bike). */
  mounted: false,
  mount: 0,
  /**
   * Riding on (components/three/ride.tsx): distance down the road from the bike's spot (m), speed (m/s), whether it's
   * cruising, a boost from scrolling (m/s), how far it's left the landing behind (0 to 1), seconds spent moving, and
   * the surge: holding the throttle button down (`boosting`) eases `surge` up to 1, near doubling its speed.
   * The slingshot: the button dragged back along its track (`pull`, 0 to 1, from components/ride-button.tsx; `draw`,
   * the same eased, where it's drawn), let go (`release`, its strength, picked up next frame) launches it (`launch`,
   * the kick left, running down over a few seconds; `fire`, the flames round the view, following it).
   * The heartbeat: tapped on the beat (`taps`, counted by the button, picked up next frame), each tap pumps it on
   * (`pump`, 0 to 1, built up beat by beat, ebbing away without them); `beat` the heart's pulse now (0 to 1).
   */
  drive: {
    s: 0,
    speed: 0,
    cruise: false,
    boost: 0,
    away: 0,
    rewindFrom: -1,
    time: 0,
    boosting: false,
    surge: 0,
    pull: 0,
    draw: 0,
    release: 0,
    launch: 0,
    fire: 0,
    taps: 0,
    pump: 0,
    phase: 0,
    beat: 0,
  },
  /**
   * Getting off after a real ride: a sheet of black oil washes over the screen (components/three/liquid-sweep.ts) and,
   * while it covers it, the ride is put back; seconds since it began, or -1.
   */
  wash: -1,
  /**
   * The zone the ride's heading for, or in once it's there (lib/course.ts ZONES: 1 the chrome city, from the green
   * city's street, and on). It moves on to the next when the visitor picks it on the map.
   */
  zone: 1,
  /**
   * The bike's morph from one zone's bike to the next (components/three/bike.tsx): the bike it's been (`from`), the one
   * it's becoming (`to`; the same once it's done), and how far the seam has swept, nose to tail (0 to 1).
   */
  morph: { from: 0, to: 0, at: 0 },
  /**
   * Asked for from the map (components/three/holomap.tsx): ride back to the green city, getting off at the landing;
   * ride on to the next zone.
   */
  request: { back: false, on: false },
  /**
   * Getting on, a glance at the map in the rider's hands before setting off (0 to 1 and back: the same sequence as
   * arriving, components/three/holomap.tsx), and how long it's been going (s).
   */
  preview: 0,
  previewTime: -1,
  /** The map's green city on screen (CSS px), for the button over it; shown while the map's open. */
  mapBack: { x: 0, y: 0, w: 0, h: 0, shown: false, hover: 0 },
  /** The map's next place on screen (CSS px), for the button over it: ride on there; shown while the map's open. */
  mapOn: { x: 0, y: 0, w: 0, h: 0, shown: false, hover: 0 },
  /**
   * Riding into the zone the ride's heading for (ride.zone): once it's placed, `at` is how far down the road (m, as
   * drive.s) its own road takes over (lib/course.ts course.legs); `t` the change of sky and light from the zone before
   * to it (0 to 1), `arrived` once the bike's pulled up at its spot, and `arrive` the camera's glide from the rider's
   * seat to the arrival shot (0 to 1); `clear`, into the chrome city, how far the street's towers by the water have sunk
   * away and the train's beam risen in their place (0 to 1, over a few seconds); then, pulled up, `held` the seconds
   * since the arrival shot settled and `map` the map sequence after it (0 to 1: the camera back on the bike, the
   * rider's hands coming up, the hologram map opening out; components/three/holomap.tsx).
   */
  transition: { placed: false, at: 0, t: 0, arrived: false, arrive: 0, clear: 0, held: 0, map: 0 },
};

/**
 * A city's own road from where it takes over (art/build-city2.py City2.RoadPath and on: its centreline every 2 m, in
 * the city's local frame, Blender's: x along the road in, y to its left), to the bike's spot in its plaza; and its way
 * out. Set by the city's loader (components/three/zone-city.tsx) once it's loaded. Until the chrome city's in (and as a
 * fallback) its road is a straight 120 m, a 90° right-hand bend of 140 m radius and a 30 m run in.
 */
export function setZonePaths(
  k: number,
  data: { in?: { points: number[][]; step?: number; length: number }; out?: { points: number[][]; step?: number; length: number } }
) {
  const leg = course.legs[k];
  if (data.in) leg.in = makePath(data.in.points, data.in.step ?? 2, data.in.length);
  if (data.out) leg.out = makePath(data.out.points, data.out.step ?? 2, data.out.length);
  slicks.delete(k);
}
const FALLBACK = { straight: 120, radius: 140, tail: 30 };
function fallbackPath(): Path {
  const { straight, radius, tail } = FALLBACK;
  const points: number[][] = [];
  const arc = (Math.PI / 2) * radius;
  const length = straight + arc + tail;
  for (let u = 0; u <= length; u += 2) {
    if (u <= straight) points.push([u, 0]);
    else if (u <= straight + arc) {
      const a = (u - straight) / radius;
      points.push([straight + radius * Math.sin(a), -radius * (1 - Math.cos(a))]);
    } else points.push([straight + radius, -radius - (u - straight - arc)]);
  }
  return makePath(points, 2, length);
}
const fallback = fallbackPath();
/** A zone's road in (the chrome city's fallback until one's loaded). */
export const zoneRoad = (k: number) => course.legs[k].in ?? fallback;
/** The chrome city's road in: its length, where along it u metres in is, how sharply it turns there. */
export const cityRoadLength = () => zoneRoad(1).length;
export const cityRoadAt = (u: number) => pathAt(zoneRoad(1), u);
export function cityRoadCurve(u: number) {
  const d = cityRoadAt(u + 6).heading - cityRoadAt(u - 6).heading;
  return Math.atan2(Math.sin(d), Math.cos(d)) / 12;
}
/** How far a zone's road runs straight on from where it takes over (m). */
export function zoneRoadStraight(k: number) {
  const p = zoneRoad(k);
  let u = 0;
  while (u < p.length && Math.abs(pathAt(p, u).heading) < 1e-3) u += 2;
  return u;
}
export const cityRoadStraight = () => zoneRoadStraight(1);

/**
 * The second city's arrival shot (art/build-city2.py City2.ArrivalCam, fitted to concept-chrome-city with the bike at the
 * end of its road): eye and look-at in the city's frame (three's axes: x along the road in, y up, z to its right), vertical FOV.
 */
export const ARRIVAL = { eye: [617.7743, 0.5002, 169.5642], look: [627.1305, 1.9546, 172.7805], fov: 50.635 } as const;

/** How far into the next city's road a city is left behind (m): out of sight back there, so no longer drawn. */
const LEFT_BEHIND = 400;
/** Whether the ride's gone far enough into the city after zone `k` (0 the green city) that `k` needn't be drawn. */
export function leftBehind(k: number) {
  const next = course.legs[k + 1];
  return !!next?.placed && ride.drive.s > next.at + LEFT_BEHIND;
}

/**
 * Slicks of black ooze on a city's road, thickening toward its plaza (the ooze has run): placed by a hash along the
 * road's last stretch, each an ellipse (along and across the road, m) with a height. Riding through one the bike slows,
 * as through muck (components/three/ride.tsx), and rides up on it. In the zones that ooze (the chrome city, the hive).
 */
export const MUCKY = [false, true, true, false];
const slicks = new Map<number, Slick[]>();
export type Slick = { u: number; across: number; along: number; wide: number; height: number; turn: number };
export function muckSlicks(k = 1) {
  const known = slicks.get(k);
  if (known) return known;
  const end = zoneRoad(k).length;
  const hash = (i: number, n: number) => {
    const h = Math.sin(i * 127.1 + n * 311.7 + k * 17.3) * 43758.5453;
    return h - Math.floor(h);
  };
  const list: Slick[] = [];
  for (let i = 0; i < 28; i++) {
    // Denser toward the end: squared spacing back from the bike's spot.
    const u = end - 6 - hash(i, 1) ** 1.8 * 240;
    list.push({
      u,
      across: (hash(i, 2) - 0.5) * 8,
      along: 1.2 + hash(i, 3) * 3.4,
      wide: 0.9 + hash(i, 4) * 2.2,
      height: 0.06 + hash(i, 5) * 0.16,
      turn: (hash(i, 6) - 0.5) * 1.2,
    });
  }
  slicks.set(k, list);
  return list;
}
/** How high the ooze is under the bike u metres along zone k's road in (on its line): 0 off any slick. */
export function muckUnder(u: number, k = 1) {
  if (!MUCKY[k] || u < 0 || u > inLength(course.legs[k]) + 1) return 0;
  let h = 0;
  for (const s of muckSlicks(k)) {
    const a = (u - s.u) / s.along;
    const c = s.across / s.wide;
    const r = a * a + c * c;
    if (r < 1) h = Math.max(h, s.height * Math.sqrt(1 - r));
  }
  return h;
}

/** How far ahead of the bike the second city's road is placed when the change begins (m): the approach. */
export const TRANSITION_LEAD = 320;
/** Seconds for the morph's seam to sweep the bike. */
export const CHROME_SECONDS = 2.6;
/**
 * The change to the second city (and the bike's morph with it) waits for the city to load, and for at least this long
 * riding (s), so a fast load doesn't cut the ride short.
 */
export const MORPH_AFTER = 12;

/**
 * Well into the second city: the rain (the green city's weather) isn't drawn at all. (The green city itself stays, seen
 * in the distance.)
 */
export const pastFirstCity = () => {
  const tr = ride.transition;
  return ride.zone > 1 || (tr.placed && tr.t >= 1 && ride.morph.to >= 1 && ride.morph.at >= 1 && ride.drive.s - tr.at > 260);
};

/** The wash's timing (s): coming in, holding over the swap, draining away. */
export const WASH = { in: 0.85, hold: 0.25, out: 1.0 } as const;
/** How much of the screen the wash covers now, and whether it's draining. */
export function washCover() {
  const t = ride.wash;
  if (t < 0) return { cover: 0, leaving: false };
  const ease = (x: number) => x * x * (3 - 2 * x);
  if (t < WASH.in) return { cover: ease(t / WASH.in), leaving: false };
  if (t < WASH.in + WASH.hold) return { cover: 1, leaving: false };
  return { cover: 1 - ease(Math.min(1, (t - WASH.in - WASH.hold) / WASH.out)), leaving: true };
}
/** Getting off rides back to the spot (the camera gliding with it) when it's only rolled this far; further, the wash. */
export const WASH_FROM = 25;

/** Top cruising speed (m/s) and how hard it speeds up and brakes (m/s²). */
export const CRUISE = 32;
/** Holding the throttle button: how much faster it goes, at full surge. */
export const SURGE = 1.1;
export const ACCEL = 7;
export const BRAKE = 14;
/** The slingshot: how long its kick lasts (s). */
export const LAUNCH_SECONDS = 3.2;
/**
 * The heartbeat: the heart's period at rest (s) and how much quicker it beats fully pumped, how much each tap on the
 * beat pumps it, how far off the beat a tap still counts (s), and how fast the pump ebbs without them (per s).
 */
export const HEART = { period: 0.82, quicken: 0.3, pump: 0.22, window: 0.17, ebb: 0.09 };
/** Which zones' bikes have loaded (components/three/bike.tsx): the morph into one waits for it. */
export const bikeReady = [true, false, false, false];
/** The zone the bike's in now: the one it's heading for once that's mostly come in, else the one before. */
export const zoneHere = () => (ride.transition.placed && ride.transition.t > 0.5 ? ride.zone : ride.zone - 1);
// (Dev: ?feature=surge|heartbeat|slingshot puts that feature on the throttle everywhere, to try it.)
const devFeature =
  process.env.NODE_ENV === 'development' && typeof window !== 'undefined'
    ? (new URLSearchParams(window.location.search).get('feature') as Feature | null)
    : null;
/** The throttle's feature where the bike is now (lib/course.ts ZONES). */
export const featureHere = (): Feature => devFeature ?? ZONES[Math.max(0, zoneHere())].feature;
/** How much the feature here adds at full strength (as a share of cruising). */
export const boostHere = () => (ZONES.find((z) => z.feature === featureHere()) ?? ZONES[0]).boost;

/**
 * The road the bike rides along (components/three/drive.tsx works it out from the city's City.DeckTop marker): its
 * direction ahead of the bike, the heading the bike turns to (about y), the distance from the bike to the deck's far end
 * (where the endless street takes over), and the centre line at that end.
 */
export const road = { ahead: new Vector3(1, 0, 0), yaw: 0, end: 140, endCentre: new Vector3(), width: 11.8, known: false };

/** The bike's anchors (bike.glb's ButtonCentre and RiderEye, or stand-ins), found by components/three/bike.tsx. */
export const anchors = { button: null as Object3D | null, eye: null as Object3D | null, bike: null as Object3D | null };

/** The track frame from which the landing counts as settled (lib/journey.ts: the hold begins at 760). */
export const SETTLED_FRAME = 860;
