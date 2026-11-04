# Workflow: from a script to a file in the game

Marks: [T] tested on this Mac (macOS 26.3, November 2026), [M] manual, [S] other source, [J] judgement, [U] unverified.

## Contents

1. The rig
2. Environment
3. MIDI from a script
4. Capture
5. Sync
6. Takes and names
7. Trim, loop
8. Loudness
9. Encoding, and what browsers really decode
10. What hasn't been tested

## 1. The rig

All three are USB MIDI class compliant with no drivers. [M] Only the Syntakt sends audio over USB. [M]

**What the Mac showed in November 2026**, listed but not used: [T]

| Device | MIDI port | avfoundation input | Core Audio |
|---|---|---|---|
| Syntakt | `Elektron Syntakt` | `Elektron Syntakt` | 2 in, 2 out, 48 kHz, USB. So it's already in a USB audio mode |
| Focusrite Scarlett 18i16 4th Gen | `Scarlett 18i16 4th Gen` | `Scarlett 18i16 4th Gen` | 20 in, 18 out, 48 kHz |
| opsix, Hydrasynth | not plugged in then | | |

```
Syntakt     USB -> Mac    (MIDI + stereo audio)
opsix       USB -> Mac    (MIDI)     L/R -> Scarlett line inputs 5, 6
Hydrasynth  USB -> Mac    (MIDI)     L/R -> Scarlett line inputs 7, 8
```

The Scarlett's inputs at 44.1 or 48 kHz: 1-4 mic/line/instrument, 5-8 line, 9-10 loopback (the computer's own audio, routed in Focusrite Control 2), 11-12 S/PDIF, 13-20 ADAT. [S: https://userguides.focusrite.com/hc/en-gb/articles/21616759197458-Scarlett-18i16-4th-Gen-Specifications] Those match the 20 the Mac reports.

Capture one synth with `capture.py --input Scarlett --pick 5,6`. **Whether ffmpeg's avfoundation input delivers all 20 channels has not been tested** (it opens the device, so it needs a go-ahead and may raise the permission prompt). `--pick` is written assuming it does. If it comes back stereo, it needs another route: PortAudio via the `sounddevice` package, or an Aggregate Device.

For a layered take on one clock: put the Syntakt's outputs into Scarlett inputs 3 and 4 too, and record the Scarlett alone. USB and Scarlett are separate clocks, so two simultaneous ffmpeg captures would drift apart slowly and start at different times. [J]

No Scarlett? The Syntakt's INPUT L/R with USB OUT = EXT works as a two-channel interface, one stereo synth or two mono. [M Syntakt 14.6, untried] Avoid a hub for the Syntakt if Overbridge is in use. [S Elektron]

Set up each device per its reference (hardware-*.md, "Settings to change"), then `midi_ports.py` and `capture.py --list-inputs`. The opsix and Hydrasynth port names in `synth_maps.py` are guesses; correct them.

## 2. Environment

No system-wide install. A venv in the scratchpad, or wherever the user wants it:

```
python3 -m venv "$SCRATCH/venv"
"$SCRATCH/venv/bin/pip" install -r scripts/requirements.txt
```

mido 1.3.3, python-rtmidi 1.5.8 and numpy 2.5 install as wheels on Python 3.14, arm64. [T] ffmpeg 8.0 was already on this Mac, with libopus and AudioToolbox AAC. [T] sox wasn't, and nothing here needs it.

Run `scripts/selfcheck.py <tempdir>` first: it exercises the whole path with no hardware.

## 3. MIDI from a script

`perform.py` takes a JSON performance (format in its docstring; examples in assets/performances/) and is a **dry run unless given `--send`**. Sending is what the user approves, each time it's a real device.

[T] Against a virtual port, messages were sent within 0.03 ms of their scheduled time once the wait was changed from sleep to spin in the last 20 ms; plain `time.sleep` overslept by up to 17 ms on this Mac. As received, clock ticks had 2.4 ms of jitter (standard deviation), most of it plausibly in the receiving callback, and no drift (+0.06 ms over 2.5 s). Real USB devices add their own latency, which is what the sync step below handles.

Other apps talk to MIDI ports. [T] While testing, a virtual port got sixteen `F0 00 00 66 ...` messages it hadn't asked for. That's the Mackie manufacturer ID, so probably Logic Pro's control-surface scan (Logic's virtual ports were present). Quit Logic while capturing.

Libraries [S]: mido's RtMidi backend can make virtual ports; https://mido.readthedocs.io/en/stable/backends/rtmidi.html

Timing limits: only 31,250 baud on DIN, but USB's quicker. Thin dense CC ramps anyway; `--ramp-hz` defaults to 60, and each message is what a sweep's smoothness rests on. 7-bit CC steps can be heard on cutoffs in a slow, resonant sweep: use NRPN on the Syntakt or Hydrasynth for those. [J]

## 4. Capture

```
ffmpeg -f avfoundation -list_devices true -i ""       # lists inputs [T]
ffmpeg -f avfoundation -i ":<index>" -c:a pcm_s24le out.wav    # lost about 12% of frames from the Syntakt: use capture.py
```

`capture.py` wraps this: starts recording, waits, plays the performance, keeps the tail, files the take. Audio only is `":N"` [S: https://ffmpeg.org/ffmpeg-devices.html, implied by its syntax rather than given as an example]. avfoundation has no sample-rate option documented, so it takes the device's rate: set the device to 48 kHz in Audio MIDI Setup, the Syntakt's native rate. [M, S]

**Permission.** macOS requires per-app consent for microphone input, and audio interfaces count. [S: https://developer.apple.com/documentation/bundleresources/requesting-authorization-for-media-capture-on-macos] A command-line tool's access is credited to whatever launched it (Terminal, or the app hosting the agent). [J: general knowledge, not found documented for ffmpeg] With no grant, developers report silent input rather than an error. [S: anecdote, https://amm123.mataroa.blog/blog/when-macos-silences-your-game-fixing-microphone-permissions-in-guess-whos-talking/] `capture.py` flags digital silence for that reason. What to do: tell the user a permission prompt may appear on first capture, and check System Settings > Privacy & Security > Microphone. If it never prompts, `tccutil reset Microphone`, which is the user's call since it resets every app. This wasn't exercised here: recording the Mac's own microphone wasn't asked for. [U]

Gain: peaks at about -6 dBFS on the capture, so there's room. Nothing's gained by getting hot on a 24-bit capture. [J]

## 5. Sync

The job: know where beat 0 is in the file, to the sample, despite an unknown delay from ffmpeg opening and USB.

Three ways, simplest first: [J]

1. **Clean first hit.** The performance starts with a note: `audio_tools.py cut --onset --bpm B --beats N`. It finds the first onset and cuts exactly N beats from it. Good for sequenced drums and one-shots. [T: finds a test note within 1 ms]
2. **Count-in click.** For sounds with slow attacks: a short sharp hit on another track, N beats ahead of the real start, then `cut --onset --count-in N`. It's only accurate if the clock source is the device or a steady script.
3. **The device's own clock.** Let the Syntakt run its sequencer (program change to pick the pattern, MIDI Start) and take the second pass. The device's clock doesn't care about the Mac's jitter. For patterns that's best. With several devices, one sends clock to the others, by DIN if that's wired.

For a layered take, record the layers in one pass through an interface if possible. Otherwise record each, cut each from its own onset, and accept a little offset between them; that's fine for anything not phase-critical, so don't layer two bass takes this way. [J]

## 6. Takes and names

`capture.py` writes `DIR/NAME_t001.wav` and appends a line to `DIR/takes.jsonl` (performance file and its hash, input, MIDI lateness, loudness). It never overwrites.

Keep raw takes out of the repo's public tree; `art/audio/takes/` is a reasonable place, gitignored if they get large. Ask before committing large WAVs. Finished files use:

`<zone>_<kind>_<thing>[_<bpm>bpm_<key>][_<layer>][_v<NN>].<ext>`

`green_mus_bed_092bpm_Em_v02.ogg`, `chrome_sfx_surge-riser_v03.ogg`, `hive_ui_circle-222.ogg`, `core_mus_drums_140bpm_E_v01.ogg`. Zones as in `lib/course.ts`: green, chrome, hive, desert, core, plus boss, ui, bike. Kinds: mus, sfx, amb, ui, stg (stinger).

Each piece of music also gets its exact frame length written down in a manifest (`beats`, `frames`, `rate`), because browsers add frames to some formats, see section 9.

Keep the performance JSON beside the patch notes in `art/audio/performances/`: that's the recipe, the way the build-*.py scripts are for the art.

## 7. Trim, loop

- `audio_tools.py trim`: one-shots. Cuts silence by threshold, keeps a little before the onset, fades out the tail.
- `audio_tools.py loop`: music and ambience.

**How to make a loop that's actually seamless:**

1. Record at least three passes. A tail from the pass before has to be in the loop (delay, reverb, long release), so take the **second or later pass**. The tail then wraps by itself. [J: standard practice]
2. Work out the length in frames, `audio_tools.py framing --bpm B --beats N`. It's rarely an integer: 4 beats at 110 BPM at 48 kHz is 104,727.27 frames. [T] Round once, then use the same count for every stem at that tempo so they stay locked.
3. `audio_tools.py loop --start S`, where S is where a later pass starts. A short crossfade (12 ms default) mixes what came just before the start under the last frames, hiding the mismatch analog drift leaves. Longer (100 ms to seconds) with `--xfade-curve equal-power` for noise, drones, wind: those are uncorrelated with themselves, so equal gain would dip in level. Equal gain's right for material correlated with itself, the same pattern twice. [J; the maths is standard]
4. `audio_tools.py seam`: compares the jump at the wrap with the file's own sample-to-sample movement. It flags clicks, not musical mismatches; then listen. [T: catches a bad cut at +32 dB, passes a good one at -14 dB]

Never trust `buffer.duration` for looping. See section 9.

## 8. Loudness

Published targets, none of them web-specific:

| Target | Source |
|---|---|
| Console -24 LUFS ±2 LU, -1 dBTP; mobile/handheld -16 LUFS ±2 LU, LRA 10-15 | IESD/Game Audio Network Guild recommendations v3.02, 2015: https://www.audiogang.org/wp-content/uploads/2015/04/IESD-Mix-Ref-Levels-v03.02.pdf |
| PS3 -23, Vita -18 LUFS (±2 LU) in Sony's ASWG, as of 2012 | interview: https://designingsound.org/2012/07/30/video-games-and-loudness-standards-interview-with-sonys-garry-taylor/ |
| Measurement: ITU-R BS.1770 | https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf |

No published standard for browsers was found. For Ride, a web game played on laptops and headphones, on the same page as other tabs: [J]

| What | Target |
|---|---|
| Whole game, measured over minutes of play | -16 to -18 LUFS integrated, under -1 dBTP |
| Music stem, one layer | set in the mix, not by file. Normalise each zone's full stack to about -20 LUFS, keeping the same gain on all its layers |
| Ambience loops | -30 to -26 LUFS |
| SFX one-shots | by peak and by ear, against music. Under 400 ms has no integrated loudness |

Why not louder: long listening, and mix room for the things that must read at speed. Encoded files can overshoot their source's peaks, so leave -1 to -1.5 dBTP before encoding.

`audio_tools.py norm` applies **linear gain only** and stops at the true-peak ceiling rather than limit without being asked. ffmpeg's `loudnorm` has a dynamic mode that changes the sound; leave it alone for game audio, where the dynamics are the mix. Check levels: [T] the meter read -23.0 LUFS for a 997 Hz sine at -23 dBFS in stereo.

## 9. Encoding, and what browsers really decode

Sources first: Safari gained Ogg for Opus and Vorbis in 18.4 (macOS 15.4, iOS 18.4). [S: https://webkit.org/blog/16574/webkit-features-in-safari-18-4/] That's for media elements as written; Web Audio isn't mentioned. WWDC25 said Safari 19 instead. [S: https://developer.apple.com/videos/play/wwdc2025/233/] So it was tested. Same source of 104,727 frames, `scripts/webkit_decode_test.swift`, `decodeAudioData` at 48 kHz:

| File | WebKit on macOS 26.3 | Chromium 152 | Note |
|---|---|---|---|
| Ogg Opus (libopus) | 104,727, exact | exact (12,345 of 12,345) | **the format to use** |
| WebM Opus | exact | not tested | |
| Ogg Vorbis (ffmpeg's built-in encoder) | decodes, 104,768 (+41) | not tested | that encoder is marked experimental; libvorbis isn't in this build |
| AAC M4A (AudioToolbox) | 105,504 (+777) | shorter test: 13,312 of 12,345 (+967); WebKit on the same file: +999 | start aligned, end padded; differs per browser |
| AAC M4A (ffmpeg native) | 104,736 (+9) | not tested | ffmpeg itself decoded this to 105,472 |
| MP3 (LAME) | 104,727, exact, in the long test; +1,479 on a very short one | not tested | Xing/LAME header |
| FLAC, WAV | exact | not tested | |

[T] all of it, Chromium being the desktop app's browser pane. A 10-frame click in the source (frames 24,000-24,009) stayed inside those frames in every codec but Vorbis from that encoder, which moved it 127 frames early, so **for Opus, AAC and MP3 the starts line up; only the ends differ**. Firefox and iOS weren't tested. `canPlayType` on WebKit returns "probably" for Ogg Opus, Ogg Vorbis and AAC. [T]

So:

- **Ogg Opus first.** ~112 kbps stereo for music; 64-96 for ambience; 48-64 mono for short SFX. Opus always decodes at 48 kHz internally, which suits a 48 kHz rig.
- **Fall back to AAC** only for browsers before Safari 18.4: choose by `canPlayType`, fetch one, `decodeAudioData` it.
- **Always loop with explicit loop points** from the manifest: `src.loop = true; src.loopStart = 0; src.loopEnd = frames / sampleRate`. [S: https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/loopEnd] With those, the extra frames AAC grows don't matter. loopEnd in seconds against the buffer's own rate; if the AudioContext is at 44.1 kHz the buffer's resampled [S: spec, decodeAudioData step 5], and seconds stay right.
- Make `new AudioContext({sampleRate: 48000})` when it can be done, so decoded buffers aren't resampled.
- Two things can't be fixed by format: `decodeAudioData` is a burst of CPU, and decoded buffers are large (a 16-bar stem at 110 BPM is about 35 s, about 13 MB in memory as stereo float). Decode per zone, as a zone is approached, and free the last. Streaming through a media element avoids that but gives up sample accuracy: fine for long ambience, not for layered music. [S: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices]

`audio_tools.py encode` makes both formats and reports the frames ffmpeg decodes. Re-run the WebKit test on anything loop-critical. Build it with `swiftc -O scripts/webkit_decode_test.swift -o <scratch>/wk` (Xcode command-line tools, already there [T]).

The placeholder pack in `art/audio/` (CC0 and synthesised, Ogg Vorbis at 44.1 kHz, see its LICENSES.md) is what's in use until real takes replace it. It's a different agent's work; don't edit it from this skill. Move to Opus at 48 kHz as files are replaced.

## 10. What hasn't been tested

The Syntakt and Scarlett were plugged in while this was being finished. Only their names and channel counts were read; nothing was sent to them or recorded from them.

Untested: anything reaching a real device, the opsix and Hydrasynth port names, CC response, USB latency, the Syntakt as an interface, capture from a real input (tested only with ffmpeg's lavfi tone), multichannel capture from the Scarlett, the permission prompt, Overbridge. Also iOS and Firefox decoding. On first use, run a short test performance on one device with the user watching, and correct this file.
