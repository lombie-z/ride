#!/usr/bin/env python3
"""Takes a line: records its two passes, cuts an exact loop from the second, checks it, levels it, encodes it. Dry run unless --send.

    python take.py line.json --input Syntakt --name green_drums --takes takes/ --out art/audio/drums --send
    python take.py line.json --name green_drums --out art/audio/drums --from-take takes/green_drums_t003.wav

The line's a performance from drumline.Line.perf (it needs `pattern_beats`, and to start with a hit on beat 0). Refuses a take
that's turned to static. Files: <out>/<name>_vN.ogg and .m4a; the full-quality loop in <out>/wav/<name>_vN.wav.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "sound-design", "scripts"))
sys.path.insert(0, TOOLS)
import audio_tools as A  # noqa: E402

PREROLL = 3.0


def report_static(x, rate):
    """Blocks of 50 ms this loud are the FX having run away, not drums."""
    w = int(0.05 * rate)
    n = x.shape[0] // w
    hot = [i * 0.05 for i in range(n) if np.sqrt((x[i * w : (i + 1) * w] ** 2).mean()) > 0.4]
    return hot


def next_version(out, name):
    have = [int(m.group(1)) for f in glob.glob(os.path.join(out, f"{name}_v*.ogg")) if (m := re.search(r"_v(\d+)\.ogg$", f))]
    return max(have, default=0) + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("line")
    ap.add_argument("--input", default="Syntakt")
    ap.add_argument("--name", required=True)
    ap.add_argument("--takes", default="takes")
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-take", help="a take already recorded: cut this one instead of recording")
    ap.add_argument("--lufs", type=float, default=-20.0)
    ap.add_argument("--peak", type=float, default=-1.5)
    ap.add_argument("--tail", type=float, default=3.0)
    ap.add_argument("--send", action="store_true", help="really play and record")
    a = ap.parse_args()

    p = json.load(open(a.line))
    bpm, beats = p["bpm"], p["pattern_beats"]
    seconds = PREROLL + 60 / bpm + p["beats"] * 60 / bpm + a.tail
    path = a.from_take
    if not path:
        if not a.send:
            print(f"would play {len(p['events'])} events over {seconds:.1f} s and record {a.input}. Nothing sent. Add --send.")
            return
        os.makedirs(a.takes, exist_ok=True)
        r = subprocess.run([sys.executable, "capture.py", os.path.abspath(a.line), "--input", a.input, "--name", a.name, "--dir", os.path.abspath(a.takes), "--preroll", str(PREROLL), "--tail", str(a.tail), "--send"], cwd=TOOLS, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-600:] or "capture failed")
        path = sorted(glob.glob(os.path.join(a.takes, f"{a.name}_t*.wav")))[-1]
        entry = json.loads(r.stdout)
        print(f"take {os.path.basename(path)}: overruns {entry.get('overruns')}, worst MIDI lateness {entry.get('worst_midi_lateness_ms')} ms")

    x, rate = sf.read(path)
    hot = report_static(x, rate)
    if hot:
        sys.exit(f"STATIC from {hot[0]:.2f} s ({len(hot)} blocks) in {path}. Nothing filed. If the machine's still making noise, power cycle it. Then lower the FX.")

    # The first hit: past most of the preroll, so the stream's start can't be mistaken for it.
    m = x.mean(1)
    win = int(0.002 * rate)
    e = np.convolve(np.abs(m), np.ones(win) / win, "same")
    from_ = int(PREROLL * 0.8 * rate)
    t1 = (np.argmax(e[from_:] > 10 ** (-48 / 20)) + from_) / rate
    y = A.make_loop(x, rate, bpm, beats, t1 + beats * 60 / bpm)

    # How close strong hits came to where they should be: not the feel, but it shows if something's badly wrong.
    errs = []
    strong = sorted({round(ev["t"], 4) for ev in p["events"] if "note" in ev and ev["t"] >= beats and ev["vel"] > 88})
    for t in strong[:80]:
        c = t1 + t * 60 / bpm
        i, j = int((c - 0.03) * rate), int((c + 0.03) * rate)
        seg = e[i:j]
        if len(seg):
            errs.append((i + int(np.argmax(seg > seg.max() * 0.5))) / rate - c)

    os.makedirs(os.path.join(a.out, "wav"), exist_ok=True)
    v = next_version(a.out, a.name)
    base = os.path.join(a.out, f"{a.name}_v{v}")
    wav = os.path.join(a.out, "wav", f"{a.name}_v{v}.wav")
    A.write(wav, y, rate)
    me = A.measure(wav)
    lufs = me.get("integrated_lufs", me.get("lufs"))
    gain = min(a.lufs - lufs, a.peak - me["sample_peak_db"])
    sf.write(wav, y * 10 ** (gain / 20), rate, subtype="PCM_24")
    A.encode(wav, base)
    os.remove(base + ".report.json")
    final = A.measure(wav)
    print(f"{os.path.basename(base)}: first hit {t1:.3f} s, loop {y.shape[0] / rate:.3f} s, gain {gain:+.1f} dB, LUFS {final.get('integrated_lufs', final.get('lufs'))}, peak {final['sample_peak_db']} dB")
    print(f"timing of strong hits, spread: sd {np.std(errs) * 1000:.2f} ms over {len(errs)} hits (includes the line's own looseness)")
    print("seam:", A.seam_report(y, rate)["verdict"])


if __name__ == "__main__":
    main()
