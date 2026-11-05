// The green city's street as a plan: what stands on each tile of road, from its index alone, so it never changes when
// it's revisited. Read by the street's instances (components/three/drive.tsx) and the riders on it
// (components/three/street-riders.tsx). Along is metres past the deck's far end, across is metres right of the road's
// centre line; tile k runs from k * TILE to (k + 1) * TILE, and the bike reaches tile k about 6.7 + 0.75 k seconds in.
//
//   open     tiles 0-13    6.7-17 s  Towers set well back, flyovers rising alongside, the sky.
//   streets  tiles 14-30   17-30 s   Side streets off both sides, overpasses across, riders peeling off.
//   through  tiles 31-47   30-43 s   Five halls through the ground floors of towers, a dark gap between each.
//   canyon   tiles 48-65   43-56 s   Walls of towers at the barrier, sky bridges, the pack; the chrome city opens it.
//
// Past that, should the chrome city still be loading, it goes round again without the halls: a change of road ahead
// can't land inside one.

export const TILE = 24;
export const DECK_Y = -11;
export const GROUND_Y = -80;
export const SLAB = { width: 11.8, depth: 1.2 };
export const HALF = SLAB.width / 2;
/** A hall's ceiling, above the road. */
export const ROOF = 7.4;

export const hash = (a: number, b: number, c = 0) => {
  const h = Math.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453;
  return h - Math.floor(h);
};

export type Phase = 'open' | 'streets' | 'through' | 'canyon';
export type Branch = { k: number; side: 1 | -1; angle: number; cos: number; sin: number; length: number; width: number; at: number };
export type Over = { k: number; at: number; turn: number; y: number; span: number; width: number };
export type Hall = { kind: 0 | 1 | 2; i: number; n: number; tall: number; wide: number };
export type Tile = { k: number; phase: Phase; branches: Branch[]; over: Over | null; hall: Hall | null; bridge: number };

const LOOP_FROM = 66;
const LOOP = [
  ['streets', 16],
  ['canyon', 14],
  ['open', 12],
] as const;
const LOOP_LENGTH = LOOP.reduce((sum, [, n]) => sum + n, 0);

function phaseOf(k: number): Phase {
  if (k < 14) return 'open';
  if (k < 31) return 'streets';
  if (k < 48) return 'through';
  if (k < LOOP_FROM) return 'canyon';
  let i = (k - LOOP_FROM) % LOOP_LENGTH;
  for (const [phase, n] of LOOP) {
    if (i < n) return phase;
    i -= n;
  }
  return 'open';
}

// The first pass's side streets, by tile: which side, how sharply off the road (degrees).
const BRANCHES = new Map<number, [1 | -1, number][]>([
  [15, [[1, 42]]],
  [17, [[-1, 38]]],
  [
    21,
    [
      [1, 90],
      [-1, 90],
    ],
  ],
  [24, [[1, 52]]],
  [28, [[-1, 34]]],
]);
// And its overpasses: how far off square across the road (radians), how high.
const OVERS = new Map<number, [number, number]>([
  [9, [0.1, 9]],
  [19, [-0.22, 10]],
  [26, [0.28, 8.5]],
]);
// The halls: first tile, how many, which kind (0 strip-lit, 1 dim with green lines, 2 the brightest).
const HALLS: [number, number, 0 | 1 | 2][] = [
  [31, 3, 0],
  [35, 2, 1],
  [38, 3, 0],
  [42, 2, 1],
  [45, 3, 2],
];

const makeBranch = (k: number, side: 1 | -1, degrees: number): Branch => {
  const angle = (degrees * Math.PI) / 180;
  return { k, side, angle, cos: Math.cos(angle), sin: Math.sin(angle), length: 320, width: 9, at: (k + 0.5) * TILE };
};

const tiles = new Map<number, Tile>();
const DECK: Tile = { k: -1, phase: 'open', branches: [], over: null, hall: null, bridge: 0 };

/** What's on tile k. */
export function tileAt(k: number): Tile {
  if (k < 0) return DECK;
  const known = tiles.get(k);
  if (known) return known;
  const phase = phaseOf(k);
  const tile: Tile = { k, phase, branches: [], over: null, hall: null, bridge: 0 };
  if (k < LOOP_FROM) {
    for (const [side, degrees] of BRANCHES.get(k) ?? []) tile.branches.push(makeBranch(k, side, degrees));
    const over = OVERS.get(k);
    if (over) tile.over = { k, at: (k + 0.5) * TILE, turn: Math.PI / 2 + over[0], y: DECK_Y + over[1], span: 420, width: 9 };
    for (const [start, n, kind] of HALLS) {
      if (k >= start && k < start + n) tile.hall = { kind, i: k - start, n, tall: 95 + hash(start, 21) * 130, wide: 16 + hash(start, 22) * 8 };
    }
  } else if (phase === 'streets') {
    // (Going round again: the same kinds of thing, from the hash.)
    if (k % 3 === 0) tile.branches.push(makeBranch(k, hash(k, 23) > 0.5 ? 1 : -1, 34 + hash(k, 24) * 26));
    else if (k % 7 === 1)
      tile.over = { k, at: (k + 0.5) * TILE, turn: Math.PI / 2 + (hash(k, 25) - 0.5) * 0.5, y: DECK_Y + 8.5 + hash(k, 26) * 2, span: 420, width: 9 };
  }
  // A sky bridge between the canyon's walls, every few tiles: how high (0 none).
  if (phase === 'canyon' && k % 3 === 1 && hash(k, 27) > 0.2) tile.bridge = 13 + hash(k, 28) * 38;
  tiles.set(k, tile);
  return tile;
}

/** Whether a tower at this spot would stand clear of the side streets and overpasses near tile k. */
export function towerClear(k: number, along: number, across: number, radius: number) {
  // (A street leaves forward, so those from well back along the road can still reach this far.)
  for (let n = k - 13; n <= k + 1; n++) {
    const t = tileAt(n);
    for (const b of t.branches) {
      if (Math.sign(across) !== b.side) continue;
      const da = along - b.at;
      const dc = Math.abs(across) - HALF;
      const on = da * b.cos + dc * b.sin;
      const off = -da * b.sin + dc * b.cos;
      if (on > -radius && on < b.length + radius && Math.abs(off) < b.width / 2 + 3 + radius) return false;
    }
    if (t.over) {
      const off = (along - t.over.at) * Math.sin(t.over.turn) + across * Math.cos(t.over.turn);
      if (Math.abs(off) < t.over.width / 2 + 2 + radius) return false;
    }
  }
  return true;
}

// Flyovers rising alongside the road through the open stretch: from and to (tiles), how far across, how high at the top.
export const FLYOVERS = [
  { from: 2, to: 16, across: 22, up: 6.5, width: 8 },
  { from: 6, to: 15, across: -21, up: 11, width: 8 },
] as const;
export type Flyover = (typeof FLYOVERS)[number];
/** A flyover's deck height at x tiles along: climbing out from below the road at each end. */
export function flyoverY(f: Flyover, x: number) {
  const edge = Math.min(x - f.from, f.to - x) / 3;
  const e = Math.max(0, Math.min(1, edge));
  return DECK_Y - 14 + (f.up + 14) * e * e * (3 - 2 * e);
}
