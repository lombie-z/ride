#!/usr/bin/env python3
"""Post-processing for takes. Needs ffmpeg on PATH and numpy. Never overwrites its input.

    audio_tools.py measure  in.wav                                    # LUFS, true peak, LRA, peak, length
    audio_tools.py trim     in.wav out.wav [--threshold -50] [--pad 0.005] [--fade-out 0.01] [--tail]
    audio_tools.py cut      in.wav out.wav --onset --bpm 110 --beats 16 [--count-in 4]
    audio_tools.py loop     in.wav out.wav --bpm 110 --beats 16 --start 8.727 [--xfade 0.012] [--xfade-curve equal-gain]
    audio_tools.py seam     loop.wav                                  # how audible the wrap is, as a jump in dB
    audio_tools.py norm     in.wav out.wav --lufs -18 [--tp -1.5]     # linear gain only, then reports what it got
    audio_tools.py encode   in.wav outdir/name [--kbps 112]           # name.ogg (Opus), name.m4a (AAC), name.report.json
    audio_tools.py framing  --bpm 110 --beats 16 [--rate 48000]       # the exact loop length in frames

Audio is handled as 32-bit float internally; output WAVs are 24-bit at the input's rate.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np


def _ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    return "ffmpeg"


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=sample_rate,channels,duration_ts,nb_samples:format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return {"rate": int(s["sample_rate"]), "channels": int(s["channels"]), "duration": float(d["format"].get("duration", 0))}


def read(path):
    info = probe(path)
    raw = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-acodec", "pcm_f32le", "-"],
        capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype="<f4").reshape(-1, info["channels"]).copy()
    return x, info["rate"]


def write(path, x, rate):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    p = subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", "-f", "f32le", "-ar", str(rate), "-ac", str(x.shape[1]), "-i", "-",
         "-c:a", "pcm_s24le", path],
        input=x.astype("<f4").tobytes(), capture_output=True)
    if p.returncode:
        sys.exit(p.stderr.decode())


def measure(path):
    """EBU R128 / BS.1770 numbers from ffmpeg's ebur128 filter, true peak by its 4x oversampling."""
    p = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True)
    s = p.stderr
    tail = s[s.rfind("Summary:"):] if "Summary:" in s else s
    def get(pat):
        m = re.search(pat, tail)
        return float(m.group(1)) if m else None
    x, rate = read(path)
    peak = float(np.abs(x).max()) if x.size else 0.0
    return {
        "lufs": get(r"I:\s*(-?[\d.]+) LUFS"),
        "lra": get(r"LRA:\s*(-?[\d.]+) LU"),
        "true_peak_db": get(r"Peak:\s*(-?[\d.]+) dBFS"),
        "sample_peak_db": round(20 * math.log10(peak), 2) if peak > 0 else None,
        "seconds": round(x.shape[0] / rate, 4),
        "frames": int(x.shape[0]),
        "rate": rate,
        "channels": int(x.shape[1]),
    }


def _envelope_db(x, rate, win=0.002):
    n = max(1, int(win * rate))
    power = np.mean(x.astype(np.float64) ** 2, axis=1)
    c = np.convolve(power, np.ones(n) / n, mode="same")
    return 10 * np.log10(np.maximum(c, 1e-14))


def first_onset(x, rate, threshold_db=-40.0):
    """The first frame loud enough, walked back to where the sound really starts (within 10 dB of the noise floor)."""
    env = _envelope_db(x, rate)
    above = np.nonzero(env > threshold_db)[0]
    if not len(above):
        return None
    i = int(above[0])
    floor = np.median(env[: max(1, min(i, int(rate * 0.2)))]) if i > 10 else -120.0
    back = i
    limit = max(0, i - int(0.02 * rate))
    while back > limit and env[back] > floor + 10:
        back -= 1
    return back


def trim(x, rate, threshold_db=-50.0, pad=0.005, fade_out=0.01, tail=False):
    env = _envelope_db(x, rate)
    idx = np.nonzero(env > threshold_db)[0]
    if not len(idx):
        raise SystemExit("all below the threshold: nothing to keep")
    start = max(0, int(idx[0]) - int(pad * rate))
    end = min(x.shape[0], int(idx[-1]) + int(pad * rate)) if not tail else x.shape[0]
    y = x[start:end].copy()
    f = int(fade_out * rate)
    if f and y.shape[0] > f:
        y[-f:] *= np.linspace(1, 0, f)[:, None]
    return y, start


def frames_for(bpm, beats, rate):
    exact = beats * 60.0 / bpm * rate
    return int(round(exact)), exact


def make_loop(x, rate, bpm, beats, start_sec, xfade=0.012, curve="equal-gain"):
    """A loop of exactly `beats` beats starting at `start_sec`, whose end runs into its start.

    Take the loop from a later pass of the pattern, so delay and reverb tails from the pass before are already in it (the
    tail wraps by itself). The frames just before `start` are then mixed under the loop's last `xfade` seconds, hiding any
    small mismatch: free-running analog never lines up to the sample. equal-gain suits material correlated with itself
    (the same pattern played twice); equal-power suits uncorrelated noise or drones.
    """
    n, _ = frames_for(bpm, beats, rate)
    s = int(round(start_sec * rate))
    f = int(round(xfade * rate))
    if s < f:
        raise SystemExit(f"--start must leave at least {xfade}s before it for the crossfade")
    if s + n > x.shape[0]:
        raise SystemExit(f"need {(s + n) / rate:.3f}s of audio, have {x.shape[0] / rate:.3f}s: record more passes")
    y = x[s:s + n].copy()
    if f:
        t = np.linspace(0, 1, f, endpoint=False)
        if curve == "equal-power":
            fade_in, fade_out = np.sin(t * math.pi / 2), np.cos(t * math.pi / 2)
        else:
            fade_in, fade_out = t, 1 - t
        # The end of the loop fades out as what really came just before the start fades in: at the wrap the signal is
        # exactly the audio that preceded frame s, so it's continuous.
        y[-f:] = y[-f:] * fade_out[:, None] + x[s - f:s] * fade_in[:, None]
    return y


def seam_report(x, rate):
    """Compares the jump across the wrap with the signal's ordinary sample-to-sample movement."""
    d = np.diff(x, axis=0)
    typical = float(np.sqrt(np.mean(d ** 2))) or 1e-12
    p999 = float(np.percentile(np.abs(d), 99.9)) or 1e-12
    wrap = float(np.abs(x[0] - x[-1]).max())
    return {
        "wrap_jump": round(wrap, 6),
        "typical_step_rms": round(typical, 6),
        "p99_9_step": round(p999, 6),
        "jump_vs_p99_9_db": round(20 * math.log10(max(wrap, 1e-12) / p999), 2),
        "verdict": "clean" if wrap <= p999 else "listen: the wrap jumps more than 99.9% of the file's own steps",
    }


def normalise(x, gain_db):
    return x * (10 ** (gain_db / 20))


def encode(path, base, kbps=112):
    """Ogg Opus and AAC-in-M4A at the same bit rate. Reports what the files decode to, since encoders add frames."""
    os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
    src = probe(path)
    jobs = {
        ".ogg": ["-c:a", "libopus", "-b:a", f"{kbps}k", "-vbr", "on", "-application", "audio"],
        ".m4a": ["-c:a", "aac_at", "-b:a", f"{kbps}k", "-movflags", "+faststart"]
        if "aac_at" in subprocess.run([_ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        else ["-c:a", "aac", "-b:a", f"{kbps}k", "-movflags", "+faststart"],
    }
    report = {"source": os.path.basename(path), "source_seconds": src["duration"], "files": {}}
    for ext, args in jobs.items():
        out = base + ext
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", path, "-vn", *args, out], check=True)
        y, r = read(out)
        report["files"][os.path.basename(out)] = {
            "bytes": os.path.getsize(out), "decoded_frames_ffmpeg": int(y.shape[0]), "rate": r}
    with open(base + ".report.json", "w") as f:
        json.dump(report, f, indent=2)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("measure"); p.add_argument("input")
    p = sub.add_parser("trim"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--threshold", type=float, default=-50); p.add_argument("--pad", type=float, default=0.005)
    p.add_argument("--fade-out", type=float, default=0.01); p.add_argument("--tail", action="store_true", help="keep everything after the onset")
    p = sub.add_parser("cut"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--onset", action="store_true"); p.add_argument("--threshold", type=float, default=-40)
    p.add_argument("--bpm", type=float, required=True); p.add_argument("--beats", type=float, required=True)
    p.add_argument("--count-in", type=float, default=0, help="beats between the detected click and the real start")
    p.add_argument("--extra", type=float, default=0, help="seconds to keep past the end, for tails")
    p = sub.add_parser("loop"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--bpm", type=float, required=True); p.add_argument("--beats", type=float, required=True)
    p.add_argument("--start", type=float, required=True, help="seconds into the file where the loop starts")
    p.add_argument("--xfade", type=float, default=0.012); p.add_argument("--xfade-curve", default="equal-gain", choices=["equal-gain", "equal-power"])
    p = sub.add_parser("seam"); p.add_argument("input")
    p = sub.add_parser("norm"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--lufs", type=float, required=True); p.add_argument("--tp", type=float, default=-1.5)
    p.add_argument("--allow-limit", action="store_true", help="if the gain would pass --tp, apply it anyway through a soft limiter; otherwise it stops at --tp")
    p = sub.add_parser("encode"); p.add_argument("input"); p.add_argument("base"); p.add_argument("--kbps", type=int, default=112)
    p = sub.add_parser("framing"); p.add_argument("--bpm", type=float, required=True); p.add_argument("--beats", type=float, required=True); p.add_argument("--rate", type=int, default=48000)

    a = ap.parse_args()
    if a.cmd == "measure":
        print(json.dumps(measure(a.input), indent=2))
    elif a.cmd == "framing":
        n, exact = frames_for(a.bpm, a.beats, a.rate)
        print(json.dumps({"frames": n, "exact": exact, "seconds": n / a.rate, "error_ms_per_loop": (n - exact) / a.rate * 1000}, indent=2))
    elif a.cmd == "seam":
        x, r = read(a.input)
        print(json.dumps(seam_report(x, r), indent=2))
    else:
        if os.path.abspath(a.input) == os.path.abspath(getattr(a, "output", "")):
            sys.exit("won't overwrite the input")
        x, r = read(a.input)
        if a.cmd == "trim":
            y, start = trim(x, r, a.threshold, a.pad, a.fade_out, a.tail)
            write(a.output, y, r)
            print(json.dumps({"cut_from_start_s": round(start / r, 4), "seconds": round(y.shape[0] / r, 4)}))
        elif a.cmd == "cut":
            onset = first_onset(x, r, a.threshold)
            if onset is None:
                sys.exit("no onset found")
            start = onset + int(round(a.count_in * 60 / a.bpm * r))
            n, _ = frames_for(a.bpm, a.beats, r)
            end = start + n + int(a.extra * r)
            if end > x.shape[0]:
                sys.exit(f"take too short: need {end / r:.3f}s, have {x.shape[0] / r:.3f}s")
            write(a.output, x[start:end], r)
            print(json.dumps({"onset_s": round(onset / r, 5), "start_s": round(start / r, 5), "frames": end - start}))
        elif a.cmd == "loop":
            y = make_loop(x, r, a.bpm, a.beats, a.start, a.xfade, a.xfade_curve)
            write(a.output, y, r)
            print(json.dumps({"frames": int(y.shape[0]), "seconds": round(y.shape[0] / r, 5), **seam_report(y, r)}))
        elif a.cmd == "norm":
            m = measure(a.input)
            if m["lufs"] is None:
                sys.exit("couldn't measure it (shorter than 400 ms has no integrated loudness: set a level by peak or by ear)")
            gain = a.lufs - m["lufs"]
            room = a.tp - (m["true_peak_db"] if m["true_peak_db"] is not None else 0)
            limited = False
            if gain > room and not a.allow_limit:
                gain = room
                limited = True
            if gain > room and a.allow_limit:
                subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", a.input, "-af",
                                f"volume={gain}dB,alimiter=limit={10 ** (a.tp / 20)}:level=disabled:attack=5:release=60",
                                "-c:a", "pcm_s24le", a.output], check=True)
            else:
                write(a.output, normalise(x, gain), r)
            result = measure(a.output)
            print(json.dumps({"gain_db": round(gain, 2), "stopped_at_true_peak": limited, "before": m, "after": result}, indent=2))
        elif a.cmd == "encode":
            print(json.dumps(encode(a.input, a.base, a.kbps), indent=2))


if __name__ == "__main__":
    main()
