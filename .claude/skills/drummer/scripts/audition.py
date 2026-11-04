#!/usr/bin/env python3
"""Works out what's on a Syntakt kit: plays each track once, records it, says what it measured. Dry run unless --send.

    python audition.py --input Syntakt --dir takes/ --send     # plays and records
    python audition.py --analyse take.wav                      # measures a take already recorded with this script
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "sound-design", "scripts"))
GAP = 1.5
PREROLL = 3.0


def role(hz, decay, low, mid, hi):
    """A guess, only a guess: the numbers are the evidence."""
    if hi > 60:
        return "cymbal or open hat" if decay > 0.4 else "closed hat"
    if low > 60:
        if decay > 0.7:
            return "long sub or bass"
        return "kick" if decay < 0.26 else "low tom or kick"
    if low > 20 and mid > 40:
        return "low perc or tom, with noise"
    if mid > 60:
        return "snare or clap" if decay < 0.15 else "tone or perc"
    return "snare, noisy" if hi > 25 else "?"


def analyse(path, tracks=12, gap=GAP, preroll=PREROLL):
    x, sr = sf.read(path)
    m = x.mean(1) if x.ndim > 1 else x
    win = int(0.003 * sr)
    e = np.convolve(np.abs(m), np.ones(win) / win, "same")
    from_ = int(preroll * 0.8 * sr)
    if not (e[from_:] > 10 ** (-55 / 20)).any():
        sys.exit("Nothing above -55 dBFS after the preroll. Check USB CONFIG, INPUT FROM, RECEIVE NOTES, USB OUT, and that a kit's loaded.")
    t1 = (np.argmax(e[from_:] > 10 ** (-55 / 20)) + from_) / sr
    print(f"first hit at {t1:.3f} s; take {len(m) / sr:.2f} s")
    print("track  peak dB  main Hz  decay s  low%  mid%  hi%  looks like")
    for k in range(tracks):
        a = int((t1 + gap * k - 0.005) * sr)
        seg = m[a : a + int((gap - 0.05) * sr)]
        if len(seg) < sr // 4:
            print(f"{k + 1:5d}  cut off: record longer")
            continue
        peak = np.abs(seg).max()
        if peak < 3e-4:
            print(f"{k + 1:5d}  {20 * np.log10(max(peak, 1e-9)):7.1f}  silent")
            continue
        s = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
        fr = np.fft.rfftfreq(len(seg), 1 / sr)
        ee = np.convolve(np.abs(seg), np.ones(win) / win, "same")
        after = ee[np.argmax(ee) :]
        below = after < ee.max() * 10 ** (-30 / 20)
        decay = np.argmax(below) / sr if below.any() else gap
        low = 100 * s[fr < 150].sum() / s.sum()
        mid = 100 * s[(fr >= 150) & (fr < 2000)].sum() / s.sum()
        hi = 100 * s[fr >= 4000].sum() / s.sum()
        hz = fr[np.argmax(s[1:]) + 1]
        print(f"{k + 1:5d}  {20 * np.log10(peak):7.1f}  {hz:7.0f}  {decay:7.2f}  {low:4.0f}  {mid:4.0f}  {hi:3.0f}  {role(hz, decay, low, mid, hi)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyse", help="a take to measure, instead of recording")
    ap.add_argument("--input", default="Syntakt")
    ap.add_argument("--dir", default="takes")
    ap.add_argument("--tracks", type=int, default=12)
    ap.add_argument("--vel", type=int, default=110)
    ap.add_argument("--send", action="store_true", help="really play and record; otherwise says what it would do")
    a = ap.parse_args()
    if a.analyse:
        analyse(a.analyse, a.tracks)
        return
    events = [{"sec": i * GAP, "synth": "syntakt", "channel": i + 1, "note": 60, "vel": a.vel, "dur_sec": 0.08} for i in range(a.tracks)]
    if not a.send:
        print(f"would play {a.tracks} tracks once each at velocity {a.vel}, {GAP} s apart, and record {a.input}. Nothing sent. Add --send.")
        return
    os.makedirs(a.dir, exist_ok=True)
    perf = os.path.join(a.dir, "audition.json")
    with open(perf, "w") as f:
        json.dump({"bpm": 120, "events": events}, f)
    r = subprocess.run([sys.executable, "capture.py", os.path.abspath(perf), "--input", a.input, "--name", "audition", "--dir", os.path.abspath(a.dir), "--preroll", str(PREROLL), "--tail", "2", "--send"], cwd=TOOLS)
    if r.returncode:
        sys.exit(r.returncode)
    analyse(sorted(glob.glob(os.path.join(a.dir, "audition_t*.wav")))[-1], a.tracks)


if __name__ == "__main__":
    main()
