#!/usr/bin/env python3
"""Builds the flipbook sheets in art/sprites/ (8x8 frames, 128 px each, grey = density).

steam-billow, steam-rise and fog-bank are toned from sim-steam.py's frames and crossfaded
into a loop. sand-gust and light-shaft are built here, on noise periodic in x, y and time,
with everything else moving in whole cycles a loop, so they loop exactly.

    python3 art/sprites/sim-steam.py billow <cache-dir>     (and rise, fog)
    python3 art/sprites/build-sprites.py <cache-dir> [names...]
    python3 art/sprites/check-sprites.py [names...]
"""
import os
import sys

import numpy as np
import scipy.fft as sf
from numba import njit
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
F = 128       # frame size
T = 64        # frames
GUTTER = 7    # px at the frame's edge that are exactly zero
WORKERS = 12


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def grid(n=F):
    """Pixel centres in 0..1: y (row, 0 at top), x (column)."""
    c = (np.arange(n) + 0.5) / n
    return np.meshgrid(c, c, indexing="ij")


def frame_gate():
    """Multiplied in last on everything: exactly zero in the gutter, reaching 1 softly."""
    y, x = grid()
    d = np.minimum.reduce([x, 1 - x, y, 1 - y]) * F
    return smooth(GUTTER, GUTTER + 12, d)


def noise3(rng, h, w, t=T, beta=1.8, k0=1.0, k1=None, ax=1.0, ay=1.0, wind=(0, 0), churn=0.6):
    """Noise periodic in x, y and time, by spectral synthesis.

    wind: whole domain-widths travelled per loop (x, y), so it scrolls and still loops.
    churn: how many cycles per loop the pattern changes by, at wavenumber 1.
    ax, ay stretch the spectrum: ax > 1 makes features narrower in x.
    Returns unit variance floats (t, h, w).
    """
    kt = sf.fftfreq(t, 1 / t).reshape(-1, 1, 1)
    ky = sf.fftfreq(h, 1 / h).reshape(1, -1, 1)
    kx = sf.rfftfreq(w, 1 / w).reshape(1, 1, -1)
    k = np.sqrt((kx / ax) ** 2 + (ky / ay) ** 2)
    k[0, 0, 0] = 1
    amp = k ** (-(beta + 1) / 2)
    amp[k < k0] = 0
    if k1:
        amp *= np.exp(-((k / k1) ** 4))
    # Small things change faster; everything is carried along by the wind.
    centre = -(kx * wind[0] + ky * wind[1])
    sigma = churn * k ** 0.6 + 0.35
    amp = amp * np.exp(-0.5 * ((kt - centre) / sigma) ** 2)
    phase = rng.uniform(0, 2 * np.pi, amp.shape)
    spec = amp * np.exp(1j * phase)
    out = sf.irfftn(spec, s=(t, h, w), workers=WORKERS).astype(np.float32)
    return out / out.std()


def seam_blend(s, m):
    """Crossfades s[o+T..o+T+m) back under s[o..o+m), so frame T-1 runs straight into frame 0.

    Sim motion comes in bursts, so where spare frames allow it, the join goes at a quiet moment.
    """
    spare = s.shape[0] - T - m
    if spare > 0:
        steps = [np.abs(s[o + T] - s[o + T - 1]).mean() for o in range(spare + 1)]
        o = int(np.argmin(steps))
        s = s[o:o + T + m]
    out = s[:T].copy()
    for t in range(m):
        w = (t + 0.5) / m
        w = w * w * (3 - 2 * w)
        # Equal-power, so the blended middle doesn't sag; flat at both ends, so no kink at the seam.
        a, b = np.sin(0.5 * np.pi * w), np.cos(0.5 * np.pi * w)
        mix = a * s[t] + b * s[T + t]
        mean = w * s[t].mean() + (1 - w) * s[T + t].mean()
        out[t] = mix * (mean / max(mix.mean(), 1e-6))
    return out


def to_frame(s):
    """Sim frames (t, n, n) to (t, F, F), area averaged."""
    k = s.shape[1] // F
    return s.reshape(s.shape[0], F, k, F, k).mean(axis=(2, 4)).astype(np.float32)


def down2(a):
    return 0.25 * (a[..., ::2, ::2] + a[..., 1::2, ::2] + a[..., ::2, 1::2] + a[..., 1::2, 1::2])


def flatten_mean(frames, amount):
    """Takes out slow pulsing in overall density."""
    m = frames.mean(axis=(1, 2))
    return frames * ((m.mean() / np.maximum(m, 1e-6)) ** amount).reshape(-1, 1, 1)


# ---------------------------------------------------------------- the sheets

def steam_billow(cache, rng):
    s = np.load(f"{cache}/sim-billow.npy")
    # The puff sits low of centre in the box; take the square around it and use the frame fully.
    n = s.shape[1]
    c = n * 3 // 4 - (n * 3 // 4) % F
    top = int(n * 0.30)
    left = (n - c) // 2
    s = to_frame(s[:, top:top + c, left:left + c])
    s = seam_blend(s, 32)
    # Line-of-sight density through a saturating curve, like real optical depth.
    k = 1.0 / np.percentile(s, 99.7)
    d = 1 - np.exp(-1.7 * k * s)
    d = flatten_mean(d, 0.8)
    y, x = grid()
    r = np.sqrt(((x - 0.5) / 0.47) ** 2 + ((y - 0.5) / 0.44) ** 2)
    env = 1 - smooth(0.66, 1.0, r)
    d = d * env
    return d / np.percentile(d, 99.9) * 0.94


def steam_rise(cache, rng):
    s = np.load(f"{cache}/sim-rise.npy")
    s = to_frame(s)
    s = seam_blend(s, 32)
    k = 1.0 / np.percentile(s, 99.7)
    d = 1 - np.exp(-1.5 * k * s)
    d = flatten_mean(d, 0.6)
    y, x = grid()
    # Tapers out of a point low down, dissolves by the top, closes in at the sides.
    width = 0.10 + 0.36 * smooth(0.98, 0.55, y)
    side = 1 - smooth(width * 0.45, width, np.abs(x - 0.5))
    env = (1 - smooth(0.62, 0.96, y)) ** 1.3 * smooth(0.03, 0.4, y) * side
    d = d * env
    return d / np.percentile(d, 99.9) * 0.94


def fog_bank(cache, rng):
    s = np.load(f"{cache}/sim-fog.npy")                      # (t, 128, 512): the sim is 4:1
    # The whole bank also slides sideways, on top of what the sim's wind does: half a pixel a
    # frame here, so a quarter of the card a loop. The box is periodic in x, so that costs nothing.
    s = np.stack([np.roll(f, 2 * t, axis=1) for t, f in enumerate(s)])
    s = 0.25 * (s[..., ::4] + s[..., 1::4] + s[..., 2::4] + s[..., 3::4])
    s = seam_blend(s, 32)
    k = 1.0 / np.percentile(s, 99.5)
    d = 1 - np.exp(-1.1 * k * s)
    d = flatten_mean(d, 1.0)
    y, x = grid()
    # The ends close softly and unevenly, carried along with the drift, and the bank humps up
    # towards the middle, so it never reads as a rectangle.
    wob = noise3(rng, F, F, beta=2.5, k0=1, k1=5, ax=1.0, ay=1.0, wind=(1, 0), churn=0.3)
    r = np.abs(x - 0.5) * 2 + 0.07 * wob
    hump = 0.34 + 0.2 * r ** 2
    env = (1 - smooth(0.42, 0.97, r)) * smooth(hump - 0.26, hump + 0.14, y) * smooth(0.98, 0.74, y)
    d = flatten_mean(d * env, 1.0)
    return d / np.percentile(d, 99.9) * 0.9


@njit(parallel=False, fastmath=True)
def splat_dashes(img, xs, ys, lens, wids, alphas, slopes):
    """Short motion-blurred dashes, trailing back along -x from (x, y), in px."""
    h, w = img.shape
    for n in range(xs.size):
        a = alphas[n]
        if a < 0.004:
            continue
        L = lens[n]
        x1 = xs[n]
        x0 = x1 - L
        for px in range(max(0, int(x0)), min(w, int(x1) + 2)):
            u = (px + 0.5 - x0) / L
            if u <= 0 or u >= 1:
                continue
            taper = u * u * (3 - 2 * u) * min(1.0, (1 - u) * 6)   # a soft tail, a brighter tip
            yc = ys[n] + slopes[n] * (px + 0.5 - x1)
            r = wids[n] * 2.6
            for py in range(max(0, int(yc - r)), min(h, int(yc + r) + 2)):
                dy = (py + 0.5 - yc) / wids[n]
                img[py, px] += a * taper * np.exp(-0.5 * dy * dy)


def sand_gust(cache, rng):
    SS = 2
    W = F * SS
    y, x = grid(W)
    # The gust's front crosses the frame GUST times a loop. The grit it picks up moves slower
    # (GRIT wraps a loop), so it falls behind the front and tears up in the tail: clots first,
    # then separate filaments, then specks. Everything is whole wraps, so it loops exactly.
    GUST, GRIT = 3, 2
    clots = noise3(rng, W, W, beta=2.0, k0=2, k1=44, ax=0.22, ay=1.0, wind=(GRIT, 0), churn=0.5)
    streak = noise3(rng, W, W, beta=1.1, k0=3, k1=110, ax=0.09, ay=1.0, wind=(GRIT, 0), churn=0.7)

    def wave(xx, p):
        """Lane centre: slow travelling waves, whole cycles in x and t."""
        v = 0.0
        for kx, kt, amp, ph in ((1, 1, 0.012, 0.3), (2, 1, 0.007, 2.1), (3, 2, 0.004, 4.4)):
            v = v + amp * np.sin(2 * np.pi * (kx * xx - kt * p) + ph)
        return 0.5 + v

    def back(xx, p):
        return (GUST * p - xx) % 1.0

    def spread(s):
        return 0.03 + 0.1 * smooth(0.02, 1.0, s) ** 1.1

    def along(s):
        return smooth(0.0, 0.05, s) * (1 - smooth(0.62, 1.0, s))

    def tear_th(s):
        return -1.7 + 2.3 * smooth(0.25, 1.0, s)

    N = 4200
    x0 = rng.uniform(0, 1, N)
    lanes = np.clip(rng.normal(0, 0.85, 26), -1.6, 1.6)
    lane = rng.integers(0, 26, N)
    z = lanes[lane] + rng.normal(0, 0.07, N)
    free = rng.random(N) < 0.35           # loose grit between the filaments, so it isn't a comb
    z[free] = rng.normal(0, 0.8, free.sum())
    z = np.clip(z, -1.7, 1.7)
    # Each filament wanders on its own, whole cycles in x and time.
    lk = rng.integers(2, 6, 26); ln = rng.integers(1, 4, 26); lp = rng.uniform(0, 2 * np.pi, 26)
    lk, ln, lp = lk[lane], ln[lane], lp[lane]
    wraps = rng.choice([GRIT, GRIT, GRIT, GRIT, GRIT + 1, GRIT - 1], N)
    lens = rng.uniform(3.0, 7.0, N) * SS * (wraps / GRIT)
    wids = rng.uniform(0.26, 0.42, N) * SS
    gain = rng.lognormal(-2.1, 0.8, N)

    out = np.zeros((T, F, F), np.float32)
    yy = (np.arange(W) + 0.5) / W
    for t in range(T):
        p = t / T
        s = back(x, p)
        yc = wave(x, p)
        sp = spread(s)
        lane_mask = np.exp(-(((y - yc) / sp) ** 2))
        # Haze: the same streaks and clots, soft, following the wandering lane.
        dy = (yc - 0.5) * W
        rows = (y * W - 0.5) - dy
        cols = x * W - 0.5
        st = ndi.map_coordinates(streak[t], [rows, cols], order=1, mode="grid-wrap")
        cl = ndi.map_coordinates(clots[t], [rows, cols], order=1, mode="grid-wrap")
        th = tear_th(s)
        tear = smooth(th - 0.15, th + 0.5, cl)
        haze = lane_mask * along(s) * tear * np.clip(0.12 + 0.3 * st, 0, 1.2)
        # Grit.
        px = (x0 + wraps * p) % 1.0
        ps = back(px, p)
        pyc = wave(px, p)
        py = pyc + z * spread(ps) * 0.72 + 0.011 * np.sin(2 * np.pi * (lk * px - ln * p) + lp)
        ix = np.clip((px * W).astype(int), 0, W - 1)
        iy = np.clip((py * W).astype(int), 0, W - 1)
        pcl = clots[t][np.clip(((py - pyc + 0.5) * W).astype(int), 0, W - 1), ix]
        pth = tear_th(ps)
        ptear = smooth(pth - 0.1, pth + 0.35, pcl)
        alpha = gain * along(ps) * ptear
        slope = (wave(px + 0.01, p) - pyc) / 0.01
        img = np.zeros((W, W), np.float32)
        splat_dashes(img, (px * W).astype(np.float32), py.astype(np.float32) * W,
                     lens.astype(np.float32), wids.astype(np.float32), alpha.astype(np.float32), slope.astype(np.float32))
        total = 0.6 * haze + img
        out[t] = down2(total)
    win = smooth(0.05, 0.24, grid()[1]) * (1 - smooth(0.76, 0.95, grid()[1]))
    d = 1 - np.exp(-0.8 * out * win)
    d = flatten_mean(d, 0.7)
    return d / np.percentile(d, 99.9) * 0.92


def light_shaft(cache, rng):
    # Period of the drift noise is one frame, so one wrap a loop is 2 px a frame; played at
    # 10-12 fps that's slow. The rays only change by churn, they don't travel.
    W = F * 2
    drift = noise3(rng, W, W, beta=2.6, k0=1, k1=14, ax=1.0, ay=0.22, wind=(0, -1), churn=0.22)
    rays = noise3(rng, 8, W, beta=1.4, k0=3, k1=26, ax=1.0, ay=0.5, churn=0.12)
    drift, rays = down2(drift), rays[:, ::2, ::2].mean(axis=1)
    y, x = grid()
    half = 0.06 + 0.135 * y                # a beam opening as it comes down
    u = (x - 0.5) / half
    beam = np.exp(-(np.abs(u) ** 2.3))
    halo = 0.22 * np.exp(-((np.abs(u) / 2.0) ** 2))   # the lit air around the beam proper
    along = smooth(0.02, 0.3, y) * (1 - smooth(0.3, 0.97, y)) ** 0.9
    out = np.empty((T, F, F), np.float32)
    for t in range(T):
        col = np.interp(u * 0.2 + 0.5, (np.arange(F) + 0.5) / F, rays[t], period=1.0)
        out[t] = (beam * (0.72 + 0.13 * drift[t] + 0.2 * col) + halo * (0.8 + 0.25 * drift[t])) * along
    out = np.clip(out, 0, None)
    out = flatten_mean(out, 1.0)
    # Motes: few, tiny, sinking slowly through the beam, each fading in and out on its own path.
    n = 42
    mu = rng.uniform(-1.2, 1.2, n); y0 = rng.uniform(0.04, 0.75, n)
    fall = rng.uniform(0.10, 0.26, n); ph = rng.uniform(0, 1, n); ph2 = rng.uniform(0, 1, n)
    side = rng.uniform(0.004, 0.016, n); size = rng.uniform(0.42, 0.72, n)
    bright = rng.lognormal(-1.5, 0.55, n)
    yr, xr = np.mgrid[0:F, 0:F]
    for t in range(T):
        p = t / T
        for i in range(n):
            life = (p + ph[i]) % 1
            py = y0[i] + fall[i] * life
            ph_half = 0.06 + 0.135 * py
            px = 0.5 + mu[i] * ph_half + side[i] * np.sin(2 * np.pi * (life + ph2[i]))
            fade = np.sin(np.pi * life) ** 2
            cx, cy = px * F - 0.5, py * F - 0.5
            a = (bright[i] * fade * np.exp(-0.6 * mu[i] ** 2)
                 * float(smooth(0.03, 0.2, py) * (1 - smooth(0.4, 0.95, py)) ** 0.6))
            d2 = (xr - cx) ** 2 + (yr - cy) ** 2
            out[t] += a * np.exp(-d2 / (2 * size[i] ** 2))
    return out / np.percentile(out, 99.95) * 0.92


SHEETS = {
    "steam-billow": steam_billow,
    "fog-bank": fog_bank,
    "sand-gust": sand_gust,
    "steam-rise": steam_rise,
    "light-shaft": light_shaft,
}
SEEDS = {"steam-billow": 1, "fog-bank": 2, "sand-gust": 3, "steam-rise": 4, "light-shaft": 5}


def save_sheet(name, frames):
    gate = frame_gate()
    d = np.clip(frames * gate, 0, 1)
    img = np.zeros((F * 8, F * 8), np.uint8)
    for t in range(T):
        r, c = t // 8, t % 8
        # Rounded down at the bottom so the fade really gets to zero.
        v = np.floor(d[t] * 255 + 0.5).astype(np.uint8)
        v[d[t] * 255 < 1.0] = 0
        img[r * F:(r + 1) * F, c * F:(c + 1) * F] = v
    path = f"{HERE}/{name}.png"
    Image.fromarray(img, "L").save(path, optimize=True)
    print(f"{name}: {os.path.getsize(path) / 1024:.0f} KB, mean {img.mean():.1f}, max {img.max()}, "
          f"nonzero {(img > 0).mean() * 100:.0f}%")


def main():
    cache = sys.argv[1]
    names = sys.argv[2:] or list(SHEETS)
    for name in names:
        rng = np.random.default_rng(SEEDS[name])
        save_sheet(name, SHEETS[name](cache, rng))


if __name__ == "__main__":
    main()
