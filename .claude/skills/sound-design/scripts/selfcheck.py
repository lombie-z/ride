#!/usr/bin/env python3
"""Tests what can be tested with no synth attached. Makes one virtual MIDI port of its own (named so nothing mistakes it
for a device), and sends only to that. Temp files go to the directory given.

    python selfcheck.py /path/to/temp/dir
"""
import json
import math
import os
import subprocess
import sys
import threading
import time

import mido
import numpy as np

import audio_tools
import perform

HERE = os.path.dirname(os.path.abspath(__file__))
fails = []


def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        fails.append(name)


def test_midi():
    mido.set_backend("mido.backends.rtmidi")
    name = "selfcheck-virtual"
    got = []
    inp = mido.open_input(name, virtual=True, callback=lambda m: got.append((time.perf_counter(), m)))
    time.sleep(0.2)
    perf = {
        "bpm": 120, "beats": 4, "clock": ["opsix"], "start": ["syntakt"],
        "events": [
            {"t": 0, "synth": "opsix", "note": 40, "vel": 110, "dur": 1},
            {"t": 1, "synth": "opsix", "cc": "filter.cutoff", "value": 64},
            {"t": 2, "synth": "hydrasynth", "channel": 3, "nrpn": "f1.cutoff", "value": 4096},
            {"t": 3, "synth": "syntakt", "channel": 9, "cc": "filter.freq", "value": 10},
            {"t": 3, "synth": "hydrasynth", "program": 5, "bank": 2},
            {"t": 0, "synth": "opsix", "ramp": "op1.level", "from": 0, "to": 127, "dur": 2},
        ],
    }
    events, end = perform.expand(perf)
    events = sorted(events + perform.clock_events(perf, end, 1.0), key=lambda x: x[0])
    ports, opened = perform.open_ports(sorted({e[1] for e in events}), {}, virtual=name)
    late = perform.run(events, ports)
    for p in opened.values():
        p.close()
    time.sleep(0.2)
    inp.close()
    # (Other apps on the Mac may probe a new port with their own sysex, as Logic or a librarian might: not ours to count.)
    foreign = [m for _, m in got if m.type == "sysex"]
    if foreign:
        print(f"     note: {len(foreign)} sysex messages arrived from some other app probing the port, e.g. {foreign[0].hex()[:60]}")
    got = [g for g in got if g[1].type != "sysex"]
    msgs = [m for _, m in got]
    check("every message arrived", len(msgs) == len(events), f"{len(msgs)}/{len(events)}")
    check("worst lateness under 5 ms", late < 0.005, f"{late * 1000:.2f} ms")
    nrpn = [m for m in msgs if m.type == "control_change" and m.channel == 2 and m.control in (99, 98, 6, 38)]
    want = [(99, 0x40), (98, 0x28), (6, 4096 >> 7), (38, 4096 & 127)]
    check("NRPN bytes and order", [(m.control, m.value) for m in nrpn] == want, str([(m.control, m.value) for m in nrpn]))
    bank = [(m.control, m.value) for m in msgs if m.type == "control_change" and m.control in (0, 32)]
    check("bank select then program change", bank == [(0, 0), (32, 2)] and any(m.type == "program_change" and m.program == 5 for m in msgs))
    check("note off for every note on", sum(m.type == "note_on" for m in msgs) == sum(m.type == "note_off" for m in msgs))
    # The clock's spacing as received, as a check that it doesn't drift: 120 BPM is a tick every 20.83 ms.
    clocks = [t for t, m in got if m.type == "clock"]
    if len(clocks) > 2:
        span = clocks[-1] - clocks[0]
        expected = (len(clocks) - 1) * 60 / 120 / 24
        jitter = np.std(np.diff(clocks)) * 1000
        check("clock doesn't drift", abs(span - expected) < 0.003, f"{(span - expected) * 1000:+.2f} ms over {span:.2f}s, jitter sd {jitter:.3f} ms")
    # Sysex is refused unless asked for.
    try:
        perform.expand({"bpm": 120, "events": [{"t": 0, "synth": "hydrasynth", "sysex": [1, 2]}]})
        check("sysex refused without the flag", False)
    except ValueError:
        check("sysex refused without the flag", True)


def synth_take(path, rate=48000, bpm=110.0, passes=3):
    """A stand-in for a synth: 4 beats of decaying notes through a delay, repeated, with a tiny pitch drift as analog has."""
    beat = 60 / bpm
    n = int(passes * 4 * beat * rate) + rate
    t = np.arange(n) / rate
    dry = np.zeros(n)
    for b in range(passes * 4):
        s = int((0.5 + b * beat) * rate)
        k = np.arange(n - s) / rate
        f = 110 * (1 + 0.5 * (b % 4 == 2)) * (1 + 0.0002 * math.sin(b))
        dry[s:] += 0.3 * np.sin(2 * np.pi * f * k) * np.exp(-k * 6)
    wet = dry.copy()
    d = int(0.75 * beat * rate)
    for i in range(1, 5):
        wet[d * i:] += dry[: -d * i] * 0.45 ** i
    noise = np.random.default_rng(1).normal(0, 1e-4, n)
    x = np.stack([wet + noise, np.roll(wet, 20) + noise], axis=1).astype(np.float32)
    audio_tools.write(path, x, rate)
    return bpm


def test_audio(tmp):
    src = os.path.join(tmp, "take.wav")
    bpm = synth_take(src)
    x, r = audio_tools.read(src)
    check("wav round trip keeps its length", x.shape[0] > 0 and r == 48000, f"{x.shape[0]} frames")

    onset = audio_tools.first_onset(x, r)
    check("onset found near the first note (0.5 s)", abs(onset / r - 0.5) < 0.005, f"{onset / r:.4f}s")

    trimmed, start = audio_tools.trim(x, r)
    check("trim removes the lead-in", abs(start / r - 0.495) < 0.01, f"{start / r:.4f}s")

    # Loop from the second pass: 4 beats, starting where the second pass starts.
    beat = 60 / bpm
    loop = audio_tools.make_loop(x, r, bpm, 4, 0.5 + 4 * beat)
    n, exact = audio_tools.frames_for(bpm, 4, r)
    check("loop is exactly the bar in frames", loop.shape[0] == n, f"{n} frames, exact {exact:.3f}")
    rep = audio_tools.seam_report(loop, r)
    check("loop's wrap is clean", rep["verdict"] == "clean", f"jump {rep['jump_vs_p99_9_db']} dB vs its 99.9% step")
    # And a bad loop should be caught: the wrong length, cut mid-note, no crossfade.
    bad = audio_tools.make_loop(x, r, bpm, 3.9, 0.5 + 4 * beat + 0.003, xfade=0)
    rep2 = audio_tools.seam_report(bad, r)
    check("a loop cut mid-note is flagged", rep2["verdict"] != "clean", f"jump {rep2['jump_vs_p99_9_db']} dB")

    # Loudness: integrated to target within 0.5 LU, true peak under the ceiling.
    in_path = os.path.join(tmp, "loop.wav")
    audio_tools.write(in_path, loop, r)
    out_path = os.path.join(tmp, "loop_norm.wav")
    res = subprocess.run([sys.executable, os.path.join(HERE, "audio_tools.py"), "norm", in_path, out_path, "--lufs", "-20", "--tp", "-1.5"],
                         capture_output=True, text=True, check=True)
    after = json.loads(res.stdout)["after"]
    check("normalises to -20 LUFS", abs(after["lufs"] + 20) < 0.5, f"{after['lufs']} LUFS, {after['true_peak_db']} dBTP")
    check("true peak stays under -1.5", after["true_peak_db"] <= -1.4)

    # A known level: a 1 kHz sine at -23 dBFS stereo, per BS.1770, reads about -23 LUFS (+/- the meter's rounding).
    sine = os.path.join(tmp, "sine.wav")
    t = np.arange(48000 * 5) / 48000
    s = (10 ** (-23 / 20) * np.sin(2 * np.pi * 997 * t)).astype(np.float32)
    audio_tools.write(sine, np.stack([s, s], axis=1), 48000)
    m = audio_tools.measure(sine)
    check("meter agrees with a known signal", abs(m["lufs"] + 23) < 0.6, f"{m['lufs']} LUFS for a -23 dBFS 997 Hz sine in stereo")

    rep3 = audio_tools.encode(out_path, os.path.join(tmp, "enc", "loop"), kbps=112)
    for name, f in rep3["files"].items():
        extra = f["decoded_frames_ffmpeg"] - loop.shape[0]
        print(f"     {name}: {f['bytes']} bytes, decodes (ffmpeg) to {f['decoded_frames_ffmpeg']} frames ({extra:+d} from the source)")
    check("encodes both formats", set(rep3["files"]) == {"loop.ogg", "loop.m4a"})


def test_capture(tmp):
    perf = os.path.join(tmp, "perf.json")
    with open(perf, "w") as f:
        json.dump({"bpm": 120, "beats": 2, "events": [{"t": 0, "synth": "opsix", "note": 40, "dur": 1}]}, f)
    base = [sys.executable, os.path.join(HERE, "capture.py"), perf, "--name", "test_sfx_x", "--dir", os.path.join(tmp, "takes"), "--tail", "0.2", "--preroll", "0.2", "--dry-run-audio"]
    subprocess.run(base, capture_output=True, text=True, check=True)
    subprocess.run(base, capture_output=True, text=True, check=True)
    files = sorted(os.listdir(os.path.join(tmp, "takes")))
    check("takes number themselves, never overwrite", files == ["takes.jsonl", "test_sfx_x_t001.wav", "test_sfx_x_t002.wav"], str(files))
    lines = open(os.path.join(tmp, "takes", "takes.jsonl")).read().splitlines()
    check("each take is logged", len(lines) == 2 and json.loads(lines[1])["take"] == 2)
    picked = subprocess.run(base[:2] + [perf, "--name", "test_pick", "--dir", os.path.join(tmp, "picked"), "--tail", "0.2", "--preroll", "0.2", "--dry-run-audio", "--pick", "1,1"], capture_output=True, text=True, check=True)
    check("--pick makes a stereo file from chosen channels", json.loads(picked.stdout)["measure"]["channels"] == 2)
    dry = subprocess.run([sys.executable, os.path.join(HERE, "capture.py"), perf, "--name", "n", "--dir", os.path.join(tmp, "takes")], capture_output=True, text=True, check=True)
    check("without --send it does nothing", "Nothing done" in dry.stdout)
    dry2 = subprocess.run([sys.executable, os.path.join(HERE, "perform.py"), perf], capture_output=True, text=True, check=True)
    check("perform's dry run sends nothing", "Nothing sent" in dry2.stdout)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tmp = sys.argv[1]
    os.makedirs(tmp, exist_ok=True)
    test_midi()
    test_audio(tmp)
    test_capture(tmp)
    print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
