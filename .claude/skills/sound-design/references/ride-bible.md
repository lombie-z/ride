# Ride: sound bible

The plan for how Ride sounds. Nothing here's been heard yet: it's a score on paper, written from the code and concept art in November 2026. Patches are starting points. Theory behind it is in theory.md, synth facts in hardware-*.md.

**Facts from the code** are marked (code), with the file. **All musical choices are judgement**; "Taste" lines point out where one could easily go another way. Pitches: C4 = MIDI 60 (the Syntakt's manual calls that C5).

## Contents

1. The whole ride: plan in one table
2. The harmonic idea
3. The motif
4. Tempo
5. Synth jobs
6. Green city
7. Chrome city: the surge
8. Coral hive: the angel numbers
9. Data desert: slingshot and jumps
10. The core: lab, servers, ghost
11. The boss
12. The bike, and between zones
13. UI
14. Stems and files
15. Where to start
16. Taste: what could go otherwise

## 1. The whole ride

| Zone (code: lib/course.ts) | Centre | Mode | Tempo | Meter | Cruise m/s (code) | Colour | Sound in a phrase |
|---|---|---|---|---|---|---|---|
| Green | E | Phrygian | 80, half-time | 4/4 | 32 | night, rain, green smog | a church in the rain with a machine in the crypt |
| Chrome | G | Lydian | 95 | 4/4 | 38 | chrome, sunset, monorails | beautiful and slightly too clean |
| Hive | Db | Phrygian dominant, just intonation | grid 110; heart 73 rising to 115 | free over 4/4 | 44 | bone, coral, a glowing heart | an angel choir inside a body |
| Desert | Bb | whole tone over a Bb-F pedal | 125 | 7/8 | 50 | sand, dead servers, a storm | machines dying in the heat |
| Core | E | Locrian, then Phrygian | none, then 140 | 4/4 | 56 | white tile, green tanks, red lamps | it wakes up |
| Boss | E and Bb at once | [0167] | 140, 140, 160 | 4/4, 7/8, 4/4 | | red | you and it, on the same clock |

## 2. The harmonic idea

**The four tonics are E, G, Db, Bb: a minor-third axis, all from one octatonic** (E F G Ab Bb B Db D). The route is:

```
E  --m3 up-->  G  --tritone-->  Db  --m3 down-->  Bb  --tritone-->  E
```

- E to G is the small step: E minor's relative major, then Lydian lifts it.
- G to Db and Bb to E are tritone moves, the "beyond normal human experience" ones (Murphy, theory.md). They're at the two places the ride leaves the ordinary: into the living hive and into the core.
- The ride comes home to E, which matches the picture: the core is green-lit, like the first city. It's the same place underneath.

## 3. The motif: two heartbeats

The code's heart has a first peak at phase 0 and a second, 0.6 as strong, at phase 0.28 of its period (code: components/three/ride.tsx). That's the motif's rhythm: **lub-dub, lub-dub**, each dub a sixteenth after its lub, with the rest of the beat empty.

```
Pitch:    0  +1    |   +6  +7        in E:  E F | Bb B
Rhythm:   x x.     |   x x.          two lub-dubs, a tritone apart
```

Each dub is a semitone above its lub. The second pair sits a tritone up, and its top note lands on the fifth, so the phrase moves from unease to a hard sort of arrival. The set {E F Bb B} is its own tritone transposition, so the motif in E and the motif in Bb use the same four notes (theory.md). It's generic material, nobody's tune.

| Where | Form | In | How |
|---|---|---|---|
| Green | original, slow: one pair per bar | E F, Bb B | low FM bell tolling, an organ's pedal under it |
| Chrome | semitone widened: 0 +2 | +6 +7 | G A, C# D | glassy FM arpeggio's top notes; the tritone's now Lydian's bright #4, resolving to the fifth. Same contour, false comfort |
| Hive | 0 +1 | +4 +5 | Db D, F Gb | choir, pure tuning; the tritone has softened to a fourth, sung |
| Desert | fragments, first pair only, in dead-modem tones | Bb B, later E F | it's the same four notes as green, heard wrong. Drops out mid-phrase |
| Core | original, full force, harmonised | E F, Bb B | pulsed polychords |
| Ghost | retrograde, double time | B Bb, F E | digital, reversed, and dub before lub |
| Boss | canon at the tritone | E F Bb B, with Bb B E F half a bar later | all four notes always sounding |
| End | one pair, then home | Bb B, then E and B | the only open fifth with nothing against it in the whole ride |

## 4. Tempo

**Tempo = 2.5 × the zone's cruising speed**: 80, 95, 110, 125, 140. It rises with the ride, in steps; continuous speed goes to the engine and wind.

Frame counts for 48 kHz (`audio_tools.py framing` gives any other):

| Tempo | Bar | Frames per bar |
|---|---|---|
| 80, 4/4 | 3.0 s | 144,000 |
| 95, 4/4 | 2.526 s | 121,263.16 |
| 110, 4/4 | 2.182 s | 104,727.27 |
| 125, 7/8 | 1.68 s | 80,640 |
| 140, 4/4 | 1.714 s | 82,285.71 |
| 140, 7/8 | 1.5 s | 72,000 |
| 160, 4/4 | 1.5 s | 72,000 |

**The hive's heart.** Period is `HEART.period - HEART.quicken × max(pump, landed/6)`, 0.82 s less up to 0.3 (code: lib/ride.ts, lib/rhythm.ts):

| Circles landed | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| Period, s | 0.82 | 0.77 | 0.72 | 0.67 | 0.62 | 0.57 | 0.52 |
| BPM | 73.2 | 77.9 | 83.3 | 89.6 | 96.8 | 105.3 | 115.4 |

At 110 BPM on the grid, 73.3 is exactly two heartbeats to three beats. So **the heart starts in 2:3 against the music and accelerates until, at 666, it's caught up with it.** That's why the hive is at 110. A small code change would make it exact: `HEART = { period: 0.8182, quicken: 0.2727 }` gives 73.3 and 110. That changes game feel, slightly, so it's the user's call. It works either way, since the catching-up is what's heard.

## 5. Synth jobs

| Synth | Job | Why |
|---|---|---|
| **Syntakt** | drums, bass, glue; anything struck, via SY TOY; dying data via SY BITS and SY CHIP. And the capture path | analog drums and FX block, a sequencer with per-track length and Euclid for polymeter |
| **opsix** | machines: bells, glass, alarms, ring, metal, the creature | inharmonic spectra at will, ring mod, Filter FM, folders, FIXED Hz operators, per-voice decimator |
| **Hydrasynth** | living things: choirs, organ, pads, breath, storms, the boss's voice | Mutants, Vowel filter, polyphonic aftertouch, long reverb and Freeze, and the only microtuning |

Rule of thumb: machine = opsix, body = Hydrasynth, floor = Syntakt.

## 6. Green city (E Phrygian, 80)

**Picture**: gothic towers, green smog, rain, a wet freeway; a biotech bike waits. It's the landing, and the longest anyone may stay.

**Harmony**: E pedal; open fifth E-B in organ, F as the one wrong note; no third at first, then G for E minor when the drums arrive. Bb only in the motif, so it stands out.

**Before the ride**: rain (placeholder rain-loop), a far low drone, a bell every few bars. No beat at all. The first press of the pill should be a quiet thump, then the bike's heart once, then drums on the next bar when speed passes a threshold, not at the press. (feature: `start`, boost 0; code: lib/course.ts)

| Stem | Synth | Patch start |
|---|---|---|
| Rain and city | placeholder, then field-recording-like noise from Hydrasynth (pink noise, BP filter, slow LFO) | |
| Organ-choir bed | Hydrasynth | WavStack on OSC1 and 2 with organ-like waves, Filter 1 Vowel slow-moving, long reverb, Macro 1 = Vowel, Macro 2 = reverb. Stereo. Hold E2, B2, E3, B3. F4 now and then |
| Bell (motif) | opsix | 2 carriers, ratio 1:1 and 1:2.76 (inharmonic), modulators 1:1.41 with decaying index; long decay. E2 and E3 together. Shimmer or Spring Reverb in FX |
| Bass | Syntakt, SY RAW | two saws, DET slightly, OVER some, filter low. E1 (MIDI 28) on the first beat of a bar, a falling F-to-E on the fourth bar |
| Drums | Syntakt, BD HARD, SD FM, CH METALLIC | half-time: kick on 1, snare on 3, sparse hats with micro-timing. All through the analog FX block with drive |
| Heart | Syntakt, BD SILKY plus BD FM a sixteenth later | follows `drive.beat`, at the bike. Quiet here |

Half-time at 80 is a slow walk over a fast bike. If it fails to feel like speed, double the hats; the speed's in the engine and road.

## 7. Chrome city (G Lydian, 95): the surge

**Picture**: chrome and glass, a violet-orange sunset, palms, monorails, hover traffic, a chrome bike with a heart in it, black ooze at the edges. Everything's clean and something's wrong.

**Harmony**: vamp G to A/G (I to II over a G pedal, Lydian's signature), with C# on top. Occasional Em. The black ooze gets one low Db under a bright chord, once in 16 bars: the tritone under the shine, and a preview of the hive.

| Stem | Synth | Patch start |
|---|---|---|
| Glass arpeggio (motif on top) | opsix | algorithm with carriers at ratio 1 and 3.5 (tine), tri wave for softness, short decay, velocity to index. 16ths. Delay (BPM) in FX |
| Pad | Hydrasynth | WavStack, slow WaveScan through glassy tables, Chorus Pre-FX; a bright, wide wall |
| Bass | Syntakt, SY SWARM low or SY RAW | clean, round, sidechained in feel |
| Drums | Syntakt, BD MODERN, CP VINTAGE, CH CLASSIC | a four-on-the-floor pulse, hats in 16ths; early-2000s glossy trance-pop weight |
| Chords | Syntakt, SY CHORD | stabs on offbeats through delay |
| City sparkle | opsix, SY TOY | high pings as the windows and glass towers pass |

### The surge (code: lib/trace.ts, ride.drive.surge)

A press sends a star wandering; hold on it and `trace.level` builds 0 to 1 over 11 s (`TRACE.build`). Drop off for more than 0.28 s (`TRACE.grace`) and it's lost; let go and it's over.

Eleven seconds at 95 is 17.4 beats: don't try to hit a bar. Drive it from `level`, in code:

| Level | What's heard |
|---|---|
| start | a rising ping on the press; the arpeggio's filter starts to open |
| 0 to 1 | **a Risset riser**: 8 octave-spaced sines under a Hann envelope in log frequency, cycling at a rate rising with level. It can't run out of pitch, so it holds for any length of build. Web Audio, driven directly |
| 0.25 | quantised to the next beat: hats double |
| 0.5 | arpeggio to 32nds, Mutant OSC Sync sweep opening on a Hydrasynth layer |
| 0.75 | chord vamp stops, G pedal only, riser on top. The drums thin out to kick |
| 1 | a hit on the next bar: full G major with C# held, everything open, until they let go |

| Event | Sound |
|---|---|
| Pointer on the star | a faint shimmer |
| Off the star (`trace.on` false, grace running) | **two shimmer sines detune apart, beats rising from 4 to 20 Hz over the 0.28 s**: a warning you can hear without looking |
| Let go | a soft fall, an octave, with reverb |
| Lost (`endTrace(true)`, red trail) | everything down a tritone in 300 ms (tape-stop on a stem, playback rate), one dry low Db |

Taste: the build could instead be a stack of pre-recorded stages. A riser's cheaper, and it's the honest answer to a build with no fixed length.

## 8. Coral hive (Db, heart): the angel numbers

**Picture**: pink dusk, bone arches, coral, honeycomb windows lit gold, tar running down, and a huge glowing heart in the plaza. Lovely and appalling.

**Tuning**: Hydrasynth holds a scale with Db as tonic, made in Scala, sent as MTS (asks first, since it's a change to the device):

| Degree | Db | D | F | Gb | Ab | A | B (Cb) |
|---|---|---|---|---|---|---|---|
| Ratio | 1/1 | 16/15 | 5/4 | 4/3 | 3/2 | 8/5 | 7/4 |
| Cents | 0 | 112 | 386 | 498 | 702 | 814 | 969 |

The seventh is the harmonic 7/4, flat of equal temperament by 31 cents. The chords stop beating, and that stillness against the ordinary tuning elsewhere is the point. Syntakt and opsix stay in equal temperament, so keep them to Db and Ab, or to unpitched, near the choir. Taste: the 7/4 could be 9/5 for a sharper seventh. Or start from the preset "W. Carlos Harmonic" or "Harmonic A 1-60" and hear them.

| Stem | Synth | Patch start |
|---|---|---|
| Choir bed | Hydrasynth | Filter 1 Vowel, Mutants in Harmonic mode, so single partials sing; slow WaveScan; reverb very long; Freeze for transitions. Poly aftertouch on each voice into Vowel, so notes in a chord swell separately (scripted as polytouch) |
| The grid at 110 | Syntakt, SY TOY | FORM at bone or wood, short; very quiet ticks in 16ths, the hive's insects. Coral knocks on an Euclidean 5/16 and 7/16 |
| Tar | opsix, Filter FM | low, slow, wet: bubbling, sparse |
| Heart | Syntakt, BD SILKY + BD FM, plus Hydrasynth sub | the visible thing in the plaza. Louder here than anywhere. It follows the code's phase |

### The run (code: lib/rhythm.ts, components/rhythm-overlay.tsx)

Six circles, 111 to 666, each landing on a heart beat, ring closing over `RHYTHM.approach` = 0.8 s; perfect within 0.11 s, good within 0.27 s. Gold at 111 to blood at 666. The clean run makes a stronger boost.

Each hit adds a note to a chord. **The chord is the score.** Hits are never quantised.

| Number | Note | MIDI | Chord so far | Colour |
|---|---|---|---|---|
| 111 | Db3 | 49 | root | gold |
| 222 | F3 | 53 | third | gold |
| 333 | Ab3 | 56 | triad | warm |
| 444 | B3 (7/4) | 59 | dominant seventh, pure | warm, strange |
| 555 | D4 | 62 | adds the b9 | dark |
| 666 | G4 | 67 | adds the tritone. Top note | blood |

| Event | Sound |
|---|---|
| Ring closing | a soft pitch-rising tick into the landing; ears can catch what eyes miss at speed |
| Perfect | its note in choir plus a clean high FM bell (opsix), sustaining. It stays till the end of the run |
| Good | the same choir note, no bell |
| Miss | **the note isn't there**: a dry, sour knock in its place, and a hole in the chord. `rhythm.glare` raises the roughness layer (below) |
| Wrong moment (`glare` up by 0.25, no circle) | a dull wet click, the eyes' attention |
| 666 lands, boost | the chord as played, plus a Db1 sub drop and a big reverb tail. A clean run's six-note chord is overwhelming; a messy one is audibly thin. Heart doubles in level |
| First run, teaching (`rhythm.teaching`, `rhythm.slow` to 0) | the heart and everything scheduled on it stops as the ride stops. Only the bed's held tail, ducked. Silence does the teaching. Hit: heart starts at once |

The heart's sounds must be scheduled from the same phase as the visuals. See the audio-clock note in section 15.

### Eyes (code: rhythm-overlay.tsx, `rhythm.glare`, boost-pod eye)

- **Opening on a boost**: wet lid (placeholder eyes-open) slowed; a whispering choir swells, in Hydrasynth Vowel over noise, panned to all four corners. They hold while the boost lasts, close as it runs out.
- **Glaring at a miss**: a high tone at about 1.2 kHz (Gb or G) with AM at 70 Hz, which sits in the scream roughness band (theory.md section 4). Depth = `glare`. Web Audio: GainNode, an oscillator into its gain. No sample needed. It's disturbing by design, so keep it short and well below the mix.
- **The boost button's eye blink**: tiny lid click, panned to the pod. Very quiet.

## 9. Data desert (Bb, whole tone, 125 in 7/8)

**Picture**: orange sand, a storm wall with lightning, dead server towers and cracked terminals ("AWAITING INPUT"), a fortress ahead. Rusted bike. Dry and huge.

**Harmony**: a Bb-F pedal, for a floor. Over it the whole-tone scale (Bb C D E F# G#), with no perfect fifth inside it and nothing to lean on: heat haze. E, the tritone from Bb, keeps showing up on top, and it's the next zone's centre.

**Meter**: 7/8 grouped 4+3, kick on 1 and 5. It limps. It also sets up the boss. Fans as polymeter: a 7-step and a 5-step tick against it, realigning every 35 eighths.

| Stem | Synth | Patch start |
|---|---|---|
| Storm | Hydrasynth | noise (red, brown), Filter 1 LP 8 Pole, slow LFOs on cutoff, stereo; a whistle from resonance in gusts |
| Pedal | Syntakt, SY RAW | low Bb and F, distorted, breathing |
| Drums | Syntakt, BD FM, RS HARD, CH METALLIC, CP VINTAGE | dry, no reverb, the analog drive hard. Micro-timing, retrigs like stutters |
| Data | Syntakt, SY BITS, SY CHIP; opsix Sine 8bit with Decimator | the motif's first pair at modem pitch, bits falling away; chatter that stops mid-word |
| Lightning | opsix ring | far crack, tail, a low roll later |

### Slingshot (code: `drive.pull`, `draw`, `release`, `launch`, `fire`; LAUNCH_SECONDS = 3.2)

| Event | Sound |
|---|---|
| Pull (`draw` 0 to 1) | a rubbery stretch: a resonant filtered saw rising up to an octave with `draw`, engine pitch sagging down, as if held back. Music low-passing. Pulled further, tighter; hold it long, it trembles (beats) |
| Release | **instantly**: a falling snap, sub, the flame whoosh. Never quantised |
| Launch 3.2 s (about 6.7 beats) | on the next beat, drums into double-time for the kick's length, an extra distorted layer, flames (`fire`) as a filtered roar panned to the sides |
| End | down on a bar line |

### Jumps (code: `drive.air`, `vy`, `land`, lib/ride.ts JUMP)

| Event | Sound |
|---|---|
| Leaving a crest (`air` true) | road noise and engine load cut at once; wind opens; music high-passes a little. The missing road is the sensation of flying |
| In the air | engine revving free, up a third. Stem filter open |
| Landing (`land` 0 to 1, from impact) | sand thump scaled to `land`: sub plus noise burst plus creak of suspension; sand spray tail. Road returns. Above a threshold, a duck of 200 ms |

The dunes' crests come on the road's data, so a stinger could anticipate them; judge in play.

## 10. The core (E Locrian, then Phrygian, none then 140)

**Picture**: gate first. White tiled lab with green tanks of specimens under flickering lights, then server hall, then a dark plaza with a huge sphere of green light, red lamps, cables, steam. (code: art/core/, LAB_DOOR = 1392: "It comes alive past the doors", and the boost is locked until then: `ghostLocked`.)

Arrival is short: the change into the core takes 210 m, about 4 s at speed, against about 480 m elsewhere (code: `transitionLead`, `transitionTail`). It's the most abrupt change in the ride, and it's a tritone. Good.

| Section | What's heard |
|---|---|
| **Gate** | No beat. A low E and Bb, far apart, very slow. Mains hum on E2 (82.4 Hz, not real mains). Steam. It's quiet, the survival-horror held breath |
| **Lab**, before the doors | Tile reverb. Bubbling (opsix Filter FM). A tank's glass ringing as you pass (SY TOY with FORM at glass, Doppler), panned. **The specimens' own hearts, out of phase with each other**, very quiet, in 3:4:5 from three sides. A breath in a Vowel filter. Fluorescents buzzing, flickering in sync with the lights |
| **The doors, LAB_DOOR** | The motif once, on opsix bell. Then **a beat**: the first in the core. 140, kick and pulse, everything from here on driven |
| **Servers** | Data as hats: Euclidean 5/16, 7/16, 11/16 at high pitch on the Syntakt (CH METALLIC, SY BITS), fans in the bed, disk seeks. Motif harmonised in polychords |
| **Plaza, the sphere** | Bed opens into a choir of machines: Hydrasynth with opsix FM brass, a low E pedal, motif full size. Mode shifts to E Phrygian (the fifth B returns) for the arrival. A short relief. Then alarms |

**Polychord**: E minor over F minor pulsing in 8ths on "E F"; then Bb major over B minor on "Bb B". FM brass (opsix: sine carriers, 1:1 modulators, index envelope with a slow rise, little detune), trumpets over horns in register. Syntakt's drive on it.

Locrian's hard to hold: if it won't sit, use Phrygian and keep the Bb as an accent. That's fine.

### The ghost (code: lib/ride.ts `ride.ghost`, GHOST = out 0.5, run 3.2, back 0.8, cool 6; digital-ghost.tsx)

The bike turns to blocks of light, the creature runs in its place, about 420 m/s, past the speed of sound (343 m/s). So **nothing behind it can reach you.**

| State | Sound |
|---|---|
| `denied` (locked or uncharged) | a dead relay: a dull click, no pitch |
| `out` 0.5 s | a reverse swell, world high-passing; a crack as `kick` passes Mach 1 (Web Audio gain, opsix noise and sub, no reverb) |
| `run` 3.2 s | The world's cut: no road, no ambience, no Doppler. In its place the data layer: the motif backwards at double time (B Bb, F E), SY BITS and opsix with Decimator rising. **The creature's heart: dub-lub, backwards, in 3 against the beat**, low and close, plus claws on the same pulse. Nothing else. Stem drums down to kick |
| `back` 0.8 s | down-pitching re-entry, world fading back in from high-passed; a boom as it reforms. Then the bar line catches it: next downbeat is a full hit. Not exactly on time; the hit covers that |
| `cool` 6 s | a very quiet rising tone with charge |
| ready | a two-note ping on the next beat, E F |

## 11. The boss

Not built yet. This is for when it is.

### Before the fight

| Moment | Sound |
|---|---|
| **Alarms** | **Tritone siren**: E5 and Bb4 alternating every 0.75 s, with AM at 70 Hz (opsix Ring Mod for the capture, or code). The roughness is the alarm. Placeholder alarm-klaxon-loop until then. Also red lamps' relays clicking. Beat continues underneath, ducked |
| **Voice of the place** | Hydrasynth vocoder-like: Vowel filter, saw, no words. On the alarm's first cycle |
| **Gates shutting** | Each a falling pitch plus sub plus big metal strike (opsix FM 1:1.41 low; SY DUAL VCO with BEND; a real reverb tail). **On the downbeat**, nearest last, spatialised ahead. Far ones first: distance, then scale |
| **Traps** | Each telegraphs in rhythm: two ticks a beat apart, third is the strike. The music's beat tells you when; the picture tells you where. So you can read it while riding |
| **Into the room** | Silence for one bar. A single lub-dub, very low. That's when they know |

### The fight

**The audio's the clock.** Everything's scheduled against the context; actions judged on the heard beat (adaptive.md).

| Phase | Tempo, meter | Centre | What the player does | Music |
|---|---|---|---|---|
| 1 | 140, 4/4, bar 1.714 s | E Phrygian | call and response: it plays a lub-dub, you answer | motif in low brass and Syntakt, boss's pulse. Full drums |
| 2 | 140, 7/8, bar 1.5 s (one eighth shorter) | E Locrian | mixed rhythms on the limp from the desert; holds and pairs | motif over a 7 + 5 polymeter. Drums thrown off balance |
| 3 | 160, 4/4, bar still 1.5 s, exactly | E and Bb together | fastest; pairs, then both hands | **canon**: motif and its tritone answer, half a bar apart, using the same four notes. 160 = 2 × 80, the green city's tempo doubled |

Phase 2 to 3 is a metric modulation: the bar doesn't change length, 72,000 frames in both, and the beat inside it does. It should feel like being grabbed.

**Each hit damages the music.** Vertical layers drop, or get swapped for broken versions: bit-reduced, with dropouts. By the end of a phase it's stuttering. A new phase restores it, bigger and angrier.

| Event | Sound |
|---|---|
| Best | clean, bright confirmation (opsix bell in key), on the click |
| Good | same, duller |
| Miss | no note; a sour dry sound, and a 150 ms duck of the top layers. The rhythm doesn't wait |
| Damage taken | low-pass the whole mix for a moment, the heart comes up, close, faster |
| Boss hurt | a downward pitch shift with noise: both are on the record as negative for listeners (Blumstein, theory.md) |
| Kill | motif's last pair, Bb to B, on the beat. Everything stops dead. Bar of silence. Then E and B, an open fifth, the bell from the green city. Rain. The heart at rest, 73 |

Windows: start at best ±45 ms, good ±100 ms, with a silent calibration from the player's offsets in the hive (adaptive.md). Loosen if it isn't fun. Taste: the 7/8 phase could be a 3:4 polyrhythm instead, at less risk of throwing players; 7/8 is easier to hear if it's been taught in the desert.

## 12. The bike, and between zones

**Each bike has a heart**: visible in chrome, a tissue tank in the core's. So every engine has a pulse in it, from `drive.beat`, at rest 73 per minute.

| Bike | Engine | Layers |
|---|---|---|
| Green | low, wet, biological twin; Syntakt SY RAW through drive with a noise bed | at idle the heart's most of it |
| Chrome | turbine whine plus glass; opsix sine carriers, ratio 1 and 7, high level at high speed | |
| Hive | breath, tendon; Hydrasynth Vowel on saw, breathing | |
| Desert | dry, rattling, rusted; Syntakt SY BITS on low, opsix Sine 8bit | |
| Core | heavy electric hum with a green glow: FM, fixed operator on E; coil whine | |

**Speed**: loops at 3 bands crossfaded by `drive.speed`; a morph crossfade across the join, the same span as the visual's (code: `transitionLead`, `transitionTail`). Placeholder engine-loop until then.

**Passing things**: Doppler (craft.md); 3.2 semitones at green, 5.7 at core.

**Transitions**: distances from code, 320 m lead and 160 m tail, except 90 and 120 into the core. At cruise that's about 13 s, 11 s, 10 s and 4 s. Crossfade by distance rather than time so a boost makes them faster.

| Change | Held pitch across it | Move |
|---|---|---|
| Green to Chrome | **B and G** are in both | bed gives way to bed. Drums stop on their bar; new drums on their first bar after the join |
| Chrome to Hive | **B** (it's Db's seventh, Cb) | tritone. All stems out but a held B. Choir enters on Db under it |
| Hive to Desert | **F** | Freeze the choir's reverb on F, let it decay to wind as the storm comes up |
| Desert to Core | **Bb B E F**, the motif's four notes, which the desert's data has been playing | 4 s. Cut, not a fade. The gate's low E and Bb are already there in the desert's last bars |

## 13. UI

Plain, small, in the current zone's key. Rendered per zone or transposed by playback rate (a fixed set of semitones).

| Thing (code) | Sound |
|---|---|
| Ticket tear (components/ticket.tsx) | one dry paper rip; it's the first sound of the site, so make it real. Then rain fades in, which needs the first gesture to start audio |
| Pill play and pause | a tight mechanical click, soft; a low tick up or down |
| Getting on, off | seat creak, heart's pulse in or out |
| Map terminal (holomap.tsx) | CRT-ish whine on open, opsix SIN 12BIT beeps, in the zone's key; a pick is rising |
| Boost not ready | a short dull tick |

## 14. Stems and files

Names as in workflow.md. Rough budget: [J]

| Zone | Stems | Frames per loop | Notes |
|---|---|---|---|
| Green | bed, bell, bass, drums | 8 bars = 1,152,000 | bed could be longer, at 16 bars, since it's slow |
| Chrome | pad, arp, bass, drums, chords | 8 bars ≈ 970,105 | |
| Hive | choir, grid, tar | free | heart is one-shots, scheduled |
| Desert | storm, pedal, drums, data | 8 × 7/8 = 645,120 | |
| Core | gate bed, lab bed, servers, drums, brass | 8 bars ≈ 658,286 | |
| Boss | 3 phases × 4 layers + breakups | | load at the door |

At 112 kbps, 35 s of stereo Opus is about 490 kB. A zone is about 2 to 3 MB; all five zones and the boss near 15 MB plus SFX. Load per zone. Mono for bass and drums' kick where it won't be missed.

## 15. Where to start

1. **Get the rig talking**: hardware-*.md settings, `midi_ports.py`, then one note on one device with the user there.
2. **The motif, on the opsix bell**, E F, Bb B, at 80. If that isn't right, nothing else is. Play it for the user. Try it in the other forms.
3. **The hive first.** It's the mechanic that most needs sound, and it's got the strongest idea. Record the six notes (perfect and good) and the heart; hook them to `lib/rhythm.ts`.
4. **An audio clock for the heart.** Today `drive.phase` is integrated from frame time, and `rhythm.clock` likewise. For the heart to match scheduled sound, derive them from the AudioContext when it's running, and fall back to frame time when it isn't. Schedule the lub and dub with look-ahead. Ring-closing uses heard time. This is a real code change to the game; plan it with the user.
5. Then green, then the rest.

## 16. Taste: what could go otherwise

- **The key plan**: E, G, Db, Bb is an idea, and a tidy one. If the bell sounds better in D or F, transpose the lot; only relations matter. E was chosen for low-riff weight.
- **Mode per zone**: chrome could as easily be Ionian, more naive. Desert could be Phrygian with no whole-tone haze, more riff, less mirage. Hive could be Double Harmonic for more bite, less warmth.
- **Tempo = 2.5 × speed**: neat, not necessary. If 80 drags, or 95 feels soft for its look, push chrome to 110 and hive's grid to 128. You'd lose the 2:3 heart unless the heart changes too.
- **Half-time green**: a straight 160 breakbeat would be nearer Y2K drum and bass and more immediately thrilling, less gothic. Worth a try; 160 is already the boss's tempo.
- **7/8**: risky; hear it on the bike. 4/4 with an odd-length fan pattern keeps the machinery, and loses the limp.
- **Just intonation in the hive**: a real difference on a sustained choir, and a sysex step on the device. Worth hearing against plain 12-TET before committing.
- **Damage strips the boss's music**: alternatively it could get *bigger* as the boss gets desperate. Both work, and the mix is harder if it grows.
- **Real sounds**: the rig's synthetic by choice. Rain and paper may be better recorded, or kept CC0.

Sources: see theory.md, adaptive.md, craft.md. Facts about the game: read the current code; it moves faster than this file does.
