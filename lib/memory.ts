// A memory lock, on the core's doors (lib/doors.ts): five tiles in a cross, each with a sigil of its own and a chroma. They light in an
// order, then twist (chromas swap, tiles move round the screen), then they want the order back. One line says what to hold on to, the
// sigil or the chroma; the rest is worked out by playing, a wrong answer showing the tile that was wanted. What makes it fair: that one
// thing is always readable on the tile, wherever it's gone, so there's nothing to guess. A round won moves on to the next, up the table
// it was given; one wrong and the run's back to nothing.
//
// A pure state machine run by updateMemory(dt); components/memory-overlay.tsx draws it and feeds it presses. It knows nothing of the
// ride: startMemory({ table, onWin, onLose }), or read memory.status.

export type Rule = 'a' | 'b' | 'c' | 'd';
export type Truth = 'chroma' | 'tile' | 'sigil' | 'place';

export const RULES: Record<Rule, { truth: Truth; moves: boolean; swaps: boolean; name: string }> = {
  a: { truth: 'chroma', moves: true, swaps: true, name: 'Chroma' },
  b: { truth: 'tile', moves: true, swaps: false, name: 'The tile' },
  c: { truth: 'sigil', moves: true, swaps: true, name: 'Sigils' },
  d: { truth: 'place', moves: true, swaps: true, name: 'The place' },
};

/** The cross's places, in cross units (one is the distance from the centre to an arm). */
export const SLOTS = [
  { name: 'TOP', x: 0, y: -1 },
  { name: 'LEFT', x: -1, y: 0 },
  { name: 'CENTRE', x: 0, y: 0 },
  { name: 'RIGHT', x: 1, y: 0 },
  { name: 'BOTTOM', x: 0, y: 1 },
];
const RING = [0, 3, 4, 1];

export const SIGILS = [
  { name: 'BARS', rows: ['#########', '.........', '#########', '.........', '#########', '.........', '#########', '.........', '#########'] },
  { name: 'CHECKS', rows: ['###...###', '###...###', '###...###', '...###...', '...###...', '...###...', '###...###', '###...###', '###...###'] },
  { name: 'RING', rows: ['#########', '#########', '##.....##', '##.....##', '##.....##', '##.....##', '##.....##', '#########', '#########'] },
  { name: 'CROSS', rows: ['##.....##', '###...###', '.###.###.', '..#####..', '...###...', '..#####..', '.###.###.', '###...###', '##.....##'] },
  { name: 'SPIKE', rows: ['....#....', '....#....', '...###...', '...###...', '..#####..', '..#####..', '.#######.', '.#######.', '#########'] },
];

/**
 * Hard and saturated, none of them the terminal's green. Picked by simulating protan, deutan and tritan vision (Machado 2009):
 * every pair's at least 25 apart in Lab for all three, 70 for full vision. Chroma rounds answer by that alone, so there each also
 * wears its letter.
 */
export const CHROMAS = [
  { name: 'YELLOW', mark: 'Y', hex: '#ffe600' },
  { name: 'RED', mark: 'R', hex: '#ff2a12' },
  { name: 'BLUE', mark: 'B', hex: '#2a5cff' },
  { name: 'WHITE', mark: 'W', hex: '#f4fff8' },
  { name: 'MAGENTA', mark: 'M', hex: '#ff2fc8' },
];

/**
 * One round: how many to remember and how fast they're shown; the twist's steps (0: none), how long each takes, how long it's
 * warned of beforehand, and how nasty (`moves`: tiles change places, `hues`: chromas do); seconds allowed per press (0: no clock).
 */
export type Round = {
  remember: number;
  lit: number;
  gap: number;
  steps: number;
  stepTime: number;
  telegraph: number;
  pairs: number;
  ring: boolean;
  scatter: boolean;
  moves: boolean;
  hues: boolean;
  press: number;
};

/** Beats (s): before the first light, the wrong answer shown, a round cleared, and how long the end holds before a press counts. */
const BEAT = { lead: 0.55, fail: 1.9, pass: 0.95, end: 0.9 };
/** How long a round's point of light takes to get to what it lights (s). */
export const SPARK = 0.5;

export type Phase = 'off' | 'show' | 'twist' | 'repeat' | 'fail' | 'pass' | 'won' | 'lost';
export type Status = 'idle' | 'playing' | 'won' | 'lost';

export type Tile = {
  /** Its sigil, for good. */
  id: number;
  /** Where in the cross it is (where it last came to rest). */
  slot: number;
  chroma: number;
  /** Where it is now, in cross units. */
  x: number;
  y: number;
  /** And on the screen, in CSS px (the overlay keeps these up). */
  sx: number;
  sy: number;
  /** What can be read off it this frame (its chroma turns over partway through a handover): all a fair player gets. */
  shownChroma: number;
  shownSigil: number;
  /** How much of its face has chroma (down to 0 and back as one's handed over). */
  fill: number;
  /** Lit up (1) and dying away. */
  glow: number;
};

type Move = { tile: number; fromX: number; fromY: number; toX: number; toY: number; bend: number; slot: number };
type Hue = { from: number; to: number; chroma: number };
export type Step = { telegraph: number; time: number; age: number; moves: Move[]; hues: Hue[]; links: [number, number][] };

export type MemoryEvent = { type: 'tone'; truth: number } | { type: 'twist' | 'wrong' | 'key' | 'won' | 'lost' | 'locked' | 'go' };

export type MemoryOptions = {
  /** The rounds to play. */
  table: Round[];
  rule?: Rule;
  /** Draws the rule afresh each time a round's shown. */
  ruleFor?: () => Rule;
  /** Starts this far up the table, with this many failed already. */
  start?: number;
  fails?: number;
  /** After this many failed goes in a row, the hint's on offer. */
  hintAfter?: number;
  /** How many wrong answers it takes to lose. */
  strikes?: number;
  /** The same seed, the same run. */
  seed?: number;
  /** Shuts itself this long (s) after the end; otherwise it waits there for a press to go again. */
  closeAfter?: number;
  /** Opened to look at (`?memory=`, `?door=`): the overlay shows keys for the others. */
  review?: 'rules' | 'doors';
  /** What the overlay dresses it in. */
  look?: object;
  onWin?: () => void;
  onLose?: () => void;
};

export const memory = {
  open: false,
  status: 'idle' as Status,
  phase: 'off' as Phase,
  rule: 'c' as Rule,
  rounds: 1,
  /** Which round (from 0). */
  round: 0,
  /** The order, as what's true under the rule: a chroma, a tile (its sigil), or a place. It grows by one a round. */
  sequence: [] as number[],
  /** How far through the showing, and how many have been pressed right. */
  shown: -1,
  pressed: 0,
  /** The tile lit in the showing. */
  lit: null as number | null,
  strikes: 0,
  maxStrikes: 3,
  tiles: [] as Tile[],
  /** Seconds in this phase. */
  phaseT: 0,
  clock: 0,
  /** Seconds left for this press, and out of how many (0: no limit). */
  timer: 0,
  timerMax: 0,
  /** The twist moving now (or the aftershock in a repeat), and those still to come. */
  step: null as Step | null,
  plan: [] as string[][],
  /** The first round ever: forgiving, in no hurry, pointing at what's wanted. */
  teaching: false,
  taught: false,
  /** How many goes have failed. The hint: spent this round; forced on (to test it); the tile it's showing, and that dying away. */
  fails: 0,
  hintSpent: false,
  hintForced: false,
  hintTile: null as number | null,
  hintFlash: 0,
  /** The tile last pressed right. */
  lastPress: 0,
  /** The tile that's wanted, shown only while teaching. */
  hint: null as number | null,
  /** A wrong press while teaching (1, dying away). */
  nudge: 0,
  /** A press that came while it couldn't be taken (1, dying away). */
  locked: 0,
  shake: 0,
  flash: 0,
  /** How far the view's gone to the ghost's green (0 to 1). */
  haze: 0,
  /** What went wrong: who was pressed (null: time ran out), and who was wanted. */
  fail: null as { pressed: number | null; wanted: number; slow: boolean } | null,
  /** How far tiles may fly in cross units (the overlay keeps it to the view). */
  bounds: { x: 1.6, y: 1.2 },
  /** For the sound. The overlay drains it. */
  events: [] as MemoryEvent[],
  options: { table: [] } as MemoryOptions,
  seed: 0,
};

const rand = () => {
  // (mulberry32)
  memory.seed = (memory.seed + 0x6d2b79f5) | 0;
  let t = memory.seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const pick = <T>(list: T[]) => list[Math.floor(rand() * list.length)];
function shuffled<T>(list: T[]) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
const smooth = (t: number) => t * t * (3 - 2 * t);

export const roundOf = () => memory.options.table[Math.min(memory.round, memory.options.table.length - 1)];

/** How many rounds have got as far as lighting something: the one just won once its point of light gets there. */
export function memoryLit() {
  const m = memory;
  if (m.phase === 'won') return m.rounds;
  return m.round + (m.phase === 'pass' && m.phaseT >= SPARK ? 1 : 0);
}

/** What's true of a tile under the rule: what the sequence holds. */
export function truthOf(t: Tile) {
  const truth = RULES[memory.rule].truth;
  return truth === 'chroma' ? t.chroma : truth === 'place' ? t.slot : t.id;
}
const tileFor = (truth: number) => memory.tiles.find((t) => truthOf(t) === truth) as Tile;

function enter(phase: Phase) {
  memory.phase = phase;
  memory.phaseT = 0;
}

/** A new order for the round. */
function grow() {
  const m = memory;
  const length = roundOf().remember;
  m.sequence = [];
  // (Never the same twice running: a light that doesn't change can't be seen to have lit again.)
  while (m.sequence.length < length) {
    const last = m.sequence[m.sequence.length - 1];
    const next = pick([0, 1, 2, 3, 4].filter((n) => n !== last));
    m.sequence.push(next);
  }
}

function show() {
  const m = memory;
  if (m.options.ruleFor) m.rule = m.options.ruleFor();
  grow();
  m.shown = -1;
  m.pressed = 0;
  m.lit = null;
  m.hint = null;
  m.fail = null;
  m.step = null;
  m.hintSpent = false;
  m.hintFlash = 0;
  enter('show');
}

/** The twist's kinds per step, by the rule and the round. Each entry's run together, as one step. */
function planTwist() {
  const m = memory;
  const cfg = roundOf();
  const moves = RULES[m.rule].moves && cfg.moves;
  const swaps = RULES[m.rule].swaps && cfg.hues;
  const plan: string[][] = [];
  const moveKinds = cfg.ring ? ['swap', 'swap', 'ring'] : ['swap'];
  const hueKinds = cfg.ring ? ['hue', 'hue', 'cycle'] : ['hue'];
  let scattered = false;
  for (let i = 0; i < cfg.steps; i++) {
    const both = moves && swaps && cfg.pairs > 1 && rand() < 0.6;
    if (moves && cfg.scatter && !scattered && i > 0 && rand() < 0.6) {
      scattered = true;
      plan.push(swaps ? ['out', 'hue'] : ['out'], ['in']);
      continue;
    }
    if (both) plan.push([pick(moveKinds), pick(hueKinds)]);
    // (Rule c and d's alternate, so a round always has some of each.)
    else if (moves && (!swaps || i % 2 === 0)) plan.push([pick(moveKinds)]);
    else plan.push([pick(hueKinds)]);
  }
  m.plan = plan;
}

/** Tiles by slot: all five, as they are now. */
const bySlot = (slot: number) => memory.tiles.find((t) => t.slot === slot) as Tile;

let lastPair = '';
function pairs(n: number) {
  // (At least one of the first pair is one they've to remember: a lone swap of two that aren't is no twist.)
  const wanted = memory.sequence.map((truth) => tileFor(truth).slot);
  for (let tries = 0; ; tries++) {
    const order = shuffled([0, 1, 2, 3, 4]);
    const list: [number, number][] = [];
    for (let i = 0; i < n; i++) list.push([order[i * 2], order[i * 2 + 1]]);
    const key = [...list[0]].sort().join();
    const touches = wanted.includes(list[0][0]) || wanted.includes(list[0][1]);
    if ((key === lastPair || !touches) && tries < 12) continue;
    lastPair = key;
    return list;
  }
}

function scatterSpots() {
  const { x, y } = memory.bounds;
  const spots: { x: number; y: number }[] = [];
  for (let tries = 0; spots.length < 5 && tries < 400; tries++) {
    const s = { x: (rand() * 2 - 1) * x, y: (rand() * 2 - 1) * y };
    if (spots.every((o) => Math.max(Math.abs(o.x - s.x), Math.abs(o.y - s.y)) > 0.98)) spots.push(s);
  }
  // (The view's too tight for it: they just go wide of the cross.)
  while (spots.length < 5) spots.push({ ...SLOTS[spots.length], x: SLOTS[spots.length].x * 1.1, y: SLOTS[spots.length].y * 1.1 });
  return spots;
}

/** A step of the twist from what's on the board now. `time`: how long it runs. */
function makeStep(kinds: string[], time: number, telegraph: number, pairCount: number): Step {
  const m = memory;
  const step: Step = { telegraph, time, age: 0, moves: [], hues: [], links: [] };
  const move = (t: Tile, x: number, y: number, slot: number, bend: number) =>
    step.moves.push({ tile: t.id, fromX: t.x, fromY: t.y, toX: x, toY: y, bend, slot });
  for (const kind of kinds) {
    if (kind === 'swap') {
      for (const [a, b] of pairs(pairCount)) {
        const ta = bySlot(a);
        const tb = bySlot(b);
        // (Round each other: up and down would go through the centre otherwise.)
        const bend = a === 2 || b === 2 ? 0.22 : 0.55;
        move(ta, SLOTS[b].x, SLOTS[b].y, b, bend);
        move(tb, SLOTS[a].x, SLOTS[a].y, a, bend);
        step.links.push([ta.id, tb.id]);
      }
    } else if (kind === 'ring') {
      const turn = rand() < 0.5 ? 1 : 3;
      const bend = turn === 1 ? -0.32 : 0.32;
      RING.forEach((slot, i) => {
        const to = RING[(i + turn) % 4];
        move(bySlot(slot), SLOTS[to].x, SLOTS[to].y, to, bend);
        step.links.push([bySlot(slot).id, bySlot(to).id]);
      });
    } else if (kind === 'out') {
      const spots = scatterSpots();
      for (const t of m.tiles) move(t, spots[t.id].x, spots[t.id].y, t.slot, 0.2);
    } else if (kind === 'in') {
      const order = shuffled([0, 1, 2, 3, 4]);
      m.tiles.forEach((t, i) => {
        const to = order[i];
        move(t, SLOTS[to].x, SLOTS[to].y, to, -0.15);
      });
    } else if (kind === 'hue') {
      for (const [a, b] of pairs(pairCount)) {
        const ta = bySlot(a);
        const tb = bySlot(b);
        step.hues.push({ from: ta.id, to: tb.id, chroma: ta.chroma }, { from: tb.id, to: ta.id, chroma: tb.chroma });
        step.links.push([ta.id, tb.id]);
      }
    } else if (kind === 'cycle') {
      const order = shuffled([0, 1, 2, 3, 4]);
      order.forEach((slot, i) => {
        const a = bySlot(slot);
        const b = bySlot(order[(i + 1) % 5]);
        step.hues.push({ from: a.id, to: b.id, chroma: a.chroma });
        step.links.push([a.id, b.id]);
      });
    }
  }
  return step;
}

/** The arrangement as far as the sequence goes: to see a twist has really changed something. */
const signature = () => {
  const m = memory;
  return m.sequence.map((truth) => tileFor(truth).slot).join();
};

let before = '';
function twist() {
  const m = memory;
  planTwist();
  before = signature();
  m.lit = null;
  enter('twist');
}

function nextStep() {
  const m = memory;
  const cfg = roundOf();
  const kinds = m.plan.shift();
  if (!kinds) {
    // (It's come back round to how it was: once more, or the twist did nothing. Under `place` nothing's ever meant to change.)
    if (signature() === before && cfg.steps > 0 && RULES[m.rule].truth !== 'place') {
      m.plan.push(RULES[m.rule].moves && cfg.moves ? ['swap'] : ['hue']);
      return;
    }
    repeat();
    return;
  }
  const time = kinds.includes('out') || kinds.includes('in') ? cfg.stepTime * 1.15 : cfg.stepTime;
  m.step = makeStep(kinds, time, cfg.telegraph, cfg.pairs);
  m.events.push({ type: 'twist' });
}

function repeat() {
  const m = memory;
  m.step = null;
  m.pressed = 0;
  m.timerMax = m.teaching ? 0 : roundOf().press;
  m.timer = m.timerMax;
  // Their turn: every tile thrown a frame, with a note of its own. It's the one thing that says so.
  for (const t of m.tiles) t.glow = 1;
  m.events.push({ type: 'go' });
  enter('repeat');
}

function endStep(step: Step) {
  const m = memory;
  for (const mv of step.moves) {
    const t = m.tiles[mv.tile];
    t.x = mv.toX;
    t.y = mv.toY;
    t.slot = mv.slot;
  }
  for (const h of step.hues) m.tiles[h.to].chroma = h.chroma;
  m.step = null;
}

function runStep(step: Step, dt: number) {
  const m = memory;
  step.age += dt;
  const u = Math.max(0, Math.min(1, (step.age - step.telegraph) / step.time));
  const k = smooth(u);
  for (const mv of step.moves) {
    const t = m.tiles[mv.tile];
    const dx = mv.toX - mv.fromX;
    const dy = mv.toY - mv.fromY;
    const len = Math.hypot(dx, dy) || 1;
    const arc = Math.sin(k * Math.PI) * mv.bend;
    t.x = mv.fromX + dx * k + (-dy / len) * arc;
    t.y = mv.fromY + dy * k + (dx / len) * arc;
  }
  if (u >= 1) endStep(step);
}

/** How far through its motion the step is (0 to 1): 0 through its warning. */
export const stepProgress = (step: Step) => smooth(Math.max(0, Math.min(1, (step.age - step.telegraph) / step.time)));

function fail(pressed: number | null, wanted: number, slow: boolean) {
  const m = memory;
  m.strikes++;
  m.fails++;
  m.hintFlash = 0;
  // (The run's gone, all of it: whatever they'd won goes dark at once.)
  m.round = 0;
  m.fail = { pressed, wanted, slow };
  m.step = null;
  m.shake = 1;
  m.flash = 1;
  m.events.push({ type: 'wrong' });
  enter('fail');
}

function finish(status: 'won' | 'lost') {
  const m = memory;
  m.status = status;
  m.step = null;
  m.lit = null;
  m.events.push({ type: status });
  enter(status);
  if (status === 'won') m.options.onWin?.();
  else m.options.onLose?.();
}

function rest() {
  const m = memory;
  m.tiles = [0, 1, 2, 3, 4].map((id) => ({
    id,
    slot: id,
    chroma: id,
    x: SLOTS[id].x,
    y: SLOTS[id].y,
    sx: 0,
    sy: 0,
    shownChroma: id,
    shownSigil: id,
    fill: 1,
    glow: 0,
  }));
  // (Not chroma and sigil tied together from the off: rule a's and c's whole point is that they aren't.)
  const chromas = shuffled([0, 1, 2, 3, 4]);
  for (const t of m.tiles) t.chroma = chromas[t.id];
  const places = shuffled([0, 1, 2, 3, 4]);
  for (const t of m.tiles) {
    t.slot = places[t.id];
    t.x = SLOTS[t.slot].x;
    t.y = SLOTS[t.slot].y;
  }
}

/** Opens the game and starts straight in. */
export function startMemory(options: MemoryOptions) {
  const m = memory;
  m.options = options;
  m.open = true;
  m.rule = options.rule ?? 'c';
  m.rounds = options.table.length;
  m.maxStrikes = Math.max(1, options.strikes ?? 3);
  m.seed = options.seed ?? Math.floor(Math.random() * 2 ** 31);
  m.round = Math.max(0, Math.min(options.start ?? 0, m.rounds - 1));
  m.sequence = [];
  m.strikes = 0;
  m.fails = options.fails ?? 0;
  m.pressed = 0;
  m.shown = -1;
  m.lit = null;
  m.step = null;
  m.plan = [];
  m.fail = null;
  m.hint = null;
  m.events.length = 0;
  m.teaching = !m.taught;
  rest();
  m.status = 'playing';
  show();
}

export function closeMemory() {
  const m = memory;
  m.open = false;
  m.status = 'idle';
  m.phase = 'off';
  m.step = null;
}

/** A press once it's ended, comparing the rules: goes again. */
export function advanceMemory() {
  const m = memory;
  if ((m.phase === 'won' || m.phase === 'lost') && m.phaseT > BEAT.end) startMemory({ ...m.options, seed: undefined });
}

/** A press of a tile. */
export function pressMemory(id: number) {
  const m = memory;
  if (m.phase === 'won' || m.phase === 'lost') {
    advanceMemory();
    return;
  }
  if (m.phase !== 'repeat' || m.step) {
    // (Not their turn. No harm done, they just see it's shut.)
    m.locked = 1;
    m.events.push({ type: 'locked' });
    return;
  }
  const t = m.tiles[id];
  const wanted = m.sequence[m.pressed];
  if (truthOf(t) !== wanted) {
    if (m.teaching) {
      m.nudge = 1;
      m.shake = 0.5;
      m.events.push({ type: 'wrong' });
      return;
    }
    fail(id, tileFor(wanted).id, false);
    return;
  }
  m.events.push({ type: 'tone', truth: wanted });
  t.glow = 1;
  m.lastPress = id;
  m.pressed++;
  m.timer = m.timerMax;
  if (m.pressed >= m.sequence.length) {
    m.hint = null;
    m.events.push({ type: 'key' });
    enter('pass');
  }
}

/** Whether there's a hint on offer: not at all; it can be had right now; it's not their turn; or it's spent till the next round. */
export function hintState(): 'ready' | 'wait' | 'spent' | null {
  const m = memory;
  const after = m.options.hintAfter;
  if (!m.open || m.status !== 'playing' || !(m.hintForced || (after !== undefined && m.fails >= after))) return null;
  if (m.hintSpent) return 'spent';
  return m.phase === 'repeat' && !m.step ? 'ready' : 'wait';
}

/** Shows the next tile to press, wherever it's got to. Costs nothing but itself. */
export function pressHint() {
  const m = memory;
  if (hintState() !== 'ready') return;
  const wanted = m.sequence[m.pressed];
  const t = tileFor(wanted);
  m.hintSpent = true;
  m.hintTile = t.id;
  m.hintFlash = 1;
  m.events.push({ type: 'tone', truth: wanted });
}

/** A press by place (the arrow keys and space). */
export function pressMemorySlot(slot: number) {
  const m = memory;
  const t = m.tiles.find((o) => o.slot === slot);
  if (t) pressMemory(t.id);
}

/** What can be read off each tile this frame. */
function refreshFaces() {
  const m = memory;
  for (const t of m.tiles) {
    let chroma = t.chroma;
    t.fill = 1;
    const step = m.step;
    if (step) {
      const h = step.hues.find((o) => o.to === t.id);
      if (h) {
        const u = stepProgress(step);
        if (u >= 0.5) chroma = h.chroma;
        if (step.age >= step.telegraph) t.fill = Math.abs(2 * u - 1);
      }
    }
    t.shownChroma = chroma;
    t.shownSigil = t.id;
  }
}

/** Runs the game on (dt: the frame's real time). */
export function updateMemory(dt: number) {
  const m = memory;
  m.haze += ((m.open ? 0.5 : 0) - m.haze) * Math.min(1, dt * (m.open ? 5 : 4));
  if (!m.open) return;
  m.clock += dt;
  // The first go's twist is slower, so there's time to see what's being shown.
  const rate = m.teaching && m.phase === 'twist' ? 0.6 : 1;
  m.phaseT += dt * rate;
  m.nudge = Math.max(0, m.nudge - dt * 1.6);
  m.locked = Math.max(0, m.locked - dt * 3);
  m.shake = Math.max(0, m.shake - dt * 2.6);
  m.flash = Math.max(0, m.flash - dt * 2.2);
  m.hintFlash = Math.max(0, m.hintFlash - dt / 1.1);
  for (const t of m.tiles) t.glow = Math.max(0, t.glow - dt * 3.2);
  if (m.phase === 'show') {
    const cfg = roundOf();
    const stretch = m.teaching ? 1.5 : 1;
    const lit = cfg.lit * stretch;
    const beat = lit + cfg.gap * stretch;
    const t = m.phaseT - BEAT.lead;
    if (t >= m.sequence.length * beat) twist();
    else if (t >= 0) {
      const i = Math.floor(t / beat);
      if (i !== m.shown) {
        m.shown = i;
        m.events.push({ type: 'tone', truth: m.sequence[i] });
      }
      const tile = t % beat < lit ? tileFor(m.sequence[i]) : null;
      m.lit = tile ? tile.id : null;
      if (tile) tile.glow = 1;
    }
  } else if (m.phase === 'twist') {
    if (!m.step) nextStep();
    if (m.step) runStep(m.step, dt * rate);
  } else if (m.phase === 'repeat') {
    if (m.step) runStep(m.step, dt);
    else if (m.timerMax) {
      m.timer -= dt;
      if (m.timer <= 0) fail(null, tileFor(m.sequence[m.pressed]).id, true);
    }
    if (m.phase === 'repeat' && m.teaching && !m.step) m.hint = tileFor(m.sequence[m.pressed]).id;
  } else if (m.phase === 'fail') {
    if (m.phaseT >= BEAT.fail) {
      if (m.strikes >= m.maxStrikes) finish('lost');
      else show();
    }
  } else if (m.phase === 'pass') {
    if (m.phaseT >= BEAT.pass) {
      if (m.teaching) {
        m.teaching = false;
        m.taught = true;
      }
      m.round++;
      if (m.round >= m.rounds) finish('won');
      else show();
    }
  } else if ((m.phase === 'won' || m.phase === 'lost') && m.options.closeAfter && m.phaseT >= m.options.closeAfter) {
    closeMemory();
    return;
  }
  refreshFaces();
}
