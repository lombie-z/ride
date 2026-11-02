'use client';

import { useEffect, useRef } from 'react';
import { journey, smoothstep } from '@/lib/journey';

// The way in: a black cinema ticket in the top right, printed in phosphor green, the film struck out and "Scroll to
// enter" scrawled over it in green paint marker. As you scroll through the pre-roll (the pixel sweep, lib/journey.ts PRE_ROLL) its stub tears off, drops into
// the oncoming wave and breaks up into pixels; the rest of the ticket goes to pixels as the wave reaches the corner.
// Drawn on its own small canvas so it can pixelate like the scene.

const W = 300; // CSS px
const H = 136;
const STUB = 70; // the stub's width, on the right
const BAND = 22; // the white brand band along the foot
const PAD = 80; // room round the ticket for the stub to tumble into
const CELL = 4; // the scene's pixel size (lib/journey.ts pixelSize)

const STOCK = '#0c0f0d';
const INK = 'rgba(128, 255, 112, 0.88)';
const MARKER = '#a4ff5c';

function hash(x: number, y: number) {
  const h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return h - Math.floor(h);
}

function seeded(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Fonts = { print: string; marker: string; band: string };

/** The ticket's outline: one side of the torn edge, slightly ragged all round like worn card. */
function outline(ctx: CanvasRenderingContext2D, part: 'body' | 'stub') {
  const tear = W - STUB;
  const wobble = (i: number, k: number) => (hash(i, k) - 0.5) * 0.9;
  const edge: [number, number][] = [];
  for (let y = 0; y <= H; y += 3) edge.push([tear + (hash(y, 1) - 0.5) * 4 + (hash(y, 2) > 0.85 ? 2 : 0), y]);
  const [x0, x1] = part === 'body' ? [0, tear] : [tear, W];
  ctx.beginPath();
  ctx.moveTo(x0, 0);
  for (let x = x0; x <= x1; x += 6) ctx.lineTo(x, wobble(x, 4));
  if (part === 'body') for (const [x, y] of edge) ctx.lineTo(x, y);
  else for (let y = 0; y <= H; y += 6) ctx.lineTo(W + wobble(y, 5), y);
  for (let x = x1; x >= x0; x -= 6) ctx.lineTo(x, H + wobble(x, 6));
  if (part === 'body') for (let y = H; y >= 0; y -= 6) ctx.lineTo(wobble(y, 7), y);
  else for (const [x, y] of [...edge].reverse()) ctx.lineTo(x, y);
  ctx.closePath();
}

/** The thermal print: the programme, the seat, and the stub's copy of it. */
function printText(ctx: CanvasRenderingContext2D, fonts: Fonts) {
  const now = new Date();
  const two = (n: number) => String(n).padStart(2, '0');
  const date = `${two(now.getDate())}/${two(now.getMonth() + 1)}/${String(now.getFullYear()).slice(2)}`;
  const time = `${two(now.getHours())}:${two(now.getMinutes())}`;
  const tear = W - STUB;

  ctx.fillStyle = INK;
  ctx.font = `9px ${fonts.print}`;
  ctx.fillText('MICRO BIOME PRESENTS', 24, 15);
  ctx.font = `15px ${fonts.print}`;
  ctx.fillText('CLAY PLANTER (2D)', 24, 35);

  ctx.font = `8px ${fonts.print}`;
  ctx.fillText('SCREEN', 24, 50);
  ctx.fillText('ROW', 92, 50);
  ctx.fillText('SEAT', 150, 50);
  ctx.font = `25px ${fonts.print}`;
  ctx.fillText('2D', 24, 75);
  ctx.fillText('A', 92, 75);
  ctx.fillText('01', 150, 75);

  ctx.font = `8px ${fonts.print}`;
  ctx.fillText('PRICE', 24, 90);
  ctx.fillText('DATE', 66, 90);
  ctx.fillText('TIME', 122, 90);
  ctx.fillText('RATING', 164, 90);
  ctx.font = `11px ${fonts.print}`;
  ctx.fillText('$0.00', 24, 102);
  ctx.fillText(date, 66, 102);
  ctx.fillText(time, 122, 102);
  ctx.fillText('MA15+', 164, 102);
  ctx.font = `7px ${fonts.print}`;
  ctx.fillText('SERVED BY 0001  TERMINAL 03', 24, 111);

  // Down the left edge, and down the stub's.
  ctx.font = `9px ${fonts.print}`;
  ctx.save();
  ctx.translate(13, H - BAND - 6);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Blender', 0, 0);
  ctx.restore();
  ctx.save();
  ctx.translate(W - 14, 44);
  ctx.rotate(Math.PI / 2);
  ctx.fillText('ADMIT ONE', 0, 0);
  ctx.restore();

  // The stub: screen, row and seat again, and a barcode.
  ctx.font = `8px ${fonts.print}`;
  ctx.fillText('SCR ROW SEAT', tear + 8, 16);
  ctx.font = `13px ${fonts.print}`;
  ctx.fillText('3D', tear + 8, 32);
  ctx.fillText('A', tear + 29, 32);
  ctx.fillText('01', tear + 44, 32);
  const r = seeded(7);
  for (let x = tear + 8; x < W - 26; ) {
    const w = r() > 0.6 ? 2 : 1;
    if (r() > 0.4) ctx.fillRect(x, 44, w, 30);
    x += w + 1;
  }
  ctx.font = `7px ${fonts.print}`;
  ctx.fillText('95C50183', tear + 8, 84);
}

/** The ticket's two halves, drawn separately so the stub can tear away. */
function drawTicket(ctx: CanvasRenderingContext2D, part: 'body' | 'stub', fonts: Fonts, scale: number) {
  ctx.save();
  // Card, with a soft shadow on the plaster.
  outline(ctx, part);
  ctx.fillStyle = STOCK;
  ctx.shadowColor = 'rgba(10, 20, 14, 0.35)';
  ctx.shadowBlur = 12;
  ctx.shadowOffsetY = 4;
  ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.clip();

  // A glossy black card: a faint green sheen across it, and the screen's scanlines.
  const light = ctx.createLinearGradient(0, 0, W, H);
  light.addColorStop(0, 'rgba(90, 255, 140, 0)');
  light.addColorStop(0.45, 'rgba(90, 255, 140, 0.09)');
  light.addColorStop(0.55, 'rgba(160, 255, 200, 0.05)');
  light.addColorStop(1, 'rgba(90, 255, 140, 0)');
  ctx.fillStyle = light;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = 'rgba(120, 255, 140, 0.035)';
  for (let y = 0; y < H; y += 2) ctx.fillRect(0, y, W, 1);

  // The brand band along the foot: black on a green bar.
  ctx.fillStyle = 'rgba(120, 255, 100, 0.92)';
  ctx.fillRect(0, H - BAND, W, BAND);
  ctx.fillStyle = STOCK;
  for (let x = 6; x < W; x += 52) {
    ctx.font = `700 17px ${fonts.band}`;
    ctx.fillText('RIDE', x, H - 8);
    ctx.font = `4.5px ${fonts.print}`;
    ctx.fillText('CLAUDE-MODELLED', x + 1, H - 2.5);
  }

  // The print on its own layer, so it can fade and break up where the print head missed without marking the card.
  const ink = document.createElement('canvas');
  ink.width = ctx.canvas.width;
  ink.height = ctx.canvas.height;
  const g = ink.getContext('2d') as CanvasRenderingContext2D;
  g.setTransform(ctx.getTransform());
  printText(g, fonts);
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalCompositeOperation = 'destination-out';
  const r = seeded(part === 'body' ? 3 : 5);
  for (let i = 0; i < 2600; i++) {
    g.fillStyle = `rgba(0,0,0,${0.25 + r() * 0.5})`;
    g.fillRect(r() * ink.width, r() * ink.height, scale, scale);
  }
  const streak = g.createLinearGradient(0, 0, ink.width, 0);
  streak.addColorStop(0.55, 'rgba(0,0,0,0)');
  streak.addColorStop(0.62, 'rgba(0,0,0,0.35)');
  streak.addColorStop(0.7, 'rgba(0,0,0,0)');
  g.fillStyle = streak;
  g.fillRect(0, 0, ink.width, ink.height);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(ink, 0, 0);
  ctx.restore();

  // Marker over the print: the film struck out and "Scroll to enter" scrawled over it, the screen changed to 3D.
  ctx.strokeStyle = MARKER;
  ctx.fillStyle = MARKER;
  ctx.lineCap = 'round';
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(20, 31);
  ctx.bezierCurveTo(70, 28, 130, 33, 190, 29);
  ctx.stroke();
  ctx.save();
  ctx.translate(62, 25);
  ctx.rotate(-0.05);
  ctx.font = `19px ${fonts.marker}`;
  ctx.fillText('Scroll to enter', 0, 0);
  ctx.restore();
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(22, 72);
  ctx.lineTo(54, 58);
  ctx.stroke();
  ctx.save();
  ctx.translate(46, 80);
  ctx.rotate(-0.08);
  ctx.font = `20px ${fonts.marker}`;
  ctx.fillText('3D', 0, 0);
  ctx.restore();
  // An arrow down, scrawled.
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(206, 58);
  ctx.quadraticCurveTo(209, 76, 207, 94);
  ctx.moveTo(199, 85);
  ctx.lineTo(207, 95);
  ctx.lineTo(214, 84);
  ctx.stroke();

  // Grain and specks in the card.
  const rg = seeded(part === 'body' ? 11 : 13);
  for (let i = 0; i < 900; i++) {
    ctx.fillStyle = rg() > 0.5 ? 'rgba(200, 255, 210, 0.08)' : 'rgba(0, 0, 0, 0.3)';
    ctx.fillRect(rg() * W, rg() * H, 0.6 + rg(), 0.6 + rg());
  }
  // Worn, paler fibres along the edges and the tear, catching the green.
  outline(ctx, part);
  ctx.strokeStyle = 'rgba(150, 255, 170, 0.35)';
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.restore();
}

/** Draws `source` into `ctx` broken up into pixel cells of `cell` px, `gone` (0 to 1) of them dropped at random. */
function pixelated(ctx: CanvasRenderingContext2D, source: HTMLCanvasElement, dpr: number, cell: number, gone: number) {
  const w = Math.ceil(source.width / (cell * dpr));
  const h = Math.ceil(source.height / (cell * dpr));
  const small = document.createElement('canvas');
  small.width = w;
  small.height = h;
  const s = small.getContext('2d') as CanvasRenderingContext2D;
  s.drawImage(source, 0, 0, w, h);
  if (gone > 0) {
    const img = s.getImageData(0, 0, w, h);
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        // Going from the bottom-left first, as the sweep does, ragged.
        const order = 0.6 * hash(x, y) + 0.4 * (1 - (x / w + (1 - y / h)) / 2);
        if (order < gone) img.data[(y * w + x) * 4 + 3] = 0;
      }
    s.putImageData(img, 0, 0);
  }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(small, 0, 0, source.width, source.height);
}

export function Ticket() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const dpr = window.devicePixelRatio || 1;
    // Smaller on phones.
    const ui = window.innerWidth < 640 ? 0.72 : 1;
    const scale = dpr * ui;
    el.width = Math.round((W + PAD * 2) * scale);
    el.height = Math.round((H + PAD * 2) * scale);
    Object.assign(el.style, {
      width: `${(W + PAD * 2) * ui}px`,
      height: `${(H + PAD * 2) * ui}px`,
      marginTop: `${-(PAD - 44) * ui}px`,
      marginRight: `${-(PAD - 32) * ui}px`,
    });
    const ctx = el.getContext('2d') as CanvasRenderingContext2D;
    const root = getComputedStyle(document.documentElement);
    const fonts: Fonts = {
      print: root.getPropertyValue('--font-print') || 'monospace',
      marker: root.getPropertyValue('--font-marker') || 'cursive',
      band: root.getPropertyValue('--font-band') || 'sans-serif',
    };

    const layer = (part: 'body' | 'stub') => {
      const c = document.createElement('canvas');
      c.width = el.width;
      c.height = el.height;
      const g = c.getContext('2d') as CanvasRenderingContext2D;
      g.scale(scale, scale);
      // Set down a little askew.
      g.translate(PAD + W / 2, PAD + H / 2);
      g.rotate(-0.1);
      g.translate(-W / 2, -H / 2);
      drawTicket(g, part, fonts, scale);
      return c;
    };
    let body = layer('body');
    let stub = layer('stub');
    let last = -1;
    // Redraw once the ticket's fonts are in (nothing else on the page uses them, so they have to be asked for).
    Promise.all([`9px ${fonts.print}`, `21px ${fonts.marker}`, `700 17px ${fonts.band}`].map((f) => document.fonts.load(f))).then(() => {
      body = layer('body');
      stub = layer('stub');
      last = -1;
    });
    const scratch = document.createElement('canvas');
    scratch.width = el.width;
    scratch.height = el.height;
    const sc = scratch.getContext('2d') as CanvasRenderingContext2D;

    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const s = journey.sweep;
      if (s === last) return;
      last = s;
      ctx.clearRect(0, 0, el.width, el.height);
      // The stub: tears off, swinging down round its top corner, then drops into the oncoming wave, breaking up into
      // pixels as it goes.
      const tear = smoothstep(0.02, 0.4, s);
      const stubGone = smoothstep(0.25, 0.62, s);
      if (stubGone < 1) {
        sc.clearRect(0, 0, el.width, el.height);
        sc.save();
        const pivotX = (PAD + W) * scale;
        const pivotY = PAD * scale;
        sc.translate(pivotX - tear * 24 * scale, pivotY + tear * tear * 120 * scale);
        sc.rotate(-tear * 0.55);
        sc.translate(-pivotX, -pivotY);
        sc.drawImage(stub, 0, 0);
        sc.restore();
        if (stubGone > 0 || tear > 0.3) pixelated(ctx, scratch, dpr, CELL * (1 + stubGone * 1.5), stubGone);
        else ctx.drawImage(scratch, 0, 0);
      }
      // The body: whole until the sweep's wave reaches the corner, then to pixels with it.
      const bodyGone = smoothstep(0.7, 0.95, s);
      if (bodyGone < 1) {
        if (bodyGone > 0) pixelated(ctx, body, dpr, CELL, bodyGone);
        else ctx.drawImage(body, 0, 0);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvas} aria-label="Scroll to enter" role="img" className="pointer-events-none fixed top-0 right-0 z-10" />;
}
