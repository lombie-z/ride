/** Scroll progress through the journey: 0 at the hero, 1 at the end. Cheap enough to read every frame. */
export function journeyProgress() {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  return max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
}

/**
 * The hero stage: a centred square the biome fills, the same size as the blog's biome section
 * (640 px max, 24 px gutters), so following the link lands on the same picture.
 */
export function heroStageSize(width: number, height: number) {
  return Math.min(Math.min(640, width) - 48, height * 0.72);
}

/** The journey's length in track frames (art/build-journey.py F_END); beats below are in the same frames. */
export const TRACK_FRAMES = 920;
export const BEATS = {
  /** End of the opening dolly zoom, where the fitted hero hands over to the authored path. */
  open: 80,
  /** The real sky and low sun come in as the camera leaves the hero. */
  sunIn: 70,
  sunFull: 170,
  /** Fog closes in once the camera is among the falls, and thins to a warm haze over the lake. */
  fogIn: 110,
  fogOut: [520, 720],
  /** The rainbow over the pool. */
  bowIn: 640,
  bowFull: 720,
} as const;

/** Shared per-frame journey state: written once a frame by JourneyCamera, read by everything else. */
export const journey = {
  /** Current track frame (0 to TRACK_FRAMES), smoothed by Lenis. */
  frame: 0,
  /** The pixel sweep over the hero before the camera moves (0 to 1; see PRE_ROLL). */
  sweep: 0,
};

/**
 * The scroll's first stretch (a share of the whole) holds the camera on the hero while a pixel sweep runs over it
 * (pixel mode, components/three/pixel-sweep.ts); the camera's journey runs over the rest.
 */
export const PRE_ROLL = 0.06;

/**
 * Pixel mode: the scene drawn at 1/PIXEL of the screen's resolution and scaled up with hard pixel edges, once the
 * sweep has run: the look, and far cheaper to draw. ?pixel=N picks the cell size; ?pixel=1 turns it off.
 */
export const pixelSize = () => {
  if (typeof window === 'undefined') return 4;
  const param = new URLSearchParams(window.location.search).get('pixel');
  const n = param === null ? 4 : Number(param);
  return n > 1 ? n : 0;
};

export const smoothstep = (edge0: number, edge1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
};

/** Dev switches for isolating rendering costs and problems (?nofx, ?norays, ?nolake, ...); always false in production. */
export const devFlag = (name: string) =>
  process.env.NODE_ENV === 'development' && typeof window !== 'undefined' && new URLSearchParams(window.location.search).has(name);

/** Phones and tablets get a lighter render: fewer particles, no light rays, lower resolution. */
export const isLightDevice = () => typeof window !== 'undefined' && (window.matchMedia('(pointer: coarse)').matches || window.innerWidth < 768);

/** 0 until the camera nears the lake, 1 at the landing: the landing's own light, haze and grade blend in on this. */
/**
 * Whether the world below (the canyon, lake and their dressing) is drawn: not for the hero, which sits on the blog's
 * plain plaster, until the fog has closed in (just after the opening): it then emerges as the haze thins.
 */
export const belowVisible = (frame: number) => frame > BEATS.open + 12;

/** The render layer the rainbow lives on: the camera draws it, the lake's mirror doesn't. */
export const RAINBOW_LAYER = 2;

/** The fall's rock ledge, its trees and the waterfall itself come in gradually as the haze opens (0 to 1). */
export const ledgeIn = (frame: number) => smoothstep(BEATS.open + 12, 220, frame);

export const landingAt = (frame: number) => smoothstep(BEATS.fogOut[0], BEATS.fogOut[1], frame);

/**
 * The pull-back: the planter (the clay toy) recedes into the haze above as the camera draws back across the lake, and
 * its streams come to pour out of the sky. 1 while it's there, 0 once it's gone.
 */
export const toyPresence = (frame: number) => 1 - smoothstep(380, 560, frame);
