import { course } from './course';
import { smoothstep } from './journey';
import { rhythm } from './rhythm';
import { LAB_DOOR, ride } from './ride';
import { trace } from './trace';

// The music: each zone's piece (art/audio/hydrasynth, public/audio) looping on the Web Audio clock, handed from one to the next
// over the same stretch of road as the sky and light (components/three/ride.tsx ride.transition.t), so a boost makes the
// change quicker. It starts with the press that gets on the bike, since browsers won't start sound without one.

/** Each piece: its exact loop length (a file's own length isn't to be trusted for looping), and its level against the others. */
const TRACKS = [
  { name: 'green', seconds: 24, level: 1.2 },
  { name: 'chrome', seconds: (32 * 60) / 95, level: 1 },
  { name: 'hive', seconds: (32 * 60) / 110, level: 0.82 },
  { name: 'desert', seconds: (28 * 60) / 125, level: 0.88 },
  { name: 'core', seconds: (32 * 60) / 140, level: 0.88 },
];
const MASTER = 0.8;
const MUTE_KEY = 'ride-muted';

type Voice = { buffer: AudioBuffer | null; loading: boolean; source: AudioBufferSourceNode | null; gain: GainNode; quiet: number };

let context: AudioContext | null = null;
let master: GainNode;
let tone: BiquadFilterNode;
let coreTone: BiquadFilterNode;
let voices: Voice[] = [];

function readMuted() {
  try {
    return localStorage.getItem(MUTE_KEY) === '1';
  } catch {
    return false;
  }
}

/** Sound on or off: remembered for the visitor. */
export const music = { muted: typeof window === 'undefined' ? false : readMuted() };

export function toggleMuted() {
  music.muted = !music.muted;
  try {
    localStorage.setItem(MUTE_KEY, music.muted ? '1' : '0');
  } catch {
    // (Not remembered, then: private windows and the like.)
  }
}

async function decode(ctx: AudioContext, url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return ctx.decodeAudioData(await response.arrayBuffer());
}

/** Fetched and decoded when wanted, Opus first (it decodes to exact frames), AAC if the browser can't. */
function load(k: number) {
  const voice = voices[k];
  if (!context || !voice || voice.buffer || voice.loading) return;
  voice.loading = true;
  const ctx = context;
  const { name } = TRACKS[k];
  decode(ctx, `/audio/${name}.ogg`)
    .catch(() => decode(ctx, `/audio/${name}.m4a`))
    .then((buffer) => {
      voice.buffer = buffer;
    })
    .catch(() => {
      // (No music for this zone, then: the ride goes on without it.)
    });
}

/** Called from the press that gets on the bike. */
export function startMusic() {
  if (context) {
    context.resume().catch(() => {});
    return;
  }
  const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return;
  context = new Context();
  master = context.createGain();
  master.gain.value = 0;
  tone = context.createBiquadFilter();
  tone.type = 'lowpass';
  tone.frequency.value = 20000;
  tone.connect(master);
  master.connect(context.destination);
  // The core's own, for its muffled gate and lab, opening at the doors.
  coreTone = context.createBiquadFilter();
  coreTone.type = 'lowpass';
  coreTone.frequency.value = 20000;
  coreTone.connect(tone);
  const ctx = context;
  voices = TRACKS.map((_, k) => {
    const gain = ctx.createGain();
    gain.gain.value = 0;
    gain.connect(k === 4 ? coreTone : tone);
    return { buffer: null, loading: false, source: null, gain, quiet: 0 };
  });
  load(0);
  load(1);
  context.resume().catch(() => {});
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) ctx.suspend().catch(() => {});
    else ctx.resume().catch(() => {});
  });
  if (process.env.NODE_ENV === 'development') (window as unknown as { __music?: unknown }).__music = { context, master, voices, music };
}

function play(k: number, voice: Voice) {
  if (!context || !voice.buffer || voice.source) return;
  const source = context.createBufferSource();
  source.buffer = voice.buffer;
  source.loop = true;
  source.loopStart = 0;
  source.loopEnd = Math.min(TRACKS[k].seconds, voice.buffer.duration);
  source.connect(voice.gain);
  source.start();
  voice.source = source;
}

const wanted = TRACKS.map(() => 0);

/** Each frame: who's playing how loud, from where the ride is. */
export function updateMusic(dt: number) {
  if (!context || !voices.length) return;
  const now = context.currentTime;
  const tr = ride.transition;
  const k = ride.zone;
  wanted.fill(0);
  if (tr.placed) {
    // An equal-power handover, over the same road as the sky's.
    wanted[k - 1] = Math.cos((tr.t * Math.PI) / 2);
    wanted[k] = Math.sin((tr.t * Math.PI) / 2);
    load(k);
  } else wanted[k - 1] = 1;
  // Ahead of time, so the next is ready before it's needed.
  if (tr.arrived && k + 1 < TRACKS.length) load(k + 1);

  // The core keeps back through its gate and lab, muffled, as if through the walls, and opens as the lab's doors do.
  const leg = course.legs[4];
  const open = k === 4 && tr.placed ? smoothstep(LAB_DOOR - 140, LAB_DOOR - 10, ride.drive.s - leg.at) : 1;
  coreTone.frequency.setTargetAtTime(420 * 48 ** open, now, 0.2);

  for (const [i, voice] of voices.entries()) {
    const level = wanted[i] * TRACKS[i].level * (i === 4 ? 0.6 + 0.4 * open : 1);
    voice.gain.gain.setTargetAtTime(level, now, 0.2);
    if (wanted[i] > 0.001) {
      voice.quiet = 0;
      if (!voice.buffer) load(i);
      play(i, voice);
    } else if (voice.source) {
      voice.quiet += dt;
      // Stopped once it's been silent a while: it comes in from the top when it's next wanted.
      if (voice.quiet > 3) {
        voice.source.stop();
        voice.source.disconnect();
        voice.source = null;
      }
    }
  }

  // Time slowed to teach a boost, the music slows and sinks with it, like a tape dragging. As data, in the core's boost, it's far away.
  const slow = Math.min(rhythm.slow, trace.slow);
  const rate = 0.4 + 0.6 * slow;
  for (const voice of voices) voice.source?.playbackRate.setTargetAtTime(rate, now, 0.25);
  const ghost = ride.ghost.amount;
  const cutoff = Math.min(800 * 25 ** slow, 1100 * 18 ** (1 - ghost));
  tone.frequency.setTargetAtTime(cutoff, now, 0.08);
  const up = ride.mounted && !music.muted ? MASTER * (1 - 0.3 * ghost) : 0;
  master.gain.setTargetAtTime(up, now, ride.mounted ? 0.5 : 0.35);
}
