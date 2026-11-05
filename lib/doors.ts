import { course, inLength } from './course';
import { closeMemory, type MemoryOptions, memory, memoryLit, type Round, type Rule, startMemory } from './memory';
import { LAB_DOOR, ride } from './ride';
import { sections } from './sections';

// The core's doors: each is a stop on its road and a memory lock (lib/memory.ts) to open it. The ride brakes to a halt in front of a
// shut one (components/three/ride.tsx) and the game opens by itself; each win lights a segment of the door, a wrong answer puts them
// all out, and with them all lit it opens and the ride goes on. Everything about a door is in the table below. They're drawn by
// components/three/core-doors.tsx (the lab's own leaves by components/three/zone-city.tsx) and each has its look in the overlay
// (components/memory-overlay.tsx). Shut again on a new ride.

/** How the game dresses for a door: same tiles and line; its colours and what lights up. */
export type DoorLook = {
  /** The line, the tiles' hairline, a segment lit and unlit, the point of light, and a wash over the view. */
  ink: string;
  frame: string;
  lit: string;
  dark: string;
  spark: string;
  wash: string;
  /** What it lights: plates in the cross's corners, bars there, a wheel stepping round, or rings closing. */
  lock: 'plates' | 'bars' | 'wheel' | 'rings';
};

const LOOKS: Record<string, DoorLook> = {
  vault: { ink: '#e4edf0', frame: '#c4d0d6', lit: '#ffffff', dark: '#26323a', spark: '#ffffff', wash: 'rgba(8, 16, 22, 0.34)', lock: 'plates' },
  lab: { ink: '#7dffa6', frame: '#eef3e6', lit: '#5dff8f', dark: '#17382a', spark: '#c8ffd9', wash: 'rgba(0, 20, 8, 0.34)', lock: 'bars' },
  brass: { ink: '#efb65c', frame: '#b5803a', lit: '#ff5a2a', dark: '#3c2412', spark: '#ffb060', wash: 'rgba(30, 10, 4, 0.42)', lock: 'wheel' },
  core: { ink: '#5dff8f', frame: '#2fe07a', lit: '#b8ffd0', dark: '#0c3a22', spark: '#eafff0', wash: 'rgba(0, 10, 5, 0.46)', lock: 'rings' },
};

const CALM = { pairs: 1, ring: false, scatter: false, moves: false, hues: false };
/** A round: remember, each light and the gap after it, twist steps, how long each, its warning, seconds per press (0: no clock). */
const round = (remember: number, lit: number, gap: number, steps: number, stepTime: number, telegraph: number, press: number, more: Partial<Round>): Round => ({
  ...CALM,
  remember,
  lit,
  gap,
  steps,
  stepTime,
  telegraph,
  press,
  ...more,
});
const SWAP = { moves: true };
const HUES = { hues: true };
const BOTH = { moves: true, hues: true };
const WILD = { ...BOTH, pairs: 2, ring: true };

/** How far the chamber's mouth stands short of the core's road's end (art/core/kit.py MOUTH_BACK), so it's right however long the road is. */
const MOUTH_BACK = 130.43;

/**
 * The doors, in order along the road. `at`: metres along it, null while it isn't on the road yet. `stand`: how far short of it the
 * ride pulls up. `width`, `height`: the leaves drawn for it, 0 where the door's the city's own. `rules`: what it asks, one drawn at
 * random each round if there are two. One round for each win wanted, in an unbroken run. `hintAfter`: how many failed goes in a row
 * before the hint's on offer, for the rest of that door.
 */
export const DOORS = [
  {
    name: 'The gate into the lab',
    at: 148 as number | null,
    stand: 20,
    width: 16.4,
    height: 9.2,
    hintAfter: 3,
    rules: ['c'] as Rule[],
    look: LOOKS.vault,
    rounds: [
      round(3, 0.62, 0.2, 0, 0, 0, 0, {}),
      round(3, 0.58, 0.18, 0, 0, 0, 0, {}),
      round(4, 0.54, 0.16, 0, 0, 0, 0, {}),
      round(4, 0.5, 0.15, 0, 0, 0, 0, {}),
    ],
  },
  {
    name: 'The lab doors',
    at: LAB_DOOR,
    stand: 20,
    width: 0,
    height: 0,
    hintAfter: 3,
    rules: ['c'] as Rule[],
    look: LOOKS.lab,
    rounds: [
      round(3, 0.56, 0.18, 1, 0.9, 0.45, 9, SWAP),
      round(4, 0.52, 0.16, 1, 0.85, 0.4, 8, SWAP),
      round(4, 0.5, 0.15, 2, 0.8, 0.32, 8, SWAP),
      round(5, 0.46, 0.14, 2, 0.75, 0.25, 7, SWAP),
    ],
  },
  {
    name: "The tunnel's bulkhead",
    // (Off the road till the sections are spliced in, lib/sections.ts, which puts it at its seat. `?door=3` plays it. The door's the tunnel's own,
    // components/three/core-sections.tsx, swung open slowly: it's huge. Nothing stands between its stop and it.)
    at: null as number | null,
    stand: 24,
    width: 0,
    height: 0,
    slide: 3.2,
    hintAfter: 3,
    rules: ['a'] as Rule[],
    look: LOOKS.brass,
    rounds: [
      round(3, 0.52, 0.16, 1, 0.85, 0.4, 9, HUES),
      round(4, 0.5, 0.15, 2, 0.8, 0.32, 8, HUES),
      round(5, 0.46, 0.14, 2, 0.75, 0.25, 8, HUES),
      round(5, 0.44, 0.13, 3, 0.7, 0.2, 7, HUES),
    ],
  },
  {
    name: "The chamber's mouth",
    get at() {
      return inLength(course.legs[4]) - MOUTH_BACK;
    },
    stand: 30,
    width: 40,
    height: 30,
    hintAfter: 3,
    rules: ['c', 'a'] as Rule[],
    look: LOOKS.core,
    rounds: [
      round(4, 0.44, 0.13, 2, 0.7, 0.2, 8, BOTH),
      round(4, 0.42, 0.12, 2, 0.66, 0.18, 8, BOTH),
      round(5, 0.4, 0.12, 3, 0.62, 0.14, 7, WILD),
      round(5, 0.38, 0.11, 3, 0.58, 0.1, 7, { ...WILD, scatter: true }),
      round(6, 0.36, 0.1, 4, 0.54, 0.08, 6, { ...WILD, scatter: true }),
    ],
  },
];

export const doorState = DOORS.map(() => ({ opened: false, open: 0, lit: 0, fails: 0 }));
export const doors = {
  /** The door whose game's open on the road, and what the ride was stopped for. */
  current: null as number | null,
};

/** How long the leaves take to slide (s), but for a door with its own, and how far they've gone before the ride sets off. */
const SLIDE = 1.3;
const THROUGH = 0.55;

const inCore = () => ride.zone === 4 && ride.transition.placed;

/** The next shut door up the road from here, if any. */
function nextShut() {
  if (!inCore()) return -1;
  const from = ride.drive.s - ride.transition.at;
  for (let i = 0; i < DOORS.length; i++) {
    const d = DOORS[i];
    if (d.at !== null && !(doorState[i].opened && doorState[i].open >= THROUGH) && d.at - d.stand > from - 1.5) return i;
  }
  return -1;
}

/** Where the ride has to stop for a shut door, along the whole course; infinity if nothing's in its way. */
export function doorStop() {
  const i = nextShut();
  return i < 0 ? Number.POSITIVE_INFINITY : ride.transition.at + (DOORS[i].at as number) - DOORS[i].stand;
}

/** How far a door's open: past it (a jump, in dev), it's as good as open. */
export function doorOpen(i: number) {
  const d = DOORS[i];
  // (Not one it's just set off from, still opening.)
  if (inCore() && d.at !== null && !doorState[i].opened && ride.drive.s - ride.transition.at > d.at - d.stand + 1.5) return 1;
  const k = doorState[i].open;
  return k * k * (3 - 2 * k);
}

/** A door's game, for the road or just to look at. */
export function doorGame(i: number, more: Partial<MemoryOptions>): MemoryOptions {
  const d = DOORS[i];
  return {
    table: d.rounds,
    hintAfter: d.hintAfter,
    ruleFor: () => d.rules[Math.floor(Math.random() * d.rules.length)],
    strikes: Number.POSITIVE_INFINITY,
    look: d.look,
    ...more,
  };
}

function openGame(i: number) {
  const state = doorState[i];
  doors.current = i;
  startMemory(
    doorGame(i, {
      start: state.lit,
      fails: state.fails,
      closeAfter: 0.9,
      onWin: () => {
        state.opened = true;
        state.lit = DOORS[i].rounds.length;
        state.fails = 0;
      },
    })
  );
}

/** Runs the doors on (dt: the frame's real time). */
export function updateDoors(dt: number) {
  // (The lab's only once what's behind it is loaded: components/three/core-sections.tsx.)
  doorState.forEach((s, i) => {
    if (s.opened && (i !== 1 || !sections.spliced || sections.ready.stair)) s.open = Math.min(1, s.open + dt / (DOORS[i].slide ?? SLIDE));
  });
  if (doors.current !== null) {
    const state = doorState[doors.current];
    if (!memory.open) doors.current = null;
    else {
      state.lit = memoryLit();
      // (Once it's open they're done with: onWin's cleared them.)
      if (!state.opened) state.fails = memory.fails;
      // (Pulled up in front of it: the game's put away, its run kept for when they set off again.)
      if (!ride.mounted || !ride.drive.cruise) {
        closeMemory();
        doors.current = null;
      }
    }
  }
  if (memory.open || !ride.mounted || ride.mount < 0.95 || !ride.drive.cruise || ride.transition.arrived) return;
  const stop = doorStop();
  const leg = course.legs[4];
  if (leg.in && ride.drive.s < leg.at + inLength(leg) && ride.drive.s > stop - 1 && ride.drive.speed < 0.6 && !doorState[nextShut()]?.opened)
    openGame(nextShut());
}

/** Puts the bulkhead on the road, or takes it off, as the sections are spliced in (lib/sections.ts: the core's city's just been read). */
export function placeBulkhead() {
  // (Its own `at` is plain: only the chamber's mouth's is worked out, and read-only.)
  (DOORS[2] as { at: number | null }).at = sections.spliced ? sections.bulkhead.at : null;
}

/** Whether the hall's in sight: the bulkhead's opening, or it's through it. It's sealed off till then, and it stands through the shaft's plan. */
export const hallShown = (u: number) => !sections.spliced || doorOpen(2) > 0 || u > sections.bulkhead.at;

/** Getting off: they're all shut again for the next ride. */
export function resetDoors() {
  if (doors.current !== null) {
    closeMemory();
    doors.current = null;
  }
  for (const s of doorState) Object.assign(s, { opened: false, open: 0, lit: 0, fails: 0 });
}
