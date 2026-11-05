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
  ringAt,
  smooth,
} from './shared';

// B: black ooze. The hive's own stuff, on the glass: beads of it welling up, black with the red moving inside them, the
// dawn's pale in a hard crescent across the top of each. The ring's a thread of the same, broken up into beads as a thread of
// liquid does, drawn in till it runs into the bead on the beat. Hit, it splashes; good, it slumps; miss, an eye opens in it. The
// sigil's a thread sagging from bead to bead and dripping, red pulsing down it. It comes down the view from the top of the glass
// as the run goes on, and pools in the bottom corners; on 666 a sheet of it swallows the view, red through the black, and
// slides off.

const KEY = hex('#070205');
const BLACK = hex('#040103');
const FLOW = ['#160206', '#36040b', '#6e0712', '#c0101f'].map((c) => hex(c));
const SKY = hex('#ffe4d8');
const SKY_LOW = hex('#c08a98');
const RIM = hex('#c81420');
const RIM_LOW = hex('#6a0812');
const GLINT = hex('#ffffff');
const SCLERA = hex('#8c7464');
const IRIS = ['#ff4a20', '#c00e12', '#6c0408'].map((c) => hex(c));

const TAU = Math.PI * 2;
const THRESH = 0.744;

const body = new Relief();
const sheet = new Relief();
const watch = new RunWatch();
const bits: Bit[] = [];
let clock = 0;
/** How much the red's up (the run's dread, 666). */
let lit = 0;
let lastDrip = 0;
let curtain = 0;

function shadeOoze(x: number, y: number, nx: number, ny: number, nz: number) {
  // A black mirror: the sky's pale in a hard crescent over the top, the red's light in a thin line under the bottom.
  const up = -ny;
  if (up > 0.74 && Math.abs(nx) < 0.5) {
    // (Broken up by the ripples on it: a thread's not striped along its length.)
    if (noise(x * 2.3 + 9, y * 2.3) < 0.36) return BLACK;
    return up > 0.86 && Math.abs(nx) < 0.3 ? SKY : SKY_LOW;
  }
  if (ny > 0.88) return ny > 0.96 ? RIM : RIM_LOW;
  if (nz < 0.42) return BLACK;
  // Inside: deep red flowing like blood through the black, downward; mostly the black.
  const flow = noise(x * 1.7 + clock * 3, y * 1.2 - clock * 22) * 0.6 + noise(x * 3.1 - clock * 5, y * 2.6 - clock * 34) * 0.4 + lit * 0.4;
  if (flow < 0.58) return BLACK;
  if (flow < 0.62) return bayer(x, y) > 0.5 ? FLOW[0] : BLACK;
  return FLOW[Math.min(lit > 0.2 ? 3 : 2, Math.floor((flow - 0.62) * 11))];
}

/** Stamps a bead, its edge at radius r, with a tail hanging off it. */
function bead(x: number, y: number, r: number, u: number, seed: number, wobble: number) {
  body.dome(x, y, r / THRESH, 1, 1 + wobble);
  const tail = (3 + 7 * hash(seed)) * u * (0.6 + 0.4 * Math.sin(clock * 0.9 + seed));
  if (r > 3 * u) body.line(x + r * 0.2 * Math.sin(seed), y + r * 0.8, x + r * 0.2 * Math.sin(seed), y + r + tail, 2.6 * u, 1.8 * u);
}

function sagAt(f: RhythmFrame, i: number, t: number) {
  const a = f.points[(i - 1 + f.points.length) % f.points.length];
  const b = f.points[i % f.points.length];
  const len = Math.hypot(b.x - a.x, b.y - a.y);
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t + (0.09 * len + 2 * f.u) * 4 * t * (1 - t), len };
}

function thread(f: RhythmFrame) {
  const { u, now, landed, burn } = f;
  const count = f.points.length;
  const pulses: { x: number; y: number }[] = [];
  for (let i = 1; i <= count; i++) {
    const closing = i === count;
    if (closing ? !f.closed || landed < count : i >= landed) continue;
    const at = watch.landedAt[closing ? count - 1 : i] ?? now;
    // It runs along from the last to the next.
    const grown = smooth((now - at) / 0.2);
    const hit = closing ? true : f.drawn[i] !== false;
    const len = sagAt(f, i, 0.5).len;
    const steps = Math.ceil(len / 1.3);
    const shed = 1 - clamp(burn > 0 ? (1 - burn) * 2.4 : 1 - f.fade);
    for (let s = 0; s <= steps * grown; s++) {
      const t = s / steps;
      const p = sagAt(f, i, t);
      const cell = Math.floor(t * 7);
      const h = hash(cell + i * 9);
      const inCell = t * 7 - cell;
      const bulge = Math.exp(-(((inCell - 0.3 - 0.4 * h) / 0.17) ** 2)) * (h > 0.45 ? 1 : 0);
      const fall = (1 - shed) * (1 - shed) * f.h * (0.2 + 0.6 * h);
      if (hit) {
        const neck = (1.25 + 0.5 * (Math.abs(t - 0.5) * 2) ** 2 + 0.9 * f.beat * 0.25) * u * shed;
        body.dome(p.x, p.y + fall, neck + bulge * 2.2 * u * (0.5 + 0.5 * shed) + 0.2);
      } else if (bulge > 0.5) {
        // Missed: it's broken up into droplets.
        body.dome(p.x, p.y + fall, 2.1 * u * bulge);
      }
    }
    if (hit && grown >= 1) {
      // The drips hanging off it, slowly getting longer; the blood being pushed down it.
      for (let d = 0; d < 3; d++) {
        const h = hash(i * 13 + d);
        const p = sagAt(f, i, 0.15 + 0.7 * h);
        const reach = (3 + 9 * h) * u * clamp((now - at) * 1.1) * (0.8 + 0.2 * Math.sin(now * 1.3 + h * 9)) * shed;
        if (reach > u) body.line(p.x, p.y, p.x, p.y + reach, 1.9 * u, 1.4 * u + 0.8 * u * h);
      }
      const q = (now * 1.1 + i * 0.37) % 1;
      pulses.push(sagAt(f, i, q));
    }
  }
  // Now and then one lets go.
  if (f.active && landed > 1 && now - lastDrip > 0.45) {
    lastDrip = now;
    const i = 1 + Math.floor(Math.random() * Math.max(1, landed - 1));
    if (f.drawn[i] !== false) {
      const p = sagAt(f, i, 0.2 + 0.6 * Math.random());
      bits.push({ x: p.x, y: p.y + 4 * u, vx: 0, vy: 30 * u, r: (1.6 + Math.random()) * u, age: 0, life: 1.1, kind: 1 });
    }
  }
  return pulses;
}

/** The top of the glass's come-down and the corners' pools; `sink` how far it's let go and slid down. */
function drawCurtain(f: RhythmFrame, g: number, sink: number) {
  const { w, h, u } = f;
  for (let x = 0; x < w; x++) {
    const xn = (x - w / 2) / (w / 2);
    const wander = noise(x * 1.3 + clock * 0.8, 40) * 0.6 + noise(x * 3.7 - clock, 90) * 0.4;
    // (From nothing: at the start of a run, only a few tongues of it have come over the edge.)
    const reach = h * (-0.012 + 0.21 * g + 0.05 * wander) * (0.4 + 1.1 * wander) + xn ** 4 * h * 0.1 * (0.2 + g);
    const top = Math.round(reach + sink);
    for (let y = Math.max(0, Math.round(sink) - 2); y <= Math.min(h - 1, top); y++) {
      const v = clamp((top - y + 1) / (6 * u));
      if (v > 0) sheet.put(x, y, v * v * (3 - 2 * v));
    }
    // The bottom corners.
    const pool = Math.round((Math.abs(xn) ** 3.4 - 0.1) * h * 0.3 * g + (wander - 0.5) * 6 * u * g) - (sink > 0 ? Math.round(sink * 0.4) : 0);
    for (let y = h - 1; y >= Math.max(0, h - pool); y--) {
      const v = clamp((y - (h - pool) + 1) / (6 * u));
      if (v > 0) sheet.put(x, y, v * v * (3 - 2 * v));
    }
  }
  // The long drips.
  for (let i = 0; i < 15; i++) {
    const seed = hash(i * 7.3 + 1);
    const x = ((i + 0.2 + 0.6 * hash(i * 3.1)) / 15) * w;
    const len = h * Math.max(0, g * 1.25 - seed * 0.7) * (0.2 + 0.42 * hash(i * 5.7)) * (0.92 + 0.08 * Math.sin(clock * 0.7 + i));
    if (len < 2 * u) continue;
    const y0 = h * (0.012 + 0.1 * g) + sink;
    const r = (1.9 + 1.5 * hash(i * 9.1)) * u;
    const steps = Math.ceil(len / 1.4);
    for (let s = 0; s <= steps; s++) {
      const t = s / steps;
      // (Thin, with a fat bulb at its end.)
      sheet.dome(x + Math.sin(t * 4 + i) * 0.8 * u, y0 + len * t, r * (0.72 + 0.1 * (1 - t)) + r * 0.85 * clamp((t - 0.92) / 0.08), 1);
    }
  }
}

/** A flat black-eye eye set in the ooze, looking out, shutting now and then: `open` 0 to 1. */
function setEye(x: number, y: number, r: number, open: number, f: RhythmFrame, pinned = 0) {
  const px = layer.px;
  const { w, h } = f;
  for (let py = Math.max(0, Math.round(y - r * 0.62)); py <= Math.min(h - 1, y + r * 0.62); py++) {
    const v = (py - y) / r;
    for (let qx = Math.max(0, Math.round(x - r)); qx <= Math.min(w - 1, x + r); qx++) {
      const a = (qx - x) / r;
      if (Math.abs(v) >= 0.58 * open * (1 - a * a)) continue;
      const rho = Math.hypot(a, v);
      let c = SCLERA;
      if (rho < 0.42) c = rho < 0.2 ? IRIS[0] : rho < 0.32 ? IRIS[1] : IRIS[2];
      // The slit.
      if (Math.abs(a) < 0.07 + 0.06 * (1 - pinned) && Math.abs(v) < 0.36) c = BLACK;
      px[py * w + qx] = c;
    }
  }
}

function under(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { w, h, u, burn } = f;
  clock = f.now;
  watch.update(f, (b) => {
    const x = b.x * w;
    const y = b.y * h;
    const n = b.kind === 'perfect' ? 30 : b.kind === 'good' ? 8 : 0;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU;
      const v = (b.kind === 'perfect' ? 60 + Math.random() * 170 : 20 + Math.random() * 60) * u;
      bits.push({
        x,
        y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v,
        r: (1 + Math.random() * Math.random() * 3.6) * u,
        age: 0,
        life: 0.9 + Math.random() * 0.9,
        kind: 0,
      });
    }
  });
  const show = f.active || f.slow < 1 || burn > 0 || f.fade > 0;
  if (!show) return false;
  if (f.active) curtain = f.gloom;
  // The whole view dulled, a little more each step, as it gets on the glass.
  g.fillStyle = `rgba(10, 2, 5, ${(0.1 + 0.22 * f.gloom + 0.28 * (1 - f.slow)) * f.fade})`;
  g.fillRect(0, 0, w, h);
  layer.begin(w, h);
  sheet.begin(w, h);
  lit = 0.04 + 0.06 * curtain;
  const sink = f.active ? 0 : (1 - f.fade) ** 2 * h * 1.7;
  drawCurtain(f, curtain, sink);
  // 666: the sheet comes down over everything, and goes.
  if (burn > 0) {
    const t = (1 - burn) * 1.1;
    const low = h * 1.15 * smooth(t / 0.1);
    const high = t < 0.2 ? -1 : ((t - 0.2) / 0.42) ** 2 * h * 1.4;
    lit = 0.1 + 0.34 * clamp(1 - t * 1.4);
    for (let x = 0; x < w; x++) {
      const edge = noise(x * 2, t * 60) * 22 * u;
      const y1 = Math.min(h - 1, Math.round(low + edge));
      for (let y = Math.max(0, Math.round(high + edge)); y <= y1; y++) sheet.put(x, y, 1);
    }
  }
  sheet.shade(layer, shadeOoze, KEY);
  // Eyes opening and closing in the curtain.
  if (f.active || sink < h * 0.3) {
    for (let i = 0; i < 9; i++) {
      const seed = hash(i * 17.3 + 2);
      if (curtain < 0.1 + seed * 0.6) continue;
      const x = ((i + 0.5) / 9) * w + (seed - 0.5) * 18 * u;
      const y = h * (0.012 + 0.1 * curtain) * (0.4 + 0.5 * hash(i * 3.3)) + sink;
      const size = (5 + 4 * hash(i * 2.2)) * u;
      const open = smooth(Math.sin(clock * (0.5 + seed) + seed * 40) * 2.4 + 0.3);
      if (open > 0.05) setEye(x, y, size, open, f);
    }
  }
  // Where it's going: flecks already on the glass, in the line it'll take.
  body.begin(w, h);
  const pulses = thread(f);
  body.shade(layer, shadeOoze, KEY);
  for (const p of pulses) {
    const x = Math.round(p.x);
    const y = Math.round(p.y);
    layer.set(x, y, FLOW[3]);
    layer.set(x + 1, y, FLOW[2]);
    layer.set(x - 1, y, FLOW[2]);
  }
  if (f.active) {
    const count = f.points.length;
    for (let i = Math.max(1, f.landed); i <= count; i++) {
      if (i === count && !f.closed) break;
      const steps = Math.ceil(sagAt(f, i, 0.5).len / (4.5 * u));
      for (let s = 1; s < steps; s++) {
        const p = sagAt(f, i, s / steps);
        const x = Math.round(p.x);
        const y = Math.round(p.y);
        layer.set(x, y, KEY);
        layer.set(x, y + 1, KEY);
        layer.set(x + 1, y + 1, RIM_LOW);
        layer.set(x, y - 1, SKY_LOW);
      }
    }
  }
  layer.flush(g);
  return true;
}

function over(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { r, u, w, h, now, dt } = f;
  body.begin(w, h);
  layer.begin(w, h);
  const eyes: { x: number; y: number; size: number; open: number }[] = [];
  const glints: { x: number; y: number; r: number }[] = [];
  // What's left at each point: a little bead, dripping.
  if (f.fade > 0) {
    for (let i = 0; i < f.landed; i++) {
      if (now - (watch.landedAt[i] ?? now) < 0.25) continue;
      const p = f.points[i];
      const size = (f.drawn[i] === false ? 2.4 : 4.2) * u * (0.4 + 0.6 * f.fade);
      bead(p.x, p.y, size, u, i + 1, 0.04);
      glints.push({ x: p.x, y: p.y, r: size });
    }
  }
  for (const c of [...f.circles].reverse()) {
    const show = appear(c.left);
    if (show <= 0) continue;
    // It wells up, overshooting a little, and shivers.
    const grow = show < 1 ? smooth(show) * (1 + 0.14 * Math.sin(show * Math.PI)) : 1;
    const late = clamp(-c.left / 0.34);
    const fat = 1 + 0.03 * f.beat + 0.09 * late;
    const shiver = 0.03 * Math.sin(now * 14 + c.number) + 0.05 * late * Math.sin(now * 42);
    bead(c.x, c.y, r * grow * fat, u, c.number, shiver);
    glints.push({ x: c.x, y: c.y, r: r * grow });
    // The ring: a thread of it, beaded, heavier below; its inner edge what runs into the bead on the beat.
    if (c.left > 0) {
      const ring = ringAt(f, c.left);
      const tube = 1.9 * u;
      const centre = ring + tube * THRESH;
      const steps = Math.ceil((centre * TAU) / 1.3);
      const turn = -now * 0.45 + c.number;
      const beads = 8;
      for (let s = 0; s < steps; s++) {
        const a = (s / steps) * TAU;
        const low = Math.max(0, Math.sin(a));
        const nearest = Math.cos((a - turn) * beads);
        const swell = tube * (0.86 + 0.5 * low) + (nearest > 0.72 ? ((nearest - 0.72) / 0.28) * 1.8 * u : 0);
        // (Swelling outward: its inner edge has to stay true to the time.)
        const off = swell - tube;
        body.dome(c.x + Math.cos(a) * (centre + off * THRESH), c.y + Math.sin(a) * (centre + off * THRESH), Math.max(1.5 * u, swell));
      }
    }
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    if (b.kind === 'perfect') {
      // Gone in a splash, a fat ring of it thrown off.
      bead(x, y, r * Math.max(0.28, 1 - smooth(t * 3.5)), u, b.number, 0.1);
      const out = r * (1 + 1.5 * smooth(t * 1.4));
      const thick = 2.6 * u * (1 - t) + 0.2;
      for (let s = 0; s < 44 && t < 0.9; s++) {
        const a = (s / 44) * TAU;
        if (hash(s * 3 + b.number) > 0.55 + 0.45 * (1 - t)) continue;
        body.dome(x + Math.cos(a) * out, y + Math.sin(a) * out, thick + hash(s + b.number) * 1.6 * u * (1 - t));
      }
    } else if (b.kind === 'good') {
      // It slumps, and runs off down the glass.
      const sag = smooth(t) * 11 * u;
      bead(x, y + sag, r * (1 - 0.68 * smooth(t * 1.2)), u, b.number, 0.22 * t);
      body.line(x, y, x, y + sag, 3 * u, 2 * u);
    } else {
      // It doesn't go anywhere: it opens, and looks.
      const sag = t > 0.72 ? ((t - 0.72) / 0.28) ** 2 * 14 * u : 0;
      bead(x, y + sag, r * (1 - 0.3 * clamp((t - 0.72) / 0.28)), u, b.number, 0.02);
      eyes.push({ x, y: y + sag, size: r * 0.96, open: smooth(t * 4) * (t > 0.85 ? 1 - (t - 0.85) / 0.15 : 1) });
    }
  }
  moveBits(bits, dt, 26 * u, (b, k) => {
    // (Splashed on the glass: they fly, stick, and creep down.)
    if (b.kind === 0) {
      const drag = Math.exp(-7 * dt);
      b.vx *= drag;
      b.vy *= drag;
      if (Math.hypot(b.vx, b.vy) < 16 * u) b.vy = Math.max(b.vy, 5 + 16 * b.r * u);
    }
    const size = b.r * (k > 0.8 ? 1 - (k - 0.8) / 0.2 : 1);
    body.dome(b.x, b.y, size + 0.6, 1, 1.2);
    if (b.kind === 1) body.dome(b.x, b.y - size * 1.6, size * 0.7, 0.8);
  });
  // (Red coming up in it as a bead ripens: most of all, late.)
  lit = 0.02 + 0.3 * clamp((f.circles[0] ? 0.15 - f.circles[0].left : 0) * 3) + 0.08 * f.beat;
  body.shade(layer, shadeOoze, KEY);
  for (const e of eyes) setEye(e.x, e.y, e.size, e.open, f, 1);
  for (const p of glints) {
    if (p.r < 2 * u) continue;
    const size = Math.max(1, Math.round(p.r * 0.2));
    const gx = Math.round(p.x - p.r * 0.46);
    const gy = Math.round(p.y - p.r * 0.56);
    for (let j = 0; j < size; j++) for (let i = 0; i < size + 1; i++) layer.set(gx + i, gy + j, GLINT);
  }
  layer.flush(g);
  for (const c of f.circles) {
    const show = appear(c.left);
    if (show <= 0) continue;
    f.label(String(c.number), c.x, c.y + 0.5, r * 0.9, '#ffe8dc', show);
    if (f.teaching) f.label('CLICK', c.x, c.y + r * 2.25, r * 1.05, '#ffe8dc', 0.55 + 0.45 * Math.sin(now * 8));
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    if (b.kind === 'perfect') f.label(String(b.number), x, y + 0.5, r * (0.9 + 0.7 * t), '#fff4ec', 1 - t);
    else if (b.kind === 'good') f.label(String(b.number), x, y + smooth(t) * 11 * u + 0.5, r * 0.8, '#d88a88', 1 - t);
  }
  return bits.length > 0 || f.fade > 0;
}

export const ooze: RhythmLook = { id: 'b', name: 'BLACK OOZE', under, stare: almondEyes, over };
