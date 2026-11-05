import { appear, type Bit, bayer, clamp, hex, layer, moveBits, noise, type RhythmFrame, type RhythmLook, RunWatch, ramp, ringAt, type Stare } from './shared';

// D: the burning brand. The sigil's being seared into the glass with a hot iron. Each point's the iron's head, black, its rim
// heating as a line of fire closes in on it, leaving the glass scorched behind it; on the beat the fire meets the rim, white-hot.
// Hit, it stamps, and sparks fly; good, it takes unevenly; miss, it's gone cold and smokes. The line's dragged on from the last
// point white-hot and cools through orange and red to a black scar with a little ash on it. The view's own edges char and burn
// in, a hot fringe creeping on as the run goes; on 666 the whole brand and the fringe flare up at once.
// Kept for the boss: nothing in here knows about the hive. It needs only a RhythmFrame and a quarter-resolution canvas (shared.ts).

const HEAT = ['#0c0604', '#2c0c06', '#701406', '#b82608', '#ee4c0c', '#ff8e14', '#ffd24a', '#fff8dc'].map((c) => hex(c));
const KEY = hex('#0a0504');
const CHAR = hex('#090504');
const CHAR_UP = hex('#1a0e0a');
const ASH = hex('#7a685a');
const IRON = ['#0e0908', '#221714', '#3c2c26', '#604a3e'].map((c) => hex(c));
const SOOT = hex('#120a07');
const SCORCH = hex('#3c2010');
const SMOKE = ['#2a2420', '#4a423c', '#6a6058'].map((c) => hex(c));

const TAU = Math.PI * 2;

const watch = new RunWatch();
const bits: Bit[] = [];
let sparkAt = 0;

const hot = (t: number, x: number, y: number) => ramp(HEAT, t, x, y);

/** The view's edges, charring in: black, a hot fringe where it's burning, a brown scorch ahead of that. */
function burnIn(f: RhythmFrame, reach: number, flare: number) {
  const { w, h, u, now } = f;
  const px = layer.px;
  const pulse = 0.5 + 0.5 * f.beat;
  const late = clamp(1 - f.gloom * 1.6);
  for (let y = 0; y < h; y++) {
    const row = y * w;
    for (let x = 0; x < w; x++) {
      // (Deeper along the top and sides than along the bottom, where the bike is.)
      // (And from the corners first: early on it's only got hold there, not ruled round the whole frame.)
      const corner = Math.abs(((x / w) * 2 - 1) * ((y / h) * 2 - 1));
      const e = Math.min(x, w - 1 - x, y * 1.1, (h - 1 - y) * 1.5) + (1 - corner) * 26 * u * late;
      if (e > reach + 22 * u) continue;
      const n = noise(x * 1.2 + 31, y * 1.2 + now * 1.4) * 0.72 + noise(x * 3.5, y * 3.5 - now * 0.6) * 0.28;
      const s = e + (n - 0.5) * Math.min(34 * u, 7 * u + reach * 1.3) - reach;
      if (s < 0) {
        // Burnt: black, with the embers still going in places, and a little more on the beat.
        const ember = noise(x * 4 + 9, y * 4 - now * 2);
        if (s > -6 * u && ember > 0.62) px[row + x] = hot(0.22 + 0.2 * pulse * (1 + flare), x, y);
        else if (flare > 0 && ember > 0.5 - flare * 0.25) px[row + x] = hot(0.3 + 0.55 * flare, x, y);
        else px[row + x] = s < -3 * u && ember > 0.55 ? CHAR_UP : CHAR;
      } else if (s < 1.3 * u) px[row + x] = hot(0.8 + 0.2 * flare - (0.1 * s) / u, x, y);
      else if (s < 2.6 * u) px[row + x] = hot(0.5 + 0.2 * flare, x, y);
      else if (s < 7 * u) {
        const k = 1 - (s - 2.6 * u) / (4.4 * u);
        if (bayer(x, y) < k * 0.8) px[row + x] = k > 0.5 ? SOOT : SCORCH;
      }
    }
  }
}

/** A round of the line laid at (x, y): radius rr, colour by how hot. */
function sear(x: number, y: number, rr: number, temp: number, seed: number, beat: number) {
  const top = Math.ceil(rr) + 1;
  const cx = Math.round(x);
  const cy = Math.round(y);
  for (let dy = -top; dy <= top; dy++) {
    for (let dx = -top; dx <= top; dx++) {
      const d = Math.hypot(dx, dy);
      if (d > rr + 0.4) continue;
      const qx = cx + dx;
      const qy = cy + dy;
      let c: number;
      if (temp > 0.08) c = hot(0.15 + 0.85 * temp * (1 - (0.25 * d) / (rr + 1)), qx, qy);
      // Cold: a black scar, ash along its top edge, an ember or two that the heart still stirs.
      else if (dy < -rr * 0.5 && noise(qx * 6 + seed, qy * 6) > 0.42) c = ASH;
      else if (noise(qx * 5 + seed, qy * 5) > 0.76) c = hot(0.3 + 0.28 * beat, qx, qy);
      else c = CHAR;
      layer.set(qx, qy, c);
    }
  }
}

function segment(f: RhythmFrame, i: number) {
  const a = f.points[(i - 1 + f.points.length) % f.points.length];
  const b = f.points[i % f.points.length];
  return { a, b, len: Math.hypot(b.x - a.x, b.y - a.y) || 1 };
}

function under(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { w, h, u, now, burn, gloom } = f;
  watch.update(f, (b) => {
    const x = b.x * w;
    const y = b.y * h;
    const n = b.kind === 'perfect' ? 40 : b.kind === 'good' ? 14 : 0;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * TAU;
      const v = (b.kind === 'perfect' ? 50 + Math.random() * 190 : 20 + Math.random() * 90) * u;
      bits.push({
        x: x + Math.cos(a) * f.r,
        y: y + Math.sin(a) * f.r,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - 40 * u,
        r: 1,
        age: 0,
        life: 0.35 + Math.random() * 0.6,
        kind: 0,
      });
    }
    if (b.kind === 'miss') {
      for (let i = 0; i < 12; i++) {
        bits.push({
          x: x + (Math.random() - 0.5) * f.r * 1.4,
          y: y + (Math.random() - 0.5) * f.r,
          vx: (Math.random() - 0.5) * 10 * u,
          vy: -(14 + Math.random() * 26) * u,
          r: (2.5 + Math.random() * 4) * u,
          age: 0,
          life: 0.7 + Math.random() * 0.6,
          kind: 1,
        });
      }
    }
  });
  const show = f.active || f.slow < 1 || burn > 0 || f.fade > 0;
  if (!show) return bits.length > 0;
  g.fillStyle = `rgba(16, 6, 3, ${(0.12 + 0.2 * gloom + 0.26 * (1 - f.slow)) * f.fade})`;
  g.fillRect(0, 0, w, h);
  layer.begin(w, h);
  // It flares and races in, on 666, then dies away out of the view.
  const flare = burn > 0 ? burn * burn : 0;
  const reach =
    ((0.5 + 34 * gloom + 4 * (1 - f.slow)) * u + (burn > 0 ? Math.sin(Math.min(1, (1 - burn) * 2.4) * Math.PI) * 0.34 * h : 0)) * (burn > 0 ? 1 : f.fade) -
    (1 - f.fade) * 22 * u;
  if (reach > -8 * u) burnIn(f, reach, flare);
  // Where it's going: the iron's marks, not yet burnt, a scorch in dots.
  const count = f.points.length;
  if (f.active) {
    for (let i = Math.max(1, f.landed); i <= count; i++) {
      if (i === count && !f.closed) break;
      const { a, b, len } = segment(f, i);
      const steps = Math.floor(len / (5 * u));
      for (let s = 1; s < steps; s++) {
        const t = s / steps;
        const x = Math.round(a.x + (b.x - a.x) * t);
        const y = Math.round(a.y + (b.y - a.y) * t);
        layer.set(x, y, CHAR);
        layer.set(x + 1, y, s % 2 ? ASH : CHAR);
      }
    }
  }
  for (let i = 1; i <= count; i++) {
    const closing = i === count;
    if (closing ? !f.closed || f.landed < count : i >= f.landed) continue;
    const at = watch.landedAt[closing ? count - 1 : i] ?? now;
    const hit = closing ? true : f.drawn[i] !== false;
    const { a, b, len } = segment(f, i);
    const age = now - at;
    const drag = 0.2;
    const head = Math.min(1, age / drag);
    const steps = Math.ceil(len / 1.4);
    for (let s = 0; s <= steps * head; s++) {
      const t = s / steps;
      const passed = age - t * drag;
      const x = a.x + (b.x - a.x) * t + (noise(t * 90 + i * 20, 5) - 0.5) * 1.6 * u;
      const y = a.y + (b.y - a.y) * t + (noise(t * 90 + i * 20, 25) - 0.5) * 1.6 * u;
      if (!hit) {
        // Missed: the iron skipped it: a dry smear, broken.
        if (Math.floor(t * 18) % 3 === 0) sear(x, y, 0.9 * u, 0, i * 3, 0);
        continue;
      }
      let temp = Math.exp(-passed / 0.75) * 1.05;
      // 666: all of it again, white-hot, and thicker.
      if (burn > 0) temp = Math.max(temp, burn ** 1.4);
      const rr = (1.5 + 0.9 * clamp(temp) + 1.2 * clamp(burn * 1.5) + 0.5 * (noise(t * 50 + i, 70) - 0.5)) * u * (temp > 0.08 ? 1 : 0.5 + 0.5 * f.fade);
      if (f.fade <= 0 && burn <= 0) continue;
      sear(x, y, rr, f.active || burn > 0 ? temp : temp * f.fade, i * 7, f.beat);
    }
    if (head < 1 && hit) {
      const x = a.x + (b.x - a.x) * head;
      const y = a.y + (b.y - a.y) * head;
      if (now - sparkAt > 0.02) {
        sparkAt = now;
        const ang = Math.random() * TAU;
        bits.push({ x, y, vx: Math.cos(ang) * 60 * u, vy: Math.sin(ang) * 60 * u - 30 * u, r: 1, age: 0, life: 0.4 + Math.random() * 0.3, kind: 0 });
      }
    }
  }
  // The brand's heads burnt in where they landed: a ring and its mark.
  for (let i = 0; i < f.landed; i++) {
    const age = now - (watch.landedAt[i] ?? now);
    if (age < 0.25 || f.fade <= 0) continue;
    const hit = f.drawn[i] !== false;
    if (!hit) continue;
    const p = f.points[i];
    const temp = Math.max(Math.exp(-age / 0.9) * 0.9, burn ** 1.4);
    const size = f.r * 0.62;
    const steps = Math.ceil((size * TAU) / 1.4);
    for (let s = 0; s < steps; s++) {
      const ang = (s / steps) * TAU;
      sear(p.x + Math.cos(ang) * size, p.y + Math.sin(ang) * size, 1.5 * u, temp * f.fade, i * 11, f.beat);
    }
    // (Six ticks out of it, and a dot in it: its own mark, the iron's.)
    sear(p.x, p.y, 2.2 * u, temp * f.fade, i * 13, f.beat);
    for (let k = 0; k < 6; k++) {
      const ang = (k / 6) * TAU;
      for (let s = 1; s <= 3; s++) {
        const d = size + s * 1.8 * u;
        sear(p.x + Math.cos(ang) * d, p.y + Math.sin(ang) * d, 0.9 * u, temp * f.fade, i * 13, f.beat);
      }
    }
  }
  layer.flush(g);
  return true;
}

/** The ring of fire: hard on its inside, its true edge, tongues licking out and up from that; soot left where it's been. */
function fireRing(f: RhythmFrame, x: number, y: number, ring: number, start: number, show: number, seed: number) {
  const { u, w, h, now } = f;
  const px = layer.px;
  const lick = 8 * u;
  const reach = Math.ceil(Math.max(ring + lick * 2, start) + 2);
  for (let py = Math.max(0, Math.round(y) - reach); py <= Math.min(h - 1, Math.round(y) + reach); py++) {
    const dy = py - y;
    for (let qx = Math.max(0, Math.round(x) - reach); qx <= Math.min(w - 1, Math.round(x) + reach); qx++) {
      const dx = qx - x;
      const d2 = dx * dx + dy * dy;
      if (d2 < (ring - 1.6 * u) * (ring - 1.6 * u)) continue;
      const d = Math.sqrt(d2);
      if (d < ring) {
        // A dark line just inside: it's what the fire's edge stands against on a bright sky.
        px[py * w + qx] = KEY;
        continue;
      }
      if (show < 1 && bayer(qx, py) > show) continue;
      const a = Math.atan2(dy, dx);
      // (Round the tile exactly once, so it meets itself; the tongues rising out of it as time goes.)
      const n = noise((a / TAU + 0.5) * 256 + seed * 13, now * 40 - d * 2.4);
      const up = Math.max(0, -dy / d);
      const tongue = (1.8 * u + lick * (n * n * 1.5) * (0.5 + 1.1 * up)) * (0.75 + 0.25 * f.beat);
      const q = (d - ring) / tongue;
      if (q < 1) px[py * w + qx] = hot(1.02 - q * 0.82 - (n < 0.3 ? 0.1 : 0), qx, py);
      // Soot where it's been: flecks, thinning away from it.
      else if (d < start && noise(qx * 11 + seed, py * 11) > 0.84 + 0.16 * ((d - ring) / (start - ring + 1))) px[py * w + qx] = SOOT;
    }
  }
}

/** The iron's head. `glow`: how hot, from its rim in; 0 cold. `cracked`: cold, split. */
function iron(f: RhythmFrame, x: number, y: number, glow: number, heat: number, cracked: number) {
  const { r, w, h, now } = f;
  const px = layer.px;
  const top = Math.ceil(r) + 1;
  const px1 = 1 / r;
  for (let py = Math.max(0, Math.round(y) - top); py <= Math.min(h - 1, Math.round(y) + top); py++) {
    const v = (py - y) / r;
    for (let qx = Math.max(0, Math.round(x) - top); qx <= Math.min(w - 1, Math.round(x) + top); qx++) {
      const a = (qx - x) / r;
      const rho = Math.sqrt(a * a + v * v);
      if (rho > 1) continue;
      const i = py * w + qx;
      if (rho > 1 - px1) {
        px[i] = glow > 0.5 ? hot(glow, qx, py) : KEY;
        continue;
      }
      // The heat coming in from the rim: what's hot's bright; the face stays black so the number can be read on it.
      const t = glow * (0.04 + rho ** 3.4 * 1.08) + (noise(qx * 3, py * 3 + now * 3) - 0.5) * 0.08 * glow;
      if (t > 0.2) {
        px[i] = hot(t, qx, py);
        continue;
      }
      // Forged: its two raised rings, its six pips, lit from up on the left.
      const ringed = (rho > 0.78 && rho < 0.84) || rho > 0.94;
      const angle = Math.atan2(v, a);
      const six = ((angle / TAU) * 6 + 6) % 1;
      const pip = rho > 0.84 && rho < 0.94 && Math.abs(six - 0.5) < 0.12;
      const lit = -a * 0.6 - v * 0.8;
      if (ringed || pip) px[i] = ramp(IRON, 0.5 + 0.55 * lit, qx, py);
      else px[i] = rho > 0.84 ? IRON[0] : bayer(qx, py) < 0.1 + 0.08 * (noise(qx * 5, py * 5) * 3) ? IRON[1] : IRON[0];
      if (cracked > 0 && Math.abs(a + Math.sin(v * 7 + heat * 9) * 0.1 + v * 0.24) < 0.035) px[i] = hex('#6a5a50');
    }
  }
}

function over(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { r, u, w, h, now, dt } = f;
  layer.begin(w, h);
  for (const c of [...f.circles].reverse()) {
    const show = appear(c.left);
    if (show <= 0) continue;
    const ring = ringAt(f, c.left);
    const start = ringAt(f, 1);
    const closed = clamp(1 - c.left);
    // Hot in step with the fire closing: dull red at half way, white on the beat, and held there, late.
    const glow = closed * closed * (1 + 0.04 * f.beat);
    fireRing(f, c.x, c.y, ring, start, show, c.number);
    iron(f, c.x, c.y, glow, c.point / 5, 0);
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    const heat = (b.number / 111 - 1) / 5;
    if (b.kind === 'perfect') {
      iron(f, x, y, Math.max(0, 1 - t * 1.4) * 1.1, heat, 0);
      // The stamp's shock: a hard ring of heat, out and cooling.
      const out = r * (1 + 1.7 * t);
      const thick = 2 * u * (1 - t) + 0.4;
      const steps = Math.ceil((out * TAU) / 1.2);
      for (let s = 0; s < steps; s++) {
        const a = (s / steps) * TAU;
        // (Breaking up as it goes, from its thin places.)
        if (noise(a * 40 + b.number, 4) < t * 0.9) continue;
        sear(x + Math.cos(a) * out, y + Math.sin(a) * out, thick, Math.max(0.28, 1.05 - t * 1.1), 0, 0);
      }
    } else if (b.kind === 'good') {
      // It takes on one side only.
      iron(f, x, y, Math.max(0, 0.72 - t), heat, 0);
      const out = r * (1 + 0.3 * t);
      for (let s = 0; s < 22; s++) {
        const a = (s / 22) * Math.PI * 1.1 + b.number + (noise(s * 7, b.number) - 0.5);
        sear(x + Math.cos(a) * out, y + Math.sin(a) * out, 1.6 * u * (1 - t) + 0.3, 0.62 * (1 - t) + 0.1, 0, 0);
      }
    } else {
      iron(f, x, y + 4 * u * t * t, 0, heat, 1);
    }
  }
  moveBits(bits, dt, 190 * u, (b, k) => {
    if (b.kind === 0) {
      // A spark: a white point going orange going out.
      const x = Math.round(b.x);
      const y = Math.round(b.y);
      const c = hot(1 - k * 0.8, x, y);
      layer.set(x, y, c);
      const px = Math.round(b.x - b.vx * 0.012);
      const py = Math.round(b.y - b.vy * 0.012);
      if (k < 0.6) layer.set(px, py, hot(0.72 - k, px, py));
    } else {
      // Smoke, going the other way: undo the gravity, and thin it out.
      b.vy -= 190 * u * dt + 14 * u * dt;
      const rr = b.r * (0.6 + k);
      const cx = Math.round(b.x);
      const cy = Math.round(b.y);
      const top = Math.ceil(rr);
      for (let dy = -top; dy <= top; dy++) {
        for (let dx = -top; dx <= top; dx++) {
          if (dx * dx + dy * dy > rr * rr) continue;
          if (bayer(cx + dx, cy + dy) > 0.95 - k * 0.9) continue;
          layer.set(cx + dx, cy + dy, SMOKE[dy < -rr * 0.3 ? 2 : dy < rr * 0.3 ? 1 : 0]);
        }
      }
    }
  });
  layer.flush(g);
  for (const c of f.circles) {
    const show = appear(c.left);
    if (show <= 0) continue;
    f.label(String(c.number), c.x, c.y + 0.5, r * 0.9, '#ffe8c0', show);
    if (f.teaching) f.label('CLICK', c.x, c.y + r * 2.55, r * 1.05, '#ffe8c0', 0.55 + 0.45 * Math.sin(now * 8));
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    if (b.kind === 'perfect') f.label(String(b.number), x, y + 0.5, r * (0.9 + 0.5 * t), t < 0.25 ? '#fffbe8' : '#ffb040', 1 - t);
    else if (b.kind === 'good') f.label(String(b.number), x, y + 0.5, r * 0.88, '#e8802c', 1 - t);
    else f.label(String(b.number), x, y + 0.5, r * 0.82, '#7a6a60', 1 - t * t);
  }
  return bits.length > 0 || f.fade > 0;
}

// Its eyes: burnt through the glass, black in the socket with a coal for an iris, the edge of the burn still going.
function stare(g: CanvasRenderingContext2D, f: RhythmFrame, eyes: Stare[]) {
  const { w, h, beat } = f;
  const px = layer.px;
  layer.begin(w, h);
  for (const e of eyes) {
    const c = Math.cos(e.tilt);
    const s = Math.sin(e.tilt);
    const d0 = Math.hypot(e.lookX - e.x, e.lookY - e.y) || 1;
    const ix = (((e.lookX - e.x) * c + (e.lookY - e.y) * s) / d0) * 0.34;
    const iy = ((-(e.lookX - e.x) * s + (e.lookY - e.y) * c) / d0) * 0.14;
    const span = Math.ceil(e.size) + 2;
    for (let py = Math.max(0, Math.round(e.y) - span); py <= Math.min(h - 1, Math.round(e.y) + span); py++) {
      for (let qx = Math.max(0, Math.round(e.x) - span); qx <= Math.min(w - 1, Math.round(e.x) + span); qx++) {
        const a = ((qx - e.x) * c + (py - e.y) * s) / e.size;
        const v = (-(qx - e.x) * s + (py - e.y) * c) / e.size;
        if (Math.abs(a) > 1.05) continue;
        const lid = 0.62 * e.open * (1 - a * a) + 0.02;
        const out = Math.abs(v) - lid;
        const edge = 1.6 / e.size;
        if (out > edge * 1.8) continue;
        const i = py * w + qx;
        if (out > edge) px[i] = KEY;
        else if (out > 0) px[i] = hot(0.5 + 0.3 * beat + (noise(qx * 5, py * 5 + f.now * 4) - 0.5) * 0.5, qx, py);
        else {
          const rho = Math.hypot(a - ix, (v - iy) * 1.1);
          if (rho < 0.13) px[i] = KEY;
          else if (rho < 0.5) px[i] = hot(0.98 - rho * 1.3 + 0.08 * beat, qx, py);
          else px[i] = noise(qx * 7, py * 7) > 0.74 ? HEAT[1] : CHAR;
        }
      }
    }
  }
  layer.flush(g);
}

export const brand: RhythmLook = { id: 'd', name: 'BURNING BRAND', under, stare, over };
