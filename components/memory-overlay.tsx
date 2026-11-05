'use client';

import { useEffect, useRef, useState } from 'react';
import { DOORS, type DoorLook, doorGame, doorState, doors } from '@/lib/doors';
import {
  advanceMemory,
  CHROMAS,
  closeMemory,
  hintState,
  memory,
  memoryLit,
  pressHint,
  pressMemory,
  pressMemorySlot,
  RULES,
  type Rule,
  SIGILS,
  SLOTS,
  SPARK,
  startMemory,
  stepProgress,
  type Tile,
  truthOf,
  updateMemory,
} from '@/lib/memory';
import { music } from '@/lib/music';

// The memory lock (lib/memory.ts) on a door (lib/doors.ts), floating over the view: no panel, just hard tiles on a canvas of their own,
// like components/rhythm-overlay.tsx, the view gone to data behind them (memory.haze, phased() in components/three/speed-blur.ts).
// Each door has its chromas and what lights up with a win (its DoorLook). One line of words says what to remember. Presses that land on a
// tile are its; anything else goes on to the page. `?memory=a|b|c|d` compares the rules and `?door=1..4` plays a door, in production too.

const RULE_KEYS: Rule[] = ['a', 'b', 'c', 'd'];
const GREEN = '#5dff8f';
const WHITE = '#eafff0';
const ALERT = '#ff3a2a';
const INK = '#010402';
const TRUTHS = { chroma: 'CHROMA', sigil: 'SIGILS', tile: 'TILES', place: 'PLACES' };
const playRule = (rule: Rule) => startMemory({ table: DOORS[3].rounds, look: DOORS[3].look, rule, review: 'rules' });
const playDoor = (i: number) => startMemory(doorGame(i, { review: 'doors' }));
/** The pointer that shows the first press. */
const CURSOR = ['#.......', '##......', '###.....', '####....', '#####...', '######..', '#######.', '####....', '##.##...', '#...##..', '....##..'];

const hash = (n: number) => {
  const h = Math.sin(n * 127.1 + 3.7) * 43758.5453;
  return h - Math.floor(h);
};

// The tones: a tile's truth has its own, a second way to hold the order. Their own small graph, out of the music's.
const PENTA = [262, 311, 392, 466, 587];
let audio: AudioContext | null = null;
function wakeAudio() {
  if (!audio) {
    const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (Context) audio = new Context();
  }
  audio?.resume().catch(() => {});
}
function beep(freq: number, seconds: number, level = 0.07, wave: OscillatorType = 'square', after = 0, slideTo = 0) {
  if (!audio || audio.state !== 'running' || music.muted) return;
  const at = audio.currentTime + after;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = wave;
  osc.frequency.setValueAtTime(freq, at);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, at + seconds);
  gain.gain.setValueAtTime(level, at);
  gain.gain.setValueAtTime(level, at + seconds * 0.6);
  gain.gain.linearRampToValueAtTime(0, at + seconds);
  osc.connect(gain).connect(audio.destination);
  osc.start(at);
  osc.stop(at + seconds + 0.02);
}
function playEvents() {
  for (const e of memory.events) {
    if (e.type === 'tone') beep(PENTA[e.truth], 0.22);
    else if (e.type === 'twist') beep(90, 0.09, 0.05, 'sawtooth', 0, 160);
    else if (e.type === 'locked') beep(70, 0.05, 0.04);
    else if (e.type === 'go') {
      beep(523, 0.06, 0.05);
      beep(784, 0.08, 0.05, 'square', 0.07);
    } else if (e.type === 'wrong') {
      // The door's alarm.
      beep(880, 0.16, 0.06);
      beep(660, 0.16, 0.06, 'square', 0.18);
      beep(880, 0.16, 0.06, 'square', 0.36);
      beep(110, 0.5, 0.08, 'sawtooth', 0, 48);
    } else if (e.type === 'key') {
      // A key turning, as the point of light gets there.
      beep(190, 0.05, 0.1, 'square', SPARK - 0.05, 90);
      beep(120, 0.08, 0.1, 'square', SPARK + 0.04, 70);
      beep(784, 0.12, 0.04, 'square', SPARK + 0.1);
    } else if (e.type === 'won') {
      [262, 392, 523, 784, 1046].forEach((f, i) => {
        beep(f, 0.16, 0.07, 'square', i * 0.1);
      });
    } else if (e.type === 'lost') beep(160, 1.1, 0.1, 'sawtooth', 0, 30);
  }
  memory.events.length = 0;
}

function layoutFor() {
  const W = window.innerWidth;
  const H = window.innerHeight;
  const pixel = Math.min(W, H) < 500 ? 3 : 4;
  const w = Math.ceil(W / pixel);
  const h = Math.ceil(H / pixel);
  // Over the middle of the view, clear of the bike and its buttons below.
  const pitch = Math.floor(Math.min(w * 0.31, h * 0.18));
  const size = Math.round(pitch * 0.88);
  return { w, h, pixel, pitch, size, cx: Math.round(w / 2), cy: Math.round(h * 0.45), css: Math.max(15, Math.min(22, W / 40)), textPx: pixel === 3 ? 1 : 2 };
}

export function MemoryOverlay() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const lettering = useRef<HTMLCanvasElement>(null);
  const [review, setReview] = useState<'rules' | 'doors' | null>(null);
  const [rule, setRule] = useState<Rule>('c');
  const hintButton = useRef<HTMLButtonElement>(null);
  const [hint, setHint] = useState<'ready' | 'wait' | 'spent' | null>(null);

  // `?memory=`: read once. And the dev handle, like window.__ride.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const asked = params.get('memory');
    const door = Number(params.get('door'));
    if (asked && (RULE_KEYS as string[]).includes(asked)) playRule(asked as Rule);
    else if (door >= 1 && door <= DOORS.length) playDoor(door - 1);
    if (process.env.NODE_ENV === 'development')
      (window as unknown as { __memory?: unknown }).__memory = {
        memory,
        startMemory,
        closeMemory,
        pressMemory,
        truthOf,
        doors,
        doorState,
        DOORS,
        playDoor,
        playRule,
      };
  }, []);

  // A press on a tile is the game's, and nothing else's. Comparing, once it's over, a press anywhere goes again.
  useEffect(() => {
    const down = (e: PointerEvent) => {
      if (!memory.open) return;
      if ((e.target as HTMLElement).closest?.('[data-memory-keys]')) return;
      wakeAudio();
      const L = layoutFor();
      let best: Tile | null = null;
      let near = (L.size * L.pixel * 1.12) / 2;
      for (const t of memory.tiles) {
        const d = Math.max(Math.abs(e.clientX - t.sx), Math.abs(e.clientY - t.sy));
        if (d < near) {
          near = d;
          best = t;
        }
      }
      const ended = memory.phase === 'won' || memory.phase === 'lost';
      const waiting = memory.options.review && ended;
      if (best && !ended) pressMemory(best.id);
      else if (waiting) advanceMemory();
      else return;
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    window.addEventListener('pointerdown', down, { capture: true });
    return () => window.removeEventListener('pointerdown', down, { capture: true });
  }, []);

  // The arrows and space, to the cross's places; the rest of the page doesn't get them while it's open.
  useEffect(() => {
    const slots: Record<string, number> = { ArrowUp: 0, ArrowLeft: 1, ' ': 2, ArrowRight: 3, ArrowDown: 4 };
    const key = (e: KeyboardEvent) => {
      if (!memory.open || e.metaKey || e.ctrlKey || e.altKey) return;
      // (On the road, the door stays shut: pulling up's the way to put the game away.)
      if (e.key === 'Escape' && memory.options.review) closeMemory();
      else if (e.key === 'h' || e.key === 'H') pressHint();
      // (Just looking: the hint on without failing for it first.)
      else if (e.key === 'f' && memory.options.review) memory.hintForced = !memory.hintForced;
      else if (e.key in slots) {
        wakeAudio();
        if (!e.repeat) {
          if (memory.phase === 'won' || memory.phase === 'lost') advanceMemory();
          else pressMemorySlot(slots[e.key]);
        }
      } else if (memory.options.review === 'rules' && (RULE_KEYS as string[]).includes(e.key)) playRule(e.key as Rule);
      else if (memory.options.review === 'doors' && Number(e.key) >= 1 && Number(e.key) <= DOORS.length) playDoor(Number(e.key) - 1);
      else return;
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    const keyUp = (e: KeyboardEvent) => {
      if (memory.open && e.key in slots) e.stopImmediatePropagation();
    };
    window.addEventListener('keydown', key, { capture: true });
    window.addEventListener('keyup', keyUp, { capture: true });
    return () => {
      window.removeEventListener('keydown', key, { capture: true });
      window.removeEventListener('keyup', keyUp, { capture: true });
    };
  }, []);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let drawn = false;
    let shownReview: 'rules' | 'doors' | null = null;
    let shownHint: ReturnType<typeof hintState> = null;
    // (Where a wheel's got to, easing round to the next step, and a ring's size closing in.)
    let wheel = 0;
    let ring = 1;
    let shownRule: Rule = 'c';
    const print = getComputedStyle(document.documentElement).getPropertyValue('--font-print') || 'monospace';
    document.fonts.load(`20px ${print}`, 'YRBWM WON LOST').catch(() => {});

    const tick = () => {
      raf = requestAnimationFrame(tick);
      const el = canvas.current;
      const g = el?.getContext('2d');
      const textEl = lettering.current;
      const text = textEl?.getContext('2d');
      if (!el || !g || !textEl || !text) return;
      const stamp = performance.now();
      const dt = Math.min(0.05, (stamp - last) / 1000);
      last = stamp;
      updateMemory(dt);
      const reviewing = memory.open ? (memory.options.review ?? null) : null;
      if (shownReview !== reviewing) {
        shownReview = reviewing;
        setReview(reviewing);
      }
      const hintNow = hintState();
      if (shownHint !== hintNow) {
        shownHint = hintNow;
        setHint(hintNow);
      }
      if (shownRule !== memory.rule) {
        shownRule = memory.rule;
        setRule(shownRule);
      }
      if (!memory.open) {
        if (drawn) {
          g.setTransform(1, 0, 0, 1, 0, 0);
          g.clearRect(0, 0, el.width, el.height);
          text.clearRect(0, 0, textEl.width, textEl.height);
          drawn = false;
        }
        return;
      }
      if (!drawn) wakeAudio();
      drawn = true;
      playEvents();
      const m = memory;
      const { w, h, pixel, pitch, size, cx, cy, css, textPx } = layoutFor();
      const tw = Math.ceil((w * pixel) / textPx);
      const th = Math.ceil((h * pixel) / textPx);
      if (el.width !== w || el.height !== h || textEl.width !== tw || textEl.height !== th) {
        el.width = w;
        el.height = h;
        textEl.width = tw;
        textEl.height = th;
      }
      // How far tiles may fly: the whole view.
      m.bounds.x = Math.max(1.05, (Math.min(cx, w - cx) - size / 2 - 2) / pitch);
      m.bounds.y = Math.max(1.05, (Math.min(cy, h - cy) - size / 2 - 2) / pitch);

      const now = m.clock;
      const look = (m.options.look ?? DOORS[3].look) as DoorLook;
      g.imageSmoothingEnabled = false;
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, w, h);
      text.clearRect(0, 0, tw, th);
      text.lineJoin = 'round';
      text.textBaseline = 'middle';

      const ended0 = () => m.phase === 'won' || m.phase === 'lost';
      /** Lettering at (x, y) in pixels, `fontCss` in CSS px: rule a's chroma marks, and the ends when comparing. Nothing else. */
      const label = (words: string, x: number, y: number, fontCss: number, ink: string, flat = false) => {
        const font = Math.round(fontCss / textPx);
        text.textAlign = 'center';
        text.font = `${font}px ${print}`;
        const X = (x * pixel) / textPx;
        const Y = (y * pixel) / textPx;
        if (!flat) {
          text.lineWidth = Math.max(3, font * 0.34);
          text.strokeStyle = 'rgba(0, 8, 3, 0.95)';
          text.strokeText(words, X, Y);
        }
        text.fillStyle = ink;
        text.fillText(words, X, Y);
      };
      const posOf = (t: Tile) => ({ x: cx + t.x * pitch, y: cy + t.y * pitch });
      for (const t of m.tiles) {
        const p = posOf(t);
        t.sx = p.x * pixel;
        t.sy = p.y * pixel;
      }

      // The world behind, dimmed further and darkest round the cross, so the tiles sit on something over the lab's white lights.
      const fade = Math.min(1, m.haze / 0.5);
      g.globalAlpha = fade;
      g.fillStyle = look.wash;
      g.fillRect(0, 0, w, h);
      g.globalAlpha = 1;
      const pool = g.createRadialGradient(cx, cy, pitch * 0.9, cx, cy, pitch * 2.4);
      pool.addColorStop(0, `rgba(0, 14, 6, ${0.62 * fade})`);
      pool.addColorStop(1, 'rgba(0, 14, 6, 0)');
      g.fillStyle = pool;
      g.fillRect(0, 0, w, h);
      g.fillStyle = `rgba(0, 0, 0, ${0.16 * fade})`;
      for (let y = 0; y < h; y += 2) g.fillRect(0, y, w, 1);
      // Blocks of light rising off the middle of it.
      for (let i = 0; i < 46; i++) {
        const k = hash(i * 3.1);
        const a = hash(i * 7.7) * Math.PI * 2;
        const rise = (now * (0.05 + k * 0.12) + hash(i)) % 1;
        const r = pitch * (1.75 + 2.6 * hash(i * 1.9));
        const b = 1 + (i % 3 === 0 ? 1 : 0);
        g.globalAlpha = 0.65 * (1 - rise) * fade;
        g.fillStyle = look.spark;
        g.fillRect(Math.round(cx + Math.cos(a) * r), Math.round(cy + Math.sin(a) * r * 0.8 - rise * pitch * 1.3), b, b);
      }
      g.globalAlpha = 1;

      // The shake of a wrong answer, tiles and all.
      const shake = m.shake * m.shake * 4;
      if (shake > 0.4) g.setTransform(1, 0, 0, 1, Math.round((hash(now * 91) - 0.5) * shake * 2), Math.round((hash(now * 53) - 0.5) * shake * 2));

      // The cross they rest on: brackets and a hairline, nothing solid.
      const half = Math.round(size / 2);
      g.globalAlpha = 0.35;
      g.fillStyle = look.frame;
      g.fillRect(cx - pitch, cy, pitch * 2, 1);
      g.fillRect(cx, cy - pitch, 1, pitch * 2);
      g.globalAlpha = 1;
      const arm = Math.max(3, Math.round(size * 0.16));
      for (const s of SLOTS) {
        const x = cx + s.x * pitch;
        const y = cy + s.y * pitch;
        g.fillStyle = 'rgba(0, 10, 4, 0.5)';
        g.fillRect(x - half, y - half, size, size);
        g.fillStyle = look.frame;
        for (const [ex, ey] of [
          [-1, -1],
          [1, -1],
          [-1, 1],
          [1, 1],
        ]) {
          const X = ex < 0 ? x - half - 2 : x + half + 1;
          const Y = ey < 0 ? y - half - 2 : y + half + 1;
          g.fillRect(ex < 0 ? X : X - arm + 1, Y, arm, 1);
          g.fillRect(X, ey < 0 ? Y : Y - arm + 1, 1, arm);
        }
      }

      // What this door lights with each win, behind the tiles, in the corners the cross leaves empty or round it.
      const lit = memoryLit();
      const wins = m.rounds;
      wheel += ((lit * Math.PI) / 4 - wheel) * Math.min(1, dt * 12);
      ring += (1 - (0.28 * lit) / wins - ring) * Math.min(1, dt * 7);
      // (Kept on the view: a phone's narrow.)
      const ringR = Math.min(pitch * 2.05, w / 2 - 3) * ring;
      /** Where the segment `k` is. */
      const segment = (k: number) => {
        if (look.lock === 'rings') {
          const a = -Math.PI / 2 + ((k + 0.5) / wins) * Math.PI * 2;
          return { x: cx + Math.cos(a) * ringR, y: cy + Math.sin(a) * ringR };
        }
        const sx = k === 0 || k === 3 ? -1 : 1;
        const sy = k < 2 ? -1 : 1;
        const out = look.lock === 'wheel' ? 1.22 : 1;
        return { x: cx + sx * pitch * out, y: cy + sy * pitch * out };
      };
      /** A hard arc of blocks. */
      const arc = (r: number, a0: number, a1: number, ink: string, thick: number) => {
        g.fillStyle = ink;
        for (let a = a0; a < a1; a += 0.8 / r) g.fillRect(Math.round(cx + Math.cos(a) * r), Math.round(cy + Math.sin(a) * r), thick, thick);
      };
      if (!ended0()) {
        if (look.lock === 'rings') {
          const step5 = (Math.PI * 2) / wins;
          arc(ringR + 5, 0, Math.PI * 2, look.frame, 1);
          for (let k = 0; k < wins; k++) {
            const a0 = -Math.PI / 2 + k * step5 + 0.05;
            arc(ringR, a0, a0 + step5 - 0.1, k < lit ? look.lit : look.dark, k < lit ? 4 : 3);
          }
        } else if (look.lock === 'wheel') {
          const R = Math.min(pitch * 1.72, w / 2 - 3);
          arc(R, 0, Math.PI * 2, look.frame, 3);
          arc(R * 0.42, 0, Math.PI * 2, look.frame, 2);
          g.fillStyle = look.frame;
          for (let k = 0; k < 8; k++) {
            const a = wheel + (k * Math.PI) / 4;
            for (let r = R * 0.42; r < R; r += 1.5) g.fillRect(Math.round(cx + Math.cos(a) * r), Math.round(cy + Math.sin(a) * r), 2, 2);
          }
        }
        if (look.lock !== 'rings') {
          for (let k = 0; k < wins; k++) {
            const p = segment(k);
            const on = k < lit;
            const q = Math.round(size * (look.lock === 'wheel' ? 0.34 : 0.56));
            const x = Math.round(p.x - q / 2);
            const y = Math.round(p.y - q / 2);
            g.fillStyle = INK;
            g.fillRect(x - 1, y - 1, q + 2, q + 2);
            if (look.lock === 'bars') {
              // The lab's: three bars, like the strip lights on its tanks.
              const bar = Math.max(2, Math.round(q / 5));
              g.fillStyle = on ? look.lit : look.dark;
              for (let b = 0; b < 3; b++) g.fillRect(x, y + b * bar * 2, q, bar);
            } else {
              g.fillStyle = on ? look.lit : look.dark;
              g.fillRect(x, y, q, q);
              g.fillStyle = on ? look.frame : INK;
              g.fillRect(x + Math.round(q * 0.3), y + Math.round(q * 0.3), Math.round(q * 0.4), Math.round(q * 0.4));
            }
          }
        }
      }

      // The warning of what's about to go where.
      const step = m.step;
      if (step && step.telegraph > 0 && step.age < step.telegraph) {
        const blink = Math.floor(step.age * 18) % 2 === 0;
        for (const [a, b] of step.links) {
          const A = posOf(m.tiles[a]);
          const B = posOf(m.tiles[b]);
          const hue = step.hues.find((o) => o.from === a && o.to === b);
          g.fillStyle = hue ? CHROMAS[hue.chroma].hex : blink ? WHITE : GREEN;
          const len = Math.hypot(B.x - A.x, B.y - A.y);
          for (let d = 0; d < len; d += 4) {
            g.fillRect(Math.round(A.x + ((B.x - A.x) * d) / len) - 1, Math.round(A.y + ((B.y - A.y) * d) / len) - 1, 2, 2);
          }
        }
      }

      const ended = ended0();
      const cell = Math.max(1, Math.floor((size - 2) / 9));
      const moving = (t: Tile) => !!step && step.age >= step.telegraph && step.moves.some((o) => o.tile === t.id);
      const order = [...m.tiles].sort((a, b) => Number(moving(a)) - Number(moving(b)) || a.glow - b.glow);

      if (ended) {
        // The end: the tiles come apart. Won, into blocks of light flung outward; lost, they fall dead.
        const won = m.phase === 'won';
        const u = Math.min(1, m.phaseT / (won ? 0.8 : 1.1));
        for (const t of m.tiles) {
          const p = posOf(t);
          const rows = SIGILS[t.id].rows;
          for (let r = 0; r < 9; r++) {
            for (let c = 0; c < 9; c++) {
              const dx = (c - 4) * cell;
              const dy = (r - 4) * cell;
              const k = hash(t.id * 90 + r * 9 + c);
              const X = p.x + dx * (1 + (won ? 3 + 5 * k : 0) * u) + (won ? (p.x - cx) * 1.5 * u * k : (k - 0.5) * 6 * u);
              const Y = p.y + dy * (1 + (won ? 3 + 5 * k : 0) * u) + (won ? (p.y - cy) * 1.5 * u * k - pitch * u * k : pitch * 1.6 * u * u * (0.5 + k));
              const alpha = 1 - u * (0.4 + 0.6 * k);
              if (alpha <= 0) continue;
              g.globalAlpha = alpha;
              g.fillStyle = won ? (rows[r][c] === '#' ? WHITE : look.lit) : rows[r][c] === '#' ? '#3a0604' : ALERT;
              g.fillRect(Math.round(X), Math.round(Y), cell, cell);
            }
          }
        }
        g.globalAlpha = 1;
      } else {
        const dimAll = m.phase === 'show';
        for (const t of order) {
          const p = posOf(t);
          const lift = moving(t) ? 1.06 : 1;
          const grow = 1 + (m.lit === t.id ? 0.12 : t.glow * 0.08);
          const s = Math.round(size * lift * grow);
          const x = Math.round(p.x - s / 2);
          const y = Math.round(p.y - s / 2);
          // A hard black edge and a hairline of the door's chroma outside it: it holds over white ceiling and black floor both.
          g.fillStyle = look.frame;
          g.fillRect(x - 3, y - 3, s + 6, s + 6);
          g.fillStyle = INK;
          g.fillRect(x - 2, y - 2, s + 4, s + 4);
          const base = CHROMAS[t.shownChroma].hex;
          if (t.fill < 1) {
            // (A chroma handing over: pale behind it, for the sigil to stay readable right through.)
            g.fillStyle = '#7fa98a';
            g.fillRect(x, y, s, s);
            g.fillStyle = base;
            const f = Math.round(s * t.fill);
            g.fillRect(x + Math.round((s - f) / 2), y + Math.round((s - f) / 2), f, f);
          } else {
            g.fillStyle = base;
            g.fillRect(x, y, s, s);
          }
          // Its sigil, in hard black.
          const off = Math.round((s - cell * 9) / 2);
          g.fillStyle = INK;
          const rows = SIGILS[t.shownSigil].rows;
          for (let r = 0; r < 9; r++) {
            for (let c = 0; c < 9; c++) if (rows[r][c] === '#') g.fillRect(x + off + c * cell, y + off + r * cell, cell, cell);
          }
          if (dimAll && m.lit !== t.id) {
            g.fillStyle = 'rgba(1, 10, 5, 0.42)';
            g.fillRect(x, y, s, s);
          }
          // Lit: a frame thrown out from it, the face left alone (the chroma's what might be being read).
          if (t.glow > 0) {
            g.fillStyle = `rgba(255, 255, 255, ${t.glow})`;
            for (const out of [3, 5 + Math.round((1 - t.glow) * size * 0.22)]) {
              const thick = out === 3 ? 2 : 1;
              g.fillRect(x - out, y - out, s + out * 2, thick);
              g.fillRect(x - out, y + s + out - thick, s + out * 2, thick);
              g.fillRect(x - out, y - out, thick, s + out * 2);
              g.fillRect(x + s + out - thick, y - out, thick, s + out * 2);
            }
          }
          // Rule a answers by chroma alone: each chroma's letter goes with it, for whoever can't tell them apart.
          if (RULES[m.rule].truth === 'chroma' && t.fill > 0.6) {
            const tag = Math.max(5, Math.round((css * 0.95) / pixel) + 2);
            g.fillStyle = 'rgba(244, 255, 248, 0.94)';
            g.fillRect(x + s - tag - 1, y + 1, tag, tag);
            label(CHROMAS[t.shownChroma].mark, x + s - tag / 2 - 1, y + 1 + tag / 2, css * 0.95, INK, true);
          }
        }
        // Chroma crossing over between tiles, in the open: this is how a tile's chroma can be tracked even when it's cut.
        if (step && step.age >= step.telegraph && step.hues.length) {
          const u = stepProgress(step);
          const b = Math.max(4, Math.round(size * 0.3));
          for (const hue of step.hues) {
            const A = posOf(m.tiles[hue.from]);
            const B = posOf(m.tiles[hue.to]);
            const X = Math.round(A.x + (B.x - A.x) * u - b / 2);
            const Y = Math.round(A.y + (B.y - A.y) * u - b / 2);
            g.fillStyle = INK;
            g.fillRect(X - 1, Y - 1, b + 2, b + 2);
            g.fillStyle = CHROMAS[hue.chroma].hex;
            g.fillRect(X, Y, b, b);
          }
        }
        // Brackets on the one that's wanted (teaching) or was wanted (a wrong answer).
        const bracket = (t: Tile, ink: string, gap: number) => {
          const p = posOf(t);
          const e = half + gap;
          const long = Math.max(4, Math.round(size * 0.24));
          g.fillStyle = ink;
          for (const [sx, sy] of [
            [-1, -1],
            [1, -1],
            [-1, 1],
            [1, 1],
          ]) {
            const X = Math.round(p.x + sx * e);
            const Y = Math.round(p.y + sy * e);
            g.fillRect(sx < 0 ? X : X - long + 2, Y, long, 2);
            g.fillRect(X, sy < 0 ? Y : Y - long + 2, 2, long);
          }
        };
        if (m.hint !== null) {
          // The first ever: brackets on the tile that's wanted, and a pointer tapping at it. That's all the telling there is.
          const t = m.tiles[m.hint];
          bracket(t, WHITE, 4 + (Math.floor(now * 5) % 2) * 2);
          const p = posOf(t);
          const k = Math.max(1, Math.floor(size / 22));
          const tap = Math.floor(now * 3) % 2 ? 0 : 2 * k;
          const X = Math.round(p.x + size * 0.12) + tap;
          const Y = Math.round(p.y + size * 0.12) + tap;
          for (const [ink, grow] of [
            [INK, 1],
            [WHITE, 0],
          ] as const) {
            g.fillStyle = ink;
            CURSOR.forEach((row, r) => {
              for (let c = 0; c < row.length; c++) if (row[c] === '#') g.fillRect(X + c * k - grow, Y + r * k - grow, k + grow * 2, k + grow * 2);
            });
          }
        }
        // The hint: the next tile to press, wherever it's got to, in the door's colours.
        if (m.hintFlash > 0 && m.hintTile !== null) {
          const t = m.tiles[m.hintTile];
          const p = posOf(t);
          if (Math.floor(now * 9) % 3 !== 2) bracket(t, look.spark, 5);
          const out = half + 7 + Math.round((1 - m.hintFlash) * 3);
          g.globalAlpha = Math.min(1, m.hintFlash * 2);
          g.fillStyle = look.lit;
          g.fillRect(p.x - out, p.y - out, out * 2, 2);
          g.fillRect(p.x - out, p.y + out - 2, out * 2, 2);
          g.fillRect(p.x - out, p.y - out, 2, out * 2);
          g.fillRect(p.x + out - 2, p.y - out, 2, out * 2);
          g.globalAlpha = 1;
        }
        if (m.phase === 'fail' && m.fail) {
          if (m.fail.pressed !== null) {
            const p = posOf(m.tiles[m.fail.pressed]);
            g.fillStyle = 'rgba(0, 0, 0, 0.55)';
            g.fillRect(p.x - half, p.y - half, size, size);
            g.fillStyle = ALERT;
            const n = Math.floor(size * 0.8);
            const stroke = Math.max(2, Math.round(size * 0.12));
            for (let i = 0; i < n; i++) {
              const k = i - n / 2;
              g.fillRect(Math.round(p.x + k - stroke / 2), Math.round(p.y + k - stroke / 2), stroke, stroke);
              g.fillRect(Math.round(p.x + k - stroke / 2), Math.round(p.y - k - stroke / 2), stroke, stroke);
            }
          }
          bracket(m.tiles[m.fail.wanted], WHITE, 5 + (Math.floor(now * 8) % 2));
        }
      }
      g.setTransform(1, 0, 0, 1, 0, 0);
      if (m.flash > 0) {
        g.fillStyle = `rgba(255, 30, 20, ${0.42 * m.flash})`;
        g.fillRect(0, 0, w, h);
      }
      if (m.phase === 'pass') {
        // A point of light from the tile to what it lights; there, a burst.
        const from = posOf(m.tiles[m.lastPress]);
        const to = segment(m.round);
        const u = Math.min(1, m.phaseT / SPARK);
        const k = u * u * (3 - 2 * u);
        g.fillStyle = look.spark;
        if (u < 1) {
          for (let i = 0; i < 7; i++) {
            const t = Math.max(0, k - i * 0.04);
            const b = Math.max(1, 5 - i);
            g.fillRect(Math.round(from.x + (to.x - from.x) * t - b / 2), Math.round(from.y + (to.y - from.y) * t - b / 2), b, b);
          }
        } else {
          const t = (m.phaseT - SPARK) / 0.4;
          const r = Math.round(3 + t * size * 0.5);
          g.globalAlpha = Math.max(0, 1 - t);
          g.fillRect(to.x - r, to.y - r, r * 2, 1);
          g.fillRect(to.x - r, to.y + r, r * 2, 1);
          g.fillRect(to.x - r, to.y - r, 1, r * 2);
          g.fillRect(to.x + r, to.y - r, 1, r * 2);
          g.globalAlpha = 1;
        }
      }

      // The one line: what to hold on to. All the telling there is, bar the pointer on the first press ever.
      const row = (css * 1.42) / pixel;
      const pip = Math.max(2, Math.round(css / pixel) - 1);
      if (!ended) label(`ENCRYPTION: ${TRUTHS[RULES[m.rule].truth]}`, cx, cy - pitch - half - row * 1.05, css * 1.15, look.ink);

      // Under the cross: the order so far and the wrong answers left; the clock.
      const n = m.sequence.length;
      const under = cy + pitch + size / 2 + 5;
      if (n && !ended) {
        const strikes = Number.isFinite(m.maxStrikes) ? m.maxStrikes : 0;
        const across = n * (pip + 2) + 4 + strikes * (pip + 2);
        const start = Math.round(cx - across / 2);
        for (let i = 0; i < n; i++) {
          const on = m.phase === 'show' ? i <= m.shown : m.phase === 'pass' || i < m.pressed;
          g.fillStyle = INK;
          g.fillRect(start + i * (pip + 2) - 1, under - 1, pip + 2, pip + 2);
          g.fillStyle = m.locked > 0 ? ALERT : on ? look.lit : look.dark;
          g.fillRect(start + i * (pip + 2), under, pip, pip);
        }
        for (let i = 0; i < strikes; i++) {
          const x = start + n * (pip + 2) + 4 + i * (pip + 2);
          g.fillStyle = INK;
          g.fillRect(x - 1, under - 1, pip + 2, pip + 2);
          g.fillStyle = i < m.maxStrikes - m.strikes ? ALERT : '#3a0a08';
          g.fillRect(x, under, pip, pip);
        }
        if (m.timerMax && m.phase === 'repeat') {
          const f = Math.max(0, m.timer / m.timerMax);
          const barW = pitch * 2 + size;
          const barY = under + pip + 3;
          g.fillStyle = INK;
          g.fillRect(cx - barW / 2 - 1, barY - 1, barW + 2, 4);
          g.fillStyle = f < 0.3 ? ALERT : look.lit;
          g.fillRect(cx - barW / 2, barY, Math.round(barW * f), 2);
        }
      }

      // The hint's button, clear of the tiles and whatever's round them: beside the cross if there's room, else under it.
      const hb = hintButton.current;
      if (hb) {
        const bw = hb.offsetWidth;
        const side = (cx + pitch * 2.4) * pixel;
        const beside = side + bw + 8 < window.innerWidth;
        hb.style.left = `${beside ? side : cx * pixel - bw / 2}px`;
        hb.style.top = `${(beside ? cy + pitch - hb.offsetHeight / (2 * pixel) : under + pip + 9) * pixel}px`;
        hb.style.color = hintNow === 'ready' ? INK : look.ink;
        hb.style.background = hintNow === 'ready' ? look.lit : 'rgba(2, 16, 8, 0.72)';
        hb.style.borderColor = hintNow === 'ready' ? look.spark : look.frame;
      }

      // Just looking, the end has to say which it was and what to do. On the road, the door says it.
      if (m.options.review && ended) {
        const won = m.phase === 'won';
        label(won ? 'OPEN' : 'LOST', cx, cy, css * 3, won ? WHITE : ALERT);
        label('PRESS TO GO AGAIN', cx, cy + row * 2, css * 0.88, GREEN);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const key = 'grid h-7 min-w-7 place-items-center border border-[#5dff8f] px-1 text-[13px] leading-none font-[family-name:var(--font-print)]';
  return (
    <>
      <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
      <canvas ref={lettering} aria-hidden className="pointer-events-none fixed inset-0 z-[14] h-full w-full [image-rendering:pixelated]" />
      {hint && (
        <button
          ref={hintButton}
          type="button"
          data-memory-keys
          aria-label={hint === 'ready' ? 'Hint' : hint === 'spent' ? 'Hint, spent this round' : 'Hint, not yet'}
          aria-disabled={hint !== 'ready'}
          onPointerDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            pressHint();
          }}
          className={`fixed z-[41] h-12 min-w-20 touch-none border-2 px-3 text-[16px] leading-none font-[family-name:var(--font-print)] ${hint === 'ready' ? 'cursor-pointer' : 'opacity-50'} ${hint === 'spent' ? 'line-through' : ''}`}
        >
          HINT
        </button>
      )}
      {review && (
        <div data-memory-keys className="fixed top-2 right-2 z-[41] flex gap-1">
          {review === 'rules' &&
            RULE_KEYS.map((k) => (
              <button
                key={k}
                type="button"
                aria-label={`Rule ${k}: ${RULES[k].name.toLowerCase()}`}
                title={RULES[k].name}
                aria-pressed={rule === k}
                onClick={() => playRule(k)}
                className={`${key} ${rule === k ? 'bg-[#5dff8f] text-[#010402]' : 'bg-[#021008]/80 text-[#5dff8f]'}`}
              >
                {k.toUpperCase()}
              </button>
            ))}
          {review === 'doors' &&
            DOORS.map((d, i) => (
              <button
                key={d.name}
                type="button"
                aria-label={d.name}
                title={d.name}
                onClick={() => playDoor(i)}
                className={`${key} bg-[#021008]/80 text-[#5dff8f]`}
              >
                {i + 1}
              </button>
            ))}
          <button type="button" aria-label="Leave the game" onClick={() => closeMemory()} className={`${key} bg-[#021008]/80 text-[#5dff8f]`}>
            X
          </button>
        </div>
      )}
    </>
  );
}
