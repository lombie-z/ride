import type { Object3D } from 'three';

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
};

/** The bike's anchors (bike.glb's ButtonCentre and RiderEye, or stand-ins), found by components/three/bike.tsx. */
export const anchors = { button: null as Object3D | null, eye: null as Object3D | null, bike: null as Object3D | null };

/** The track frame from which the landing counts as settled (lib/journey.ts: the hold begins at 760). */
export const SETTLED_FRAME = 860;
