"""The stair and tunnel sections' sounds, from CC0 Freesound previews (see LICENSES.md): cut, faded, gain set to about -18 LUFS, encoded as Ogg
Vorbis (through Blender's own encoder, this machine's ffmpeg only has the experimental one, as the rest of art/audio) and m4a.

    python3 -I art/audio/sections/build-sections.py <folder of <id>.wav, decoded at 44.1 kHz> <scratch folder>
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt

SRC, TMP = sys.argv[1], sys.argv[2]
OUT = os.path.dirname(os.path.abspath(__file__))
TARGET, CEILING = -18.0, -1.0
R = 44100

# name: source id, from s, to s, fade out s, loop crossfade s (loops only), high-pass Hz
CUTS = {
    'rushing-water-loop': (497695, 30.0, 42.0, 0, 2.0, 35),
    'splash': (442773, 0.0, 2.17, 0.5, 0, 0),
    'splash-big': (529794, 0.16, 4.2, 1.4, 0, 0),
    'steam-burst': (675574, 0.39, 6.5, 2.6, 0, 60),
    'steam-burst-short': (90143, 0.0, 1.33, 0.4, 0, 60),
    'metal-impact-1': (569555, 23.5, 26.3, 0.6, 0, 0),
    'metal-impact-2': (569555, 26.72, 29.8, 0.6, 0, 0),
    'metal-impact-3': (569555, 13.82, 15.15, 0.3, 0, 0),
    'metal-impact-4': (569555, 11.05, 12.5, 0.3, 0, 0),
    'metal-impact-5': (850040, 0.0, 2.7, 0.7, 0, 0),
    'concrete-collapse': (703247, 0.0, 4.67, 1.0, 0, 0),
    'concrete-debris': (703248, 0.0, 3.92, 0.9, 0, 0),
    'stair-rattle-loop': (460595, 18.5, 25.0, 0, 0.4, 50),
}


def cut(sid, a, b, fade, xf, hp):
    r, x = wavfile.read(os.path.join(SRC, f'{sid}.wav'))
    assert r == R
    x = (x.astype(np.float64) / 32768).reshape(len(x), -1)
    if hp:
        x = sosfiltfilt(butter(4, hp / (R / 2), 'high', output='sos'), x, axis=0)
    i, j = int(a * R), min(int(b * R), len(x))
    if xf:
        # A loop: what runs on past the end fades in under the start, equal power, so the last sample goes on into the first.
        n = int(xf * R)
        out = x[i:j].copy()
        t = np.linspace(0, np.pi / 2, n, endpoint=False)[:, None]
        out[:n] = out[:n] * np.sin(t) + x[j:j + n] * np.cos(t)
        return out
    out = x[i:j].copy()
    n = int(0.003 * R)
    out[:n] *= np.linspace(0, 1, n)[:, None]
    n = int(fade * R)
    out[-n:] *= (np.cos(np.linspace(0, np.pi / 2, n)) ** 2)[:, None]
    return out


def loudness(path):
    e = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    tail = e[e.rindex('Summary:'):]
    return float(re.search(r'I:\s+(-?[\d.]+) LUFS', tail).group(1)), float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail).group(1))


def write(path, x):
    wavfile.write(path, R, (np.clip(x, -1, 1) * 32767).astype(np.int16).squeeze())


ENCODE = """
import aud, sys
a = sys.argv[sys.argv.index('--') + 1:]
for src, dst, ch in zip(a[::3], a[1::3], a[2::3]):
    aud.Sound(src).write(dst, rate=44100, channels=aud.CHANNELS_STEREO if ch == '2' else aud.CHANNELS_MONO, format=aud.FORMAT_S16, container=aud.CONTAINER_OGG, codec=aud.CODEC_VORBIS, bitrate=128000 if ch == '2' else 80000, buffersize=4096)
"""


def main():
    os.makedirs(TMP, exist_ok=True)
    report = {}
    jobs = []
    for name, (sid, a, b, fade, xf, hp) in CUTS.items():
        x = cut(sid, a, b, fade, xf, hp)
        raw = os.path.join(TMP, name + '.raw.wav')
        write(raw, x)
        i, p = loudness(raw)
        gain = TARGET - i
        # Not past the ceiling, even if that leaves a sharp hit short of the target.
        gain = min(gain, CEILING - 20 * np.log10(np.abs(x).max() + 1e-9))
        y = x * 10 ** (gain / 20)
        wav = os.path.join(TMP, name + '.wav')
        write(wav, y)
        jobs += [wav, os.path.join(OUT, name + '.ogg'), str(y.shape[1])]
        m = os.path.join(OUT, name + '.m4a')
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-i', wav, '-c:a', 'aac_at', '-b:a', '128k' if y.shape[1] == 2 else '96k', '-movflags', '+faststart', m], check=True)
        report[name] = dict(source=sid, seconds=round(len(y) / R, 2), channels=int(y.shape[1]))
    enc = os.path.join(TMP, 'encode.py')
    with open(enc, 'w') as f:
        f.write(ENCODE)
    subprocess.run(['blender', '--background', '--factory-startup', '--python', enc, '--', *jobs], check=True, capture_output=True)
    for name, d in report.items():
        for ext in ('ogg', 'm4a'):
            path = os.path.join(OUT, f'{name}.{ext}')
            i, p = loudness(path)
            d[ext] = dict(lufs=i, peak=p, kb=os.path.getsize(path) // 1024)
        print(name, json.dumps(d))


if __name__ == '__main__':
    main()
