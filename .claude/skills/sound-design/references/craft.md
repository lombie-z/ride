# Sound design craft

Marks: [S] sourced, [T] tested here, [J] practice and judgement. A lot here is craft knowledge, where the evidence is that it works; it's labelled as such.

Standing references: Gordon Reid's *Synth Secrets*, 63 parts in Sound On Sound, free: https://www.soundonsound.com/series/synth-secrets-sound-sound (subtractive, filters, envelopes, FM, percussion recipes). Farnell, *Designing Sound*, MIT Press 2010, for synthesising things from their physics. Roads, *Microsound*, MIT Press 2001, for grains. These were found to exist, but not read for this. Chowning 1973 for FM.

## Synthesis, and where to reach for it in this rig [J]

**Subtractive.** A bright source through a moving filter. Shape: the filter envelope gives the attack its bite, not the amp. Keytrack up for consistent tone. Syntakt SY RAW (analog) through its filter and analog FX; Hydrasynth Filter 1 with ladder or MS-20.

**FM.** Spectrum comes from ratio and index. Integer ratios are harmonic; non-integer are inharmonic. Index (modulator level) sets brightness, so **an envelope on the modulator is the timbre's envelope**; a decaying index sounds like a struck thing. Bell: ratio about 1:1.41 or 1:3.5, fast attack, long decay, index decaying faster than the amp. Glass: higher ratios, shorter, low index. Bass with click: 1:1, a short bright index burst, then pure. Feedback gets from saw to noise. opsix does all this per operator, with Fixed-Hz operators as the unmoving partials. Hydrasynth FM-Lin uses any wave as carrier or modulator. Syntakt: SY TONE, BD FM, SD FM, SY DUAL VCO's FM.

**Wavetable.** Move through a table with an envelope or LFO; the sound's change over time is the point. Hydrasynth's WaveScan through 8 of 219 waves, then Mutants on top. Slow scan on a pad; fast scan on an attack.

**Granular.** Many short overlapping pieces of a sound; grains of about 1-100 ms. It gives time-stretch without pitch and turns any sound to a cloud. None of the synths has a full engine (opsix's Grain Shifter is the nearest). For real clouds, process a capture afterwards in code or the user's DAW, or schedule grains from an AudioBuffer in Web Audio. Ask before installing tools for it.

**Ring mod.** Sum and difference of two signals: a pitched source turned metallic, unmusical and alarmed. Instantly useful at 40-100 Hz for roughness.

**Wave folding.** Overtones that bloom with level, so velocity or an envelope controls brightness. opsix Wave Folder.

**Sync.** Hydrasynth OSC Sync: tearing sweeps; put an envelope on the ratio.

**Noise.** Filtered with a moving resonance: wind, sand, steam, whoosh, breath. Different colours matter: Hydrasynth has seven. Pink for air, grey for neutrality, red and brown for rumble.

## Layering: transient, body, tail

A common breakdown: an attack carrying the click, a body, a tail carrying decay and room, plus a sweetener. [S: https://sounddesign.irpr.agency/glossary/layering/] A shooter's gun can have transient, body, sub, mechanical and tail layers controlled separately, and small timing shifts between transient and body change perceived size. Multiple tails let you vary the space. [S: https://www.liortega.com/post/first-person-shooter-gun-sound-design] Layers should sit in complementary ranges; align the transients. [S: IRPR above]

Rules of thumb: [J]
- Transient under 20 ms, 2-8 kHz, reads through anything. Often noise or a short FM burst.
- Sub 40-80 Hz: one pitch, mono, short envelope. Only one layer owns it.
- Body 100-800 Hz: the identity of the thing.
- Tail: sold separately as reverb or a real decay. Mid-high band, so it doesn't pile up on the low end.
- A short pre-echo or reverse swell of 50-200 ms before a hit gives anticipation.
- High-pass everything that isn't the low layer.

## Envelopes

- Percussive decays are exponential. A linear decay sounds fake and truncated.
- A hard attack clicks: a 1-2 ms ramp if it isn't wanted. A click is sometimes the transient you wanted.
- Attack time reads as distance and softness; 50-500 ms stops it reading as an event.
- Shorter than about 50 ms, a sound reads as a click with a colour, not a pitch. Under 100 ms is about the shortest thing with a clear pitch, so UI tones need a hair more.

## Spectral balance and masking

- Masking is mostly within critical bands and spreads upward: a loud low sound hides quieter sounds above it, more than the reverse.
- Don't EQ everything to fit; give the thing that must read a slot, and take that slot out of whatever's competing while it plays.
- Rough ranges: sub 20-60, bass 60-200, low mid 200-500 (where mud lives), mid 500-2k (identity), upper mid 2-5k (attention, and fatigue), air 8k+.
- The ear's most sensitive at 2-5 kHz: alarms and UI live there, and it's what tires people. [J]
- Listen on the worst target too: laptop speakers roll off under about 150 Hz, so give bass a harmonic.

## Mixing a game

**Buses.** `master <- limiter <- [music, sfx, ui, ambience]`, each with its own gain, plus sub-buses for bike and world. Lets you duck groups.

**Priority.** A typical order is voice, player SFX, enemy SFX, ducked music, ambience; duck music 6-9 dB under a key sound. [S: general listing, https://skills.sh/vudovn/antigravity-kit/game-audio; treat as secondary] Ride has no voices: rhythm cues first, then player-action SFX, then danger, then music, then world.

**Ducking in Web Audio.** No sidechain node needed: when an important sound starts, `music.gain.setTargetAtTime(0.5, t, 0.02)`, then back with a slow constant. Attack fast, release slow (200-600 ms). Musical pumping from the kick can be baked in on the stem.

**HDR mixing.** Rather than fixed ducks, a whole-game loudness window where the current loudest sounds decide what's audible: loud sounds make soft ones vanish, and they return when it's quiet. Battlefield: Bad Company's mixer ran on it. [S: https://www.ea.com/frostbite/news/how-hdr-audio-makes-battlefield-bad-company-go-boom, https://designingsound.org/2013/06/21/finding-your-way-with-high-dynamic-range-audio-in-wwise/] Overkill for Ride, but the idea's useful: rate sounds by loudness and don't mix against each other by hand.

**Voice limits.** Web Audio has no virtual voices, so manage it: per sound and per category, cap instances (3-4 of any one thing, 16-32 in all), steal the oldest or quietest. Reuse nodes where you can; a burst of one-shots allocates. Skip sounds below an audibility threshold. [J]

**Repetition.** 3-5 variations for frequently triggered sounds [S: skills listing above], plus small pitch (±1 semitone or less) and gain variation. The hive's numbers want their pitches kept exact; vary brightness there instead. [J]

**Master.** A DynamicsCompressorNode set as a limiter catches accidents; it has lookahead and adds tail. Don't lean on it for level. [S: Web Audio spec] Mix so it barely moves.

**Stereo.** Keep below 120 Hz mono. A wide stem can vanish on a phone speaker summing to mono; check. [J]

## UI sound

- Short, quiet, consistent. Under 100 ms where possible; pressing it 200 times must not annoy.
- The palette should belong to the world: UI for Ride comes from the zone's own tonal centre, so it never clashes with the music.
- Direction means something: rising confirms, falling cancels or fails. Blumstein's result on downshifts supports the last. [S: theory.md]
- Different actions differ in contour and timbre, not just pitch.
- Nothing plays when nothing happened.

## Loudness and fatigue

Fatigue comes from sustained energy at 2-5 kHz, from never having quiet, and from compression with no dynamics. Give the ear rest: a zone with drums at the same level for ten minutes is more tiring than the same music with dropouts. Bernardi's silent pauses lowered heart rate and breathing. [S: theory.md] Targets are in workflow.md.

## SFX that read at speed

At 56 m/s a roadside thing is past in under a second.

- A distinct contour and attack, instead of a detailed sound. It has a tenth of a second to say what it is.
- Exaggerated pitch movement.
- Spectral slot free of the engine: high transient, or a sub thump.
- Lead with anticipation before an event you can predict: gates, traps. Sound tells you when, the picture where.
- Prefer ones whose shape matches the action: a pull is a rising stretch, a release a falling snap.

## Speed

**Engine.** 3-4 loops recorded at speed bands, crossfaded by speed, each with a little playback-rate movement (±20% or so before it sounds like a chipmunk), is a common approach. Add load: throttle-on brighter than coast. For a bike with a heart, that's mixed with a heart layer that follows `drive.beat`. [J]

**Wind and road.** Filtered noise; cutoff and gain rising with speed: `f ~ 400 Hz + 60 Hz x speed`, gain in dB proportional to `log(speed)`. Road noise varies with surface: wet, sand, tile. It's a strong cue and cheap, and it's what stops when airborne. [J]

**Doppler.** The panner's own Doppler is gone from the spec: only ABSNs were pitched, not smoothly. [S: https://github.com/WebAudio/web-audio-api/issues/455, https://developer.mozilla.org/zh-CN/docs/Web/API/AudioListener] `setVelocity` isn't on PannerNode in this Mac's WebKit. [T] Do it by hand:

```ts
// Closing speed along the line between them, in m/s; positive when approaching.
const toSource = source.pos.clone().sub(listener.pos).normalize();
const closing = listener.vel.dot(toSource) - source.vel.dot(toSource);
const c = 343;
abs.playbackRate.setTargetAtTime(c / Math.max(c - closing, 1), ctx.currentTime, 0.02);
```

For a stationary thing passed by at speed v, pitch goes from c/(c-v) to c/(c+v): [J: arithmetic]

| Speed m/s | In Ride | Pitch drop over the pass |
|---|---|---|
| 32 | green | 3.2 semitones |
| 38 | chrome | 3.9 |
| 44 | hive | 4.5 |
| 50 | desert | 5.1 |
| 56 | core | 5.7, near a tritone |
| 58.8 | | exactly a tritone |
| 343 | Mach 1 | |
| 420 | ghost | past the speed of sound: nothing behind can reach you |

**Spatial in Web Audio.** PannerNode's panning models are equalpower and HRTF; HRTF is stereo-only and for headphones it's the convincing one, at a CPU cost. Listener has position and orientation params, all a-rate. [S: spec] Use `equalpower` by default, HRTF for a few things that matter; use StereoPanner for road-side pass-bys. A ConvolverNode with a short impulse per zone (tile, dune, nave) makes everything sit in a place; 1, 2 or 4 channels, and it normalises by default. [S: spec] Record an impulse by capture of a reverb's tail on the hardware from a short click: Hydrasynth's long reverbs or the Syntakt's. [J]
