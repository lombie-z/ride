#!/usr/bin/env python3
"""Cuts each recorded part to its loop and lays a zone's parts over its drum line.

    python mix.py <takes dir> <performances dir>   # stems to art/audio/hydrasynth/stems, mixes to art/audio/previews

Every part starts on the clock (performance beat 0 comes a known time into the take), so they line up without hunting for
onsets, which slow attacks would throw off. Levels are by role, set by the numbers: to be argued with by ear.
"""
import glob
import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, ".claude/skills/sound-design/scripts")
sys.dont_write_bytecode = True
import audio_tools as A  # noqa: E402

TAKES, PERF = sys.argv[1], sys.argv[2]
LEAD = 3.0 + 1.5 + 0.02 + 0.012  # preroll, the program change's lead, the send's own start, the path through to the input
LEVEL = {"bed": -27.0, "lead": -28.0, "bass": -26.0, "top": -30.0}
DRUMS = -2.0
os.makedirs("art/audio/hydrasynth/stems", exist_ok=True)
os.makedirs("art/audio/previews", exist_ok=True)

db = lambda v: float(20 * np.log10(max(float(v), 1e-9)))
parts = json.load(open(os.path.join(PERF, "parts.json")))
zones = {}
print("part            rms    peak   low<200  >2k  active   onset off  seam")
for name in parts:
    p = json.load(open(os.path.join(PERF, name + ".json")))
    f = sorted(glob.glob(os.path.join(TAKES, name + "_t*.wav")), key=os.path.getmtime)[-1]
    x, rate = sf.read(f)
    bpm, beats = p["bpm"], p["pattern_beats"]
    sec = beats * 60 / bpm
    first = min(e["t"] for e in p["events"] if "note" in e) * 60 / bpm
    win = int(0.002 * rate)
    e = np.convolve(np.abs(x.mean(1)), np.ones(win) / win, "same")
    probe = e[int((LEAD + first - 0.1) * rate) :]
    off = (np.argmax(probe > 10 ** (-55 / 20)) / rate - 0.1) * 1000 if (probe > 10 ** (-55 / 20)).any() else float("nan")
    y = A.make_loop(x, rate, bpm, beats, LEAD + sec, xfade=p["xfade"], curve="equal-power" if p["xfade"] > 0.1 else "equal-gain")
    rms = float(np.sqrt((y**2).mean()))
    s = np.abs(np.fft.rfft(y.mean(1) * np.hanning(len(y)))) ** 2
    fr = np.fft.rfftfreq(len(y), 1 / rate)
    block = int(0.1 * rate)
    active = np.mean([np.sqrt((y[i : i + block] ** 2).mean()) > 10 ** (-60 / 20) for i in range(0, len(y) - block, block)])
    seam = A.seam_report(y, rate)["verdict"]
    print(f"{name:15s} {db(rms):5.1f}  {db(np.abs(y).max()):5.1f}  {100 * s[fr < 200].sum() / s.sum():5.0f}%  {100 * s[fr > 2000].sum() / s.sum():3.0f}%  {100 * active:4.0f}%  {off:7.0f} ms  {seam}")
    # By how loud it is while it's sounding: over the whole loop a sparse bell would be pushed far too high to make up for its rests.
    blocks = [float(np.sqrt((y[i : i + block] ** 2).mean())) for i in range(0, len(y) - block, block)]
    loudest = max(blocks)
    sounding = [v for v in blocks if v > loudest * 10 ** (-20 / 20)]
    level = float(np.sqrt(np.mean(np.square(sounding))))
    y = y * 10 ** ((LEVEL[p["role"]] - db(level)) / 20)
    sf.write(f"art/audio/hydrasynth/stems/{name}_v1.wav", y, rate, subtype="PCM_24")
    zones.setdefault(p["zone"], []).append(y)

print()
for zone, stems in zones.items():
    d, rate = sf.read(f"art/audio/drums/wav/{zone}.wav")
    n = min(len(d), *(len(s) for s in stems))
    m = d[:n] * 10 ** (DRUMS / 20) + sum(s[:n] for s in stems)
    peak = np.abs(m).max()
    m = m * min(1.0, 10 ** (-1.5 / 20) / peak)
    wav = f"art/audio/previews/{zone}_full_v1.wav"
    sf.write(wav, m, rate, subtype="PCM_24")
    me = A.measure(wav)
    A.encode(wav, f"art/audio/previews/{zone}_full_v1")
    os.remove(f"art/audio/previews/{zone}_full_v1.report.json")
    os.remove(wav)
    print(f"{zone:7s} {n / rate:6.2f} s  LUFS {me.get('integrated_lufs', me.get('lufs'))}  peak {me['sample_peak_db']}  pulled down {db(min(1.0, 10 ** (-1.5 / 20) / peak)):.1f} dB")
