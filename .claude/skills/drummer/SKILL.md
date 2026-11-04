---
name: drummer
description: Write, play and record drum lines that feel played by a person, on the Elektron Syntakt over USB MIDI. Use this whenever the user wants drums, a beat, a groove, a drum line, a fill, a percussion loop or a rhythm stem, wants drums to feel more human or less programmed, wants velocity, swing, ghost notes or live FX moves, or wants to retake or change a line, even if they don't say "skill" or name the Syntakt. Also for working out what a Syntakt kit's tracks actually are. For melody, harmony, synth patches, sound effects or the overall score of Ride, use sound-design (this skill runs on its capture tools).
---

# Drummer

The script is the drummer. It plays the Syntakt live over MIDI, one hit at a time, while the Syntakt's main output is recorded over USB. So every hit has its own velocity and timing, and FX can move mid-phrase.

**You can't hear any of this.** Timing, levels and clipping can be measured. Whether it grooves can't, so never claim it does: play it, send it, and ask. Take the user's words ("more swing", "kick too clean") as the brief for the next take.

## Before sending anything

Sending plays out loud in the user's room, so get a go-ahead for the first send of a session and for anything riskier than before.

1. **Environment.** A venv with `.claude/skills/sound-design/scripts/requirements.txt`. Run these scripts with its Python.
2. **Syntakt settings.** `USB CONFIG` = `USB AUDIO/MIDI`, `INPUT FROM` = `USB`, `RECEIVE NOTES` and `RECEIVE CC/NRPN` on, `USB OUT` = `MAIN`, tracks 1-12 on channels 1-12. They can't be read or set from here; the user checks them on the device. Details: sound-design's `references/hardware-syntakt.md`.
3. **Monitors low** when trying FX settings for the first time.
4. **Quit Logic Pro** or any librarian: they talk to the ports.

## Workflow

1. **Map the kit.** A kit's tracks can be anything, and machines can't be chosen over MIDI: only the user can change them. Audition it, and never assume last session's map still holds if the kit may have changed.

   ```bash
   python .claude/skills/drummer/scripts/audition.py --input Syntakt --dir <takes> --send
   ```

   It plays each track once and prints what it measured (peak, main frequency, decay, band shares) with a guess at the role. The numbers are the evidence; the guess is only a guess. If a sound's needed that the kit hasn't got, ask the user for that machine.

2. **Write the line** in Python with `scripts/drumline.py`. See `art/audio/drums/lines.py` for six worked lines. Read `references/playing.md` before writing one: it's what separates playing from stepping.

   ```python
   from drumline import Line, euclid
   L = Line(seed=1)
   L.start(13, 92, 70)              # where a control starts (here reverb mix, on the FX channel)
   L.hit(0, 2, 118, spread=3)       # beat, track, velocity; how far velocity wanders; `drift` for time
   L.throw(15.5, 6, 84, 80, 0)      # a send opened for one hit and shut again
   L.ramp(0, 4, 74, 90, 124, 16)    # a control riding over 16 beats
   perf = L.perf(bpm=80, beats=32)  # the pattern played twice
   ```

3. **Take it.** Dry run without `--send`.

   ```bash
   python .claude/skills/drummer/scripts/take.py line.json --input Syntakt --name green_drums --takes <takes> --out art/audio/drums --send
   ```

   It records both passes, cuts an exact loop from the second (so the first pass's tails are in it), checks for static, levels it and encodes `.ogg` and `.m4a`. It prints timing spread, level and seam.

4. **Send it to the user and listen to what they say.** Name what you measured and what you couldn't. Retakes are cheap: a line takes about a minute.

## What will go wrong

- **FX run away into full-scale static, and stay stuck until a power cycle.** It happened at delay feedback 70, send 105, reverb decay 112, mix 95, on a hit that had been fine a pass earlier, then persisted through later takes. So `drumline.py` refuses values over its ceilings, and `capture.py` has a watchdog that stops on sustained noise and pulls the FX down. If the user reports static, stop sending. It's the FX until proven otherwise, not their setup. Have them power cycle.
- **Every CC edits the kit's working copy.** Tell the user, and that reloading the kit brings it back. Don't save anything.
- **The delay keeps ringing after a take.** That's normal with feedback in the 50s and 60s; it can take a while to fade. Warn them so it doesn't read as a fault.
- **Don't record through ffmpeg's avfoundation input.** On the Syntakt it silently lost about 12% of frames, so hits landed closer together than played. `capture.py` uses Core Audio. On any new input, check that hits sent a known distance apart land that far apart.
- **The first second or two of a stream can lose frames.** Keep the preroll, and never measure from the start of a file: find the first hit.
- **Check tracks in the recording, not by assumption.** An audition that drifted once misassigned every track, and it looked plausible. Check that gaps match what was sent.
- **Don't normalise by LUFS alone.** Drums have high crest factors. `take.py` raises each line to the target or a peak ceiling, whichever comes first, so the takes' loudness isn't comparable between lines yet.
- **A line's character is limited by the kit.** The same kit across lines gives different rhythm and FX but much the same sound. Say so, rather than letting it pass as finished.

## Files

- `scripts/drumline.py`: the line, its hits and FX moves, Euclidean patterns, the FX ceilings
- `scripts/audition.py`: maps a kit
- `scripts/take.py`: records a line and makes the loop
- `references/playing.md`: how to write lines that feel played, and FX moves by feel
- `art/audio/drums/lines.py`: Ride's lines, and what's on the kit they were written for
- sound-design's `references/ride-bible.md`: tempos, meters and each zone's feel in Ride
