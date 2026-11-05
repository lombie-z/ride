// What the hive's run's looks have in common: what each frame hands them, and the means to lay down hard pixels that have
// some body to them. The canvas is at a quarter of the resolution, shown pixelated, so a canvas pixel is a chunky one: the art
// here is written pixel by pixel into a layer rather than left to anti-aliasing, which would go to mush scaled up.

export const PIXEL = 4;
/** The lettering's canvas over the art, finer than it: blackletter would turn to mush at the art's resolution. */
export const TEXT_SCALE = 2;

/** What's left of a circle once it's landed: where (as shares of the view), how long since (s; gone at 0.6), and how it went. */
export type FrameBurst = { x: number; y: number; age: number; kind: 'perfect' | 'good' | 'miss'; number: number };

export type FrameCircle = {
  point: number;
  number: number;
  /** Where it stands, in canvas pixels. */
  x: number;
  y: number;
  /** How far off landing, as a share of the ring's closing: 1 starting to close, 0 on the beat, below that late. */
  left: number;
};

/** One frame, in canvas pixels. */
export type RhythmFrame = {
  w: number;
  h: number;
  unit: number;
  /** The circle's radius: what a click's measured from, and what the closing ring has to touch on the beat. */
  r: number;
  /** r as a share of what it is in a 720p window, to size the art's details by. */
  u: number;
  dt: number;
  now: number;
  /** The heart's pulse now (0 to 1). */
  beat: number;
  active: boolean;
  teaching: boolean;
  /** How fast the ride's running (1 full speed, 0 stopped to teach). */
  slow: number;
  /** The flash as the boost hits (1 down to 0): 666 reached with something hit. */
  burn: number;
  /** How far through the run, and that eased (and dying away after it): what the view's darkening should go by. */
  landed: number;
  gloom: number;
  /** 1 while it's running, dying away to 0 once it's over: for what's left of the sigil. */
  fade: number;
  /** Counts the runs: it changes as one starts. */
  run: number;
  /** This run's sigil: the points in canvas pixels, whether the last joins up to the first, and which were hit. */
  points: { x: number; y: number }[];
  closed: boolean;
  drawn: (boolean | undefined)[];
  /** The next to land first. */
  circles: FrameCircle[];
  bursts: FrameBurst[];
  /** The pointer, in canvas pixels. */
  pointer: { x: number; y: number } | null;
  /** Lettering, in canvas pixels: the blackletter on its finer canvas, dark round its edge so it reads on anything. */
  label: (words: string, x: number, y: number, size: number, ink: string, alpha: number) => void;
};

/** One of the eyes staring in from the corners, in canvas pixels: half its width, `open` 0 to 1, the spot it's looking at, a steady 0 to 1 of its own. */
export type Stare = { x: number; y: number; size: number; tilt: number; open: number; lookX: number; lookY: number; seed: number };

export type RhythmLook = {
  id: string;
  name: string;
  /** Under the corners' eyes: the view darkening, the sigil. True if it still has something on screen once the run's over. */
  under: (g: CanvasRenderingContext2D, f: RhythmFrame) => boolean;
  /** The eyes themselves (rhythm-overlay.tsx says where, how open, and casts the shadow they're in). */
  stare: (g: CanvasRenderingContext2D, f: RhythmFrame, eyes: Stare[]) => void;
  /** Over them: the circles and what's left of them, the 666. */
  over: (g: CanvasRenderingContext2D, f: RhythmFrame) => boolean;
};

export const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
export const smooth = (t: number) => {
  const k = clamp(t);
  return k * k * (3 - 2 * k);
};
/** Where the closing ring's inner edge is: on the circle's edge exactly as it lands, then staying there. */
export const ringAt = (f: RhythmFrame, left: number) => f.r * (1 + 1.9 * Math.max(0, left));
/** How far a circle's come in: nothing before its ring starts closing. */
export const appear = (left: number) => clamp((1 - left) * 4);

/** A steady number from a whole number. */
export function hash(n: number) {
  const h = Math.sin(n * 127.1 + 3.7) * 43758.5453;
  return h - Math.floor(h);
}

/** A colour as the layer's pixels hold it. */
export const rgba = (r: number, g: number, b: number, a = 255) => ((a << 24) | (b << 16) | (g << 8) | r) >>> 0;
export const hex = (s: string, a = 255) => rgba(Number.parseInt(s.slice(1, 3), 16), Number.parseInt(s.slice(3, 5), 16), Number.parseInt(s.slice(5, 7), 16), a);

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);
/** The 4x4 ordered dither: what stands in for a gradient, as it did on the machines this is after. */
export const bayer = (x: number, y: number) => BAYER[(x & 3) + ((y & 3) << 2)];

/** A ramp of colours picked by t (0 to 1), dithered between its steps. */
export function ramp(colours: number[], t: number, x: number, y: number) {
  const k = clamp(t) * (colours.length - 1);
  const i = Math.floor(k);
  return colours[Math.min(colours.length - 1, i + (k - i > bayer(x, y) ? 1 : 0))];
}

let noiseField: Float32Array | null = null;
const NOISE = 256;
/** Tiling cloudy noise (0 to 1), at whole pixels: the red flowing through the black, the grain in the bone, the soot. */
export function noise(x: number, y: number) {
  if (!noiseField) {
    const field = new Float32Array(NOISE * NOISE);
    const lattice = (ix: number, iy: number, cells: number) => hash((((ix % cells) + cells) % cells) * 57 + (((iy % cells) + cells) % cells));
    let total = 0;
    for (let cells = 8, a = 1; cells <= 64; cells *= 2, a *= 0.55) {
      total += a;
      const size = NOISE / cells;
      for (let py = 0; py < NOISE; py++) {
        for (let px = 0; px < NOISE; px++) {
          const fx = px / size;
          const fy = py / size;
          const ix = Math.floor(fx);
          const iy = Math.floor(fy);
          const sx = smooth(fx - ix);
          const sy = smooth(fy - iy);
          const top = lattice(ix, iy, cells) * (1 - sx) + lattice(ix + 1, iy, cells) * sx;
          const low = lattice(ix, iy + 1, cells) * (1 - sx) + lattice(ix + 1, iy + 1, cells) * sx;
          field[py * NOISE + px] += a * (top * (1 - sy) + low * sy);
        }
      }
    }
    // (Stretched back out to 0 to 1: added up, it bunches round the middle.)
    for (let i = 0; i < field.length; i++) field[i] = clamp((field[i] / total - 0.5) * 2.2 + 0.5);
    noiseField = field;
  }
  return noiseField[((Math.floor(y) & (NOISE - 1)) << 8) + (Math.floor(x) & (NOISE - 1))];
}

/** The eyes as plain almonds, bloodshot, the pupil pinned: for a look with none of its own. */
export function almondEyes(g: CanvasRenderingContext2D, _f: RhythmFrame, eyes: Stare[]) {
  for (const { x, y, size, tilt, open, lookX, lookY } of eyes) {
    const lid = size * 0.62 * open;
    g.save();
    g.translate(x, y);
    g.rotate(tilt);
    // Its own shadow round it.
    g.fillStyle = `rgba(0, 0, 0, ${0.55 * Math.min(1, open * 2)})`;
    g.beginPath();
    g.ellipse(0, 0, size * 1.32, size * 0.92, 0, 0, Math.PI * 2);
    g.fill();
    const almond = () => {
      g.beginPath();
      g.moveTo(-size, 0);
      g.quadraticCurveTo(0, -lid * 2, size, 0);
      g.quadraticCurveTo(0, lid * 2, -size, 0);
      g.closePath();
    };
    almond();
    g.fillStyle = '#f2c9b4';
    g.fill();
    g.save();
    g.clip();
    // Turned in: the iris pushed toward where it's looking.
    const dx = lookX - x;
    const dy = lookY - y;
    const dist = Math.hypot(dx, dy) || 1;
    const c = Math.cos(-tilt);
    const s = Math.sin(-tilt);
    const ix = ((dx * c - dy * s) / dist) * size * 0.42;
    const iy = ((dx * s + dy * c) / dist) * size * 0.3;
    const iris = size * 0.52;
    g.fillStyle = '#c10f1c';
    g.beginPath();
    g.arc(ix, iy, iris, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#080203';
    g.beginPath();
    g.arc(ix, iy, iris * 0.36, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = 'rgba(255, 245, 225, 0.9)';
    g.fillRect(ix - iris * 0.42, iy - iris * 0.5, Math.max(1, iris * 0.26), Math.max(1, iris * 0.26));
    g.restore();
    almond();
    g.lineWidth = Math.max(1, size * 0.14);
    g.strokeStyle = '#0c0204';
    g.stroke();
    g.restore();
  }
}

/** A view's worth of pixels to write into and lay over the canvas in one go. */
export class Layer {
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private image: ImageData | null = null;
  px = new Uint32Array(0);
  w = 0;
  h = 0;
  begin(w: number, h: number) {
    if (!this.canvas || this.w !== w || this.h !== h) {
      this.canvas ??= document.createElement('canvas');
      this.canvas.width = w;
      this.canvas.height = h;
      this.ctx = this.canvas.getContext('2d');
      this.image = this.ctx?.createImageData(w, h) ?? null;
      this.px = this.image ? new Uint32Array(this.image.data.buffer) : new Uint32Array(0);
      this.w = w;
      this.h = h;
    } else this.px.fill(0);
  }
  /** Writes one, if it's on the view. */
  set(x: number, y: number, c: number) {
    if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.px[y * this.w + x] = c;
  }
  flush(g: CanvasRenderingContext2D) {
    if (!this.canvas || !this.ctx || !this.image) return;
    this.ctx.putImageData(this.image, 0, 0);
    g.drawImage(this.canvas, 0, 0);
  }
}

/** The one layer they all use: only one look draws at a time, and it's flushed before it's used again. */
export const layer = new Layer();

/**
 * Bodies built up as a field of soft domes that run together where they meet, then shaded from its slope: a liquid's necks,
 * the fork of a branch and the swell of a lump all come out of that on their own, and the slope gives each its own lighting.
 */
export class Relief {
  f = new Float32Array(0);
  w = 0;
  h = 0;
  private x0 = 1e9;
  private y0 = 1e9;
  private x1 = -1;
  private y1 = -1;
  begin(w: number, h: number) {
    if (this.w !== w || this.h !== h) {
      this.f = new Float32Array(w * h);
      this.w = w;
      this.h = h;
    } else if (this.x1 >= 0) {
      for (let y = this.y0; y <= this.y1; y++) this.f.fill(0, y * w + this.x0, y * w + this.x1 + 1);
    }
    this.x0 = 1e9;
    this.y0 = 1e9;
    this.x1 = -1;
    this.y1 = -1;
  }
  private mark(x0: number, y0: number, x1: number, y1: number) {
    if (x0 < this.x0) this.x0 = x0;
    if (y0 < this.y0) this.y0 = y0;
    if (x1 > this.x1) this.x1 = x1;
    if (y1 > this.y1) this.y1 = y1;
  }
  /** A dome, radius r, its height k; `squash` draws it out up and down. */
  dome(x: number, y: number, r: number, k = 1, squash = 1) {
    const ry = r * squash;
    const x0 = Math.max(0, Math.floor(x - r));
    const x1 = Math.min(this.w - 1, Math.ceil(x + r));
    const y0 = Math.max(0, Math.floor(y - ry));
    const y1 = Math.min(this.h - 1, Math.ceil(y + ry));
    if (x0 > x1 || y0 > y1) return;
    this.mark(x0, y0, x1, y1);
    const { f, w } = this;
    for (let py = y0; py <= y1; py++) {
      const dy = (py - y) / ry;
      const row = py * w;
      for (let px = x0; px <= x1; px++) {
        const dx = (px - x) / r;
        const d = dx * dx + dy * dy;
        if (d >= 1) continue;
        const v = (1 - d) * (1 - d) * k;
        // (Soft union: what's there and what's coming, never above 1, running together however many overlap.)
        f[row + px] = f[row + px] + v - f[row + px] * v;
      }
    }
  }
  /** A line of domes from one point to the other, its radius going from ra to rb. */
  line(xa: number, ya: number, xb: number, yb: number, ra: number, rb = ra, k = 1) {
    const n = Math.max(1, Math.ceil(Math.hypot(xb - xa, yb - ya) / 1.2));
    for (let i = 0; i <= n; i++) this.dome(xa + ((xb - xa) * i) / n, ya + ((yb - ya) * i) / n, ra + ((rb - ra) * i) / n, k);
  }
  /** A value straight into the field, for a body that's worked out column by column. */
  put(x: number, y: number, v: number) {
    if (x < 0 || y < 0 || x >= this.w || y >= this.h) return;
    this.mark(x, y, x, y);
    const i = y * this.w + x;
    this.f[i] = this.f[i] + v - this.f[i] * v;
  }
  /**
   * Paints every pixel over the threshold through `shade` (given its slope as a unit normal and its height over the threshold,
   * 0 to 1), and a hard one-pixel keyline just outside: that line is what makes it a body rather than a tint.
   */
  shade(out: Layer, shade: (x: number, y: number, nx: number, ny: number, nz: number, height: number) => number, key: number, threshold = 0.2, slope = 7) {
    if (this.x1 < 0) return;
    const { f, w, h } = this;
    const px = out.px;
    const y1 = Math.min(h - 1, this.y1 + 1);
    const x1 = Math.min(w - 1, this.x1 + 1);
    for (let y = Math.max(0, this.y0 - 1); y <= y1; y++) {
      const row = y * w;
      for (let x = Math.max(0, this.x0 - 1); x <= x1; x++) {
        const i = row + x;
        const v = f[i];
        const left = x > 0 ? f[i - 1] : 0;
        const right = x < w - 1 ? f[i + 1] : 0;
        const up = y > 0 ? f[i - w] : 0;
        const down = y < h - 1 ? f[i + w] : 0;
        if (v < threshold) {
          if (key && (left >= threshold || right >= threshold || up >= threshold || down >= threshold)) px[i] = key;
          continue;
        }
        const gx = (left - right) * slope;
        const gy = (up - down) * slope;
        const n = 1 / Math.sqrt(gx * gx + gy * gy + 1);
        px[i] = shade(x, y, gx * n, gy * n, n, (v - threshold) / (1 - threshold));
      }
    }
  }
}

/** A hard one-pixel line; `every` leaves gaps. */
export function pixelLine(out: Layer, x0: number, y0: number, x1: number, y1: number, c: number, every = 1) {
  let x = Math.round(x0);
  let y = Math.round(y0);
  const ex = Math.round(x1);
  const ey = Math.round(y1);
  const dx = Math.abs(ex - x);
  const dy = Math.abs(ey - y);
  const sx = x < ex ? 1 : -1;
  const sy = y < ey ? 1 : -1;
  let err = dx - dy;
  for (let n = 0; n < 4096; n++) {
    if (n % every === 0) out.set(x, y, c);
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

export type Bit = { x: number; y: number; vx: number; vy: number; r: number; age: number; life: number; kind: number };

/** What's been flung: moved on with gravity and dropped when its time's up. */
export function moveBits(bits: Bit[], dt: number, gravity: number, each: (b: Bit, k: number) => void) {
  for (let i = bits.length - 1; i >= 0; i--) {
    const b = bits[i];
    b.age += dt;
    if (b.age > b.life) {
      bits.splice(i, 1);
      continue;
    }
    b.vy += gravity * dt;
    b.x += b.vx * dt;
    b.y += b.vy * dt;
    each(b, b.age / b.life);
  }
}

/** Keeps track of a look's run for it: picks out the bursts it's not seen, and how long ago each stretch of the sigil was laid. */
export class RunWatch {
  private seen = new WeakSet<FrameBurst>();
  private run = -1;
  private count = 0;
  /** When each point landed (seconds, as f.now). */
  landedAt: number[] = [];
  /** True on the frame a new run begins. */
  fresh = false;
  update(f: RhythmFrame, onBurst: (b: FrameBurst) => void) {
    this.fresh = f.run !== this.run;
    if (this.fresh) {
      this.run = f.run;
      this.count = 0;
      this.landedAt.length = 0;
    }
    while (this.count < f.landed) this.landedAt[this.count++] = f.now;
    for (const b of f.bursts) {
      if (this.seen.has(b)) continue;
      this.seen.add(b);
      onBurst(b);
    }
  }
}
