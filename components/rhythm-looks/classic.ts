import { almondEyes, type RhythmFrame, type RhythmLook } from './shared';

// 0: as it was. A flat dark disc with a hot rim and eyes in its ring, a thin straight sigil, a broken halo closing in, a red
// vignette; gold at 111 turning to blood by 666. Up against the others until one's chosen.

const MISS = '#ff2238';
const GOLD = [255, 190, 70];
const BLOOD = [255, 24, 40];

const mix = (t: number) => GOLD.map((a, i) => Math.round(a + (BLOOD[i] - a) * t));
const css = (c: number[], a = 1) => `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`;

/** The sigil's line through its points, as far as `n` of them. */
function sigilPath(g: CanvasRenderingContext2D, f: RhythmFrame, n: number) {
  g.beginPath();
  for (let i = 0; i < n; i++) {
    const p = f.points[i];
    if (i === 0) g.moveTo(p.x, p.y);
    else g.lineTo(p.x, p.y);
  }
  if (n === f.points.length && f.closed) g.closePath();
}

function under(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { w, h, unit, landed } = f;
  // The view darkens as the run goes on, toward red at the edges; to a stop, more.
  const dread = f.active ? landed / f.points.length : 0;
  if (f.active || f.slow < 1) {
    const v = g.createRadialGradient(w / 2, h * 0.42, unit * 0.2, w / 2, h * 0.42, Math.max(w, h) * 0.72);
    v.addColorStop(0, `rgba(10, 2, 2, ${0.12 + 0.3 * (1 - f.slow)})`);
    v.addColorStop(1, `rgba(${40 + 90 * dread}, 2, 4, ${0.5 + 0.3 * dread})`);
    g.fillStyle = v;
    g.fillRect(0, 0, w, h);
  }
  // The sigil, as far as it's been drawn, and a faint guide to where it's going.
  if (f.active) {
    g.strokeStyle = css(mix(dread), 0.16);
    g.lineWidth = 1;
    sigilPath(g, f, f.points.length);
    g.stroke();
    if (landed > 0) {
      g.strokeStyle = css(mix(dread), 0.9);
      g.lineWidth = 1.5;
      sigilPath(g, f, landed);
      g.stroke();
    }
  }
  return false;
}

function over(g: CanvasRenderingContext2D, f: RhythmFrame) {
  const { r, now, w, h } = f;
  // The next to land last, on top.
  for (const c of [...f.circles].reverse()) {
    const { x, y, left } = c;
    const ink = mix((c.number / 111 - 1) / 5);
    g.globalAlpha = Math.min(1, Math.max(0, (1 - left) * 4));
    // Its wheel: a dark disc, a hot rim, ticks turning round it and eyes in the ring.
    g.fillStyle = 'rgba(6, 2, 2, 0.86)';
    g.beginPath();
    g.arc(x, y, r, 0, Math.PI * 2);
    g.fill();
    g.lineWidth = Math.max(1.5, r * 0.11);
    g.strokeStyle = css(ink);
    g.beginPath();
    g.arc(x, y, r, 0, Math.PI * 2);
    g.stroke();
    for (let i = 0; i < 6; i++) {
      const a = now * 0.9 + (i * Math.PI) / 3;
      const ex = x + Math.cos(a) * r;
      const ey = y + Math.sin(a) * r;
      g.fillStyle = '#fff4d8';
      g.beginPath();
      g.ellipse(ex, ey, r * 0.24, r * 0.15, a + Math.PI / 2, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = '#100404';
      g.beginPath();
      g.arc(ex, ey, r * 0.1, 0, Math.PI * 2);
      g.fill();
    }
    // The ring closing on it: a broken halo, turning the other way.
    const ring = r * (1 + 1.9 * Math.max(0, left));
    g.lineWidth = Math.max(1.5, r * 0.09);
    g.strokeStyle = css(ink, 0.95);
    for (let i = 0; i < 3; i++) {
      const a = -now * 1.4 + (i * Math.PI * 2) / 3;
      g.beginPath();
      g.arc(x, y, ring, a, a + Math.PI * 0.52);
      g.stroke();
    }
    f.label(String(c.number), x, y + 0.5, r * 0.9, '#fff4d8', g.globalAlpha);
    // Showing what's wanted: the word, pulsing.
    if (f.teaching) f.label('CLICK', x, y + r * 2.05, r * 1.05, '#fff4d8', 0.55 + 0.45 * Math.sin(now * 8));
    g.globalAlpha = 1;
  }
  for (const b of f.bursts) {
    const x = b.x * w;
    const y = b.y * h;
    const t = b.age / 0.6;
    const ink = mix((b.number / 111 - 1) / 5);
    g.globalAlpha = 1 - t;
    if (b.kind === 'miss') {
      g.strokeStyle = MISS;
      g.lineWidth = Math.max(2, r * 0.2);
      const k = r * 0.55;
      g.beginPath();
      g.moveTo(x - k, y - k);
      g.lineTo(x + k, y + k);
      g.moveTo(x + k, y - k);
      g.lineTo(x - k, y + k);
      g.stroke();
    } else {
      g.strokeStyle = b.kind === 'perfect' ? '#fff4d8' : css(ink);
      g.lineWidth = Math.max(1.5, r * 0.26 * (1 - t));
      g.beginPath();
      g.arc(x, y, r * (1 + 1.3 * t), 0, Math.PI * 2);
      g.stroke();
      f.label(String(b.number), x, y + 0.5, r * (0.9 + 0.5 * t), css(ink), 1 - t);
    }
  }
  g.globalAlpha = 1;
  // 666: the flash.
  if (f.burn > 0) {
    const b = f.burn;
    g.fillStyle = `rgba(255, ${Math.round(40 + 70 * b * b)}, ${Math.round(30 + 40 * b * b)}, ${0.75 * b * b})`;
    g.fillRect(0, 0, w, h);
  }
  return false;
}

export const classic: RhythmLook = { id: '0', name: 'AS IT WAS', under, stare: almondEyes, over };
