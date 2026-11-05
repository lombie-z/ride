import { TRACE } from '@/lib/trace';
import { hash, PIXEL, pixelDisc, prompt, type TraceFrame, type TraceLook } from './shared';

// A: mercury. The point's a bead of liquid chrome with the sunset's horizon in it; behind it a thread of the same stuff,
// necking and breaking into droplets that sag and fall. It builds by taking up more beads, a ring of them round it. Off the
// point the reflection goes oxide red; lost, the bead bursts. Round the view, mercury pools in from the edges of the glass.

type Palette = { sky: string; glow: string; line: string; low: string; warm: string; key: string };
const SUNSET: Palette = { sky: '#fff6e8', glow: '#ffc49c', line: '#1d1826', low: '#57465a', warm: '#f58a58', key: 'rgba(12, 9, 16, 0.92)' };
const OXIDE: Palette = { sky: '#ffb09a', glow: '#e0432c', line: '#190406', low: '#5c0f12', warm: '#a81f1a', key: 'rgba(16, 3, 4, 0.95)' };

/** What a chrome ball shows at height v down it (-1 to 1): sky, a hard dark horizon, the ground lit warm from under. */
function band(p: Palette, v: number) {
  if (v < -0.58) return p.sky;
  if (v < -0.12) return p.glow;
  if (v < 0.1) return p.line;
  if (v < 0.5) return p.low;
  return p.warm;
}

function bead(g: CanvasRenderingContext2D, x: number, y: number, R: number, p: Palette, wobble: number) {
  const ax = 1 + wobble;
  const ay = 1 - wobble;
  const cx = Math.round(x);
  const cy = Math.round(y);
  const top = Math.ceil(R * ay) + 1;
  const side = Math.ceil(R * ax) + 1;
  g.fillStyle = p.key;
  g.beginPath();
  for (let dy = -top; dy <= top; dy++) {
    const span = Math.floor(Math.sqrt(Math.max(0, 1 - (dy / (R * ay + 1.2)) ** 2)) * (R * ax + 1.2));
    if (Math.abs(dy) <= R * ay + 1.2) g.rect(cx - span, cy + dy, span * 2 + 1, 1);
  }
  g.fill();
  for (let dy = -top; dy <= top; dy++) {
    for (let dx = -side; dx <= side; dx++) {
      const u = dx / (R * ax);
      const v = dy / (R * ay);
      const d = u * u + v * v;
      if (d > 1) continue;
      // (The bands bow, as they do on a ball; its rim goes dark, which is what makes it round.)
      g.fillStyle = d > 0.8 && v > -0.3 ? p.line : band(p, v - 0.32 * u * u);
      g.fillRect(cx + dx, cy + dy, 1, 1);
    }
  }
  g.fillStyle = '#ffffff';
  const hi = Math.max(1, Math.round(R * 0.28));
  g.fillRect(cx - Math.round(R * 0.42), cy - Math.round(R * 0.58), hi + 1, hi);
}

type Stamp = { x: number; y: number; r: number };
const stamps: Stamp[] = [];

/** The thread and its droplets as discs: run together in layers, from the keyline in, they merge like a liquid. */
function layStamps(g: CanvasRenderingContext2D, p: Palette, alpha: number) {
  g.globalAlpha = alpha;
  g.fillStyle = p.key;
  g.beginPath();
  for (const s of stamps) pixelDisc(g, s.x, s.y, s.r + 1);
  g.fill();
  g.fillStyle = p.warm;
  g.beginPath();
  for (const s of stamps) if (s.r > 1.4) pixelDisc(g, s.x, s.y + s.r * 0.15, s.r);
  g.fill();
  g.fillStyle = p.line;
  g.beginPath();
  for (const s of stamps) if (s.r > 1.4) pixelDisc(g, s.x, s.y - s.r * 0.1, s.r * 0.66);
  g.fill();
  g.fillStyle = p.sky;
  g.beginPath();
  for (const s of stamps) pixelDisc(g, s.x, s.y - s.r * 0.46, s.r > 1.4 ? s.r * 0.46 : s.r * 0.5);
  g.fill();
  g.globalAlpha = 1;
}

type Drop = { x: number; y: number; vx: number; vy: number; r: number; age: number; life: number };
const drops: Drop[] = [];
let was = false;
let lastX = 0;
let lastY = 0;

function draw(g: CanvasRenderingContext2D, f: TraceFrame) {
  const list = f.trail;
  const p = (f.active && !f.on) || (!f.active && f.lost) ? OXIDE : SUNSET;
  const R = 8 + 4 * f.built;
  // Over: the bead goes. Burst, lost; let go, it just falls.
  if (was && !f.active) {
    const n = f.lost ? 18 : 3;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = f.lost ? 30 + Math.random() * 110 : 8 + Math.random() * 16;
      drops.push({
        x: f.x,
        y: f.y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - (f.lost ? 30 : 0),
        r: f.lost ? 1 + Math.random() * 2.6 : R * (0.6 - i * 0.14),
        age: 0,
        life: 0.5 + Math.random() * 0.5,
      });
    }
  }
  was = f.active;

  stamps.length = 0;
  for (let i = 1; i < list.length; i++) {
    const a = list[i - 1];
    const b = list[i];
    const steps = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / PIXEL / 1.4));
    for (let j = 0; j < steps; j++) {
      const t = j / steps;
      const age = (a.age + (b.age - a.age) * t) / TRACE.trail;
      if (age >= 1) continue;
      const s = (a.s + (b.s - a.s) * t) / PIXEL;
      // Stable along the way it was laid: each stretch of it has its own droplet, in its own place.
      const spacing = 19;
      const cell = Math.floor(s / spacing);
      const h = hash(cell);
      const at = s / spacing - cell;
      const size = (1.1 + 2 * h) * (1 + 0.55 * f.built);
      const inCell = 0.5 + (h - 0.5) * 0.4;
      const bulge = Math.max(0, 1 - ((at - inCell) * spacing) ** 2 / (size * size));
      const dropR = size * Math.sqrt(bulge);
      // The thread necks and breaks a little way back, leaving the droplets.
      const broken = Math.min(1, Math.max(0, (age - 0.1 - 0.16 * hash(cell + 40)) / 0.14));
      const thread = (1.5 + f.built) * (1 - age * 0.5) * (1 - broken);
      const shrink = Math.min(1, (1 - age) / 0.3);
      const seconds = age * TRACE.trail;
      const r = Math.max(thread, dropR * Math.min(1, age / 0.08 + 0.35)) * shrink;
      if (r < 0.45) continue;
      stamps.push({
        x: (a.x + (b.x - a.x) * t) / PIXEL,
        y: (a.y + (b.y - a.y) * t) / PIXEL + seconds * seconds * (3 + 15 * h * broken),
        r,
      });
    }
  }
  layStamps(g, p, f.fade);

  if (f.active) {
    // A tear behind it as it runs.
    const vx = f.x - lastX;
    const vy = f.y - lastY;
    const speed = Math.hypot(vx, vy) || 1;
    const stretch = Math.min(1.1, speed / 4);
    stamps.length = 0;
    for (let i = 3; i >= 1; i--) {
      const k = i / 3;
      stamps.push({ x: f.x - (vx / speed) * R * stretch * 1.3 * k, y: f.y - (vy / speed) * R * stretch * 1.3 * k, r: R * (1 - 0.55 * k) });
    }
    layStamps(g, p, 1);
    bead(g, f.x, f.y, R, p, 0.07 * Math.sin(f.now * 11) * (f.on ? 1 : 2.5));
    // How far it's built: the ring of beads it's taken up. Its empty places are just marked.
    const count = 12;
    const ring = R + 7;
    const full = f.built * count;
    for (let i = 0; i < count; i++) {
      const a = -Math.PI / 2 + (i / count) * Math.PI * 2 + f.now * 0.5;
      const bx = f.x + Math.cos(a) * ring;
      const by = f.y + Math.sin(a) * ring;
      const taken = Math.min(1, Math.max(0, full - i));
      if (taken <= 0) {
        g.fillStyle = p.key;
        g.fillRect(Math.round(bx), Math.round(by), 1, 1);
        continue;
      }
      stamps.length = 0;
      stamps.push({ x: bx, y: by, r: 0.8 + 1 * taken });
      layStamps(g, p, 1);
    }
    if (f.teaching) prompt(g, f, f.on ? 'STAY ON THE BEAD' : 'HOLD ON THE BEAD', ring + 6, f.on ? SUNSET.sky : OXIDE.sky);
  }
  lastX = f.x;
  lastY = f.y;

  stamps.length = 0;
  for (let i = drops.length - 1; i >= 0; i--) {
    const d = drops[i];
    d.age += f.dt;
    if (d.age > d.life) {
      drops.splice(i, 1);
      continue;
    }
    d.vy += 260 * f.dt;
    d.x += d.vx * f.dt;
    d.y += d.vy * f.dt;
    stamps.push({ x: d.x, y: d.y, r: d.r * (1 - 0.5 * (d.age / d.life)) });
  }
  if (stamps.length) layStamps(g, f.lost ? OXIDE : SUNSET, 1);
  return drops.length > 0;
}

// Round the view: mercury running on the glass. It pools in the corners and along the bottom, and runs down from the top in
// drips the longer it's built; mostly dark in its surface, as chrome is, with the real scene and a hard sunset horizon sliding
// over it, and a keyline and a little shadow where it meets the view.
const edge = /* glsl */ `
float mercuryDrip(vec2 p, float reach) {
  float cells = 6.0;
  float at = floor(p.x * cells);
  float best = -1.0;
  for (int i = -1; i <= 1; i++) {
    float id = at + float(i);
    float a = hash21(vec2(id, 2.3));
    if (a < 0.58) continue;
    float b = hash21(vec2(id, 7.1));
    float c = hash21(vec2(id, 4.9));
    float x = (id + 0.25 + 0.5 * b) / cells;
    float len = reach * (1.2 + 3.0 * c) * (0.9 + 0.1 * sin(time * 0.6 + id * 2.1));
    float r = (0.008 + 0.012 * b) * min(1.0, reach / 0.03);
    // Down from the top, thin, to a round bulb at its end.
    float down = 1.0 - p.y;
    float y = clamp(down, 0.0, len);
    float width = mix(r * 0.7, r * 1.25, smoothstep(len * 0.5, len, y));
    best = max(best, width - length(vec2(p.x - x, down - y)));
  }
  return best;
}
float mercuryHeight(vec2 uv, float reach) {
  float aspect = resolution.x / resolution.y;
  vec2 e = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
  vec2 p = uv * vec2(aspect, 1.0);
  float wander = noise(p * 5.0 + vec2(time * 0.2, -time * 0.14));
  // Pools in the corners: the two edges run together with a wide radius.
  float corner = -0.09 * log(exp(-e.x / 0.09) + exp(-e.y / 0.09));
  float pools = reach * (0.3 + 0.9 * wander) - corner - 0.06;
  // A broken lip round the view, thickest along the bottom where it runs to.
  float lip = reach * (-0.25 + 0.9 * wander) - min(min(e.x, 1.0 - uv.y), uv.y * 0.6);
  // (All of it drawn back past the edge of the glass as the surge runs out: it drains away rather than being switched off.)
  return max(max(pools, lip), mercuryDrip(p, reach)) - 0.03 * (1.0 - smoothstep(0.0, 0.35, surge));
}
vec3 edgeA(vec2 uv, vec2 toward, vec3 c) {
  float reach = (0.016 + 0.06 * surge) * smoothstep(0.0, 0.35, surge);
  float h = mercuryHeight(uv, reach);
  if (h < -0.016) return c;
  if (h < 0.0) return c * (1.0 - 0.55 * smoothstep(-0.016, 0.0, h));
  float aspect = resolution.x / resolution.y;
  vec2 eps = 3.0 / resolution;
  vec2 grad = vec2(mercuryHeight(uv + vec2(eps.x, 0.0), reach) - h, mercuryHeight(uv + vec2(0.0, eps.y), reach) - h) / vec2(eps.x / aspect, eps.y);
  vec2 q = uv * vec2(aspect, 1.0);
  vec2 ripple = vec2(noise(q * 9.0 + time * 0.3), noise(q * 9.0 + 5.0 - time * 0.24)) - 0.5;
  vec3 n = normalize(vec3(grad * 1.6 * (1.0 - smoothstep(0.0, 0.04, h)) + ripple * 1.1, 1.0));
  vec3 r = reflect(vec3(0.0, 0.0, -1.0), n);
  // Mostly the view itself, mirrored and bent in it, with a chrome ball's hard black horizon and a pale sky laid over that.
  float v = r.y * 0.5 + 0.5 + r.x * 0.3;
  vec3 sky = mix(vec3(1.0, 0.5, 0.3), vec3(1.0, 0.92, 0.8), smoothstep(0.5, 0.8, v));
  vec3 ground = mix(vec3(0.012, 0.01, 0.02), vec3(0.7, 0.2, 0.09), smoothstep(0.44, 0.26, v));
  vec3 env = v > 0.5 ? sky : ground;
  vec3 scene = texture2D(inputBuffer, clamp(uv + r.xy * vec2(-0.3, 0.3), 0.0, 1.0)).rgb;
  vec3 metal = mix(env, scene * scene * 1.25, 0.55 * smoothstep(0.0, 0.02, h)) + vec3(1.0, 0.97, 0.92) * pow(max(0.0, dot(n, normalize(vec3(-0.25, 0.55, 0.8)))), 90.0) * 1.6;
  // (The dark line where it starts is what makes it a body on the glass rather than a tint.)
  return mix(vec3(0.01), metal, smoothstep(0.003, 0.01, h));
}`;

export const mercury: TraceLook = { id: 'a', name: 'MERCURY', bloom: { threshold: 0.08, intensity: 0.14 }, accent: '#ffc49c', edge, draw };
