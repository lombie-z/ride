import {
  almondEyes,
  appear,
  type Bit,
  bayer,
  clamp,
  hash,
  hex,
  layer,
  moveBits,
  noise,
  Relief,
  type RhythmFrame,
  type RhythmLook,
  RunWatch,
  ramp,
  rgba,
  ringAt,
  smooth,
} from './shared';

// C: bone and coral. The hive's own building stuff. Each point's a carved wheel of bone, notched round its edge, its number in
// a dark well with the marrow moving in it. The ring's a jaw of the same, teeth inward, turning as it closes so that they meet the
// notches exactly as they touch on the beat, and then bite. Hit, the wheel cracks open; miss, it comes apart and falls. The sigil
// grows from wheel to wheel as coral does, forking and knobbed. Ribs fan in from the top corners and up from the bottom as the run
// goes on, the way the cathedral's vaults do; on 666 the marrow floods every crack and it all falls down.

const KEY = hex('#0c0604');
const BONE = ['#2a180c', '#5a3c22', '#94724c', '#ccb086', '#eedfbc', '#fffae8'].map((c) => hex(c));
const RIB = ['#140a06', '#3a2214', '#6c4c30', '#a88a60', '#dcc8a0'].map((c) => hex(c));
const WELL = hex('#120604');
const CUT = hex('#190a06');
const SHADE = [hex('#0c0604', 90), hex('#0c0604', 150), hex('#0c0604', 215)];
const MARROW = ['#3c0608', '#7a0c12', '#c8141e', '#ff4030'].map((c) => hex(c));
const GOLD = [255, 186, 70];
const BLOOD = [226, 24, 34];
const tint = (t: number, k = 1) => rgba(...(GOLD.map((v, i) => Math.round((v + (BLOOD[i] - v) * t) * k)) as [number, number, number]));

const TAU = Math.PI * 2;
const NOTCHES = 8;

const coral = new Relief();
const ribs = new Relief();
const watch = new RunWatch();
const bits: Bit[] = [];
/** How far the marrow's flooded the cracks (666). */
let flood = 0;

function shadeBone(x: number, y: number, nx: number, ny: number, nz: number) {
  const light = -nx * 0.55 - ny * 0.7 + nz * 0.42;
  const crack = noise(x * 7 + 11, y * 7);
  if (crack > 0.84 - flood * 0.26) return flood > 0.02 ? MARROW[3 - Math.floor(flood * 0.99)] : BONE[1];
  return ramp(BONE, 0.42 + 0.62 * light + (noise(x * 9, y * 2.5) - 0.5) * 0.22, x, y);
}
function shadeRib(x: number, y: number, nx: number, ny: number, nz: number) {
  const light = -nx * 0.5 - ny * 0.75 + nz * 0.25;
  if (flood > 0.02 && noise(x * 6, y * 6) > 0.66 - 0.2 * flood) return MARROW[2];
  return ramp(RIB, 0.32 + 0.72 * light + (noise(x * 8, y * 3) - 0.5) * 0.18, x, y);
}

/** One pixel of a wheel at (a, v), in shares of its radius from its centre, turned by `spin`; 0 if it's off it. */
function wheelPixel(a: number, v: number, x: number, y: number, spin: number, heat: number, r: number, now: number) {
  const rho = Math.sqrt(a * a + v * v);
  if (rho > 1) return 0;
  const px1 = 1 / r;
  // The hard edge that the jaw has to reach.
  if (rho > 1 - px1 * 1.1) return KEY;
  const well = 0.72;
  if (rho < well) {
    if (rho > well - px1 * 1.2) return KEY;
    // The dark well, the marrow moving under the number.
    const flow = noise(x * 1.6 + now * 2, y * 1.6 - now * 9);
    if (flow > 0.66) return flow > 0.78 ? tint(heat, 0.46) : tint(heat, 0.24);
    return WELL;
  }
  const angle = Math.atan2(v, a);
  const turn = ((angle + spin) / TAU) * NOTCHES;
  const phase = turn - Math.floor(turn);
  const depth = (rho - well) / (1 - well);
  // The notches, cut in from the edge, wider out.
  const notch = Math.abs(phase - 0.5);
  if (notch < depth * 0.24) return notch > depth * 0.24 - 0.05 ? BONE[0] : CUT;
  // Its band, rounded over: lit from above, in shadow under.
  const side = (depth - 0.5) * 2;
  const light = -((a / rho) * side * 0.55 + (v / rho) * side * 0.75) + 0.34;
  return ramp(BONE, 0.48 + 0.55 * light + (noise(x * 9 + spin * 20, y * 3) - 0.5) * 0.16, x, y);
}

function wheel(f: RhythmFrame, x: number, y: number, spin: number, heat: number) {
  const { r, w, h, now } = f;
  const top = Math.ceil(r) + 1;
  const px = layer.px;
  for (let py = Math.max(0, Math.round(y) - top); py <= Math.min(h - 1, Math.round(y) + top); py++) {
    for (let qx = Math.max(0, Math.round(x) - top); qx <= Math.min(w - 1, Math.round(x) + top); qx++) {
      const c = wheelPixel((qx - x) / r, (py - y) / r, qx, py, spin, heat, r, now);
      if (c) px[py * w + qx] = c;
    }
  }
}

/** A wheel come apart into wedges, each carried off by `carry` (given its number, for how far). */
function wedges(f: RhythmFrame, x: number, y: number, spin: number, heat: number, parts: number, carry: (k: number) => [number, number]) {
  const { r, now } = f;
  const top = Math.ceil(r) + 1;
  const off: [number, number][] = [];
  for (let k = 0; k < parts; k++) off.push(carry(k));
  for (let py = -top; py <= top; py++) {
    for (let qx = -top; qx <= top; qx++) {
      const a = qx / r;
      const v = py / r;
      const c = wheelPixel(a, v, Math.round(x) + qx, Math.round(y) + py, spin, heat, r, now);
      if (!c) continue;
      // (Crooked breaks, not a pie's: the angle's knocked about by noise.)
      const angle = Math.atan2(v, a) + Math.PI + (noise(qx * 3 + 40, py * 3) - 0.5) * 0.9;
      const k = Math.floor((angle / TAU) * parts + parts) % parts;
      layer.set(Math.round(x + qx + off[k][0]), Math.round(y + py + off[k][1]), c);
    }
  }
}

/** The jaw: a band of bone with teeth inward, their tips at radius `ring`. */
function jaw(f: RhythmFrame, x: number, y: number, ring: number, turn: number, show: number) {
  const { u, w, h } = f;
  const teeth = 5 * u;
  const band = 3.8 * u;
  const outer = ring + teeth + band;
  const reach = Math.ceil(outer + 2);
  const px = layer.px;
  for (let py = Math.max(0, Math.round(y) - reach); py <= Math.min(h - 1, Math.round(y) + reach); py++) {
    const dy = py - y;
    for (let qx = Math.max(0, Math.round(x) - reach); qx <= Math.min(w - 1, Math.round(x) + reach); qx++) {
      const dx = qx - x;
      const d2 = dx * dx + dy * dy;
      if (d2 > (outer + 1) * (outer + 1) || d2 < ring * ring - 1) continue;
      const d = Math.sqrt(d2);
      if (show < 1 && bayer(qx, py) > show) continue;
      const i = py * w + qx;
      if (d >= outer) {
        px[i] = KEY;
        continue;
      }
      const angle = Math.atan2(dy, dx);
      const t = ((angle + turn) / TAU) * NOTCHES;
      const phase = Math.abs(t - Math.floor(t) - 0.5);
      if (d >= ring + teeth) {
        // The band, in lengths joined at knuckles.
        const joint = ((angle + turn) / TAU) * 4;
        if (Math.abs(joint - Math.floor(joint) - 0.5) < 0.012 || d < ring + teeth + 1) {
          px[i] = KEY;
          continue;
        }
        const side = ((d - ring - teeth) / band - 0.5) * 2;
        const light = -((dx / d) * side * 0.55 + (dy / d) * side * 0.75) + 0.4;
        px[i] = ramp(BONE, 0.46 + 0.58 * light + (noise(qx * 9 + 3, py * 3) - 0.5) * 0.16, qx, py);
        continue;
      }
      // The teeth: wide at the band, to a point at the ring's radius.
      const tooth = ((d - ring) / teeth) * 0.42 + 0.02;
      if (phase > tooth + 0.05) continue;
      if (phase > tooth) {
        px[i] = KEY;
        continue;
      }
      // (One flank in the light, the other in shadow: a tooth, not a tick.)
      const flank = t - Math.floor(t) - 0.5;
      px[i] = flank < 0 ? BONE[5] : phase > tooth * 0.45 ? BONE[2] : BONE[3];
    }
  }
}

type Twig = { pts: { x: number; y: number; r: number }[]; delay: number; grow: number; seed: number };
let treesKey = '';
const trees = new Map<number, Twig[]>();

/** A stretch of the sigil as coral: the main stem from point to point, wandering, with forks off it. */
function tree(f: RhythmFrame, i: number) {
  const key = `${f.run}/${f.w}/${f.h}`;
  if (key !== treesKey) {
    treesKey = key;
    trees.clear();
  }
  const have = trees.get(i);
  if (have) return have;
  const a = f.points[(i - 1 + f.points.length) % f.points.length];
  const b = f.points[i % f.points.length];
  const u = f.u;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const salt = i * 37 + f.run * 101;
  const stem: Twig['pts'] = [];
  const n = 18;
  for (let s = 0; s <= n; s++) {
    const t = s / n;
    const off = Math.sin(t * Math.PI) * (Math.sin(t * 6 + salt) * 0.05 + (hash(salt + s) - 0.5) * 0.035) * len;
    // (Fat at its nodes, thin between.)
    const knot = hash(salt + s * 3) > 0.72 ? 1.25 : 1;
    stem.push({ x: a.x + dx * t + (-dy / len) * off, y: a.y + dy * t + (dx / len) * off, r: (3.2 - 0.9 * t) * u * knot });
  }
  const list: Twig[] = [{ pts: stem, delay: 0, grow: 0.3, seed: hash(salt) }];
  const fork = (from: { x: number; y: number; r: number }, angle: number, length: number, depth: number, delay: number, seed: number) => {
    const pts: Twig['pts'] = [];
    const steps = Math.max(3, Math.round(length / (3 * u)));
    let x = from.x;
    let y = from.y;
    let ang = angle;
    for (let s = 0; s <= steps; s++) {
      const t = s / steps;
      pts.push({ x, y, r: Math.max(1.5 * u, from.r * (0.82 - 0.42 * t)) });
      ang += (hash(seed + s * 7) - 0.5) * 0.5;
      x += Math.cos(ang) * 3 * u;
      y += Math.sin(ang) * 3 * u;
    }
    list.push({ pts, delay, grow: 0.34 + 0.2 * hash(seed + 2), seed: hash(seed + 5) });
    if (depth > 0) {
      const mid = pts[Math.floor(pts.length * 0.55)];
      fork(mid, ang + 0.7, length * 0.6, depth - 1, delay + 0.18, seed + 13);
      fork(mid, ang - 0.7, length * 0.5, depth - 1, delay + 0.24, seed + 29);
    }
  };
  const base = Math.atan2(dy, dx);
  for (let k = 0; k < 5; k++) {
    const h = hash(salt + k * 19);
    const at = stem[Math.floor(2 + h * (n - 4))];
    const side = k % 2 ? 1 : -1;
    fork(at, base + side * (0.8 + 0.6 * hash(salt + k * 23)), (11 + 15 * hash(salt + k * 31)) * u, 1, 0.14 + 0.4 * h, salt + k * 41);
  }
  trees.set(i, list);
  return list;
}

function layTwig(t: Twig, grown: number, drop: number, shrink: number) {
  const n = t.pts.length - 1;
  const upto = grown * n;
  for (let s = 0; s < n && s < upto; s++) {
    const a = t.pts[s];
    const b = t.pts[s + 1];
    const k = Math.min(1, upto - s);
    const x = a.x + (b.x - a.x) * k;
    const y = a.y + (b.y - a.y) * k;
    coral.line(a.x, a.y + drop, x, y + drop, a.r * shrink, b.r * shrink);
  }
  // A knob at its growing tip.
  if (grown > 0.08) {
    const m = Math.min(n, Math.floor(upto));
    coral.dome(t.pts[m].x, t.pts[m].y + drop, (t.pts[m].r + 0.7 * shrink * 1.2) * shrink);
  }
}

// The vaulting: fans of ribs springing from the corners and the sides of the view, the way the cathedral's roof does, with a
// course of pointed arches between them part way out. Each grows as the run goes on, the dark coming with it in hard steps.
type Fan = { x: number; y: number; from: number; to: number; ribs: number; reach: number; start: number };
const FANS: Fan[] = (() => {
  const list: Fan[] = [];
  for (const side of [0, 1]) {
    const m = (a: number) => (side ? Math.PI - a : a);
    const pair = (a: number, b: number) => (side ? [m(b), m(a)] : [a, b]);
    const [a0, a1] = pair(0.02, 1.5);
    list.push({ x: side, y: -0.02, from: a0, to: a1, ribs: 7, reach: 1.15, start: 0 });
    const [b0, b1] = pair(-0.9, 0.4);
    list.push({ x: side, y: 0.62, from: b0, to: b1, ribs: 5, reach: 0.66, start: 0.25 });
    const [c0, c1] = pair(-1.45, -0.1);
    list.push({ x: side, y: 1.02, from: c0, to: c1, ribs: 4, reach: 0.44, start: 0.4 });
  }
  return list;
})();

function drawRibs(f: RhythmFrame, g: number, sinking: number) {
  const { w, h, u, unit } = f;
  const px = layer.px;
  const grown = FANS.map((b) => smooth((g - b.start) / (1 - b.start + 0.1)) * b.reach * unit);
  // The dark behind them, in three hard steps, a little ragged: what's cast by what's closing in.
  if (g > 0.01) {
    const hold = (1 - sinking) ** 2;
    for (let y = 0; y < h; y += 2) {
      for (let x = 0; x < w; x += 2) {
        let dark = 0;
        for (let k = 0; k < FANS.length; k++) {
          if (grown[k] <= 0) continue;
          const dx = x - FANS[k].x * w;
          const dy = y - FANS[k].y * h;
          // (Scalloped: each cell of the vault arching out between its two ribs, not a disc.)
          const b = FANS[k];
          const at = (Math.atan2(dy, dx) - b.from) / ((b.to - b.from) / b.ribs);
          const cell = Math.abs((((at % 1) + 1) % 1) - 0.5) * 2;
          const v = 1 - Math.sqrt(dx * dx + dy * dy) / (grown[k] * (0.72 + 0.28 * (1 - cell * cell)));
          if (v > dark && at > -0.5 && at < b.ribs + 0.5) dark = v;
        }
        if (dark <= 0) continue;
        const n = dark * 3 + (noise(x * 2, y * 2) - 0.5) * 0.3;
        const c = n > 1.5 ? SHADE[2] : n > 0.7 ? SHADE[1] : SHADE[0];
        if (hold < 1 && hash(x * 13 + y) > hold) continue;
        px[y * w + x] = c;
        px[y * w + x + 1] = c;
        if (y + 1 < h) {
          px[(y + 1) * w + x] = c;
          px[(y + 1) * w + x + 1] = c;
        }
      }
    }
  }
  ribs.begin(w, h);
  FANS.forEach((b, k) => {
    if (grown[k] <= 0) return;
    const ox = b.x * w;
    const oy = b.y * h;
    const tips: { x: number; y: number }[][] = [];
    for (let i = 0; i < b.ribs; i++) {
      const seed = hash(k * 13 + i * 7);
      const a = b.from + ((b.to - b.from) * (i + 0.5)) / b.ribs;
      const len = grown[k] * (0.82 + 0.18 * seed);
      const drop = sinking * sinking * h * (0.7 + 0.9 * seed);
      const steps = Math.ceil(len / (1.5 * u));
      const line: { x: number; y: number }[] = [];
      for (let s = 0; s <= steps; s++) {
        const t = s / steps;
        // (Each bowed a little, away from the fan's middle, and tapering to a thorn.)
        const bow = (a + (i - (b.ribs - 1) / 2) * 0.09 * t * t) % (Math.PI * 2);
        const x = ox + Math.cos(bow) * len * t;
        const y = oy + Math.sin(bow) * len * t + drop;
        const knuckle = 1 + 0.26 * Math.max(0, Math.sin(t * 26 + seed * 9)) ** 10;
        ribs.dome(x, y, ((3.8 * (1 - t) ** 0.8 + 0.5) * u + (t > 0.95 ? -0.3 : 0)) * knuckle);
        if (s % 2 === 0) line.push({ x, y });
      }
      tips.push(line);
    }
    // The course of arches between neighbours: two curves up to a point.
    for (const at of [0.48, 0.74]) {
      for (let i = 0; i + 1 < tips.length; i++) {
        const l = tips[i];
        const r = tips[i + 1];
        const p = l[Math.floor(l.length * at)];
        const q = r[Math.floor(r.length * at)];
        if (!p || !q) continue;
        const peak = { x: ox + ((p.x + q.x) / 2 - ox) * 1.14, y: oy + ((p.y + q.y) / 2 - oy) * 1.14 };
        ribs.line(p.x, p.y, peak.x, peak.y, 1.5 * u, 1.3 * u, 0.8);
        ribs.line(q.x, q.y, peak.x, peak.y, 1.5 * u, 1.3 * u, 0.8);
      }
    }
  });
  ribs.shade(layer, shadeRib, KEY);
}

function under(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { w, h, u, now, r, burn } = f;
  watch.update(f, (b) => {
    const x = b.x * w;
    const y = b.y * h;
    const n = b.kind === 'perfect' ? 20 : b.kind === 'good' ? 7 : 12;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU;
      const v = (b.kind === 'perfect' ? 60 + Math.random() * 150 : 20 + Math.random() * 50) * u;
      bits.push({
        x: x + Math.cos(a) * r * 0.8,
        y: y + Math.sin(a) * r * 0.8,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - 30 * u,
        r: (0.8 + Math.random() * 1.8) * u,
        age: 0,
        life: 0.5 + Math.random() * 0.6,
        kind: 0,
      });
    }
  });
  const show = f.active || f.slow < 1 || burn > 0 || f.fade > 0;
  if (!show) return false;
  flood = burn > 0 ? clamp(burn * 1.8) : 0;
  // 666: red behind everything, the bone black against it.
  if (burn > 0.25) {
    g.fillStyle = `rgba(150, 8, 14, ${0.86 * clamp((burn - 0.25) / 0.5)})`;
    g.fillRect(0, 0, w, h);
  }
  layer.begin(w, h);
  const sinking = f.active ? 0 : 1 - f.fade;
  drawRibs(f, Math.max(0.1, f.gloom), sinking);
  coral.begin(w, h);
  // Where it'll grow: scratches ahead of it, across the line, as a mason marks a stone.
  if (f.active) {
    const count = f.points.length;
    const dim = hex('#ecdcb8');
    for (let i = Math.max(1, f.landed); i <= count; i++) {
      if (i === count && !f.closed) break;
      const a = f.points[i - 1];
      const b = f.points[i % count];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const steps = Math.floor(len / (7 * u));
      for (let s = 1; s < steps; s++) {
        const t = s / steps;
        const x = a.x + dx * t;
        const y = a.y + dy * t;
        const nx = -dy / len;
        const ny = dx / len;
        for (let k = -1; k <= 1; k++) {
          layer.set(Math.round(x + nx * k * 1.5 * u), Math.round(y + ny * k * 1.5 * u), k === -1 ? dim : KEY);
        }
      }
    }
  }
  const count = f.points.length;
  for (let i = 1; i <= count; i++) {
    const closing = i === count;
    if (closing ? !f.closed || f.landed < count : i >= f.landed) continue;
    const at = watch.landedAt[closing ? count - 1 : i] ?? now;
    const hit = closing ? true : f.drawn[i] !== false;
    const age = now - at;
    for (const [k, twig] of tree(f, i).entries()) {
      const grown = smooth((age - twig.delay) / twig.grow);
      if (grown <= 0) continue;
      // (Missed: the stem only gets part way, a stump from each end, and nothing forks.)
      if (!hit && k > 0) continue;
      const drop = sinking * sinking * h * (0.5 + 1.1 * twig.seed);
      if (!hit) {
        layTwig({ ...twig, pts: twig.pts.slice(0, 7) }, grown, drop, 0.72);
        layTwig({ ...twig, pts: twig.pts.slice(-6).reverse() }, grown, drop, 0.72);
      } else layTwig(twig, grown, drop, 1);
    }
  }
  coral.shade(layer, shadeBone, KEY);
  layer.flush(g);
  return true;
}

function over(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { r, u, w, h, now, dt } = f;
  layer.begin(w, h);
  coral.begin(w, h);
  // What's left at each point: a knot in the coral.
  if (f.fade > 0) {
    for (let i = 0; i < f.landed; i++) {
      if (now - (watch.landedAt[i] ?? now) < 0.5) continue;
      const p = f.points[i];
      const hit = f.drawn[i] !== false;
      const drop = f.active ? 0 : (1 - f.fade) ** 2 * h;
      coral.dome(p.x, p.y + drop, (hit ? 7 : 4.6) * u * (0.5 + 0.5 * f.fade) * 1.34);
      if (hit) for (let k = 0; k < 4; k++) coral.dome(p.x + Math.cos(i * 2 + k * 1.57) * 5.4 * u, p.y + Math.sin(i * 2 + k * 1.57) * 5.4 * u + drop, 2.6 * u);
    }
  }
  moveBits(bits, dt, 340 * u, (b) => coral.dome(b.x, b.y, b.r + 0.9));
  coral.shade(layer, shadeBone, KEY);
  for (const c of [...f.circles].reverse()) {
    const show = appear(c.left);
    if (show <= 0) continue;
    const spin = now * 0.5 + c.number;
    const heat = c.point / 5;
    if (show < 1) {
      // It turns up by being cut out of nothing, line by line.
      const reveal = show;
      wheel(f, c.x, c.y, spin, heat);
      for (let py = Math.round(c.y - r - 1); py <= c.y + r + 1; py++) {
        if ((py - c.y + r) / (2 * r) > reveal * 1.02) for (let qx = Math.round(c.x - r - 1); qx <= c.x + r + 1; qx++) layer.set(qx, py, 0);
      }
    } else wheel(f, c.x, c.y, spin, heat);
    // Turning into step with the notches, so they meet as it lands; then biting in, late.
    const late = clamp(-c.left / 0.34);
    const ring = ringAt(f, c.left) - late * 3.4 * u;
    jaw(f, c.x, c.y, ring, spin + 1.15 * Math.max(0, c.left), show);
    // (Late: blood comes up in the cuts it's bitten.)
    if (late > 0) {
      for (let k = 0; k < NOTCHES; k++) {
        const a = ((k + 0.5) / NOTCHES) * TAU - spin;
        const x = Math.round(c.x + Math.cos(a) * r * 0.86);
        const y = Math.round(c.y + Math.sin(a) * r * 0.86);
        layer.set(x, y, MARROW[2]);
        layer.set(x, y + 1, MARROW[1]);
      }
    }
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    const spin = b.number;
    const heat = (b.number / 111 - 1) / 5;
    if (b.kind === 'perfect') {
      wedges(f, x, y, spin, heat, 7, (k) => {
        const a = (k + 0.5) * (TAU / 7) - Math.PI;
        const out = r * (0.1 + 2.2 * t);
        return [Math.cos(a) * out, Math.sin(a) * out + 120 * u * t * t];
      });
      // The marrow bursting out of the middle of it.
      const blast = r * 0.74 * (1 - t);
      for (let py = Math.round(y - blast); py <= y + blast; py++) {
        for (let qx = Math.round(x - blast); qx <= x + blast; qx++) {
          if (Math.hypot(qx - x, py - y) < blast) layer.set(qx, py, MARROW[bayer(qx, py) < 0.5 ? 3 : 2]);
        }
      }
    } else if (b.kind === 'good') {
      const gap = 2.4 * u * smooth(t * 3);
      wedges(f, x, y, spin, heat, 3, (k) => {
        const a = (k + 0.5) * (TAU / 3) - Math.PI;
        return [Math.cos(a) * gap, Math.sin(a) * gap + 16 * u * clamp((t - 0.6) / 0.4) ** 2];
      });
    } else {
      // It comes apart and falls, not flung: nothing's been won.
      wedges(f, x, y, spin, 1, 9, (k) => {
        const delay = hash(k * 3 + b.number) * 0.3;
        const fall = Math.max(0, t - delay);
        return [(k - 4) * 0.8 * u * fall * 3, 170 * u * fall * fall];
      });
    }
  }
  layer.flush(g);
  for (const c of f.circles) {
    const show = appear(c.left);
    if (show <= 0) continue;
    f.label(String(c.number), c.x, c.y + 0.5, r * 0.9, '#f4e6c6', show);
    if (f.teaching) f.label('CLICK', c.x, c.y + r * 2.55, r * 1.05, '#f4e6c6', 0.55 + 0.45 * Math.sin(now * 8));
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    if (b.kind === 'perfect') f.label(String(b.number), x, y + 0.5, r * (0.9 + 0.7 * t), '#fff4d8', 1 - t);
    else if (b.kind === 'good') f.label(String(b.number), x, y + 0.5, r * 0.85, '#d8bc90', 1 - t);
    else f.label(String(b.number), x, y + 170 * u * t * t * 0.7 + 0.5, r * 0.7, '#a82028', 1 - t);
  }
  return bits.length > 0 || f.fade > 0;
}

export const bone: RhythmLook = { id: 'c', name: 'BONE AND CORAL', under, stare: almondEyes, over };
