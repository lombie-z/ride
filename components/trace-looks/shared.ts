import type { TracePoint } from '@/lib/trace';

// What the surge's looks have in common: what each frame hands them, and the hard pixels they're drawn with. The overlay's
// canvas is at half resolution and shown pixelated, so a canvas pixel is a chunky one: the lines and the lettering here are
// laid down in whole pixels rather than left to anti-aliasing, which would go to mush when it's scaled up.

export const PIXEL = 2;

/** One frame, in canvas pixels (the trail's points stay in CSS pixels, as lib/trace.ts keeps them). */
export type TraceFrame = {
  w: number;
  h: number;
  dt: number;
  now: number;
  /** The point, the pointer and the rocket button. */
  x: number;
  y: number;
  px: number;
  py: number;
  bx: number;
  by: number;
  /** How far off the point the pointer may be (what lib/trace.ts is checking right now). */
  reach: number;
  /** The ride's speed and the surge's strength as it reaches the view (0 to 1). */
  speed: number;
  surge: number;
  /** How far it's built (0 to 1). */
  built: number;
  /** 1 while it's running, dying away to 0 once it's over. */
  fade: number;
  active: boolean;
  teaching: boolean;
  /** The pointer's on the point and pressed. */
  on: boolean;
  /** It ended by falling off rather than letting go. */
  lost: boolean;
  trail: TracePoint[];
};

export type TraceLook = {
  id: string;
  name: string;
  /** What the surge adds to the bloom at full strength: taken off its threshold, added to its intensity. */
  bloom: { threshold: number; intensity: number };
  /** The rocket button's colour while it's surging. */
  accent: string;
  /** GLSL, in speed-blur.ts's shader: this look's treatment of the edges of the view, as `vec3 edge<ID>(vec2 uv, vec2 toward, vec3 c)`. */
  edge: string;
  /** Draws a frame; true if it still has something on screen once the run itself is over (sparks, say). */
  draw: (g: CanvasRenderingContext2D, f: TraceFrame) => boolean;
};

// A plain 5x7 pixel font: each glyph's five columns, low bit at the top.
const GLYPHS: Record<string, number[]> = {
  ' ': [0, 0, 0, 0, 0],
  '%': [0x23, 0x13, 0x08, 0x64, 0x62],
  '+': [0x08, 0x08, 0x3e, 0x08, 0x08],
  '-': [0x08, 0x08, 0x08, 0x08, 0x08],
  '.': [0, 0, 0x60, 0x60, 0],
  '/': [0x20, 0x10, 0x08, 0x04, 0x02],
  ':': [0, 0, 0x14, 0, 0],
  '>': [0, 0x41, 0x22, 0x14, 0x08],
  '0': [0x3e, 0x51, 0x49, 0x45, 0x3e],
  '1': [0, 0x42, 0x7f, 0x40, 0],
  '2': [0x72, 0x49, 0x49, 0x49, 0x46],
  '3': [0x21, 0x41, 0x49, 0x4d, 0x33],
  '4': [0x18, 0x14, 0x12, 0x7f, 0x10],
  '5': [0x27, 0x45, 0x45, 0x45, 0x39],
  '6': [0x3c, 0x4a, 0x49, 0x49, 0x31],
  '7': [0x41, 0x21, 0x11, 0x09, 0x07],
  '8': [0x36, 0x49, 0x49, 0x49, 0x36],
  '9': [0x46, 0x49, 0x49, 0x29, 0x1e],
  A: [0x7c, 0x12, 0x11, 0x12, 0x7c],
  B: [0x7f, 0x49, 0x49, 0x49, 0x36],
  C: [0x3e, 0x41, 0x41, 0x41, 0x22],
  D: [0x7f, 0x41, 0x41, 0x41, 0x3e],
  E: [0x7f, 0x49, 0x49, 0x49, 0x41],
  F: [0x7f, 0x09, 0x09, 0x09, 0x01],
  G: [0x3e, 0x41, 0x41, 0x51, 0x73],
  H: [0x7f, 0x08, 0x08, 0x08, 0x7f],
  I: [0, 0x41, 0x7f, 0x41, 0],
  J: [0x20, 0x40, 0x41, 0x3f, 0x01],
  K: [0x7f, 0x08, 0x14, 0x22, 0x41],
  L: [0x7f, 0x40, 0x40, 0x40, 0x40],
  M: [0x7f, 0x02, 0x1c, 0x02, 0x7f],
  N: [0x7f, 0x04, 0x08, 0x10, 0x7f],
  O: [0x3e, 0x41, 0x41, 0x41, 0x3e],
  P: [0x7f, 0x09, 0x09, 0x09, 0x06],
  Q: [0x3e, 0x41, 0x51, 0x21, 0x5e],
  R: [0x7f, 0x09, 0x19, 0x29, 0x46],
  S: [0x26, 0x49, 0x49, 0x49, 0x32],
  T: [0x03, 0x01, 0x7f, 0x01, 0x03],
  U: [0x3f, 0x40, 0x40, 0x40, 0x3f],
  V: [0x1f, 0x20, 0x40, 0x20, 0x1f],
  W: [0x3f, 0x40, 0x38, 0x40, 0x3f],
  X: [0x63, 0x14, 0x08, 0x14, 0x63],
  Y: [0x03, 0x04, 0x78, 0x04, 0x03],
  Z: [0x61, 0x59, 0x49, 0x4d, 0x43],
};

export const GLYPH_W = 6;
export const GLYPH_H = 8;

/** Text in the pixel font from (x, y), its top left, at whole pixels; a hard keyline round it, if it's given one, so it reads on anything. */
export function pixelText(g: CanvasRenderingContext2D, text: string, x: number, y: number, colour: string, key?: string) {
  const x0 = Math.round(x);
  const y0 = Math.round(y);
  const lay = (dx: number, dy: number) => {
    g.beginPath();
    for (let i = 0; i < text.length; i++) {
      const glyph = GLYPHS[text[i]];
      if (!glyph) continue;
      for (let c = 0; c < 5; c++) {
        for (let r = 0; r < 7; r++) if (glyph[c] & (1 << r)) g.rect(x0 + i * GLYPH_W + c + dx, y0 + r + dy, 1, 1);
      }
    }
    g.fill();
  };
  if (key) {
    g.fillStyle = key;
    lay(-1, 0);
    lay(1, 0);
    lay(0, -1);
    lay(0, 1);
  }
  g.fillStyle = colour;
  lay(0, 0);
}

/** A run of text on a dark plate, placed by its top left and kept on the screen. */
export function plate(g: CanvasRenderingContext2D, f: TraceFrame, lines: string[], x: number, y: number, colour: string, back = 'rgba(6, 5, 8, 0.74)') {
  const wide = Math.max(...lines.map((l) => l.length)) * GLYPH_W + 5;
  const high = lines.length * GLYPH_H + 5;
  const px = Math.round(Math.max(2, Math.min(f.w - wide - 2, x)));
  const py = Math.round(Math.max(2, Math.min(f.h - high - 2, y)));
  g.fillStyle = back;
  g.fillRect(px, py, wide, high);
  lines.forEach((line, i) => {
    pixelText(g, line, px + 3, py + 3 + i * GLYPH_H, colour);
  });
}

/** The taught state's prompt, on its plate, centred under the point (or over it, down at the bottom of the view). */
export function prompt(g: CanvasRenderingContext2D, f: TraceFrame, text: string, gap: number, colour: string, back?: string) {
  const wide = text.length * GLYPH_W + 5;
  const y = f.y + gap + GLYPH_H + 5 > f.h - 4 ? f.y - gap - GLYPH_H - 5 : f.y + gap;
  plate(g, f, [text], f.x - wide / 2, y, colour, back);
}

/** A hard one-pixel line, added to the current path (fill it after); `every` leaves gaps, `from` slides them along. */
export function pixelLine(g: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, every = 1, from = 0) {
  let x = Math.round(x0);
  let y = Math.round(y0);
  const ex = Math.round(x1);
  const ey = Math.round(y1);
  const dx = Math.abs(ex - x);
  const dy = Math.abs(ey - y);
  const sx = x < ex ? 1 : -1;
  const sy = y < ey ? 1 : -1;
  let err = dx - dy;
  let n = from;
  for (let guard = 0; guard < 4096; guard++) {
    if (every === 1 || n % every === 0) g.rect(x, y, 1, 1);
    n++;
    if (x === ex && y === ey) return;
    const e2 = 2 * err;
    if (e2 > -dy) {
      err -= dy;
      x += sx;
    }
    if (e2 < dx) {
      err += dx;
      y += sy;
    }
  }
}

/** A solid disc in whole pixels, added to the current path (fill it after). */
export function pixelDisc(g: CanvasRenderingContext2D, x: number, y: number, r: number) {
  const cx = Math.round(x);
  const cy = Math.round(y);
  const top = Math.ceil(r);
  for (let dy = -top; dy <= top; dy++) {
    if (r * r - dy * dy < 0) continue;
    const span = Math.round(Math.sqrt(r * r - dy * dy));
    g.rect(cx - span, cy + dy, span * 2 + 1, 1);
  }
}

/** A steady number from a whole number. */
export function hash(n: number) {
  const h = Math.sin(n * 127.1 + 3.7) * 43758.5453;
  return h - Math.floor(h);
}
