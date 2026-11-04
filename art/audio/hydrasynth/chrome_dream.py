#!/usr/bin/env python3
"""The chrome city's mix, made dreamier: everything further back in one long dark reverb, the glass most of all, and quieter.

    python chrome_dream.py     # from the stems and drums to art/audio/previews/chrome_full_v2

The reverb's a synthetic impulse convolved round the loop, so its tail wraps into the loop's start and the seam stays exact.
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, ".claude/skills/sound-design/scripts")
sys.dont_write_bytecode = True
import audio_tools as A  # noqa: E402

RATE = 48000
OUT = "art/audio/previews/chrome_full_v2"


def impulse(seconds=6.0, predelay=0.045, seed=95):
    """Stereo noise that dies away, the highs first: a big soft room. Nothing under 180 Hz, so the bass stays clean."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    out = np.zeros((n, 2))
    for c in range(2):
        spec = np.fft.rfft(rng.normal(size=n))
        fr = np.fft.rfftfreq(n, 1 / RATE)
        bands = [(180, 900, 4.8), (900, 3000, 3.2), (3000, 9000, 1.5)]
        y = np.zeros(n)
        for lo, hi, t60 in bands:
            shape = np.exp(-(((np.log(fr + 1) - np.log(np.sqrt(lo * hi))) / np.log(hi / lo) * 1.5) ** 2))
            band = np.fft.irfft(spec * shape, n)
            y += band * 10 ** (-3 * t / t60)
        # A soft swell at the start rather than a slap.
        y *= np.minimum(1.0, t / 0.08)
        out[:, c] = y
    gap = int(predelay * RATE)
    out = np.vstack([np.zeros((gap, 2)), out])
    return out / np.sqrt((out**2).sum(0).mean())


def wrap_verb(x, ir):
    """Convolved round the loop, so what rings past the end comes back in at the start."""
    n = len(x)
    if len(ir) > n:
        ir = ir[:n]
    return np.stack([np.fft.irfft(np.fft.rfft(x[:, c], n) * np.fft.rfft(ir[:, c], n), n) for c in range(2)], axis=1)


def soften(x, hz):
    """Rolls the top off: less edge."""
    n = len(x)
    fr = np.fft.rfftfreq(n, 1 / RATE)
    gain = 1 / np.sqrt(1 + (fr / hz) ** 4)
    return np.stack([np.fft.irfft(np.fft.rfft(x[:, c]) * gain, n) for c in range(2)], axis=1)


def db(d):
    return 10 ** (d / 20)


drums, _ = sf.read("art/audio/drums/wav/chrome.wav")
pad, _ = sf.read("art/audio/hydrasynth/stems/chrome_pad_v1.wav")
glass, _ = sf.read("art/audio/hydrasynth/stems/chrome_glass_v1.wav")
bass, _ = sf.read("art/audio/hydrasynth/stems/chrome_bass_v1.wav")
n = min(len(drums), len(pad), len(glass), len(bass))
drums, pad, glass, bass = drums[:n], pad[:n], glass[:n], bass[:n]

ir = impulse()
# (part, softened to, dry level, send level): the glass is nearly all reverb now, a shimmer behind the rest.
mix = (
    soften(drums, 7000) * db(-7)
    + soften(pad, 9000) * db(-1)
    + soften(glass, 6000) * db(-13)
    + bass * db(-5)
)
wet = (
    wrap_verb(soften(drums, 5000), ir) * db(-13)
    + wrap_verb(pad, ir) * db(-3)
    + wrap_verb(soften(glass, 6000), ir) * db(-3)
    + wrap_verb(bass, ir) * db(-26)
)
m = mix + wet
m = m * min(1.0, db(-1.5) / np.abs(m).max())
A.write(OUT + ".wav", m, RATE)
level = A.measure(OUT + ".wav")
lufs = level.get("integrated_lufs", level.get("lufs"))
m = m * min(db(-24 - lufs), db(-1.5) / np.abs(m).max())
A.write(OUT + ".wav", m, RATE)
A.encode(OUT + ".wav", OUT)
os.remove(OUT + ".report.json")
final = A.measure(OUT + ".wav")
os.remove(OUT + ".wav")
print("loop", round(n / RATE, 3), "s LUFS", final.get("integrated_lufs", final.get("lufs")), "peak", final["sample_peak_db"], "seam", A.seam_report(m, RATE)["verdict"])
print("wet vs dry rms dB", round(20 * np.log10(np.sqrt((wet**2).mean()) / np.sqrt((mix**2).mean())), 1))
