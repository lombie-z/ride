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
   * cruising, a boost from scrolling (m/s), and how far it's left the landing behind (0 to 1).
   */
  drive: { s: 0, speed: 0, cruise: false, boost: 0, away: 0, rewindFrom: -1 },
  /**
   * Getting off after a real ride: a sheet of black oil washes over the screen (components/three/liquid-sweep.ts) and,
   * while it covers it, the ride is put back; seconds since it began, or -1.
   */
  wash: -1,
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
