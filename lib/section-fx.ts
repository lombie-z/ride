import type { Path } from './course';
import { sections } from './sections';

// Where the stairwell's and flooded tunnel's effects happen (components/three/section-fx.tsx, lib/section-audio.ts). Distances are along the
// core's road (ride.drive.s less its leg's at), positions in its frame on three's axes. Sites go by share of their section and metres off the
// road's line, so they move and stretch with it (art/core/road_sections.py's lengths and doors), and steam comes from the stair's own events.

/** Sparks, moment 6: share of the stairwell, metres to the road's left, up over it. */
const SPARKS: [number, number, number][] = [
  [0.506, 3.6, 6],
  [0.57, -3.6, 6],
  [0.601, 3.6, 6],
  [0.665, -3.6, 6],
  [0.696, 3.6, 6],
  [0.761, -3.6, 6],
  [0.798, 3.6, 6],
  [0.849, -3.6, 6],
];

/** Drips off the beams: share of the stairwell, left, up. */
const STAIR_DRIPS: [number, number, number][] = [
  [0.12, -5.2, 6.8],
  [0.22, 5.2, 6.8],
  [0.342, -5.2, 6.8],
  [0.43, 5.2, 6.8],
  [0.497, -5.2, 6.8],
  [0.541, 5.2, 6.8],
  [0.597, -5.2, 6.8],
  [0.641, 5.2, 6.8],
  [0.696, -5.2, 6.8],
  [0.746, 5.2, 6.8],
  [0.796, -5.2, 6.8],
  [0.84, 5.2, 6.8],
];
/** And off the tube's crown: share of the tunnel, left, up. */
const TUNNEL_DRIPS: [number, number, number][] = [
  [0.03, 4.8, 9.5],
  [0.095, -4.8, 9.5],
  [0.173, 4.8, 9.5],
  [0.238, -4.8, 9.5],
  [0.329, 4.8, 9.5],
  [0.394, -4.8, 9.5],
  [0.524, 4.8, 9.5],
  [0.602, -4.8, 9.5],
  [0.69, 4.8, 9.5],
  [0.771, -4.8, 9.5],
  [0.843, 4.8, 9.5],
  [0.908, -4.8, 9.5],
];

/** The tube's centre over the water, and its inner radius (art/core/ASSETS.md: 5.5 over the deck, the water 0.35). */
export const TUBE = { overWater: 5.15, radius: 9 };

/** A road's per-point value `u` metres along it, between its points. */
export function pathValue(road: Path, values: ArrayLike<number> | undefined, u: number) {
  if (!values || u < 0 || u > road.length) return 0;
  const f = Math.min(u / road.step, values.length - 1);
  const i = Math.min(Math.floor(f), values.length - 2);
  return values[i] + (values[i + 1] - values[i]) * (f - i);
}

/** A point `left` metres off the road's line and `up` over it, at `u`. */
function off(road: Path, u: number, left: number, up: number): [number, number, number] {
  const i = Math.min(Math.round(u / road.step), road.x.length - 3);
  const a = Math.max(i - 2, 0);
  const heading = Math.atan2(road.y[i + 2] - road.y[a], road.x[i + 2] - road.x[a]);
  const x = road.x[i] - Math.sin(heading) * left;
  const y = road.y[i] + Math.cos(heading) * left;
  return [x, (road.heights?.[i] ?? 0) + up, -y];
}

/** All of it, for the road as it's been spliced together. */
export function placeSectionFx(road: Path) {
  const { stair, flood, water, air, events } = sections;
  const inStair = (share: number) => stair.from + share * (stair.to - stair.from);
  const inFlood = (share: number) => flood.from + share * (flood.to - flood.from);
  const steam = events
    .filter((e) => e.kind === 'steam' && e.at)
    .map((e) => {
      const [x, y, z] = e.at as number[];
      return { s: e.s, at: [x, z, -y] as [number, number, number], dir: e.dir ?? 0 };
    });
  const sparks = SPARKS.map(([share, left, up]) => ({ s: inStair(share), at: off(road, inStair(share), left, up) }));
  const drips = [
    ...STAIR_DRIPS.map(([share, left, up]) => off(road, inStair(share), left, up)),
    ...TUNNEL_DRIPS.map(([share, left, up]) => off(road, inFlood(share), left, up)),
  ];
  // Splashes: into the water at the foot of the stairs, and back into it off the wall (where the spray comes back on).
  const splashes: { s: number; size: number; sound: 'splash' | 'splash-big' }[] = [{ s: flood.from - 3, size: 1, sound: 'splash-big' }];
  const spray = road.spray;
  if (spray) {
    for (let i = Math.round((flood.from + 20) / road.step); i < spray.length; i++) {
      if (spray[i - 1] < 0.5 && spray[i] >= 0.5 && i * road.step < water.to - 10) splashes.push({ s: i * road.step, size: 0.6, sound: 'splash' });
    }
  }
  return {
    from: stair.from,
    to: flood.to,
    /** Past this, it's the tunnel's: where the water's rush takes over. */
    water: flood.from,
    waterTo: water.to,
    level: water.level,
    bulkhead: sections.bulkhead.at,
    steam,
    sparks,
    drips,
    splashes,
    /** Where it lands off the stair's gap. */
    landings: air.map((a) => a[1]),
  };
}

export type SectionFxPlaces = ReturnType<typeof placeSectionFx>;
