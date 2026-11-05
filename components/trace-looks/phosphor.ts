import { TRACE } from '@/lib/trace';
import { hash, PIXEL, pixelLine, plate, prompt, type TraceFrame, type TraceLook } from './shared';

// C: phosphor. The view's a scope: a green beam with a square dot on the end, quantised to a coarse stepped grid, its trace
// decaying down through hard shades of green as phosphor does; a graticule over the view, scanlines through all of it, the odd
// retrace flicker. It builds as a signal: a small window beside the dot, the wave in it growing and quickening. Off the point
// the beam goes orange; lost, the tube collapses to a flat line and out. Round the view, the world goes to green on a tube's
// rounded mask, a refresh bar rolling up it.

const GRID = 3;
const SHADES = ['#eafff0', '#8dffa0', '#37e866', '#17a544', '#0c6a2c'];
const OFF = ['#fff0e0', '#ffae70', '#ff7a38', '#d84e20', '#8a2c10'];
const BACK = 'rgba(0, 12, 4, 0.8)';

const snap = (v: number) => Math.round(v / GRID) * GRID;

function graticule(g: CanvasRenderingContext2D, f: TraceFrame) {
  const strength = Math.max(f.surge, f.teaching ? 0.6 : 0);
  if (strength < 0.02) return;
  const xs = Math.round(f.w / 10);
  const ys = Math.round(f.h / 8);
  g.globalAlpha = 0.55 * Math.min(1, strength * 1.5);
  g.fillStyle = '#7dff9a';
  g.beginPath();
  for (let i = 1; i < 10; i++) for (let y = 0; y < f.h; y += 4) g.rect(i * xs, y, 1, 1);
  for (let i = 1; i < 8; i++) for (let x = 0; x < f.w; x += 4) g.rect(x, i * ys, 1, 1);
  // (Ticks down the middle axes.)
  const mx = 5 * xs;
  const my = 4 * ys;
  for (let i = 0; i < f.w; i += Math.round(xs / 5)) g.rect(i, my - 1, 1, 3);
  for (let i = 0; i < f.h; i += Math.round(ys / 5)) g.rect(mx - 1, i, 3, 1);
  g.fill();
  g.globalAlpha = 1;
}

function draw(g: CanvasRenderingContext2D, f: TraceFrame) {
  graticule(g, f);
  const list = f.trail;
  const off = f.active && !f.on;
  const shades = off ? OFF : SHADES;
  // A few frames in every so many the beam's retracing: its trace dims, the return line shows.
  const frame = Math.floor(f.now * 30);
  const retrace = hash(frame) < 0.05;
  const flicker = (retrace ? 0.55 : 0.88 + 0.12 * hash(frame + 9)) * f.fade;
  const jog = retrace ? GRID : 0;

  // The trace, stepped: each move across then down on the grid, in bands of shade by age.
  const bands: [number, number, number, number][][] = [[], [], [], [], []];
  const under: [number, number, number, number][] = [];
  let ax = 0;
  let ay = 0;
  for (let i = 0; i < list.length; i++) {
    const x = snap(list[i].x / PIXEL) + jog;
    const y = snap(list[i].y / PIXEL);
    if (i > 0 && (x !== ax || y !== ay)) {
      const life = 1 - list[i].age / TRACE.trail;
      if (life > 0) {
        const k = Math.min(4, Math.floor((1 - life) ** 1.2 * 5));
        const thick = k < 1 ? 3 : k < 3 ? 2 : 1;
        const across: [number, number, number, number] = [Math.min(ax, x), ay, Math.abs(x - ax) + thick, thick];
        const down: [number, number, number, number] = [x, Math.min(ay, y), thick, Math.abs(y - ay) + thick];
        bands[k].push(across, down);
        if (k < 4) under.push(across, down);
      }
    }
    ax = x;
    ay = y;
  }
  g.globalAlpha = f.fade;
  g.fillStyle = BACK;
  g.beginPath();
  for (const [x, y, w, h] of under) g.rect(x - 1, y - 1, w + 2, h + 2);
  g.fill();
  g.globalAlpha = flicker;
  for (let k = 4; k >= 0; k--) {
    g.fillStyle = shades[k];
    g.beginPath();
    for (const [x, y, w, h] of bands[k]) g.rect(x, y, w, h);
    g.fill();
  }
  g.globalAlpha = 1;
  if (retrace && f.active && list.length > 1) {
    g.fillStyle = shades[3];
    g.beginPath();
    pixelLine(g, f.x, f.y, list[0].x / PIXEL, list[0].y / PIXEL, 3);
    g.fill();
  }

  if (f.active) {
    const x = snap(f.x);
    const y = snap(f.y);
    const size = 3 + Math.round(f.built * 2);
    // Its persistence: hard steps out from the dot, not a soft glow.
    g.fillStyle = off ? 'rgba(255, 110, 40, 0.24)' : 'rgba(70, 255, 120, 0.26)';
    g.fillRect(x - size - 8, y - size - 8, size * 2 + 17, size * 2 + 17);
    g.fillStyle = off ? 'rgba(255, 110, 40, 0.42)' : 'rgba(70, 255, 120, 0.46)';
    g.fillRect(x - size - 4, y - size - 4, size * 2 + 9, size * 2 + 9);
    g.fillStyle = BACK;
    g.fillRect(x - size - 1, y - size - 1, size * 2 + 3, size * 2 + 3);
    g.fillStyle = shades[0];
    g.fillRect(x - size, y - size, size * 2 + 1, size * 2 + 1);
    g.fillStyle = shades[1];
    g.fillRect(x - size - 13, y, 9, 1);
    g.fillRect(x + size + 5, y, 9, 1);
    g.fillRect(x, y - size - 13, 1, 9);
    g.fillRect(x, y + size + 5, 1, 9);

    // How far it's built: a small scope window by the dot, its wave growing and quickening.
    const W = 58;
    const H = 26;
    const right = x + 20 + W < f.w - 4;
    const wx = right ? x + 18 : x - 18 - W;
    const wy = Math.max(4, Math.min(f.h - H - 4, y + 10));
    plate(g, f, [`CH1 ${String(Math.round(f.built * 100)).padStart(3, '0')}%`], wx, wy, shades[1], 'rgba(0, 14, 5, 0.86)');
    g.fillStyle = 'rgba(0, 14, 5, 0.86)';
    g.fillRect(wx, wy + 13, W - 5, 13);
    const mid = wy + 19;
    g.fillStyle = shades[1];
    g.beginPath();
    let py = mid;
    for (let i = 0; i < W - 9; i++) {
      const v = mid + Math.round(Math.sin(i * (0.22 + 0.42 * f.built) - f.now * 12) * (0.6 + 5 * f.built));
      g.rect(wx + 2 + i, Math.min(py, v), 1, Math.abs(v - py) + 1);
      py = v;
    }
    g.fill();
    if (f.teaching) prompt(g, f, f.on ? 'STAY ON THE BEAM' : 'NO SIGNAL. HOLD ON THE DOT', size + 34, shades[0], 'rgba(0, 14, 5, 0.86)');
  } else if (f.lost && f.fade > 0) {
    // The tube collapsing: a flash, a flat line across the view, drawn in to nothing.
    const t = 1 - f.fade;
    const half = f.w * 0.5 * (1 - t) ** 2;
    const y = Math.round(f.y);
    const thick = t < 0.2 ? 5 : t < 0.5 ? 3 : 1;
    g.fillStyle = BACK;
    g.fillRect(f.w / 2 - half - 1, y - 2, half * 2 + 2, thick + 4);
    g.fillStyle = OFF[t < 0.3 ? 0 : 1];
    g.fillRect(f.w / 2 - half, y, half * 2, thick);
    plate(g, f, ['NO SIGNAL'], f.w / 2 - 30, y + 10, OFF[1], 'rgba(0, 14, 5, 0.86)');
  }

  // Scanlines, through everything just drawn.
  g.globalCompositeOperation = 'destination-out';
  g.fillStyle = 'rgba(0, 0, 0, 0.3)';
  g.beginPath();
  for (let y = 0; y < f.h; y += 2) g.rect(0, y, f.w, 1);
  g.fill();
  g.globalCompositeOperation = 'source-over';
  return false;
}

// Round the view: the picture dims so the beam can carry, and goes to dark green phosphor toward the rim of a rounded tube,
// scanlined, a slow refresh bar rolling up through it.
const edge = /* glsl */ `
vec3 edgeC(vec2 uv, vec2 toward, vec3 c) {
  float aspect = resolution.x / resolution.y;
  float grow = smoothstep(0.0, 0.5, surge);
  vec2 a = abs(uv - 0.5) * 2.0 * vec2(aspect, 1.0);
  vec2 box = a - vec2(aspect, 1.0) + 0.3;
  float tube = length(max(box, 0.0)) + min(max(box.x, box.y), 0.0) - 0.3;
  float lum = dot(c, vec3(0.3, 0.55, 0.15));
  vec3 green = vec3(0.07, 1.0, 0.25) * (0.012 + pow(lum, 1.7) * 0.75);
  float rim = smoothstep(-0.5, -0.06, tube) * grow;
  vec3 o = mix(c * (1.0 - 0.32 * grow), green, rim);
  float row = uv.y * resolution.y;
  o *= 1.0 - 0.45 * rim * step(0.5, fract(row * 0.5));
  o *= 1.0 + 0.6 * rim * step(fract(uv.y * 0.9 - time * 0.2), 0.05);
  return mix(o, vec3(0.003, 0.008, 0.004), step(0.0, tube + (1.0 - grow) * 0.2 - 0.01 * grow) * grow);
}`;

export const phosphor: TraceLook = { id: 'c', name: 'PHOSPHOR', bloom: { threshold: 0, intensity: 0.06 }, accent: '#37e866', edge, draw };
