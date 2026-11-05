import { musicContext, musicInput } from './music';

// The stairwell's and flooded tunnel's sounds (art/audio/sections, public/audio/sections), on the music's context and in at its filter,
// so the mute, the muffling at a door's lock and the master's fades all take them too. Loops: the water while in the tunnel, the rattle
// on the steps. Nothing's fetched till components/three/section-fx.tsx asks, nearing the stairwell.

const FILES = [
  'rushing-water-loop',
  'stair-rattle-loop',
  'splash',
  'splash-big',
  'steam-burst',
  'steam-burst-short',
  'metal-impact-1',
  'metal-impact-2',
  'metal-impact-3',
  'metal-impact-4',
  'metal-impact-5',
  'concrete-collapse',
  'concrete-debris',
] as const;
export type SectionSound = (typeof FILES)[number];

/** Each one's level against the music (the files are all about -18 LUFS: art/audio/sections/LICENSES.md; levels metered, not heard). */
const LEVEL: Record<SectionSound, number> = {
  'rushing-water-loop': 0.7,
  'stair-rattle-loop': 0.8,
  splash: 0.8,
  'splash-big': 0.8,
  'steam-burst': 0.72,
  'steam-burst-short': 0.72,
  'metal-impact-1': 0.8,
  'metal-impact-2': 0.8,
  'metal-impact-3': 0.8,
  'metal-impact-4': 0.8,
  'metal-impact-5': 0.8,
  'concrete-collapse': 1,
  'concrete-debris': 0.85,
};

type Loop = {
  name: SectionSound;
  source: AudioBufferSourceNode | null;
  filter: BiquadFilterNode;
  gain: GainNode;
  quiet: number;
  level: number;
  cutoff: number;
  rate: number;
};

const buffers: Partial<Record<SectionSound, AudioBuffer>> = {};
let loading = false;
let bus: GainNode | null = null;
let water: Loop | null = null;
let rattle: Loop | null = null;

async function decode(ctx: AudioContext, name: SectionSound) {
  const read = async (ext: string) => {
    const response = await fetch(`/audio/sections/${name}.${ext}`);
    if (!response.ok) throw new Error(`${name}.${ext}: ${response.status}`);
    return ctx.decodeAudioData(await response.arrayBuffer());
  };
  // (Opus or Vorbis first: it decodes to exact frames, for the loops. AAC if the browser can't.)
  buffers[name] = await read('ogg').catch(() => read('m4a'));
}

function makeLoop(ctx: AudioContext, name: SectionSound): Loop {
  const filter = ctx.createBiquadFilter();
  filter.type = 'lowpass';
  filter.frequency.value = 20000;
  const gain = ctx.createGain();
  gain.gain.value = 0;
  filter.connect(gain);
  gain.connect(bus as GainNode);
  return { name, source: null, filter, gain, quiet: 0, level: 0, cutoff: 0, rate: 0 };
}

/** Fetched and decoded when wanted: once the music's context is there (it comes with the first press). */
export function loadSectionAudio() {
  const ctx = musicContext();
  const input = musicInput();
  if (loading || !ctx || !input) return;
  loading = true;
  bus = ctx.createGain();
  bus.connect(input);
  water = makeLoop(ctx, 'rushing-water-loop');
  rattle = makeLoop(ctx, 'stair-rattle-loop');
  for (const name of FILES) decode(ctx, name).catch(() => {}); // (Without it, then: the ride goes on.)
  if (process.env.NODE_ENV === 'development')
    (window as unknown as { __sectionAudio?: unknown }).__sectionAudio = { bus, buffers, loops: () => ({ water, rattle }), playSectionSound, sectionImpact };
}

function driveLoop(ctx: AudioContext, loop: Loop, level: number, cutoff: number, rate: number, attack: number, dt: number) {
  const buffer = buffers[loop.name];
  if (!buffer || !bus) return;
  const now = ctx.currentTime;
  const target = level * LEVEL[loop.name];
  if (target > 0.001 && !loop.source) {
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(loop.filter);
    source.start();
    loop.source = source;
  }
  if (!loop.source) return;
  if (Math.abs(target - loop.level) > 0.002) {
    loop.gain.gain.setTargetAtTime(target, now, attack);
    loop.level = target;
  }
  if (Math.abs(cutoff - loop.cutoff) > loop.cutoff * 0.02) {
    loop.filter.frequency.setTargetAtTime(cutoff, now, 0.12);
    loop.cutoff = cutoff;
  }
  if (Math.abs(rate - loop.rate) > 0.004) {
    loop.source.playbackRate.setTargetAtTime(rate, now, 0.15);
    loop.rate = rate;
  }
  loop.quiet = target > 0.001 ? 0 : loop.quiet + dt;
  // (Stopped once it's been silent a while: nothing running away from the sections.)
  if (loop.quiet > 2) {
    loop.source.stop();
    loop.source.disconnect();
    loop.source = null;
    loop.quiet = 0;
    loop.rate = 0;
  }
}

/**
 * Each frame near the sections: `flow` the water's rush (0 at rest in it, 1 at speed: a low wash stays, in the tunnel, `inWater`), `steps`
 * 0 to 1 how hard the steps are rattling, `speed` over the place's own cruising speed.
 */
export function updateSectionAudio(dt: number, inWater: boolean, flow: number, steps: number, speed: number) {
  const ctx = musicContext();
  if (!ctx || !water || !rattle) return;
  // (Nothing playing, nothing wanted: away from the sections.)
  if (!water.source && !rattle.source && !inWater && steps < 0.001) return;
  // At rest in the water, or up the wall out of it, it's a low wash; riding through it opens right up.
  const level = inWater ? 0.2 + 0.8 * flow : 0;
  driveLoop(ctx, water, level, 700 + 15000 * flow * flow, 0.86 + 0.2 * Math.min(1.4, speed), 0.18, dt);
  // (Quick: it stops dead between one flight and the next.)
  driveLoop(ctx, rattle, steps, 16000, 0.85 + 0.25 * Math.min(1.2, speed), 0.035, dt);
}

/** Plays one of the section's sounds once. `pan` -1 left to 1 right. */
export function playSectionSound(name: SectionSound, strength = 1, pan = 0) {
  const ctx = musicContext();
  const buffer = buffers[name];
  if (!ctx || !bus || !buffer) return;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  const gain = ctx.createGain();
  gain.gain.value = LEVEL[name] * strength;
  source.connect(gain);
  if (pan) {
    const panner = ctx.createStereoPanner();
    panner.pan.value = pan;
    gain.connect(panner);
    panner.connect(bus);
  } else gain.connect(bus);
  source.start();
}

let nextMetal = 0;
/**
 * For the stairwell's moving pieces, as each one lands or swings to: `metal` (a beam, a shutter: goes round the five takes), `collapse` (a
 * flight going), `debris` (its chunks). `strength` 0 to 1, a little for one that's further off.
 */
export function sectionImpact(kind: 'metal' | 'collapse' | 'debris', strength = 1, pan = 0) {
  if (kind === 'collapse') playSectionSound('concrete-collapse', strength, pan);
  else if (kind === 'debris') playSectionSound('concrete-debris', strength, pan);
  else {
    nextMetal = (nextMetal + 1) % 5;
    playSectionSound(`metal-impact-${(nextMetal + 1) as 1 | 2 | 3 | 4 | 5}`, strength, pan);
  }
}
