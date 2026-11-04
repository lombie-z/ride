---
name: sound-design
description: Compose, score and design sound for Ride with the user's Elektron Syntakt, Korg opsix and ASM Hydrasynth over USB from macOS. Use this skill for any work on the game's audio, even if not called sound design - composing, soundtrack, music, stems, leitmotif, SFX, sound effects, alarms, boss music, engine sounds, adaptive music, Web Audio, rhythm-game timing or latency, loudness, seamless loops, encoding Ogg or AAC, Safari audio; and for synth or MIDI work - sending notes, CC, NRPN or sysex from a script, patches, capturing audio from hardware, Overbridge, microtuning. Also use it for questions about modes, tritones, tension, or which synth to use for a job.
---

# Sound design for Ride

Ride has a sound plan and a way to make it, on three real synths, driven from scripts. This file is how to work. Depth is in `references/`, read when needed.

## What to read

| Need | Read |
|---|---|
| What Ride should sound like: zones, motif, each feature, the boss | `references/ride-bible.md` |
| Plugging in, capturing, trimming, looping, loudness, encoding, what browsers decode | `references/workflow.md` |
| Syntakt, opsix, Hydrasynth: USB, settings, CC and NRPN, engines | `references/hardware-syntakt.md`, `hardware-opsix.md`, `hardware-hydrasynth.md` |
| Modes, tritones, roughness, Shepard, tuning, rhythm, leitmotif, idioms, horror technique | `references/theory.md` |
| Layers, re-sequencing, stingers, Web Audio scheduling, rhythm-game latency | `references/adaptive.md` |
| Synthesis recipes, layering, masking, mix, UI, Doppler, spatial | `references/craft.md` |

Read the bible before writing any music or SFX for the game. Read the synth's reference before making any claim about what it can do, or before sending it anything.

## Rules

**Never send MIDI to a device, or record, without the user's say-so.** Every script's a dry run until `--send`. A real device can have patches overwritten by sysex, so `perform.py` also refuses sysex unless `--allow-sysex` is passed. Listing ports is always fine. When the user's said go, say what's about to play, and send a short test first, not the whole thing.

**Say when something can't be done as asked, with the options.** If a device's missing, a port's named differently, a capture comes back silent, or an install would be system-wide: stop and tell them. No substituting another synth or a software sound and carrying on.

**No system-wide installs without asking.** Python packages go in a venv. Overbridge installs drivers: ask first.

**Hear it before calling it done.** You can't hear. You can measure (loudness, peaks, seam, frames, spectrum), but what it sounds like is the user's call. Play it to them. Say what you changed and why; let them say what's right. Treat the bible's choices as a first draft; several are flagged as taste.

**Say what's verified.** Manual facts are marked in the references. Nothing in them has been tried on the actual hardware yet: the Syntakt and a Scarlett interface were listed once, nothing sent. When something's learned on the real devices, correct the reference.

**No real brands in the game's content.** The synths' names are fine here and in file notes, never in the game itself. Don't imitate specific tracks; techniques only. If the user asks for "something like X", work out what makes it that way and use the technique.

**Leave `art/audio/` placeholders to their own process.** That's the provisional CC0 and synthesised pack (see its `LICENSES.md`), used until real takes replace each sound. Replace a file by agreement, with its licence note updated.

## Which synth

| Synth | For | Because |
|---|---|---|
| **Syntakt** | drums, bass, glue, struck things, dying digital | analog drum and cymbal tracks, digital machines (SY TOY for materials, SY BITS, SY CHIP, SY SWARM), analog FX block, sequencer with per-track lengths and Euclid. And it's the capture path |
| **opsix** | machines: bells, glass, alarms, metal, the creature | operators in FM, ring, filter, Filter FM, wave folder, effect modes; fixed-Hz partials; inharmonic at will |
| **Hydrasynth** | living things: choirs, organ, pads, breath, storm, the boss's voice | WaveScan, Mutants, Vowel filter, polyphonic aftertouch, long reverb and Freeze; **the only one with microtuning** |

If it's alive, Hydrasynth. If it's a machine, opsix. If it's the floor, Syntakt.

## The rig

- All three: USB class-compliant MIDI, no drivers. Only the Syntakt does audio over USB.
- **Syntakt**: SETTINGS > SYSTEM > USB CONFIG = USB AUDIO/MIDI for stereo capture without any driver. MIDI CONFIG > PORT CONFIG: INPUT FROM USB, RECEIVE NOTES on, RECEIVE CC/NRPN on. Overbridge gives every track, dry, but it's a driver install and needs its own engine.
- **opsix, Hydrasynth**: audio from their outputs only. The user has a Focusrite Scarlett 18i16 4th Gen: line inputs 5-8 are the obvious place, `capture.py --input Scarlett --pick 5,6`. Multichannel capture through ffmpeg is untested; see `references/workflow.md`. Or a cable into the Syntakt's INPUT L/R with its USB OUT = EXT, from its manual, also untested.
- **Hydrasynth**: MIDI page 6 (Keyboard/Desktop) Param RX = CC or NRPN, or parameters won't respond at all.
- **opsix**: SHIFT + EFFECT > MIDI page: Global Channel, Rx CC on. No NRPN exists; anything off the fixed CC list goes through a Virtual Patch made on the panel.

Ask the user: which Hydrasynth model (only Keyboard and Deluxe have a ribbon; voices differ), and original opsix, SE or mk II.

## Setting up

```bash
SCRATCH=<scratchpad>                                     # or a venv path the user prefers
python3 -I -m venv "$SCRATCH/sound-venv"
"$SCRATCH/sound-venv/bin/pip" install -r .claude/skills/sound-design/scripts/requirements.txt
PY="$SCRATCH/sound-venv/bin/python"; S=.claude/skills/sound-design/scripts
"$PY" "$S/selfcheck.py" "$SCRATCH/selfcheck"             # no hardware: virtual port, synthetic audio
"$PY" "$S/midi_ports.py"                                 # what's connected; sends nothing
"$PY" "$S/capture.py" --list-inputs
```

Paths are relative to `ride/`. In the scratchpad, `-I` keeps Python from picking up stray files.

## Scripts

| Script | Does |
|---|---|
| `midi_ports.py` | lists ports, says which synth each looks like |
| `perform.py perf.json [--send]` | plays a JSON performance: notes, CC by name, NRPN, ramps, program change, clock, Start/Stop, polytouch, sysex with a flag. Dry run by default |
| `capture.py perf.json --input X --name zone_kind_thing --dir takes/ [--send]` | records while performing; numbers takes; logs them; flags silence and clipping |
| `audio_tools.py measure/trim/cut/loop/seam/norm/encode/framing` | post-processing, ffmpeg and numpy; never overwrites its input |
| `webkit_decode_test.swift` | what this Mac's WebKit really decodes, and how many frames |
| `selfcheck.py` | tests all of the above without hardware |
| `synth_maps.py` | CC and NRPN name tables behind `perform.py` |

Examples: `assets/performances/`.

## The path from idea to game

1. **Spec the sound.** What's it for, how long, one-shot or loop, what's it masking or masked by, what game value drives it? Check the bible. If it's new, write the bible's entry first.
2. **Decide where it lives**: recorded, or code. Anything continuous (a riser following a level, roughness, Doppler, ducking) goes in Web Audio. Character comes from recordings. See `references/adaptive.md`.
3. **Patch.** Scripts can reach a lot (see each synth's table), but the best patches may need hands. Work out a patch and ask the user to set up what can't be scripted; assign Hydrasynth macros and opsix Virtual Patches so the script can play it.
4. **Write a performance** JSON; keep it in `art/audio/performances/`, the recipe for the sound, as `build-*.py` is for the art.
5. **Dry run**, show it, then with the go-ahead, a short test, then the take. Several takes; vary by velocity and macro.
6. **Cut**: `audio_tools.py cut --onset` for sequences, `trim` for one-shots, `loop` for loops, taken from a later pass so tails wrap.
7. **Check**: `seam`, `measure`, and the user's ears.
8. **Normalise** to the targets, linear gain only. Encode: Ogg Opus first, AAC fallback. Note the exact frames.
9. **Hook it up**, against the audio clock, on the buses. Test with the sound off too: the game must still run.

Quick numbers (details in `references/workflow.md`):

- 48 kHz everywhere. `new AudioContext({sampleRate: 48000})`.
- Whole-game target about -16 to -18 LUFS, under -1 dBTP; ambience about -30 to -26; zone stacks about -20. No published standard for the web was found, so that's judgement from the console (-24) and mobile (-16) recommendations.
- Ogg Opus decodes to exact frames in WebKit on macOS 26.3 and Chromium 152 (tested). AAC doesn't, and differs per browser. So **always set `loopEnd = frames / sampleRate` from a manifest, never `buffer.duration`.**
- Schedule on `audioContext.currentTime` with a 25 ms timer and 100 ms look-ahead. Physical actions sound at once; their musical consequence lands on the next grid; rhythm-game hits are never quantised.
- Start and stop stems with gain. Layers must be running to be in sync.

## Composing for Ride, in brief

Details in `references/ride-bible.md`.

- **Tonics E, G, Db, Bb, E**: a minor-third axis, in one octatonic. Tritone moves mark the two big departures.
- **The motif**: two heartbeats, `0 +1 | +6 +7`, E F, Bb B, in the heart's own lub-dub rhythm. It's transformed per zone, and the set's its own tritone transposition, which pays off in the boss.
- **Tempo = 2.5 × zone cruising speed**: 80, 95, 110, 125, 140. The hive's heart starts in 2:3 with the 110 grid and catches up to it by 666. The boss's 7/8 at 140 and 4/4 at 160 share a bar of exactly 1.5 s.
- **The angel numbers build a chord**, hit by hit: Db F Ab B D G. Misses leave holes.
- **Alarms use roughness**, modulation at about 70 Hz (screams and alarms concentrate at 30-150 Hz).
- **Machine = opsix, body = Hydrasynth, floor = Syntakt.**

Guard against: making everything dark. The chrome city's pretty and the hive's beautiful. Contrast is what makes the core land; don't start at maximum. Silence is a tool, too.

Drums and beats have their own skill, `drummer`, which runs on these capture tools.

## Gotchas

- Record with `capture.py` (Core Audio), not ffmpeg's avfoundation input: on the Syntakt that delivered about 12% too few frames, with no error, so hits landed closer together than played. Measure the spacing of known hits on any new input. [T]
- The Syntakt's FX can run away into full-scale static, and it stays stuck until a power cycle. It happened at delay feedback 70, send 105 and reverb decay 112, mix 95. Stay under feedback 62, send 90, decay 92, mix 80; `capture.py` has a watchdog that stops the performance on sustained noise. [T]
- Every CC edits the Syntakt's working kit. Tell the user, and to reload the kit if they want it back. [T]
- The first second or two of a Core Audio stream can lose frames: keep the preroll. [T]
- Logic Pro or a librarian running can talk to the devices' ports, and it sends its own sysex probes. Quit them while capturing.
- `time.sleep` oversleeps by 10+ ms on macOS, which is why `perform.py` spins before each event. Don't reintroduce it.
- A capture that's digitally silent, with no error, probably means no microphone permission for whatever launched ffmpeg, and audio interfaces count as microphones here. Check before debugging routing.
- 4 beats at 110 BPM is 104,727.27 frames. Round once and use the same count on all stems at that tempo.
- Local Off on a Hydrasynth is remembered through power-off.
- Sub-400 ms sounds have no integrated loudness.
- Pitch on a Syntakt is named an octave up from most DAWs: MIDI 60 is C5 in its manual.
- Files in `art/audio/` are Ogg Vorbis at 44.1 kHz as placeholders. Real takes should be 48 kHz Opus.
