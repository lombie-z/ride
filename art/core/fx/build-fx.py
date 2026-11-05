"""The stair and tunnel sections' water normal map and flipbooks. All generated, nothing from outside: no CC0 source came as a usable
tiling sheet, and generating them keeps the format the same as art/sprites. See NOTES.md.

    python3 -I art/core/fx/build-fx.py [out]
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ni

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
F, GRID = 128, 8  # 8 x 8 frames of 128, as art/sprites
SS = 2  # drawn at twice the size, then area-averaged
GUTTER = 7


def periodic(seed, n, beta, lo, hi=None, ax=(1, 1)):
    """Periodic noise on an n x n tile, mean 0, std 1, spectrum 1/f^beta between lo and hi cycles a tile."""
    rng = np.random.default_rng(seed)
    f0 = np.fft.fftfreq(n)[:, None] * n * ax[0]
    f1 = np.fft.rfftfreq(n)[None, :] * n * ax[1]
    r = np.hypot(f0, f1)
    amp = np.where(r >= lo, 1 / np.maximum(r, 1) ** beta, 0)
    if hi:
        amp = amp * np.exp(-(r / hi) ** 2)
    x = np.fft.irfft2(amp * (rng.normal(size=amp.shape) + 1j * rng.normal(size=amp.shape)), s=(n, n))
    return ((x - x.mean()) / x.std()).astype(np.float32)


def water_normal(n=512):
    """Dark water with some chop in it: long swell across the tile, cross chop, sharp crests, a little ripple. Height is built on the whole tile, so its normals tile exactly."""
    swell = periodic(1, n, 2.2, 2, 13, ax=(1.5, 0.9))
    chop = periodic(2, n, 1.8, 6, 40, ax=(1.2, 1))
    # Sharpen the crests: water's peaks are narrower than its troughs.
    crest = 1 - np.abs(periodic(3, n, 1.9, 4, 24, ax=(1.3, 1)))
    crest = crest - crest.mean()
    ripple = periodic(4, n, 1.6, 20, 64)
    h = 1.0 * swell + 0.75 * chop + 0.7 * crest + 0.05 * ripple
    h = ni.gaussian_filter(h, 1.0, mode='wrap')
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    k = 15.0
    nx, ny, nz = -gx * k, gy * k, np.ones_like(h)  # OpenGL / three: green is up the tile
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack((nx / l, ny / l, nz / l), -1) * 0.5 + 0.5
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


class Sheet:
    def __init__(self):
        self.s = F * SS
        self.frames = np.zeros((64, self.s, self.s), np.float32)

    def blob(self, i, x, y, r, a):
        """A soft round blob, additive. x, y in 0..1 of the frame (y down)."""
        f = self.frames[i]
        s = self.s
        px, py, pr = x * s, y * s, max(r * s, 0.8)
        x0, x1 = int(max(px - 3 * pr, 0)), int(min(px + 3 * pr + 1, s))
        y0, y1 = int(max(py - 3 * pr, 0)), int(min(py + 3 * pr + 1, s))
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        f[y0:y1, x0:x1] += a * np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * pr * pr))

    def streak(self, i, x0, y0, x1, y1, w, a0, a1=None):
        """A line with a soft width, its brightness going from a0 to a1: a motion-blurred droplet or spark."""
        a1 = a0 if a1 is None else a1
        f = self.frames[i]
        s = self.s
        ax, ay, bx, by = x0 * s, y0 * s, x1 * s, y1 * s
        pw = max(w * s, 0.7)
        xa, xb = int(max(min(ax, bx) - 3 * pw, 0)), int(min(max(ax, bx) + 3 * pw + 1, s))
        ya, yb = int(max(min(ay, by) - 3 * pw, 0)), int(min(max(ay, by) + 3 * pw + 1, s))
        if xa >= xb or ya >= yb:
            return
        yy, xx = np.ogrid[ya:yb, xa:xb]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy + 1e-6
        t = np.clip(((xx - ax) * dx + (yy - ay) * dy) / ll, 0, 1)
        d2 = (xx - ax - t * dx) ** 2 + (yy - ay - t * dy) ** 2
        f[ya:yb, xa:xb] += (a0 + (a1 - a0) * t) * np.exp(-d2 / (2 * pw * pw))

    def finish(self, soft=0.0, curve=1.0, peak=1.0):
        out = np.zeros((F * GRID, F * GRID), np.uint8)
        # Clean edges: every frame fades to true black inside the same gutter as art/sprites.
        r = np.arange(F, dtype=np.float32)
        e = np.minimum(r, F - 1 - r)
        edge = np.clip((e - GUTTER + 1) / 6, 0, 1)
        win = np.minimum.outer(edge, edge)
        win = win * win * (3 - 2 * win)
        for i, f in enumerate(self.frames):
            if soft:
                f = ni.gaussian_filter(f, soft * SS)
            f = f.reshape(F, SS, F, SS).mean((1, 3))
            f = (1 - np.exp(-f / peak)) ** curve * win
            out[(i // GRID) * F:(i // GRID + 1) * F, (i % GRID) * F:(i % GRID + 1) * F] = (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)
        return out


def spray():
    """A one-shot fan of water thrown up and out to +u, as a bike ploughs through: a dense sheet at the root, tearing into drops. 64 frames, plays once."""
    S = Sheet()
    rng = np.random.default_rng(11)
    n = 2600
    # Every drop leaves the root (lower left) over the first third, up and to the right, with its own speed and size.
    t0 = rng.random(n) ** 1.4 * 0.42
    ang = np.radians(rng.normal(52, 13, n))
    spd = rng.lognormal(0.0, 0.3, n) * 1.02
    size = rng.lognormal(-5.2, 0.5, n)
    x00 = 0.14 + rng.normal(0, 0.03, n)
    y00 = 0.86 + rng.normal(0, 0.015, n)
    g = 2.0
    for i in range(64):
        t = i / 63
        dt = 1 / 63
        age = t - t0
        live = age > 0
        fade = np.clip(1 - age / (0.72 + 0.1 * (spd - 1.2)), 0, 1)
        x = x00 + np.cos(ang) * spd * age * 0.72
        y = y00 - np.sin(ang) * spd * age + 0.5 * g * age * age
        xp = x - np.cos(ang) * spd * 0.72 * dt * 2.2
        yp = y + (np.sin(ang) * spd - g * age) * dt * 2.2
        for k in np.nonzero(live & (fade > 0) & (y < 0.97))[0]:
            S.streak(i, xp[k], yp[k], x[k], y[k], size[k] * 0.7, 0.34 * fade[k] ** 0.5, 0.8 * fade[k] ** 0.5)
        # The sheet of water at the root and its mist: thick early, thin late, soft.
        body = max(0.0, 1 - t / 0.55)
        rising = min(1.0, t / 0.05)
        for j in range(26):
            u = j / 25
            ht = (0.08 + 0.55 * min(t * 3, 1)) * u
            S.blob(i, 0.17 + 0.46 * ht + 0.02 * np.sin(j * 7.3 + i * 0.3), 0.86 - ht * (1 - 0.3 * t), 0.022 + 0.09 * u + 0.06 * t, 0.44 * rising * body * (1 - 0.55 * u))
        # Mist hanging where the drops went, soft and faint.
        mist = np.sin(np.pi * np.clip(t * 1.05, 0, 1)) ** 1.5
        for j in range(9):
            a = j * 2.399
            S.blob(i, 0.24 + 0.056 * j * (0.4 + t) + 0.03 * np.sin(a), 0.74 - 0.042 * j * (0.5 + t) + 0.03 * np.cos(a), 0.04 + 0.07 * t, 0.13 * mist)
    return S.finish(curve=0.9, peak=1.1)


def fluid_step(u, v, d, dt, conf, n):
    """One step of a small periodic smoke solver on an n x n grid: semi-Lagrangian advection, vorticity confinement, FFT pressure."""
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    px, py = xx - u * dt, yy - v * dt
    co = [py, px]
    d = ni.map_coordinates(d, co, order=1, mode='wrap')
    u2 = ni.map_coordinates(u, co, order=1, mode='wrap')
    v2 = ni.map_coordinates(v, co, order=1, mode='wrap')
    w = (np.roll(v2, -1, 1) - np.roll(v2, 1, 1) - np.roll(u2, -1, 0) + np.roll(u2, 1, 0)) / 2
    aw = np.abs(w)
    gx = (np.roll(aw, -1, 1) - np.roll(aw, 1, 1)) / 2
    gy = (np.roll(aw, -1, 0) - np.roll(aw, 1, 0)) / 2
    l = np.sqrt(gx * gx + gy * gy) + 1e-4
    u2 += dt * conf * (gy / l) * w
    v2 -= dt * conf * (gx / l) * w
    ku = np.fft.fftfreq(n)[None, :] * 2 * np.pi
    kv = np.fft.fftfreq(n)[:, None] * 2 * np.pi
    k2 = ku * ku + kv * kv
    k2[0, 0] = 1
    U, V = np.fft.fft2(u2), np.fft.fft2(v2)
    div = ku * U + kv * V
    U -= ku * div / k2
    V -= kv * div / k2
    return np.fft.ifft2(U).real.astype(np.float32), np.fft.ifft2(V).real.astype(np.float32), d


def steam_layer(seed, n=256):
    """One plane of the burst: a broad jet out of the bottom centre, sudden start, cut off after a third."""
    rng = np.random.default_rng(seed)
    u = np.zeros((n, n), np.float32)
    v = np.zeros((n, n), np.float32)
    d = np.zeros((n, n), np.float32)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    # Top and bottom soak up what reaches them, or it would wrap round the periodic grid.
    r = yy / n
    sponge = np.clip(r / 0.14, 0, 1) * np.clip((0.97 - r) / 0.04, 0, 1)
    sponge = (sponge * sponge * (3 - 2 * sponge)) ** 0.08
    frames = []
    sub = 4
    ph = rng.uniform(0, 6.28, 4)
    off = rng.normal(0, 9)
    stop = rng.uniform(0.2, 0.32)
    power = rng.uniform(13, 18)
    for i in range(64):
        for j in range(sub):
            tt = (i + j / sub) / 63
            on = np.clip(tt / 0.012, 0, 1) * np.clip((stop - tt) / 0.07, 0, 1)
            if on > 0:
                cx = n * 0.5 + off + 7 * np.sin(tt * 60 + ph[0]) + 4 * np.sin(tt * 145 + ph[1])
                src = np.exp(-(((xx - cx) / 10.0) ** 2 + ((yy - n * 0.88) / 6.0) ** 2))
                d = np.maximum(d, src * on)
                v = v * (1 - src) - src * on * power
                u = u + src * on * (9 * np.sin(tt * 110 + ph[2]) + 6 * np.sin(tt * 260 + ph[3]))
            v -= 0.035 * d
            u, v, d = fluid_step(u, v, d, 0.6, 0.55, n)
            u *= 0.995 * sponge
            v *= 0.995 * sponge
            d *= 0.998 * sponge
        frames.append(d.copy())
    return frames


def steam_burst():
    """A jet going up and billowing, gone by the last frame. Plays once. Several planes of a small 2D smoke sim added up, as depth would, so it's soft with real curl in it."""
    layers = [steam_layer(21 + k) for k in range(6)]
    S = Sheet()
    for i in range(64):
        t = i / 63
        f = sum(l[i] for l in layers) / len(layers) * 1.7
        # Thins as it goes, faster at the end, so the last frames are clean.
        f = f * np.clip((1.0 - t) / 0.5, 0, 1) ** 1.2
        S.frames[i] = ni.zoom(f, S.s / f.shape[0], order=1, mode='grid-wrap', grid_mode=True)
    S.frames = ni.gaussian_filter(S.frames, (0, 1.2, 1.2))
    return S.finish(curve=0.85, peak=0.55)


def sparks():
    """A burst from the centre top third: hot drops flying out, falling, some bouncing. Thin bright lines, for additive. Plays once."""
    S = Sheet()
    rng = np.random.default_rng(31)
    n = 110
    t0 = rng.random(n) ** 2.5 * 0.3
    ang = rng.uniform(0, np.pi * 2, n)
    spd = rng.lognormal(-0.2, 0.55, n) * 0.9
    vx0, vy0 = np.cos(ang) * spd, np.sin(ang) * spd * 0.7 - 0.25
    life = rng.uniform(0.35, 0.95, n)
    x0, y0 = 0.5, 0.34
    g = 2.2
    floor = 0.86
    def pos(t, k):
        a = t - t0[k]
        y = y0 + vy0[k] * a + 0.5 * g * a * a
        x = x0 + vx0[k] * a
        return x, y
    for i in range(64):
        t = i / 63
        dt = 1 / 63
        for k in range(n):
            a = t - t0[k]
            if a <= 0 or a > life[k]:
                continue
            x, y = pos(t, k)
            xp, yp = pos(t - dt * 1.6, k)
            # Off the floor once, at half speed.
            if y > floor:
                tb = t0[k] + (-vy0[k] + np.sqrt(max(vy0[k] ** 2 + 2 * g * (floor - y0), 0))) / g
                ab = t - tb
                x = x0 + vx0[k] * (tb - t0[k]) + vx0[k] * 0.6 * ab
                y = floor + (-(vy0[k] + g * (tb - t0[k])) * 0.42) * ab + 0.5 * g * ab * ab
                ab2 = ab - dt * 1.6
                xp = x0 + vx0[k] * (tb - t0[k]) + vx0[k] * 0.6 * ab2
                yp = floor + (-(vy0[k] + g * (tb - t0[k])) * 0.42) * ab2 + 0.5 * g * ab2 * ab2
                if y > floor + 0.005:
                    continue
            heat = (1 - a / life[k]) ** 0.7
            S.streak(i, xp, yp, x, y, 0.0062, 0.7 * heat, 3.0 * heat)
        # The flash at the start.
        flash = np.exp(-t / 0.035)
        S.blob(i, x0, y0, 0.05 + 0.1 * t, 2.2 * flash)
        S.blob(i, x0, y0, 0.015, 3.5 * flash)
    return S.finish(curve=1.0, peak=0.95)


def drips():
    """A loop: a line of drops falling down the frame, each growing at the top, stretching, gone. For wet ceilings and pipes; whole cycles, so frame 63 runs on to frame 0."""
    S = Sheet()
    rng = np.random.default_rng(41)
    n = 7
    xs = 0.16 + 0.68 * (np.arange(n) + rng.uniform(0.15, 0.85, n)) / n
    phase = rng.random(n)
    cyc = rng.integers(1, 3, n)  # 1 or 2 drops a loop each
    sz = rng.uniform(0.75, 1.3, n)
    y_top = 0.12
    y_end = 1.02
    for i in range(64):
        t = i / 64
        for k in range(n):
            p = (t * cyc[k] + phase[k]) % 1
            if p < 0.62:
                # Hanging and swelling: a bead on the lip.
                g = p / 0.62
                S.blob(i, xs[k], y_top + 0.012 * g, 0.009 + 0.011 * g * sz[k], 1.3 * g)
            else:
                # Falling, accelerating, a stretched bright line.
                f = (p - 0.62) / 0.38
                y = y_top + 0.012 + (y_end - y_top) * f * f
                back = (y_end - y_top) * 2 * f * (1 / 64) * cyc[k] / 0.38 * 2.2
                S.streak(i, xs[k], max(y - back - 0.005, y_top), xs[k], y, 0.0078 * sz[k], 0.45, 2.4)
    return S.finish(curve=1.0, peak=0.8)


def save(name, a):
    p = os.path.join(OUT, name + '.png')
    Image.fromarray(a).save(p, optimize=True)
    print(name, a.shape, a.dtype, os.path.getsize(p) // 1024, 'KB')


if __name__ == '__main__':
    only = sys.argv[2:] or ['water', 'spray', 'steam', 'sparks', 'drips']
    if 'water' in only:
        save('water-normal', water_normal())
    if 'spray' in only:
        save('spray', spray())
    if 'steam' in only:
        save('steam-burst', steam_burst())
    if 'sparks' in only:
        save('sparks', sparks())
    if 'drips' in only:
        save('drips', drips())
