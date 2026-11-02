import { CanvasTexture, SRGBColorSpace } from 'three';

// The chrome bike's dash (art/build-bike2.py Bike2Dash, UVs 0-1 across it from the rider's seat): as in the transition
// concept, a dark violet glass display with the speed in km/h on a sweeping gauge, and the blob logo glowing at its
// right. Drawn on a small canvas, redrawn only when the shown speed changes.

const W = 512;
const H = 170;

function blob(ctx: CanvasRenderingContext2D, x: number, y: number, r: number) {
  // Three soft lobes meeting in the middle, like the billboard's logo.
  ctx.save();
  ctx.translate(x, y);
  ctx.shadowColor = 'rgba(200, 150, 255, 0.9)';
  ctx.shadowBlur = 16;
  const g = ctx.createRadialGradient(0, 0, 2, 0, 0, r);
  g.addColorStop(0, 'rgba(255, 245, 255, 1)');
  g.addColorStop(1, 'rgba(190, 140, 255, 0.85)');
  ctx.fillStyle = g;
  for (let i = 0; i < 3; i++) {
    const a = -Math.PI / 2 + (i * Math.PI * 2) / 3;
    ctx.beginPath();
    ctx.ellipse(Math.cos(a) * r * 0.5, Math.sin(a) * r * 0.5, r * 0.36, r * 0.5, a + Math.PI / 2, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.3, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function dashDisplay() {
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d') as CanvasRenderingContext2D;
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  let shown = -1;

  const draw = (kmh: number) => {
    const v = Math.round(kmh);
    if (v === shown) return;
    shown = v;
    const bg = ctx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#2a1440');
    bg.addColorStop(1, '#120820');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);
    // The gauge: a sweep of ticks round the speed, lit up to it.
    const cx = W * 0.42;
    const cy = H * 1.05;
    for (let i = 0; i <= 40; i++) {
      const t = i / 40;
      const a = Math.PI * (1.08 + 0.84 * t);
      const lit = t <= v / 300;
      ctx.strokeStyle = lit ? 'rgba(235, 200, 255, 0.95)' : 'rgba(160, 110, 210, 0.3)';
      ctx.lineWidth = i % 5 === 0 ? 4 : 2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * 128, cy + Math.sin(a) * 128);
      ctx.lineTo(cx + Math.cos(a) * (i % 5 === 0 ? 112 : 118), cy + Math.sin(a) * (i % 5 === 0 ? 112 : 118));
      ctx.stroke();
    }
    ctx.textAlign = 'center';
    ctx.fillStyle = '#f6eaff';
    ctx.shadowColor = 'rgba(210, 160, 255, 0.9)';
    ctx.shadowBlur = 12;
    ctx.font = '600 68px ui-sans-serif, system-ui, sans-serif';
    ctx.fillText(String(v), cx, H * 0.7);
    ctx.shadowBlur = 0;
    ctx.font = '500 20px ui-sans-serif, system-ui, sans-serif';
    ctx.fillStyle = 'rgba(230, 210, 255, 0.8)';
    ctx.fillText('km/h', cx, H * 0.9);
    blob(ctx, W * 0.84, H * 0.5, 34);
    texture.needsUpdate = true;
  };
  draw(0);
  return { texture, draw };
}
