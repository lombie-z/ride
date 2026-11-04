# Adaptive music and Web Audio timing

Marks: [T] tested on this Mac, [S] sourced, [J] judgement.

## The vocabulary

- **Vertical layering**: music composed as synchronised layers, each switched by the game. [S: https://www.mixonline.com/recording/game-composer-winifred-phillips-429243]
- **Horizontal re-sequencing**: short segments that loop, branch or transition. [S: https://etheses.whiterose.ac.uk/27365/1/Chapters/Chapter%203/Chapter%203.html, after Collins, *Game Sound*, and Phillips, *A Composer's Guide to Game Music*]
- **Stingers**: short musical events triggered by the game. [S: above]
- **Quantised transitions**: both middleware tools sync to a grid and cues. FMOD: quantised transition regions jump only on specified notes or bars. [S: https://fmod.com/docs/studio/authoring-events.html] Wwise users pick Next Bar, Next Cue and so on, per transition; Next Cue suits sections where timing can't be predicted, and transitions at phrase ends are common. [S: https://www.audiokinetic.com/en/community/blog/the-sound-design-of-clocker-part2/, https://www.audiokinetic.com/en/community/blog/from-constraint-to-creativity-the-music-design-of-hell-is-us/] A transition across a tempo change needs care. [S: https://www.audiokinetic.com/qa/12957/transition-to-the-next-beat-of-a-track-with-a-different-tempo]

The usual combination: re-sequencing for big state changes, layers for intensity inside a state. [S: https://abratabia.com/web-game-audio/dynamic-game-music.php] Start with synchronised stems with independent gains; it's the cheapest system that works. One large combat score was reported as layers and loops recombined on the fly; that's secondhand. [S: https://everythingisnoise.net/features/sound-test-doom-2016/; talk: GDC 2017 "DOOM: Behind the Music"]

**Player actions on the grid.** Rez plays hits and shots as notes on the music's grid: an early note waits for its slot. Frequent small sounds suit a fine grid (16ths), and big ones are gated: the crash needs eight shots. Quantising big sounds strictly adds delay that weakens immediacy, so give instant visual feedback and delay only the musical sound. [S: https://www.gamedeveloper.com/design/planckogenesis-part-i-quantizing-events, with history at https://gamedeveloper.com/audio/oral-history-of-i-rez-i-recounts-a-marriage-of-game-and-music]

The rule I'd use: [J]
- A physical action (throttle, release, jump, impact) sounds at once, unquantised.
- Its **musical consequence** lands on the next grid.
- In a rhythm section the player's timing is the point, so never quantise: play the note when clicked, and let them hear how close they were.

## What runs in code, what's a file

Hardware gives you recordings. Things that must respond continuously go in code. [J]

| Do it as | For |
|---|---|
| Recorded stems and stingers | music, one-shots, tails, anything whose character is the synth |
| Recorded loops, playback rate moved a little | engine, wind |
| Web Audio nodes | Shepard/Risset risers driven by a game value; level, filter and pan; roughness (a GainNode modulated by a 70 Hz oscillator); Doppler; ducking |

## Clocks

`audioContext.currentTime` is the only clock to schedule against; timers and frames jitter by tens of milliseconds. The standard pattern: a timer wakes about every 25 ms and schedules everything due in the next 100 ms. Long look-ahead delays reactions, short risks gaps. Visuals follow the audio clock via requestAnimationFrame. [S: Chris Wilson, *A Tale of Two Clocks*, https://web.dev/articles/audio-scheduling]

```ts
class Conductor {
  bar0 = 0;                 // context time of bar 0
  constructor(public ctx: AudioContext, public bpm: number, public beatsPerBar = 4) {}
  beatLen() { return 60 / this.bpm; }
  nextGrid(subdiv = 1, after = this.ctx.currentTime + 0.05) {
    const step = this.beatLen() / subdiv;
    return this.bar0 + Math.ceil((after - this.bar0) / step) * step;
  }
  nextBar(after?: number) { return this.nextGrid(1 / this.beatsPerBar, after); }
}

// A stem: all of a section's stems share one start time and the same frame count, in a manifest.
function playLoop(buffer: AudioBuffer, frames: number, when: number, out: AudioNode) {
  const s = ctx.createBufferSource();
  s.buffer = buffer;
  s.loop = true;
  s.loopStart = 0;
  s.loopEnd = frames / buffer.sampleRate;   // never buffer.duration: AAC adds frames (workflow.md)
  s.connect(out);
  s.start(when);
  return s;
}

// Fade a layer on a beat: exponential towards the target, quick enough to feel on the beat.
gain.gain.setTargetAtTime(target, conductor.nextGrid(1), 0.02);
```

Start all of a section's stems silent and bring up gains. Layers must be running to be in sync, and a looping ABSN costs little while its gain's at zero. Details: [S: https://webaudio.github.io/web-audio-api/] `playbackRate` and `detune` on ABSN are k-rate; `decodeAudioData` resamples to the context's rate.

Create or resume the context in a user gesture. [S: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices] In Ride that's the first click on the pill. iOS and tab switching can suspend it: listen to `statechange`.

**The game must still run with sound off or a blocked context.** Audio can be master only when it's running; keep the frame clock as a fallback. [J]

## Transitions

- **Into a section on a bar**: `nextBar()`, start new stems there, drop old gains over one beat.
- **Between tempos**: there's no shared grid. Best is a bridge that has none: a pad or noise bed that's tempo-free, crossfaded by distance, while old drums stop on a bar and new drums start on their first bar when the road's join passes. [J]
- **Pivot note**: hold one pitch common to both keys across the change.
- **On a musical event**: a stinger scheduled on the next beat, with a pickup if there's time.
- **Immediate**: a hard cut with a big impact covers anything; don't do it often.

## Boss phases

A common scheme: [J]

- Each phase has its own loop set and its own intensity layers.
- Damage removes or damages layers rather than adding them: the boss's music breaks up as it does.
- Move between phases on a bar, on a cue, with a short transition segment per phase pair. Keep a one-bar fill ready.
- Death: cut everything on the beat, one last sound, silence, then the ambience returns.

## Rhythm sections: audio as the clock

The beat a player hears isn't the audio clock's now: it's later by the output latency. Pressing on the heard beat means the press's context-time equivalent is that much late, unless corrected. Bluetooth can add 100 ms or more. [S: https://bugnet.io/blog/bug-tracking-for-rhythm-games]

```ts
// What was being heard when the event happened, in context time.
function heardAt(e: PointerEvent) {
  const { contextTime, performanceTime } = ctx.getOutputTimestamp();
  return contextTime + (e.timeStamp - performanceTime) / 1000;
}
// off > 0: late. calibration: the player's own offset (see below).
const off = heardAt(e) - noteTime - calibration;
```

`getOutputTimestamp` gives the frame being rendered by the output device, and `performanceTime` the estimate of when. [S: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/getOutputTimestamp] `outputLatency` is an estimate of the time from the graph to the device. [S: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/outputLatency] Both, and `baseLatency`, exist in WebKit (macOS 26.3) and in Chromium 152; their values weren't checked against measurement. [T]

Fallback: `ctx.currentTime - (ctx.baseLatency + ctx.outputLatency)` compared with a `performance.now()` pair sampled together.

Draw rings from the same time, so eyes and ears agree: `const t = heardNow(); radius = f(noteTime - t);`

**Calibration.** Reported latencies are estimates; players differ. One developer's approach: tap with no sound on the tap (scheduled sounds would carry latency and skew it), keep just 4 taps, see the offset, adjust. [S: https://rhythmquestgame.com/devlog/10.html] Another way, for a game with a rhythm section before the hard one: keep the mean offset of a player's good hits and use it as calibration silently; ask only if it's large. Save it per browser in localStorage. [J]

**Windows.** One tutorial's example is 20/50/100 ms; that's not a standard. [S: https://seanking11.github.io/gamebootcamp/modules/32-rhythm-game] A forgiving casual range is ±45 ms for best and ±100-130 for good; Ride's hive currently uses ±110 and ±270, which is generous, and right for a mechanic met while riding at speed and with a mouse. [J; numbers from lib/rhythm.ts]

**Hit sounds.** Play them on click (`start()` with no time). They reach the ear an output latency late, which can't be avoided, so keep them confirmation and let the music be the beat. Some rhythm games pre-schedule the sound for the note the player's about to hit instead; calibration screens stay silent on tap for the same reason. [S: Rhythm Quest above]

## Memory and loading

Decoded stereo at 48 kHz is 384 kB per second. Layers are 35 s, so five stems are ~65 MB decoded. Keep it down: [J]

- Mono wherever it won't be missed (bass, kick, sub, many beds).
- 8-bar stems rather than 16 if the music tolerates it.
- Load and decode a zone's audio as the zone is chosen on the map, and free the last one's after the transition.
- Long ambience can stream via an audio element, losing sample accuracy but needing no decode.
