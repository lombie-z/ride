import {
  appear,
  type Bit,
  bayer,
  clamp,
  hash,
  hex,
  layer,
  moveBits,
  noise,
  pixelLine,
  Relief,
  type RhythmFrame,
  type RhythmLook,
  RunWatch,
  ramp,
  rgba,
  ringAt,
  type Stare,
  smooth,
} from './shared';

// A: living flesh. The view's an eye itself, its lids closing in as the run goes on. Each point's an eye forcing open out of a
// wound, its number in the pupil, looking at the pointer; a raw sphincter of meat, tied to the iris by sinews, closes on it,
// clamping down on the iris's edge on the beat. Hit, it bursts and weeps down the glass; good, it shuts weeping; miss, it
// stares, pupil pinned, bloodshot. The sigil's a vein swelling with the heart, a lump of blood pushed along it each beat. 666: a
// blink, the red of the light through shut lids, and the lids tear open.

const KEY = hex('#0a0103');
const MEAT = ['#2a0409', '#5c0a18', '#a81428', '#e4505e', '#ffb8a4'].map((c) => hex(c));
const VEIN = ['#1c0308', '#4a0614', '#8c0e20', '#d8283a', '#ff9080'].map((c) => hex(c));
const WET = hex('#ffeade');
const SCLERA = ['#6e3a38', '#b98a7c', '#e8d4bc', '#f8eedc'].map((c) => hex(c));
const CORNER = hex('#b84450');
const CAPILLARY = hex('#c8323c');
const DEEP = hex('#1c0608');
const BLACK = hex('#050103');
const PUPIL_RED = hex('#2c040c');
const GLINT = hex('#fffaf0');

// Gold at 111 turning to blood by 666, as ever: the iris, from its inner edge to its outer.
const GOLD = [
  [255, 214, 110],
  [226, 142, 34],
  [120, 58, 12],
];
const BLOOD = [
  [255, 70, 60],
  [190, 16, 30],
  [84, 4, 14],
];
const iris = (t: number) => GOLD.map((c, i) => rgba(...(c.map((v, j) => Math.round(v + (BLOOD[i][j] - v) * t)) as [number, number, number])));
const IRISES = [0, 1, 2, 3, 4, 5].map((i) => iris(i / 5));

const WIDE = 1.62;
const TAU = Math.PI * 2;

const meat = new Relief();
const rings = new Relief();
const vein = new Relief();
const scars = new Relief();
const watch = new RunWatch();
const bits: Bit[] = [];
type Weep = { x: number; y: number; at: number; len: number; seed: number };
const weeps: Weep[] = [];

function shadeMeat(x: number, y: number, nx: number, ny: number, nz: number) {
  const light = -nx * 0.5 - ny * 0.8 + nz * 0.32;
  if (light > 0.93) return WET;
  return ramp(MEAT, 0.5 + 0.55 * light + (noise(x * 5, y * 5) - 0.5) * 0.28, x, y);
}
function shadeVein(x: number, y: number, nx: number, ny: number, nz: number) {
  return ramp(VEIN, 0.42 + 0.62 * (-nx * 0.5 - ny * 0.8 + nz * 0.3), x, y);
}

/** One eye in its lids. `open` 0 to 1; `pin` shrinks the pupil to a point; `blood` bursts the veins of its white. */
function eyeball(x: number, y: number, f: RhythmFrame, heat: number, open: number, pin: number, blood: number, lookX: number, lookY: number) {
  const { r, u, w, h, beat } = f;
  const px = layer.px;
  const colours = IRISES[Math.round(heat * 5)];
  const pupil = (0.72 + 0.03 * beat) * (1 - 0.68 * pin);
  const span = Math.ceil(r * WIDE);
  const seed = heat * 91;
  const top = Math.ceil(r * 1.08);
  for (let py = Math.max(0, Math.round(y) - top); py <= Math.min(h - 1, Math.round(y) + top); py++) {
    const v = (py - y) / r;
    for (let qx = Math.max(0, Math.round(x) - span); qx <= Math.min(w - 1, Math.round(x) + span); qx++) {
      const a = (qx - x) / r;
      const edge = 1 - (a * a) / (WIDE * WIDE);
      const lid = 1.06 * open * edge;
      if (Math.abs(v) >= lid) continue;
      const dx = a - lookX;
      const dy = v - lookY;
      const rho = Math.sqrt(dx * dx + dy * dy);
      let c: number;
      if (rho < 0.98) {
        if (rho < pupil) c = rho > pupil - 0.1 ? PUPIL_RED : BLACK;
        else if (rho > 0.88) c = DEEP;
        else {
          const fibre = hash(Math.floor((Math.atan2(dy, dx) / TAU + 0.5) * 34));
          const t = (rho - pupil) / (0.88 - pupil);
          c = colours[Math.min(2, Math.floor(t * 2.2 + fibre * 0.9))];
        }
      } else if (Math.abs(a) > WIDE - 0.3) c = CORNER;
      else {
        // (Its vessels are the noise's contour lines: thin, wandering and joined up, as they are. More of them as it's strained.)
        const vessel = Math.abs(noise(qx * 3 + seed, py * 3 + seed * 2) - 0.5);
        if (vessel < 0.022 + 0.05 * blood) c = CAPILLARY;
        else c = SCLERA[Math.abs(a) > 1.05 ? 1 : Math.abs(a) > 0.82 ? 2 : 3];
      }
      // (The upper lid's shadow on the ball: what puts the ball behind the lids.)
      if (v < -lid + (2.2 * u) / r) c = DEEP;
      px[py * w + qx] = c;
    }
  }
  if (open > 0.5) {
    const size = Math.max(1, Math.round(r * 0.16));
    const gx = Math.round(x + (lookX - 0.44) * r);
    const gy = Math.round(y + (lookY - 0.5) * r);
    for (let j = 0; j < size; j++) for (let i = 0; i < size + 1; i++) layer.set(gx + i, gy + j, GLINT);
  }
}

/** A lit raw edge round where the eye's forced its way out, torn further at its corners. */
function wound(x: number, y: number, f: RhythmFrame, open: number, seed: number) {
  const { r, u } = f;
  const steps = 26;
  for (let i = 0; i <= steps; i++) {
    const a = -WIDE + (2 * WIDE * i) / steps;
    const edge = 1 - (a * a) / (WIDE * WIDE);
    const lump = 2.5 + 1.1 * hash(seed + i);
    const ly = 1.06 * open * edge * r + 1.1 * u;
    meat.dome(x + a * r, y - ly, lump * u);
    meat.dome(x + a * r, y + ly, (lump + 0.4) * u);
  }
  // Its tears out from the corners, jagged, tapering.
  const tear = (r * 0.62 + 2 * u) * open;
  for (const side of [-1, 1]) {
    let px = x + side * WIDE * r;
    let py = y;
    for (let i = 0; i < 4; i++) {
      const nx = px + (side * tear) / 4;
      const ny = py + (hash(seed + side * 3 + i * 5) - 0.5) * 4 * u;
      meat.line(px, py, nx, ny, (3.2 - i * 0.65) * u, (2.7 - i * 0.65) * u);
      px = nx;
      py = ny;
    }
  }
}

function pathOf(f: RhythmFrame, i: number, t: number, seed: number) {
  const a = f.points[(i - 1 + f.points.length) % f.points.length];
  const b = f.points[i % f.points.length];
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  // (It wanders off the straight, pinned at each end.)
  const off = Math.sin(t * Math.PI) * (Math.sin(t * 7 + seed * 11) * 0.055 + Math.sin(t * 15 + seed * 5) * 0.02) * len;
  return { x: a.x + dx * t + (-dy / len) * off, y: a.y + dy * t + (dx / len) * off, len };
}

function drawVein(f: RhythmFrame) {
  const { u, beat, now, landed, burn, fade } = f;
  vein.begin(f.w, f.h);
  // (Gone before it can break up into dots: once the boost's on, it's only the blur and the shadow.)
  if (fade < 0.14) return;
  const count = f.points.length;
  const swell = 1.25 * u + 0.75 * u * beat + 3 * u * burn * burn;
  for (let i = 1; i <= count; i++) {
    const closing = i === count;
    if (closing ? !f.closed || landed < count : i >= landed) continue;
    const at = watch.landedAt[closing ? count - 1 : i] ?? now;
    const grown = smooth((now - at) / 0.22);
    const hit = closing ? true : f.drawn[i] !== false;
    const seed = hash(i + f.run * 7);
    const len = pathOf(f, i, 0.5, seed).len;
    const steps = Math.max(4, Math.ceil(len / 1.3));
    const lump = (now * 1.5 + seed) % 1;
    for (let s = 0; s <= steps * grown; s++) {
      const t = s / steps;
      const p = pathOf(f, i, t, seed);
      if (!hit && Math.floor(s / 5) % 2 === 0) continue;
      const push = Math.exp(-(((t - lump) / 0.09) ** 2)) * 1.3 * u;
      vein.dome(p.x, p.y, ((hit ? swell + push : 0.9 * u) * (0.8 + 0.2 * fade) + 0.5 * u) * fade);
    }
    // Capillaries off it.
    for (let b = 0; b < 4 && hit; b++) {
      const t0 = 0.12 + 0.76 * hash(i * 11 + b);
      if (t0 > grown) continue;
      const p = pathOf(f, i, t0, seed);
      const ang = hash(i * 23 + b) * TAU;
      const reach = (5 + 10 * hash(i * 31 + b)) * u * smooth((now - at) * 1.6) * fade;
      vein.line(p.x, p.y, p.x + Math.cos(ang) * reach, p.y + Math.sin(ang) * reach, 1.5 * u, 0.9 * u, 0.8);
    }
  }
  vein.shade(layer, shadeVein, KEY);
}

function drawLids(f: RhythmFrame) {
  const { w, h, u, gloom, burn, slow, now, fade } = f;
  const px = layer.px;
  const cy = h * 0.42;
  let high = h * (0.68 - 0.3 * gloom - 0.1 * (1 - slow));
  // (Run's over: they let go. 666: slammed shut, then torn open.)
  if (burn > 0) high = h * 1.1 * clamp((1 - burn) / 0.42) ** 1.6;
  else if (!f.active) high = h * (0.68 - 0.3 * gloom) + h * 0.8 * (1 - fade);
  const wide = burn > 0 ? w * 0.9 : w * (0.62 - 0.05 * gloom);
  const lit = clamp((burn - 0.25) / 0.45);
  const thump = 1.5 * u * f.beat;
  for (let x = 0; x < w; x++) {
    const xn = (x - w / 2) / wide;
    // (A wet edge, not a ruled one: it swells and sags along its length.)
    const open = Math.max(0, (high + thump) * (1 - xn * xn) + (noise(x * 0.9 + 70, now * 2) - 0.5) * 5 * u);
    const top = cy - open;
    const low = cy + open * 1.28;
    for (let y = 0; y < h; y++) {
      const dist = Math.max(top - y, y - low);
      if (dist < -3 * u) continue;
      const i = y * w + x;
      if (dist < 0) {
        // Its shadow on the view.
        if (bayer(x, y) < 0.55) px[i] = KEY;
        continue;
      }
      if (dist < 1) {
        px[i] = KEY;
        continue;
      }
      // The lip, wet and lit, then the lid running off into the black with the red moving through it.
      const flow = noise(x * 1.4 + now * 3, y * 1.8 - now * 8);
      const lip = (5 + 1.5 * noise(x * 2 + 30, 3)) * u;
      if (dist < lip) {
        // (Rounded over, its light from above: the lower lid catches it on its edge, the upper on its far side.)
        const side = y < cy ? dist / lip : 1 - dist / lip;
        px[i] = ramp(MEAT, 0.14 + 0.72 * side + (flow - 0.5) * 0.34, x, y);
      } else if (lit > 0) px[i] = ramp(VEIN, 0.22 + 0.42 * lit + (flow - 0.5) * 0.7, x, y);
      else if (flow > 0.74) px[i] = flow > 0.86 ? VEIN[2] : VEIN[1];
      else px[i] = dist < lip + 4 * u && bayer(x, y) > 0.5 ? VEIN[0] : BLACK;
    }
  }
}

function under(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { w, h, now, u } = f;
  watch.update(f, (b) => {
    const x = b.x * w;
    const y = b.y * h;
    const n = b.kind === 'perfect' ? 26 : b.kind === 'good' ? 9 : 4;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU;
      const v = (b.kind === 'perfect' ? 45 + Math.random() * 130 : 18 + Math.random() * 50) * u;
      bits.push({
        x,
        y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - 25 * u,
        r: (0.9 + Math.random() * 2.2) * u,
        age: 0,
        life: 0.4 + Math.random() * 0.5,
        kind: 0,
      });
    }
    const streams = b.kind === 'perfect' ? 2 : b.kind === 'good' ? 1 : 0;
    for (let i = 0; i < streams; i++) {
      // (Not in a row: where the slit's lowest, each its own length.)
      const dx = (Math.random() - 0.5) * f.r * (0.2 + 0.5 * i);
      weeps.push({ x: x + dx, y: y + f.r * 0.1, at: now + i * 0.09, len: (i ? 10 + 14 * Math.random() : 26 + 22 * Math.random()) * u, seed: Math.random() });
    }
  });
  if (watch.fresh) weeps.length = 0;
  const show = f.active || f.slow < 1 || f.burn > 0 || f.fade > 0;
  if (!show) return bits.length > 0;
  g.fillStyle = `rgba(14, 2, 4, ${(0.1 + 0.2 * f.gloom + 0.28 * (1 - f.slow)) * f.fade})`;
  g.fillRect(0, 0, w, h);
  layer.begin(w, h);
  drawLids(f);
  // Where it's going: a bruise under the skin, in dots, a little alive on each beat.
  if (f.active) {
    const dim = rgba(92, 12, 30);
    const dark = rgba(20, 2, 8);
    const last = Math.max(1, f.landed);
    for (let i = last; i <= f.points.length; i++) {
      if (i === f.points.length && !f.closed) break;
      const seed = hash(i + f.run * 7);
      const steps = Math.ceil(pathOf(f, i, 0.5, seed).len / (4.5 * u));
      for (let s = 1; s < steps; s++) {
        const p = pathOf(f, i, s / steps, seed);
        layer.set(Math.round(p.x), Math.round(p.y), dark);
        layer.set(Math.round(p.x), Math.round(p.y) - 1, dim);
      }
    }
  }
  drawVein(f);
  layer.flush(g);
  return true;
}

function over(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { r, u, w, h, now, dt } = f;
  meat.begin(w, h);
  rings.begin(w, h);
  layer.begin(w, h);
  // What's left at each point once it's landed: a wet slit, shut.
  scars.begin(w, h);
  const seams: { x0: number; y0: number; x1: number; y1: number }[] = [];
  if (f.fade > 0) {
    for (let i = 0; i < f.landed; i++) {
      const at = watch.landedAt[i] ?? now;
      if (now - at < 0.5) continue;
      const p = f.points[i];
      const hit = f.drawn[i] !== false;
      if (f.fade < 0.14) continue;
      // (Shut and crooked, each its own way, a seam down it: a scar, in the vein's dark red.)
      const tilt = (hash(i + f.run * 7) - 0.5) * 0.9;
      const reach = (hit ? 0.42 : 0.26) * WIDE * r;
      const c = Math.cos(tilt) * reach;
      const sn = Math.sin(tilt) * reach;
      const steps = Math.ceil(reach / 1.1);
      for (let s = -steps; s <= steps; s++) {
        const k = s / steps;
        scars.dome(p.x + k * c, p.y + k * sn, (hit ? 3 : 2.1) * u * (0.4 + 0.6 * (1 - k * k)) * f.fade);
      }
      seams.push({ x0: p.x - c * 0.8, y0: p.y - sn * 0.8, x1: p.x + c * 0.8, y1: p.y + sn * 0.8 });
    }
  }
  // Streams down the glass: a pixel wide, a dark edge, a bead at the end of each.
  const weepRuns: { e: Weep; run: number }[] = [];
  for (let i = weeps.length - 1; i >= 0; i--) {
    const e = weeps[i];
    const age = now - e.at;
    if (age < 0) continue;
    if (!f.active && f.fade <= 0) {
      weeps.splice(i, 1);
      continue;
    }
    weepRuns.push({ e, run: e.len * (1 - Math.exp(-age * 2.2)) * f.fade });
  }
  // The rings' strands first, then the eyes between their lips, then the rings over them.
  const eyes: { x: number; y: number; heat: number; open: number; pin: number; blood: number; lx: number; ly: number }[] = [];
  const look = (x: number, y: number) => {
    const p = f.pointer;
    if (!p) return [0, 0.04];
    const dx = p.x - x;
    const dy = p.y - y;
    const d = Math.hypot(dx, dy) || 1;
    const k = Math.min(1, d / (r * 3)) * 0.1;
    return [(dx / d) * k, (dy / d) * k * 0.7];
  };
  for (const c of [...f.circles].reverse()) {
    const show = appear(c.left);
    if (show <= 0) continue;
    const open = smooth(show * 1.1) * (1 + 0.02 * f.beat);
    wound(c.x, c.y, f, open, c.number);
    const [lx, ly] = look(c.x, c.y);
    const late = clamp(-c.left / 0.3);
    eyes.push({ x: c.x, y: c.y, heat: c.point / 5, open, pin: late * 0.25, blood: late + 0.15 * clamp(1 - c.left * 2), lx, ly });
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    const heat = (b.number / 111 - 1) / 5;
    if (b.kind === 'miss') {
      // Wide, pinned, bloodshot, shaking; it shuts at the last.
      const shake = (Math.floor(now * 30) % 2 ? 1 : -1) * u * 0.6;
      const open = 1.05 * (t > 0.82 ? 1 - (t - 0.82) / 0.18 : 1);
      wound(x + shake, y, f, open, b.number);
      eyes.push({ x: x + shake, y, heat: 1, open, pin: 1, blood: 1, lx: 0, ly: 0 });
    } else if (b.kind === 'good') {
      const open = 1 - smooth(t * 1.5);
      wound(x, y, f, Math.max(0.12, open), b.number);
      if (open > 0.02) eyes.push({ x, y, heat, open, pin: 0.3, blood: 0.6, lx: 0, ly: 0.06 });
    } else {
      // It's gone: the socket caves in behind the spray.
      wound(x, y, f, Math.max(0.12, 1 - smooth(t * 1.8)), b.number);
    }
  }
  moveBits(bits, dt, 280 * u, (b, k) => meat.dome(b.x, b.y, b.r * (1 - 0.5 * k) + 0.5));
  meat.shade(layer, shadeMeat, KEY);
  scars.shade(layer, shadeVein, KEY);
  for (const m of seams) pixelLine(layer, m.x0, m.y0, m.x1, m.y1, KEY);
  for (const { e, run } of weepRuns) {
    if (run < 2 || f.fade < 0.14) continue;
    const steps = Math.ceil(run);
    for (let s = 0; s <= steps; s++) {
      const x = Math.round(e.x + Math.sin((s / 9) * u + e.seed * 9) * 1.3 * u);
      const y = Math.round(e.y + s);
      layer.set(x + 1, y, KEY);
      layer.set(x, y, s < 3 ? VEIN[2] : VEIN[3]);
    }
    const x = Math.round(e.x + Math.sin((steps / 9) * u + e.seed * 9) * 1.3 * u);
    const y = Math.round(e.y + steps);
    const size = Math.max(1, Math.round(1.2 * u));
    for (let j = -size; j <= size + 1; j++) {
      const wide = j < 0 ? 0 : size;
      for (let i = -wide - 1; i <= wide + 1; i++) layer.set(x + i, y + j, Math.abs(i) > wide || j === size + 1 ? KEY : j < 1 && i < 0 ? MEAT[4] : VEIN[3]);
    }
  }
  for (const e of eyes) eyeball(e.x, e.y, f, e.heat, e.open, e.pin, e.blood, e.lx, e.ly);
  // The socket's dark, where the eye's burst out of it; it flashes white for a frame or two as it goes.
  for (const b of f.bursts) {
    if (b.kind !== 'perfect') continue;
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    const open = Math.max(0.1, 1 - smooth(t * 1.8));
    const flash = b.age < 0.08;
    for (let py = Math.round(y - r * 1.1); py <= y + r * 1.1; py++) {
      const v = (py - y) / r;
      for (let qx = Math.round(x - r * WIDE); qx <= x + r * WIDE; qx++) {
        const a = (qx - x) / r;
        if (Math.abs(v) < 1.06 * open * (1 - (a * a) / (WIDE * WIDE)))
          layer.set(qx, py, flash ? MEAT[3] : noise(qx * 4, py * 4 + now * 30) > 0.5 ? VEIN[1] : BLACK);
      }
    }
  }
  // Each ring: a sphincter of raw meat, its inner edge what meets the iris's on the beat, tied in by sinews.
  for (const c of f.circles) {
    const show = appear(c.left);
    if (show <= 0) continue;
    const ring = ringAt(f, c.left);
    const tube = 2.4 * u;
    const centre = ring + tube * 0.74;
    const turn = now * 0.35 + c.number;
    const sinews = 9;
    for (let i = 0; i < sinews && ring > r * 1.1; i++) {
      const a = turn + (i / sinews) * TAU;
      const wob = Math.sin(now * 5 + i) * 0.03;
      const x0 = c.x + Math.cos(a + wob) * ring;
      const y0 = c.y + Math.sin(a + wob) * ring;
      const x1 = c.x + Math.cos(a) * r * 0.98;
      const y1 = c.y + Math.sin(a) * r * 0.98;
      pixelLine(layer, x0, y0 + 1, x1, y1 + 1, KEY);
      pixelLine(layer, x0, y0, x1, y1, i % 3 === 0 ? MEAT[4] : MEAT[3]);
    }
    const steps = Math.ceil((centre * TAU) / 1.6);
    const quiver = c.left < 0 ? Math.sin(now * 60) * 0.5 * u : 0;
    for (let s = 0; s < steps; s++) {
      const a = (s / steps) * TAU;
      const lump = 1 + 0.32 * noise((a + turn) * 20, c.number);
      rings.dome(c.x + Math.cos(a) * (centre + quiver), c.y + Math.sin(a) * (centre + quiver), tube * lump);
    }
  }
  rings.shade(layer, shadeMeat, KEY);
  // Clamped: it's on the beat, or past it. A hard wet line round the sphincter's inner edge, so the moment's plain.
  for (const c of f.circles) {
    if (c.left > 0.03) continue;
    const size = r + 1 * u;
    const steps = Math.ceil(size * TAU);
    for (let s = 0; s < steps; s++) {
      const a = (s / steps) * TAU;
      layer.set(Math.round(c.x + Math.cos(a) * size), Math.round(c.y + Math.sin(a) * size), c.left < -0.05 && Math.floor(now * 16) % 2 ? MEAT[3] : WET);
    }
  }
  layer.flush(g);
  // The numbers, in the pupils.
  for (const c of f.circles) {
    const show = appear(c.left);
    if (show <= 0) continue;
    const [lx, ly] = look(c.x, c.y);
    f.label(String(c.number), c.x + lx * r, c.y + ly * r + 0.5, r * 0.9, '#ffeed6', show);
    if (f.teaching) f.label('CLICK', c.x, c.y + r * 2.25, r * 1.05, '#ffeed6', 0.55 + 0.45 * Math.sin(now * 8));
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    if (b.kind === 'perfect') f.label(String(b.number), x, y + 0.5, r * (0.9 + 0.7 * t), '#fff6e4', 1 - t);
    else if (b.kind === 'good') f.label(String(b.number), x, y + 0.5, r * 0.9, '#f0a090', 1 - t * 1.5);
    else f.label(String(b.number), x, y + 0.5, r * 0.62, '#ff3040', 1 - t * t);
  }
  return bits.length > 0 || f.fade > 0;
}

// The eyes round the view when the boost's on or it's been let down: the same eyes as the circles', torn open in the same raw
// edge. No numbers in these, so the pupil's pinned and the iris is all blood; the whites are shot through and in shadow.
const lips = new Relief();
const LIP = MEAT.slice(0, 4);
function shadeLip(x: number, y: number, nx: number, ny: number, nz: number) {
  return ramp(LIP, 0.42 + 0.6 * (-nx * 0.5 - ny * 0.8 + nz * 0.3) + (noise(x * 5, y * 5) - 0.5) * 0.26, x, y);
}

function staringEye(f: RhythmFrame, e: Stare) {
  const { w, h, beat } = f;
  const px = layer.px;
  const r = e.size / WIDE;
  const c = Math.cos(e.tilt);
  const s = Math.sin(e.tilt);
  const dx0 = e.lookX - e.x;
  const dy0 = e.lookY - e.y;
  const d0 = Math.hypot(dx0, dy0) || 1;
  // Turned in, in the eye's own axes, as far as the lids let it.
  const ix = ((dx0 * c + dy0 * s) / d0) * 0.46;
  const iy = ((-dx0 * s + dy0 * c) / d0) * 0.22;
  const pupil = 0.26 + 0.05 * beat;
  const colours = IRISES[5];
  const seed = e.seed * 211;
  const span = Math.ceil(e.size) + 1;
  for (let py = Math.max(0, Math.round(e.y) - span); py <= Math.min(h - 1, Math.round(e.y) + span); py++) {
    for (let qx = Math.max(0, Math.round(e.x) - span); qx <= Math.min(w - 1, Math.round(e.x) + span); qx++) {
      const a = ((qx - e.x) * c + (py - e.y) * s) / r;
      const v = (-(qx - e.x) * s + (py - e.y) * c) / r;
      const lid = 1.02 * e.open * (1 - (a * a) / (WIDE * WIDE));
      if (Math.abs(v) >= lid) continue;
      const dx = a - ix;
      const dy = v - iy;
      const rho = Math.sqrt(dx * dx + dy * dy);
      let col: number;
      if (rho < 0.86) {
        if (rho < pupil) col = BLACK;
        else if (rho > 0.76) col = DEEP;
        else {
          const fibre = hash(Math.floor((Math.atan2(dy, dx) / TAU + 0.5) * 22) + e.seed);
          col = colours[Math.min(2, Math.floor(((rho - pupil) / (0.76 - pupil)) * 2.2 + fibre * 0.9))];
        }
      } else if (Math.abs(a) > WIDE - 0.26) col = CORNER;
      else if (Math.abs(noise(qx * 3 + seed, py * 3 + seed) - 0.5) < 0.075) col = CAPILLARY;
      else col = SCLERA[Math.abs(a) > 1.05 ? 0 : Math.abs(a) > 0.72 ? 1 : 2];
      // (The upper lid's shadow on the ball.)
      if (v < -lid + 1.6 / r) col = DEEP;
      px[py * w + qx] = col;
    }
  }
  if (e.open > 0.5 && r > 4) {
    const size = Math.max(1, Math.round(r * 0.18));
    const gx = Math.round(e.x + (ix - 0.32) * r * c - (iy - 0.34) * r * s);
    const gy = Math.round(e.y + (ix - 0.32) * r * s + (iy - 0.34) * r * c);
    for (let j = 0; j < size; j++) for (let i = 0; i <= size; i++) layer.set(gx + i, gy + j, GLINT);
  }
}

function stare(g: CanvasRenderingContext2D, f: RhythmFrame, eyes: Stare[]) {
  layer.begin(f.w, f.h);
  lips.begin(f.w, f.h);
  for (const e of eyes) {
    const r = e.size / WIDE;
    const c = Math.cos(e.tilt);
    const s = Math.sin(e.tilt);
    const steps = Math.max(8, Math.ceil(e.size * 1.1));
    const fat = Math.max(1.5, r * 0.26);
    for (let i = 0; i <= steps; i++) {
      const a = -WIDE + (2 * WIDE * i) / steps;
      const ly = (1.02 * e.open * (1 - (a * a) / (WIDE * WIDE)) + 0.04) * r;
      const lump = fat * (0.9 + 0.4 * hash(i + e.seed * 90));
      lips.dome(e.x + a * r * c - -ly * s, e.y + a * r * s + -ly * c, lump);
      lips.dome(e.x + a * r * c - ly * s, e.y + a * r * s + ly * c, lump * 1.1);
    }
    // Torn on at its corners.
    for (const side of [-1, 1]) {
      const out = side * r * (WIDE + 0.42 + 0.3 * e.seed);
      const kink = (e.seed - 0.5) * r * 0.5 * side;
      lips.line(e.x + side * WIDE * r * c, e.y + side * WIDE * r * s, e.x + out * c - kink * s, e.y + out * s + kink * c, fat * 1.1, Math.max(1, fat * 0.45));
    }
  }
  lips.shade(layer, shadeLip, KEY);
  for (const e of eyes) staringEye(f, e);
  layer.flush(g);
}

export const flesh: RhythmLook = { id: 'a', name: 'LIVING FLESH', under, stare, over };
