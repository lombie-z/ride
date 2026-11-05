import type { Object3D } from 'three';

// The stairwell and flooded tunnel (art/core/SECTIONS.md): spliced into the core's road after the lab's doors, each its own glb, loaded ahead
// of being needed and dropped after (components/three/core-sections.tsx). Everything here is `u`, metres along the core's road (ride.drive.s
// less its leg's `at`). The road's data comes from public/models/sections/road.json (art/core/publish_sections.py), read before the core's city.

/** How the road's points ride: lib/course.ts Path.surface. */
export const SURFACE = { floor: 0, steps: 1, wall: 2, air: 3, water: 4 } as const;

export type SectionId = 'stair' | 'flood';

/**
 * How each section's ridden, in one table. `cruise` m/s (elsewhere the zone's own); `boost` the most its boost gets to, 0 sealed.
 * `sealedFrom`: no boost from this far short of its stop, so it's shed in time. `far`, `fogNear`, `fogFar`, `haze`: the camera's reach and the
 * air, as the stills have them (art/core/sheet_sections.py); `thick*`, the air where the road's own `fog` is 1. `drop`: its own glb's file.
 */
export const SECTION_TABLE = {
  stair: {
    cruise: 30,
    boost: 0,
    sealedFrom: 20,
    far: 420,
    fogNear: 18,
    fogFar: 170,
    haze: '#0d4021',
    thickNear: 10,
    thickFar: 110,
    url: '/models/sections/stair.glb',
  },
  flood: {
    cruise: 36,
    boost: 150,
    sealedFrom: 90,
    far: 300,
    fogNear: 10,
    fogFar: 200,
    haze: '#050d09',
    thickNear: 10,
    thickFar: 200,
    url: '/models/sections/flood.glb',
  },
} as const;

type RoadData = {
  points: number[][];
  length: number;
  step: number;
  width: number;
  heights: number[];
  roll: number[];
  surface: number[];
  fog: number[];
  spray?: number[];
  s0: number;
  air?: number[][];
  events?: { kind: string; s: number; at?: number[]; dir?: number; what?: string }[];
  water?: { level: number; to_s: number };
  stop?: { s: number; door_s: number };
  door?: { open_deg: number; hinge: number[] };
  wall?: number[];
};

export type CoreRoad = {
  points: number[][];
  step: number;
  length: number;
  heights: number[];
  roll: number[];
  surface: number[];
  fog: number[];
  spray: number[];
};

/** Where things stand once it's spliced; `spliced` false, the core's road is just its city's own. */
export const sections = {
  spliced: false,
  /** How far below the lab the hall and chamber stand (m). */
  sink: 0,
  /** Each section's stretch of the core's road. */
  stair: { from: 0, to: 0 },
  flood: { from: 0, to: 0 },
  /** Where the hall's road takes over (the flood's end). */
  hallFrom: 0,
  /** The bulkhead's seat and swing (from flood.py). */
  bulkhead: { at: 0, stop: 0, openDeg: 78.4 },
  /** The gap in the stairwell, the tunnel's water (`level` in the city's z, up to `to`), its stretch up the wall, the steam and so on. */
  air: [] as number[][],
  water: { level: 0, to: 0 },
  wall: [] as number[],
  events: [] as NonNullable<RoadData['events']>,
  /** Each section's glb, once it's loaded and ready to draw (components/three/core-sections.tsx). */
  ready: { stair: false, flood: false } as Record<SectionId, boolean>,
  /** Its loaded scene, null once it's dropped, for what dresses it (components/three/section-fx*). */
  scene: { stair: null, flood: null } as Record<SectionId, Object3D | null>,
};

let data: { stair: RoadData; flood: RoadData } | null = null;

/** Fetches the road's data, before the core's city is read (components/three/zone-city.tsx). Without it, the core's just its own road. */
export async function loadSectionRoad() {
  if (data) return;
  try {
    const r = await fetch('/models/sections/road.json');
    if (r.ok) data = await r.json();
  } catch {
    data = null;
  }
}

/**
 * The core's road with both sections spliced in after the lab's doors, the hall's from the flood's end on. Left as it is if they aren't built
 * for where the doors stand now (`door`, lib/ride.ts LAB_DOOR): the lab's being resized, and they move with it.
 */
export function spliceCore<T extends { points: number[][]; step?: number; length: number }>(road: T, door: number): T | CoreRoad {
  sections.spliced = false;
  sections.sink = 0;
  if (!data || Math.abs(data.stair.s0 - door) > 0.5) return road;
  const { stair, flood } = data;
  const step = road.step ?? 2;
  const head = Math.round(door / step);
  const end = flood.points[flood.points.length - 1];
  // (The flood ends on the old road: from there on it's the hall's.)
  let tail = head;
  let best = Number.POSITIVE_INFINITY;
  for (let i = head; i < road.points.length; i++) {
    const d = Math.hypot(road.points[i][0] - end[0], road.points[i][1] - end[1]);
    if (d < best) {
      best = d;
      tail = i;
    }
  }
  const depth = flood.heights[flood.heights.length - 1];
  const after = road.points.length - 1 - tail;
  const fill = <V>(n: number, v: V) => new Array<V>(n).fill(v);
  const join = (s: number[] | undefined, f: number[] | undefined, a: number, b: number) => [
    ...fill(head, a),
    ...(s ?? fill(stair.points.length, 0)),
    ...(f ?? fill(flood.points.length, 0)).slice(1),
    ...fill(after, b),
  ];
  const spliced: CoreRoad = {
    points: [...road.points.slice(0, head), ...stair.points, ...flood.points.slice(1), ...road.points.slice(tail + 1)],
    step,
    length: door + stair.length + flood.length + (road.length - tail * step),
    heights: join(stair.heights, flood.heights, 0, depth),
    roll: join(stair.roll, flood.roll, 0, 0),
    surface: join(stair.surface, flood.surface, 0, 0),
    fog: join(stair.fog, flood.fog, 0, 0),
    spray: join(undefined, flood.spray, 0, 0),
  };
  Object.assign(sections, {
    spliced: true,
    sink: -depth,
    stair: { from: stair.s0, to: stair.s0 + stair.length },
    flood: { from: flood.s0, to: flood.s0 + flood.length },
    hallFrom: flood.s0 + flood.length,
    bulkhead: { at: flood.stop?.door_s ?? 0, stop: flood.stop?.s ?? 0, openDeg: flood.door?.open_deg ?? 78.4 },
    air: stair.air ?? [],
    water: { level: flood.water?.level ?? depth, to: flood.water?.to_s ?? 0 },
    wall: flood.wall ?? [],
    events: [...(stair.events ?? []), ...(flood.events ?? [])],
  });
  return spliced;
}

/** How far the hall and chamber are sunk below the lab (m): 0 till the sections are spliced in. */
export const hallSink = () => sections.sink;

/** Which section `u` is in, if any. */
export function sectionAt(u: number): SectionId | null {
  if (!sections.spliced) return null;
  if (u >= sections.stair.from && u < sections.stair.to) return 'stair';
  if (u >= sections.flood.from && u < sections.flood.to) return 'flood';
  return null;
}

/** The most it should be going at `u`, by the section it's in or braking into (`brake` m/s²); `zone`, the zone's own cruise, elsewhere. */
export function cruiseAt(u: number, zone: number, brake: number) {
  const here = sectionAt(u);
  if (here) return SECTION_TABLE[here].cruise;
  if (sections.spliced && u < sections.stair.from) return Math.min(zone, SECTION_TABLE.stair.cruise + Math.sqrt(2 * brake * (sections.stair.from - u)));
  return zone;
}

/** The most the boost can take it to at `u`: infinite, or the section's cap. */
export function boostCapAt(u: number) {
  const here = sectionAt(u);
  return here ? SECTION_TABLE[here].boost || SECTION_TABLE[here].cruise : Number.POSITIVE_INFINITY;
}

/** No boost: all through the stairwell (from the lab's doors), and from short of the bulkhead's stop to through it. */
export function boostSealed(u: number) {
  if (!sections.spliced) return false;
  const { stair, bulkhead } = sections;
  if (u >= stair.from - SECTION_TABLE.stair.sealedFrom && u < stair.to) return true;
  return u >= bulkhead.stop - SECTION_TABLE.flood.sealedFrom && u < bulkhead.at + 8;
}

/** How far into the sections' look (their pitch, their lens) it is at `u`, 0 to 1: over the last of the lab, and the first of the hall. */
export function sectionLook(u: number) {
  if (!sections.spliced) return 0;
  const ease = (x: number) => {
    const t = Math.min(1, Math.max(0, x));
    return t * t * (3 - 2 * t);
  };
  return ease((u - sections.stair.from + 20) / 30) * (1 - ease((u - sections.hallFrom) / 60));
}

/** Whether the ride has to wait for a section it's come to (a slow connection): the stretch of tube at the end of the stair's glb is sealed black. */
export function heldAt(u: number) {
  const hold = sections.flood.from + 60;
  return sections.spliced && !sections.ready.flood && u <= hold ? hold : Number.POSITIVE_INFINITY;
}
