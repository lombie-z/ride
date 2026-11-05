import { TRACE } from '@/lib/trace';
import { hash, PIXEL, pixelLine, prompt, type TraceFrame, type TraceLook } from './shared';

// D: laser scribe. A thin hard line cut into the glass of the view: white-hot at its head, cooling down through orange to a
// scored groove, a dark line with a lit edge, that stays a moment. Sparse hard sparks, a tight heat only at the head, and a
// dial of ticks round it for how far it's built, with fractures starting off the groove as it does. Off the point the head
// cools to a dull red; lost, the glass cracks out from it. Round the view: scorched edges and cracks working in from them.

const HEAT = ['#ffffff', '#ffffff', '#fff3b8', '#ffc25c', '#ff7d2a', '#d44814'];
const KERF = 'rgba(14, 6, 2, 0.82)';
const GROOVE_DARK = 'rgba(10, 8, 12, 0.62)';
const GROOVE_LIT = 'rgba(255, 246, 235, 0.42)';

type Spark = { x: number; y: number; vx: number; vy: number; age: number; life: number };
const sparks: Spark[] = [];
/** The cracks of a lost run: each a jagged line out from where it broke. */
const cracks: Crack[] = [];
let was = false;

type Crack = { x: number; y: number }[];

/** A fracture from (x, y) heading at angle `a`, by a step's length: long straight runs, then a sudden jag. */
function fracture(x: number, y: number, a: number, steps: number, step: number, rand: () => number): Crack {
  const line = [{ x, y }];
  let cx = x;
  let cy = y;
  let heading = a;
  for (let j = 0; j < steps; j++) {
    heading += (rand() - 0.5) * (rand() < 0.3 ? 1.3 : 0.08);
    const d = step * (0.5 + rand());
    cx += Math.cos(heading) * d;
    cy += Math.sin(heading) * d;
    line.push({ x: cx, y: cy });
  }
  return line;
}

function breakGlass(x: number, y: number) {
  cracks.length = 0;
  const n = 11;
  for (let i = 0; i < n; i++) cracks.push(fracture(x, y, (i / n) * Math.PI * 2 + Math.random() * 0.5, 4 + Math.floor(Math.random() * 4), 26, Math.random));
}

/** A crack as far as `grown` (0 to 1) of it, added to the current path, `ox` to the right. */
function layCrack(g: CanvasRenderingContext2D, line: Crack, grown: number, ox: number) {
  const upto = grown * (line.length - 1);
  for (let i = 1; i <= Math.ceil(upto); i++) {
    const t = Math.min(1, upto - (i - 1));
    const a = line[i - 1];
    const b = line[i];
    pixelLine(g, a.x + ox, a.y, a.x + ox + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
  }
}

// The cracks round the view: fixed ones working in from the rim, each starting at its own point in the build.
const RIM_CRACKS = 16;
let rim: { line: Crack; at: number }[] = [];
let rimW = 0;
let rimH = 0;

function layRim(w: number, h: number) {
  rimW = w;
  rimH = h;
  rim = [];
  for (let i = 0; i < RIM_CRACKS; i++) {
    let n = i * 17 + 3;
    const rand = () => hash(n++);
    // (A place on the rim: more in the corners, where glass goes.)
    const along = rand();
    const round = (along * 2 * (w + h)) % (2 * (w + h));
    const pull = rand() < 0.5 ? 0 : (rand() - 0.5) * 0.2;
    let x = round < w ? round : round < w + h ? w : round < 2 * w + h ? 2 * w + h - round : 0;
    let y = round < w ? 0 : round < w + h ? round - w : round < 2 * w + h ? h : 2 * (w + h) - round;
    x += pull * w;
    y += pull * h;
    const a = Math.atan2(h * 0.42 - y, w * 0.5 - x) + (rand() - 0.5) * 0.7;
    const line = fracture(x, y, a, 3 + Math.floor(rand() * 3), 16 + rand() * 18, rand);
    rim.push({ line, at: rand() * 0.8 });
    // (Some fork.)
    if (rand() < 0.7) {
      const from = line[1 + Math.floor(rand() * (line.length - 2))];
      rim.push({
        line: fracture(from.x, from.y, a + (rand() < 0.5 ? -0.8 : 0.8), 2 + Math.floor(rand() * 3), 12, rand),
        at: Math.min(0.95, rim[rim.length - 1].at + 0.14),
      });
    }
  }
}

function drawRim(g: CanvasRenderingContext2D, f: TraceFrame) {
  if (f.surge < 0.01) return;
  if (f.w !== rimW || f.h !== rimH) layRim(f.w, f.h);
  for (const [ink, ox] of [
    ['rgba(8, 5, 6, 0.8)', 0],
    ['rgba(255, 244, 232, 0.72)', 1],
  ] as const) {
    g.fillStyle = ink;
    g.beginPath();
    for (const c of rim) {
      const grown = Math.min(1, (f.surge - c.at) / 0.2);
      if (grown > 0) layCrack(g, c.line, grown, ox);
    }
    g.fill();
  }
}

function draw(g: CanvasRenderingContext2D, f: TraceFrame) {
  drawRim(g, f);
  const list = f.trail;
  if (was && !f.active && f.lost) {
    breakGlass(f.x, f.y);
    for (let i = 0; i < 24; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = 60 + Math.random() * 200;
      sparks.push({ x: f.x, y: f.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, age: 0, life: 0.25 + Math.random() * 0.4 });
    }
  }
  if (f.active) cracks.length = 0;
  was = f.active;
  const off = f.active && !f.on;

  // The groove first, as far back as it's cooled: dark, with a lit edge a pixel off it, as a scratch in glass catches light.
  g.globalAlpha = f.fade;
  const coolAt = 0.32;
  g.fillStyle = GROOVE_DARK;
  g.beginPath();
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1];
    const b = list[i];
    if (b.age / TRACE.trail < coolAt * 0.5) continue;
    pixelLine(g, a.x / PIXEL, a.y / PIXEL, b.x / PIXEL, b.y / PIXEL);
    // Fractures starting off it, the more the further it's built, in places fixed along the cut.
    const cell = Math.floor(b.s / PIXEL / 14);
    if (cell !== Math.floor(a.s / PIXEL / 14) && hash(cell) < f.built * 0.75) {
      const nx = -(b.y - a.y);
      const ny = b.x - a.x;
      const len = Math.hypot(nx, ny) || 1;
      const side = hash(cell + 5) < 0.5 ? -1 : 1;
      const l = (3 + hash(cell + 9) * 9) * side;
      const sk = (hash(cell + 3) - 0.5) * 6;
      pixelLine(g, b.x / PIXEL, b.y / PIXEL, b.x / PIXEL + (nx / len) * l + sk, b.y / PIXEL + (ny / len) * l + sk);
    }
  }
  g.fill();
  g.fillStyle = GROOVE_LIT;
  g.beginPath();
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1];
    const b = list[i];
    if (b.age / TRACE.trail < coolAt * 0.5) continue;
    pixelLine(g, a.x / PIXEL + 1, a.y / PIXEL + 1, b.x / PIXEL + 1, b.y / PIXEL + 1);
  }
  g.fill();
  // The hot end: a keyline round it, for the bright sky, then its colours by how long since it was cut.
  g.fillStyle = KERF;
  g.beginPath();
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1];
    const b = list[i];
    if (b.age / TRACE.trail > coolAt) continue;
    const ax = a.x / PIXEL;
    const ay = a.y / PIXEL;
    const bx = b.x / PIXEL;
    const by = b.y / PIXEL;
    for (const [dx, dy] of [
      [-1, 0],
      [1, 0],
      [0, -1],
      [0, 1],
    ]) {
      pixelLine(g, ax + dx, ay + dy, bx + dx, by + dy);
    }
  }
  g.fill();
  for (let k = HEAT.length - 1; k >= 0; k--) {
    g.fillStyle = off ? HEAT[Math.min(HEAT.length - 1, k + 3)] : HEAT[k];
    g.beginPath();
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1];
      const b = list[i];
      const age = b.age / TRACE.trail / coolAt;
      if (age > 1 || Math.min(HEAT.length - 1, Math.floor(age * HEAT.length)) !== k) continue;
      pixelLine(g, a.x / PIXEL, a.y / PIXEL, b.x / PIXEL, b.y / PIXEL);
      if (k < 4) pixelLine(g, a.x / PIXEL + 1, a.y / PIXEL, b.x / PIXEL + 1, b.y / PIXEL);
    }
    g.fill();
  }
  g.globalAlpha = 1;

  if (f.active) {
    const x = Math.round(f.x);
    const y = Math.round(f.y);
    // A tight heat, in hard rings, only here.
    const heat = off ? 0.35 : 0.55 + 0.45 * f.built;
    const rings: [number, string][] = [
      [11 + 4 * f.built, `rgba(255, 90, 20, ${0.2 * heat})`],
      [8 + 2 * f.built, `rgba(255, 130, 30, ${0.36 * heat})`],
      [5 + f.built, `rgba(255, 210, 110, ${0.7 * heat})`],
    ];
    for (const [r, colour] of rings) {
      g.fillStyle = colour;
      g.beginPath();
      for (let dy = -Math.ceil(r); dy <= r; dy++) {
        const span = Math.round(Math.sqrt(Math.max(0, r * r - dy * dy)));
        g.rect(x - span, y + dy, span * 2 + 1, 1);
      }
      g.fill();
    }
    // The tip: a small hard diamond, dark round it so it holds against the sky.
    const tip = off ? '#c2401a' : '#ffffff';
    g.fillStyle = KERF;
    g.beginPath();
    for (let dy = -4; dy <= 4; dy++) g.rect(x - (4 - Math.abs(dy)), y + dy, (4 - Math.abs(dy)) * 2 + 1, 1);
    g.fill();
    g.fillStyle = tip;
    g.beginPath();
    for (let dy = -3; dy <= 3; dy++) g.rect(x - (3 - Math.abs(dy)), y + dy, (3 - Math.abs(dy)) * 2 + 1, 1);
    g.fill();

    // How far it's built: a dial of ticks round the tip, lit round from the top.
    const ticks = 20;
    const R = 13 + 3 * f.built;
    const lit = f.built * ticks;
    for (const pass of [0, 1]) {
      g.fillStyle = pass === 0 ? KERF : off ? '#ff6a3a' : '#fff3b8';
      g.beginPath();
      for (let i = 0; i < ticks; i++) {
        if (pass === 1 && i >= lit) continue;
        const a = -Math.PI / 2 + (i / ticks) * Math.PI * 2;
        const on = i < lit;
        const r0 = R;
        const r1 = R + (on ? 4 : 1);
        const c = Math.cos(a);
        const s = Math.sin(a);
        pixelLine(g, x + c * r0, y + s * r0, x + c * r1, y + s * r1);
      }
      g.fill();
    }

    // Sparks: few, and hard.
    if (f.on && Math.random() < f.dt * (7 + 16 * f.built)) {
      const a = Math.random() * Math.PI * 2;
      const v = 40 + Math.random() * 120;
      sparks.push({ x: f.x, y: f.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 30, age: 0, life: 0.18 + Math.random() * 0.32 });
    }
    if (f.teaching) prompt(g, f, f.on ? 'STAY ON THE CUT' : 'HOLD ON THE CUT', R + 10, f.on ? HEAT[1] : '#ff9a6a');
  }

  for (let i = sparks.length - 1; i >= 0; i--) {
    const s = sparks[i];
    s.age += f.dt;
    if (s.age > s.life) {
      sparks.splice(i, 1);
      continue;
    }
    s.vy += 300 * f.dt;
    s.x += s.vx * f.dt;
    s.y += s.vy * f.dt;
    const k = s.age / s.life;
    g.fillStyle = k < 0.4 ? HEAT[0] : k < 0.7 ? HEAT[2] : HEAT[3];
    g.beginPath();
    pixelLine(g, s.x, s.y, s.x - s.vx * 0.022, s.y - s.vy * 0.022);
    g.fill();
  }

  // The glass cracking, out from where it broke.
  if (!f.active && cracks.length && f.fade > 0) {
    const grown = Math.min(1, (1 - f.fade) * 5);
    g.globalAlpha = Math.min(1, f.fade * 2);
    for (const [ink, ox] of [
      [KERF, 0],
      ['rgba(255, 244, 232, 0.85)', 1],
    ] as const) {
      g.fillStyle = ink;
      g.beginPath();
      for (const line of cracks) layCrack(g, line, grown, ox);
      g.fill();
    }
    g.globalAlpha = 1;
  }
  return sparks.length > 0;
}

// Round the view: the glass scorched from its edges in, unevenly, and the picture dimmed a little so the cut carries. (The
// cracks working in from the rim are drawn with the rest, on the overlay: finer than this pass's pixels.)
const edge = /* glsl */ `
vec3 edgeD(vec2 uv, vec2 toward, vec3 c) {
  float aspect = resolution.x / resolution.y;
  vec2 e = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
  float d = -0.1 * log(exp(-e.x / 0.1) + exp(-e.y / 0.1));
  float grow = smoothstep(0.0, 0.8, surge);
  vec2 p = uv * vec2(aspect, 1.0);
  float front = (0.02 + 0.17 * grow) + (fbm(p * 5.0) - 0.5) * 0.12 * grow;
  float burn = 1.0 - smoothstep(front * 0.1, front, d);
  vec3 toned = c * mix(vec3(1.0), vec3(0.12, 0.07, 0.055), burn * burn);
  return toned * (1.0 - 0.2 * grow);
}`;

export const scribe: TraceLook = { id: 'd', name: 'LASER SCRIBE', bloom: { threshold: 0, intensity: 0.1 }, accent: '#fff3b8', edge, draw };
