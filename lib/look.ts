import { Color, Vector3 } from 'three';
import { course } from './course';
import { ride } from './ride';

// Each city's light: its sky, sun, haze, the grade's tones and the fill from its sky and ground (lib/course.ts ZONES).
// Riding from the green city's night into the chrome city, the night gives way to its sunset; from each city on to the
// next, its light gives way to the next's, over the way out (components/three/ride.tsx ride.transition.t). The sky
// (components/three/sky.tsx), the grade (components/three/effects.tsx) and the fill light (components/three/biome.tsx)
// all read the blend from here.

type Look = {
  top: Color;
  horizon: Color;
  glow: Color;
  cloudLit: Color;
  cloudShade: Color;
  haze: Color;
  light: Color;
  lightIntensity: number;
  /** Where its sun is, in its city's frame (three's axes: x along the road in, y up, z to its right). */
  sun: Vector3;
  fogNear: number;
  fogFar: number;
  /** How much of the sky's cloud shows (1 all of it). */
  clouds: number;
  tone: { shadow: Vector3; mid: Vector3; highlight: Vector3 };
  saturation: number;
  /** Added to the grade's exposure. */
  exposure: number;
  hemiSky: Color;
  hemiGround: Color;
  /** Added to the fill's intensity. */
  hemi: number;
};

const v3 = (x: number, y: number, z: number) => new Vector3(x, y, z);

/** Each city's (index as lib/course.ts ZONES; the green city's night is the sky's own, in components/three/sky.tsx). */
export const LOOKS: (Look | null)[] = [
  null,
  // The chrome city's sunset (concept-chrome-city): violet overhead to hot pink at the horizon, a low orange sun, rose
  // and mauve clouds, a pink haze, and its warm light.
  {
    top: new Color('#4b3586'),
    horizon: new Color('#ff9eb0'),
    glow: new Color('#ff7a3c').multiplyScalar(1.6),
    cloudLit: new Color('#ffb7c8'),
    cloudShade: new Color('#7a5191'),
    haze: new Color('#d8a2c4'),
    light: new Color('#ffb48c'),
    lightIntensity: 3.2,
    sun: v3(2759, 691, 1400).normalize(),
    fogNear: 250,
    fogFar: 3800,
    clouds: 1,
    tone: { shadow: v3(0.98, 0.9, 1.08), mid: v3(1.04, 0.97, 1.0), highlight: v3(1.06, 0.98, 0.9) },
    saturation: 1.2,
    exposure: 0.1,
    hemiSky: new Color('#c9b2ff'),
    hemiGround: new Color('#ffb59a'),
    hemi: 0.9,
  },
  // The hive's dawn (concept-hive-city, -plaza): a rose-violet sky warming to peach at the horizon, the sun low and
  // gold through pink haze, the bone lit warm and its shadows rosy.
  {
    top: new Color('#6a3a5c'),
    horizon: new Color('#ffb08a'),
    glow: new Color('#ffc36b').multiplyScalar(1.9),
    cloudLit: new Color('#ffd0b0'),
    cloudShade: new Color('#8a4a66'),
    haze: new Color('#e8a49a'),
    light: new Color('#ffc89a'),
    lightIntensity: 3.4,
    sun: v3(1, 0.13, -0.62).normalize(),
    fogNear: 180,
    fogFar: 3200,
    clouds: 0.8,
    tone: { shadow: v3(1.0, 0.9, 0.98), mid: v3(1.05, 0.97, 0.95), highlight: v3(1.08, 1.0, 0.88) },
    saturation: 1.15,
    exposure: 0.12,
    hemiSky: new Color('#ffc2c8'),
    hemiGround: new Color('#e0a07a'),
    hemi: 0.9,
  },
  // The desert's noon (concept-desert): a dusty amber sky bleached pale at the horizon, a hot white sun high up, the
  // haze thick and warm, shadows brown.
  {
    top: new Color('#b8753e'),
    horizon: new Color('#f2c27a'),
    glow: new Color('#fff2c8').multiplyScalar(2.2),
    // (Dust, not cloud: its clouds hardly show against the haze.)
    cloudLit: new Color('#efc488'),
    cloudShade: new Color('#d29a5e'),
    haze: new Color('#d9a061'),
    light: new Color('#fff0d0'),
    lightIntensity: 3.8,
    sun: v3(0.55, 0.78, -0.3).normalize(),
    fogNear: 120,
    fogFar: 2600,
    clouds: 0.12,
    tone: { shadow: v3(1.02, 0.95, 0.86), mid: v3(1.06, 0.99, 0.9), highlight: v3(1.08, 1.02, 0.9) },
    saturation: 1.05,
    exposure: 0.16,
    hemiSky: new Color('#ffe0b0'),
    hemiGround: new Color('#c98a4a'),
    hemi: 1.0,
  },
];

/**
 * The light now: how far from the green city's night it is (`day`, 0 to 1), and the blend of the cities' looks (its
 * sun in the world, turned with each city). Updated each frame by components/three/ride.tsx.
 */
export const look = {
  day: 0,
  top: new Color(),
  horizon: new Color(),
  glow: new Color(),
  cloudLit: new Color(),
  cloudShade: new Color(),
  haze: new Color(),
  light: new Color(),
  lightIntensity: 0,
  sun: new Vector3(1, 0.2, 0),
  fogNear: 0,
  fogFar: 0,
  clouds: 1,
  tone: { shadow: new Vector3(), mid: new Vector3(), highlight: new Vector3() },
  saturation: 0.82,
  exposure: 0,
  hemiSky: new Color(),
  hemiGround: new Color(),
  hemi: 0,
};

const UP = new Vector3(0, 1, 0);
const sunA = new Vector3();
const sunB = new Vector3();
/** A city's sun in the world: from where the city stands found (its sun's own position) or its look's. */
function sunOf(k: number, out: Vector3) {
  const leg = course.legs[k];
  return out.copy(leg.sun ?? (LOOKS[k] as Look).sun).applyAxisAngle(UP, leg.yaw);
}

export function updateLook() {
  const tr = ride.transition;
  const k = ride.zone;
  const to = LOOKS[k] as Look;
  // (Into the chrome city, from the night; after it, from the city before.)
  const from = k > 1 ? (LOOKS[k - 1] as Look) : to;
  const t = k > 1 ? tr.t : 1;
  look.day = k > 1 ? 1 : tr.t;
  for (const key of ['top', 'horizon', 'glow', 'cloudLit', 'cloudShade', 'haze', 'light', 'hemiSky', 'hemiGround'] as const) {
    look[key].lerpColors(from[key], to[key], t);
  }
  for (const key of ['lightIntensity', 'fogNear', 'fogFar', 'clouds', 'saturation', 'exposure', 'hemi'] as const) {
    look[key] = from[key] + (to[key] - from[key]) * t;
  }
  for (const key of ['shadow', 'mid', 'highlight'] as const) look.tone[key].lerpVectors(from.tone[key], to.tone[key], t);
  sunOf(k, sunB);
  if (k > 1) sunOf(k - 1, sunA);
  else sunA.copy(sunB);
  look.sun.lerpVectors(sunA, sunB, t).normalize();
}
