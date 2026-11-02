import { type Object3D, Vector3 } from 'three';

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
   */
  drive: { s: 0, speed: 0, cruise: false, boost: 0, away: 0, rewindFrom: -1, time: 0, boosting: false, surge: 0 },
  /**
   * Getting off after a real ride: a sheet of black oil washes over the screen (components/three/liquid-sweep.ts) and,
   * while it covers it, the ride is put back; seconds since it began, or -1.
   */
  wash: -1,
  /**
   * The bike's chrome morph for the second city (components/three/bike.tsx): wanted (0 or 1) and how far the seam has
   * swept, nose to tail (0 black chitin, 1 chrome).
   */
  chrome: { want: 0, at: 0 },
  /** The second city has loaded and is ready to draw without a hitch (components/three/city-two.tsx). */
  secondCity: { ready: false },
  /**
   * Riding into the second city: once it's placed, `at` is how far down the road (m, as drive.s) its own road takes over;
   * `t` the change from the green night to its sunset (0 to 1), `arrived` once the bike's pulled up at its spot, and
   * `arrive` the camera's glide from the rider's seat to the arrival shot (0 to 1), and `clear` how far the street's
   * towers by the water have sunk away and the train's beam risen in their place (0 to 1, over a few seconds).
   */
  transition: { placed: false, at: 0, t: 0, arrived: false, arrive: 0, clear: 0 },
};

/**
 * The second city's own road from where it takes over (art/build-city2.py City2.RoadPath: its centreline every 2 m, in
 * the city's local frame, Blender's: x along the road in, y to its left), weaving through the towers to the bike's spot.
 * Set by components/three/city-two.tsx once the city's loaded. Until then (and as a fallback) a straight 120 m, a 90°
 * right-hand bend of 140 m radius and a 30 m run in.
 */
let path: { x: Float32Array; y: Float32Array; step: number; length: number } | null = null;
export function setCityPath(points: number[][] | number[], step: number, length: number) {
  const flat = (points as (number | number[])[]).flat() as number[];
  const n = flat.length / 2;
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = flat[2 * i];
    y[i] = flat[2 * i + 1];
  }
  path = { x, y, step, length };
  slicks = null;
}
const FALLBACK = { straight: 120, radius: 140, tail: 30 };
export const cityRoadLength = () => path?.length ?? FALLBACK.straight + (Math.PI / 2) * FALLBACK.radius + FALLBACK.tail;
/** Where along the second city's road u metres in is: local x, y and heading (radians, anticlockwise from +x). */
export function cityRoadAt(u: number) {
  if (path) {
    const { x, y, step } = path;
    const last = x.length - 1;
    const at = (v: number) => {
      const f = Math.min(Math.max(v / step, 0), last);
      const i = Math.min(Math.floor(f), last - 1);
      const t = f - i;
      return [x[i] + (x[i + 1] - x[i]) * t, y[i] + (y[i + 1] - y[i]) * t];
    };
    const [px, py] = at(u);
    // (Heading from points a few metres either side, not the 2 m segment underfoot: that turned in steps, a jolt to the
    // bike, and the camera riding on it, every segment.)
    const [ax, ay] = at(u - 4);
    const [bx, by] = at(u + 4);
    return { x: px, y: py, heading: Math.atan2(by - ay, bx - ax) };
  }
  const { straight, radius, tail } = FALLBACK;
  const arc = (Math.PI / 2) * radius;
  if (u <= straight) return { x: u, y: 0, heading: 0 };
  if (u <= straight + arc) {
    const a = (u - straight) / radius;
    return { x: straight + radius * Math.sin(a), y: -radius * (1 - Math.cos(a)), heading: -a };
  }
  return { x: straight + radius, y: -radius - Math.min(tail, u - straight - arc), heading: -Math.PI / 2 };
}
/** How sharply the road turns u metres in (radians per metre, positive to the left), over a few metres either side. */
export function cityRoadCurve(u: number) {
  const d = cityRoadAt(u + 6).heading - cityRoadAt(u - 6).heading;
  return Math.atan2(Math.sin(d), Math.cos(d)) / 12;
}
/** How far the road runs straight on from where it takes over (m): the lagoon straight. */
export function cityRoadStraight() {
  let u = 0;
  while (u < cityRoadLength() && Math.abs(cityRoadAt(u).heading) < 1e-3) u += 2;
  return u;
}

/**
 * The second city's arrival shot (art/build-city2.py City2.ArrivalCam, fitted to concept-chrome-city with the bike at the
 * end of its road): eye and look-at in the city's frame (three's axes: x along the road in, y up, z to its right), vertical FOV.
 */
export const ARRIVAL = { eye: [617.7743, 0.5002, 169.5642], look: [627.1305, 1.9546, 172.7805], fov: 50.635 } as const;

/**
 * Slicks of black ooze on the second city's road, thickening toward the plaza (the billboard's ooze has run): placed by
 * a hash along the road's last stretch, each an ellipse (along and across the road, m) with a height. Riding through one
 * the bike slows, as through muck (components/three/ride.tsx), and rides up on it.
 */
let slicks: Slick[] | null = null;
export type Slick = { u: number; across: number; along: number; wide: number; height: number; turn: number };
export function muckSlicks() {
  if (slicks) return slicks;
  const end = cityRoadLength();
  const hash = (i: number, n: number) => {
    const h = Math.sin(i * 127.1 + n * 311.7) * 43758.5453;
    return h - Math.floor(h);
  };
  slicks = [];
  for (let i = 0; i < 28; i++) {
    // Denser toward the end: squared spacing back from the bike's spot.
    const u = end - 6 - hash(i, 1) ** 1.8 * 240;
    slicks.push({
      u,
      across: (hash(i, 2) - 0.5) * 8,
      along: 1.2 + hash(i, 3) * 3.4,
      wide: 0.9 + hash(i, 4) * 2.2,
      height: 0.06 + hash(i, 5) * 0.16,
      turn: (hash(i, 6) - 0.5) * 1.2,
    });
  }
  return slicks;
}
/** How high the ooze is under the bike u metres along the second city's road (on its line): 0 off any slick. */
export function muckUnder(u: number) {
  let h = 0;
  for (const s of muckSlicks()) {
    const a = (u - s.u) / s.along;
    const c = s.across / s.wide;
    const r = a * a + c * c;
    if (r < 1) h = Math.max(h, s.height * Math.sqrt(1 - r));
  }
  return h;
}

/** How far ahead of the bike the second city's road is placed when the change begins (m): the approach. */
export const TRANSITION_LEAD = 320;
/** Seconds for the chrome seam to sweep the bike. */
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
  return tr.placed && tr.t >= 1 && ride.chrome.at >= 1 && ride.drive.s - tr.at > 260;
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
