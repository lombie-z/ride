import { TRACE } from '@/lib/trace';
import { GLYPH_W, PIXEL, pixelLine, plate, prompt, type TraceFrame, type TraceLook } from './shared';

// B: lock-on. A targeting HUD: hard brackets on a moving target, drawn at the very tolerance the game's checking, so what
// you see is what you've got, closing in step as the lock builds; a thin wire back to the button, plots of the target's
// track, a lead line showing where it's going, readouts counting up, and rulers ticking how far off it you are. One ink,
// amber, on a black keyline so it holds against the bright sky. No glow. Round the view: hard letterbox bars, and a hard amber
// border up each side with a speed tape in it. (Kept for the final boss, whatever becomes of the chrome city's other looks.)

const AMBER = '#ffb300';
const DIM = '#b87a00';
const KEY = 'rgba(8, 5, 0, 0.92)';

type Rect = [number, number, number, number];

/** Fills rects in the ink with a one-pixel black keyline all round, hard. */
function inked(g: CanvasRenderingContext2D, rects: Rect[], ink = AMBER, key = KEY) {
  g.fillStyle = key;
  g.beginPath();
  for (const [x, y, w, h] of rects) g.rect(x - 1, y - 1, w + 2, h + 2);
  g.fill();
  g.fillStyle = ink;
  g.beginPath();
  for (const [x, y, w, h] of rects) g.rect(x, y, w, h);
  g.fill();
}

const pad = (n: number, width = 3) => String(Math.max(0, Math.round(n))).padStart(width, '0');

/** Four corners of a box of half-size `s` round the point, `t` thick. */
function brackets(cx: number, cy: number, s: number, len: number, t: number): Rect[] {
  const out: Rect[] = [];
  for (const sx of [-1, 1]) {
    for (const sy of [-1, 1]) {
      const x = cx + sx * s;
      const y = cy + sy * s;
      out.push([sx < 0 ? x : x - len + t, sy < 0 ? y : y - t + 1, len, t]);
      out.push([sx < 0 ? x : x - t + 1, sy < 0 ? y : y - len + 1, t, len]);
    }
  }
  return out;
}

let tape = 0;

function speedTapes(g: CanvasRenderingContext2D, f: TraceFrame) {
  if (f.surge < 0.01) return;
  tape += f.speed * f.dt * 0.6;
  const spacing = 8;
  const half = (f.h * 0.34 * Math.min(1, f.surge * 1.4)) | 0;
  const mid = (f.h * 0.46) | 0;
  const off = tape % spacing;
  for (const left of [true, false]) {
    const rects: Rect[] = [];
    const x = left ? 8 : f.w - 9;
    rects.push([x, mid - half, 1, half * 2]);
    for (let y = mid - half + spacing - off; y < mid + half; y += spacing) {
      const major = Math.round((y + off - mid) / spacing) % 5 === 0;
      const len = major ? 6 : 3;
      rects.push([left ? x + 1 : x - len, Math.round(y), len, 1]);
    }
    inked(g, rects);
  }
  plate(g, f, [`${pad(f.speed)}`], 6, mid - half - 15, AMBER);
  plate(g, f, [`${pad(f.built * 100)}%`], f.w - 30, mid - half - 15, AMBER);
}

function draw(g: CanvasRenderingContext2D, f: TraceFrame) {
  speedTapes(g, f);
  const cx = Math.round(f.x);
  const cy = Math.round(f.y);

  // The track behind it: a plot every so often, stepping down as they age.
  const every = 26;
  for (let i = 1; i < f.trail.length; i++) {
    const a = f.trail[i - 1];
    const b = f.trail[i];
    if (Math.floor(a.s / PIXEL / every) === Math.floor(b.s / PIXEL / every)) continue;
    const life = 1 - b.age / TRACE.trail;
    if (life <= 0 || (f.active && Math.hypot(b.x / PIXEL - f.x, b.y / PIXEL - f.y) < f.reach)) continue;
    g.globalAlpha = (life > 0.5 ? 1 : life > 0.2 ? 0.6 : 0.3) * f.fade;
    inked(g, [[Math.round(b.x / PIXEL) - 1, Math.round(b.y / PIXEL) - 1, 3, 3]], life > 0.5 ? AMBER : DIM);
  }
  g.globalAlpha = 1;

  if (!f.active) {
    // Over: the brackets spring open and go. Lost, a hard cross and the words on an inverted plate.
    const t = 1 - f.fade;
    if (f.fade > 0) {
      const s = Math.round(24 + 90 * t * t);
      g.globalAlpha = f.fade;
      inked(g, brackets(cx, cy, s, 9, 2));
      if (f.lost) {
        g.fillStyle = KEY;
        g.beginPath();
        pixelLine(g, cx - 13, cy - 12, cx + 13, cy + 14);
        pixelLine(g, cx + 13, cy - 12, cx - 13, cy + 14);
        pixelLine(g, cx - 12, cy - 13, cx + 14, cy + 13);
        pixelLine(g, cx + 14, cy - 13, cx - 12, cy + 13);
        g.fill();
        g.fillStyle = AMBER;
        g.beginPath();
        pixelLine(g, cx - 13, cy - 13, cx + 13, cy + 13);
        pixelLine(g, cx + 13, cy - 13, cx - 13, cy + 13);
        g.fill();
        if (Math.floor(f.now * 14) % 2 === 0) prompt(g, f, 'LOCK LOST', 20, '#0a0600', AMBER);
      }
      g.globalAlpha = 1;
    }
    return false;
  }

  // The brackets, at the tolerance, snapping in a step at each tenth. Off it they break up and blink.
  const off = !f.on;
  const step = Math.floor(f.built * 10);
  const snap = f.built * 10 - step < 0.08 && step > 0;
  const shaky = off ? (Math.random() < 0.5 ? 1 : -1) : 0;
  const s = Math.round(f.reach * 0.72);
  const blink = off && Math.floor(f.now * 12) % 2 === 0;
  const ink = blink ? '#0a0600' : snap ? '#fff4d0' : AMBER;
  inked(g, brackets(cx + shaky, cy - shaky, s, Math.max(6, Math.round(s * 0.42)), 2), ink, blink ? AMBER : KEY);
  // The target itself, small and solid; and where it's going, a lead line out of the box.
  inked(g, [[cx - 1, cy - 1, 3, 3]], ink, blink ? AMBER : KEY);
  const last = f.trail[Math.max(0, f.trail.length - 8)];
  if (last) {
    const vx = f.x - last.x / PIXEL;
    const vy = f.y - last.y / PIXEL;
    const v = Math.hypot(vx, vy);
    if (v > 1) {
      const out = (s * v) / Math.max(Math.abs(vx), Math.abs(vy)) + 3;
      const lead = out + Math.min(14, v * 0.7);
      for (const [colour, o] of [
        [KEY, 1],
        [AMBER, 0],
      ] as const) {
        g.fillStyle = colour;
        g.beginPath();
        pixelLine(g, cx + (vx / v) * out + o, cy + (vy / v) * out + o, cx + (vx / v) * lead + o, cy + (vy / v) * lead + o);
        g.fill();
      }
    }
  }

  // Everything else hangs off the side away from the button, so the wire comes in clear of it (unless that's off the screen).
  const wide = 9 * GLYPH_W + 5;
  const room = (dir: number) => (dir > 0 ? cx + s + 14 + wide < f.w - 42 : cx - s - 14 - wide > 42);
  const away = cx >= f.bx ? 1 : -1;
  const side = room(away) ? away : -away;

  // The wire back to the button: up from it, a corner cut, and across into the near side of the box (or straight up into it,
  // right over it). Its dashes crawl out to the target.
  const bx = Math.round(f.bx);
  const by = Math.round(f.by);
  const crawl = 4 - (Math.floor(f.now * 18) % 4);
  const wires: [number, number, number, number, number][] = [];
  if (Math.abs(cx - bx) <= s + 4) {
    wires.push([bx, by, bx, cy + (by > cy ? s + 9 : -s - 9), 2]);
  } else {
    const near = cx > bx ? cx - s - 2 : cx + s + 2;
    const cut = Math.min(8, Math.abs(cy - by), Math.abs(near - bx));
    const knee = near > bx ? bx + cut : bx - cut;
    const kneeY = cy > by ? cy - cut : cy + cut;
    wires.push([bx, by, bx, kneeY, 2], [bx, kneeY, knee, cy, 1], [knee, cy, near, cy, 2]);
  }
  g.fillStyle = 'rgba(8, 5, 0, 0.6)';
  g.beginPath();
  for (const [x0, y0, x1, y1] of wires) pixelLine(g, x0 + 1, y0 + 1, x1 + 1, y1 + 1);
  g.fill();
  g.fillStyle = AMBER;
  g.beginPath();
  for (const [x0, y0, x1, y1, every] of wires) pixelLine(g, x0, y0, x1, y1, every, crawl);
  g.fill();
  inked(g, [[bx - 2, by - 2, 5, 5]]);

  // Tracking error: a ruler over the box and one down its far side, a tick on each at how far off it the pointer is.
  const ex = Math.max(-1, Math.min(1, (f.px - f.x) / f.reach));
  const ey = Math.max(-1, Math.min(1, (f.py - f.y) / f.reach));
  const rulerY = cy - s - 7;
  const rulerX = cx + side * (s + 6);
  const rules: Rect[] = [
    [cx - s, rulerY, s * 2 + 1, 1],
    [cx, rulerY - 2, 1, 5],
    [rulerX, cy - s, 1, s * 2 + 1],
    [rulerX - 2, cy, 5, 1],
  ];
  inked(g, rules, DIM);
  inked(
    g,
    [
      [cx + Math.round(ex * s) - 1, rulerY - 3, 3, 3],
      [rulerX + side * 2 - 1, cy + Math.round(ey * s) - 1, 3, 3],
    ],
    off ? '#fff4d0' : AMBER
  );

  // How far it's locked: ten blocks under the box, its width.
  const cell = Math.max(3, Math.floor((s * 2 + 2) / 10));
  const barY = cy + s + 5;
  const barX = cx - Math.floor((cell * 10) / 2);
  g.fillStyle = KEY;
  g.fillRect(barX - 1, barY - 1, cell * 10 + 1, 5);
  for (let i = 0; i < 10; i++) {
    g.fillStyle = i < step ? AMBER : 'rgba(255, 179, 0, 0.3)';
    g.fillRect(barX + i * cell, barY, cell - 1, 3);
  }

  // The readouts.
  const error = Math.min(999, Math.round((Math.hypot(f.px - f.x, f.py - f.y) / f.reach) * 100));
  const lines = off
    ? ['NO TRACK', `ERR  ${pad(error)}`, `LOCK ${pad(f.built * 100)}%`]
    : [f.built >= 1 ? 'LOCKED' : `LOCK ${pad(f.built * 100)}%`, `ERR  ${pad(error)}`, `SPD  ${pad(f.speed)}`];
  plate(g, f, lines, side > 0 ? rulerX + 8 : rulerX - 8 - wide, cy - s, blink ? '#0a0600' : AMBER, blink ? AMBER : undefined);
  if (f.teaching) prompt(g, f, off ? 'HOLD THE POINTER IN THE BRACKETS' : 'KEEP IT IN THE BRACKETS', s + 14, off ? '#fff4d0' : AMBER);
  return false;
}

// Round the view: hard black bars closing top and bottom, and a hard border up each side where the world goes to dark amber,
// which is where the tapes sit. Nothing else: the view inside stays clean.
const edge = /* glsl */ `
vec3 edgeB(vec2 uv, vec2 toward, vec3 c) {
  float aspect = resolution.x / resolution.y;
  vec2 e = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
  float grow = smoothstep(0.0, 0.3, surge);
  float lum = dot(c, vec3(0.3, 0.55, 0.15));
  vec3 amber = vec3(1.0, 0.5, 0.03) * (0.012 + lum * lum * 0.3);
  vec3 o = mix(c, amber, step(e.x, 0.1 * grow));
  return mix(o, vec3(0.006, 0.004, 0.0), step(e.y, 0.062 * grow));
}`;

export const lockOn: TraceLook = { id: 'b', name: 'LOCK-ON', bloom: { threshold: 0, intensity: 0 }, accent: '#ffb300', edge, draw };
