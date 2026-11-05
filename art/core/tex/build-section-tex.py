"""The stair and tunnel sections' surfaces: wet_concrete, slimy_concrete, heavy_rust, riveted_steel, dark_steel, paint_grey (see LICENSES.md).
Every step wraps, so the 512 x 512 results tile. Sources are the 1k colour maps, in a folder given as the first argument, kept out of the repo.

    python3 -I art/core/tex/build-section-tex.py <sources> [out]
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ni

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
N = 1024


def load(name):
    im = Image.open(os.path.join(SRC, name + '.jpg')).convert('RGB')
    if im.size != (N, N):
        im = im.resize((N, N), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255


def lum(a):
    return a @ np.array([0.2126, 0.7152, 0.0722], np.float32) if a.ndim == 3 else a


def blur(a, s):
    sig = (s, s, 0) if a.ndim == 3 else (s, s)
    return ni.gaussian_filter(a, sig, mode='wrap')


def hp(a, s):
    return a - blur(a, s)


def delit(a, s=120, amount=1.0):
    """Take the photo's own broad light out, keep its colour."""
    l = np.maximum(blur(lum(a), s), 1e-3)
    return a * ((l.mean() / l) ** amount)[..., None]


def seam_free(a, w=70):
    """Fade the outer w px into the same map shifted half a tile, for sources whose edges don't quite meet."""
    r = np.linspace(0, 1, N, endpoint=False)
    e = np.minimum(r, 1 - r) * N / w
    m = np.clip(np.minimum.outer(e, e), 0, 1)
    m = (m * m * (3 - 2 * m))[..., None]
    return a * m + np.roll(a, (N // 2, N // 2), (0, 1)) * (1 - m)


def fbm(seed, beta=1.6, lo=1.5, ax=(1, 1)):
    """Soft periodic clouds with no edges of their own, 0..1 by rank."""
    rng = np.random.default_rng(seed)
    f0 = np.fft.fftfreq(N)[:, None] * N * ax[0]
    f1 = np.fft.rfftfreq(N)[None, :] * N * ax[1]
    r = np.hypot(f0, f1)
    amp = np.where(r >= lo, 1 / np.maximum(r, 1) ** beta, 0)
    x = np.fft.irfft2(amp * (rng.normal(size=amp.shape) + 1j * rng.normal(size=amp.shape)), s=(N, N))
    o = np.empty(N * N, np.float32)
    o[np.argsort(x.ravel())] = np.linspace(0, 1, N * N, dtype=np.float32)
    return o.reshape(N, N)


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def rustness(name):
    """Where a photographed plate's rust runs: red over blue, normalised. Real streaks, the shapes noise can't make."""
    a = load(name)
    # A tall median takes out the plates' horizontal seams, which would otherwise repeat as lines; the runs survive it.
    m = blur(ni.median_filter(a[..., 0] - a[..., 2], size=(21, 1), mode='wrap'), 1.2)
    lo, hi = np.percentile(m, [4, 96])
    return np.clip((m - lo) / (hi - lo), 0, 1)


def darks(name, s=60):
    """A photo's own darker-than-its-surroundings marks, 0..1."""
    l = lum(load(name))
    m = blur(l, s) - blur(l, 1.5)
    return np.clip(m / np.percentile(m, 98), 0, 1)


def run_down(m, length):
    """Whatever's in mask m runs down the tile (rows increase) and fades over about `length` px: a one-sided kernel, wrapped."""
    k = np.exp(-np.arange(N, dtype=np.float32) / length)
    k /= k.sum()
    return np.fft.irfft(np.fft.rfft(m, axis=0) * np.fft.rfft(k)[:, None], n=N, axis=0).astype(np.float32)


def tone(a, target):
    """Scale to a mean luminance, in the sRGB values kept in the JPEG."""
    return a * (target / lum(a).mean())


def save(name, a, q=88):
    a = np.clip(a, 0, 1)
    # Area down to 512, in linear light.
    lin = a ** 2.2
    lin = (lin[::2, ::2] + lin[1::2, ::2] + lin[::2, 1::2] + lin[1::2, 1::2]) / 4
    im = Image.fromarray((np.clip(lin, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8))
    p = os.path.join(OUT, name + '.jpg')
    im.save(p, quality=q, subsampling=0, optimize=True)
    print(name, im.size, os.path.getsize(p) // 1024, 'KB')


def wet_concrete():
    # concrete_wall_006 is the base: its own stains, tie holes and water marks, mostly kept.
    base = delit(load('concrete_wall_006'), 200, 0.8)
    l = lum(base)[..., None]
    a = base * 0.5 + l * 0.5
    a = a * np.array([0.97, 1.0, 0.95], np.float32)
    a += 0.5 * hp(lum(load('concrete_wall_007')), 45)[..., None]
    a += 0.4 * hp(lum(load('concrete_floor_worn_001')), 10)[..., None]
    a *= (1 - 0.35 * darks('dirty_concrete'))[..., None]
    # Stains running down: the rust runs of MetalPlates010 and 013, used only as shapes, in the dark.
    s1 = np.roll(rustness('acg_MetalPlates010'), 300, 1)
    s2 = np.roll(np.fliplr(rustness('acg_MetalPlates013')), 140, 0)
    a *= (1 - 0.6 * smooth(0.25, 0.9, s1 * (0.35 + 0.65 * fbm(41, 1.7, ax=(4, 1)))))[..., None]
    a *= (1 - 0.4 * smooth(0.45, 1.0, s2))[..., None]
    # Wet and less wet: broad, soft, long down the wall, big enough to last at 1/7.
    wet = fbm(42, 2.0, ax=(3, 1))
    a *= (1 - 0.34 * wet)[..., None]
    # Faint rusty bleed from the same shapes.
    bleed = (smooth(0.6, 1.0, np.roll(rustness('acg_MetalPlates012'), 512, 1)) * smooth(0.55, 0.85, fbm(43, 1.8, ax=(3, 1))))[..., None]
    a = a * (1 - 0.3 * bleed) + np.array([0.2, 0.11, 0.05], np.float32) * 0.3 * bleed
    return tone(a, 0.27)


def slimy_concrete():
    base = delit(load('concrete_wall_007'), 200, 0.9)
    l = lum(base)[..., None]
    a = base * 0.25 + l * 0.75
    a = a * np.array([0.95, 1.0, 0.9], np.float32) * 0.8
    a += 0.9 * hp(lum(load('concrete_wall_006')), 50)[..., None]
    a += 0.4 * hp(lum(load('concrete_floor_02')), 10)[..., None]
    # Where the slime sits: the steel-against-rust edge of MetalPlates012 gives real drips, gathered by soft long clouds.
    shape = rustness('acg_MetalPlates012')
    clouds = fbm(51, 1.8, 1.5, ax=(3.5, 1))
    slime = smooth(0.62, 1.0, shape * 0.55 + clouds * 0.75)[..., None]
    # Its colour is concrete_moss, dark and dirty; mossy_rock's lichen breaks it up.
    moss = delit(load('concrete_moss'), 70)
    ml = lum(moss)[..., None]
    moss = (ml + (moss - ml) * 0.72) * np.array([0.7, 0.72, 0.62], np.float32)
    rock = lum(load('mossy_rock'))
    lichen = np.clip(1 + 1.5 * (blur(rock, 2) - blur(rock, 40)), 0.45, 1.5)[..., None]
    a = a * (1 - 0.85 * slime) + moss * lichen * 0.85 * slime
    # Black wet runs through it all, the strongest thing in the tunnel image's wall: MetalPlates013's runs, again as shapes.
    runs = np.roll(rustness('acg_MetalPlates013'), 400, 1)
    gate = smooth(0.3, 0.72, fbm(52, 1.7, ax=(4, 1)))
    a *= (1 - 0.85 * smooth(0.35, 0.9, runs) * gate)[..., None]
    a *= (1 - 0.4 * smooth(0.25, 0.8, np.fliplr(rustness('acg_MetalPlates010'))))[..., None]
    return tone(a, 0.25)


def heavy_rust():
    # All photo: MetalPlates012 (rust over bared steel) and 011 (solid rust), with rusty_metal_05's scaling.
    a12 = delit(load('acg_MetalPlates012'), 200, 0.9)
    a11 = delit(seam_free(load('acg_MetalPlates011')), 200, 0.9)
    a05 = delit(load('rusty_metal_05'), 200, 0.9)
    bare = (1 - smooth(0.15, 0.5, rustness('acg_MetalPlates012')))[..., None]
    solid = smooth(0.35, 0.7, fbm(61, 1.9, ax=(2.5, 1)))[..., None]
    a = a12 * (1 - 0.8 * solid) + a11 * 0.8 * solid
    a = a * 0.8 + a05 * 0.2
    # What's bared under the rust is dark steel, not bright metal.
    a = a * (1 - bare * 0.85) + lum(a12)[..., None] * np.array([0.42, 0.44, 0.43], np.float32) * bare * 0.85
    a += 0.5 * hp(lum(load('rust_coarse_01')), 12)[..., None]
    # rusty_metal_04's dark flaking as pits, and 010's runs in the dark.
    flake = smooth(0.34, 0.2, lum(delit(load('rusty_metal_04'), 140)))
    a *= (1 - 0.6 * flake)[..., None]
    a *= (1 - 0.5 * smooth(0.35, 0.95, np.fliplr(rustness('acg_MetalPlates010'))))[..., None]
    # Pull the orange down: this is under dim red and green light, not daylight.
    l = lum(a)[..., None]
    a = l + (a - l) * 0.78
    return tone(a, 0.23)


def gunmetal():
    """Near-black steel with hints of rust, as the stairwell's rails and frames. Real marks: MetalPlates013's surface, metal_plate_02's scuffs."""
    a = delit(load('acg_MetalPlates013'), 200, 0.9)
    l = lum(a)[..., None]
    a = l * np.array([0.95, 0.99, 1.0], np.float32)
    a = l + (l - l.mean()) * 0.5 + (a - l)
    a += 0.8 * hp(lum(seam_free(load('metal_plate_02'))), 18)[..., None]
    a += 0.4 * hp(lum(load('rusty_metal_04')), 8)[..., None]
    return a


def rust_hints(a, sites, strength=0.5, length=60):
    """A little of rust_coarse_01's colour: at the sites, and running down from them only where MetalPlates012's runs say so."""
    rust = delit(load('rust_coarse_01'), 140)
    runs = smooth(0.45, 0.95, np.roll(rustness('acg_MetalPlates012'), 256, 1))
    m = np.clip(sites * 0.5 + run_down(sites, length) * 5 * runs, 0, 1)[..., None] * strength
    return a * (1 - m) + rust * 0.6 * m


def dark_steel():
    a = gunmetal()
    a *= (1 - 0.3 * fbm(71, 1.9, ax=(3, 1)))[..., None]
    a = tone(a, 0.23)
    # Hints only: rust just where MetalPlates012 is at its reddest.
    sites = smooth(0.82, 1.0, rustness('acg_MetalPlates012')) * smooth(0.55, 0.8, fbm(72, 1.8, ax=(3, 1)))
    return rust_hints(a, sites, 0.5, 40)


def riveted_steel():
    a = gunmetal()
    # Two courses of two plates, the second course offset half a plate: 2 x 2 m at 4 m a tile. Plate seams and rivets are generated: no CC0 source has them.
    rows, cols = np.mgrid[0:N, 0:N].astype(np.float32)
    ph = pw = N / 2
    course = np.floor(rows / ph).astype(int) % 2
    xoff = cols + course * pw / 2
    pid = (np.floor(xoff / pw).astype(int) % 2) + 2 * course
    # One tone per plate: the plates are what's left at 1/7.
    a *= np.array([0.8, 1.22, 1.0, 0.66], np.float32)[pid][..., None]
    a *= (1 - 0.25 * fbm(33, 1.9, ax=(3, 1)))[..., None]
    a = tone(a, 0.27)
    dy = np.minimum(rows % ph, ph - rows % ph)
    dx = np.minimum(xoff % pw, pw - xoff % pw)
    d = np.minimum(dy, dx)
    groove = 1 - smooth(3, 8, d)
    a *= (1 - 0.9 * groove)[..., None]
    # A lit lip beside each seam, a soft shadow past it.
    a += 0.07 * (smooth(5, 9, d) * (1 - smooth(9, 15, d)))[..., None]
    a *= (1 - 0.25 * (smooth(9, 14, d) * (1 - smooth(14, 40, d))))[..., None]
    # Rivets: rows set back from each seam, about 0.33 m apart, 0.17 m across: big, or they're gone at 1/7.
    inset, pitch, rad = 30.0, 84.0, 11.0
    rng = np.random.default_rng(31)
    height = np.zeros((N, N), np.float32)
    nx, ny = int(round(pw / pitch)), int(round(ph / pitch))
    wx, wy = pw / nx, ph / ny
    centres = []
    for c in range(2):
        for k in range(2):
            for i in range(nx):
                x0 = k * pw + (i + 0.5) * wx - c * pw / 2
                centres.append((c * ph + inset, x0))
                centres.append((c * ph + ph - inset, x0))
            for j in range(1, ny):
                x0 = k * pw - c * pw / 2
                centres.append((c * ph + j * wy, x0 + inset))
                centres.append((c * ph + j * wy, x0 - inset))
    Y, X = np.ogrid[-16:17, -16:17]
    for (y0, x0) in centres:
        if rng.random() < 0.06:
            continue  # the odd one's gone
        y0 = y0 + rng.normal(0, 0.8)
        x0 = x0 + rng.normal(0, 0.8)
        iy, ix = int(round(y0)), int(round(x0))
        dome = np.sqrt(np.clip(1 - ((Y + iy - y0) ** 2 + (X + ix - x0) ** 2) / rad ** 2, 0, 1))
        h = np.ix_(np.arange(iy - 16, iy + 17) % N, np.arange(ix - 16, ix + 17) % N)
        height[h] = np.maximum(height[h], dome)
    # Light the domes from high and to the left, as the wall lamps do.
    gy = ni.sobel(height, 0, mode='wrap') / 8
    gx = ni.sobel(height, 1, mode='wrap') / 8
    shade = np.clip(0.5 - 3.2 * (gy * 0.8 + gx * 0.5), 0, 1)
    dome = smooth(0.0, 0.25, height)[..., None]
    a = a * (1 - dome * 0.86) + (0.05 + 0.6 * shade)[..., None] * np.array([0.96, 0.96, 0.94], np.float32) * dome * 0.86
    a *= (1 - 0.55 * (blur(smooth(0.0, 0.1, height), 7) * (1 - dome[..., 0])))[..., None]
    # Hints of rust at some rivets and along some seams.
    sites = np.clip(dome[..., 0] + 0.5 * groove, 0, 1) * smooth(0.5, 0.75, fbm(34, 1.6))
    return rust_hints(a, sites, 0.6, 50)


def paint_grey():
    # Old paint on metal: rusty_metal_sheet is the coat, its colour taken down to a pale dirty grey; green_metal_rust's wear keeps the coat from being too clean.
    a = delit(load('rusty_metal_sheet'), 200, 0.9)
    rust = smooth(0.17, 0.36, blur(a[..., 0] - a[..., 2], 1))[..., None]
    l = lum(a)[..., None]
    grey = l * np.array([0.96, 0.98, 0.95], np.float32)
    grey += 0.6 * hp(lum(load('green_metal_rust')), 24)[..., None]
    # Only the heaviest of the sheet's rust survives, darkened, as chips and freckles.
    a = grey * (1 - 0.65 * rust) + (a * np.array([0.5, 0.42, 0.36], np.float32)) * 0.65 * rust
    # Grime down from the top, in MetalPlates013's runs.
    a *= (1 - 0.3 * smooth(0.45, 1.0, rustness('acg_MetalPlates013')))[..., None]
    return tone(a, 0.4)


if __name__ == '__main__':
    save('wet_concrete', wet_concrete())
    save('slimy_concrete', slimy_concrete())
    save('heavy_rust', heavy_rust())
    save('riveted_steel', riveted_steel())
    save('dark_steel', dark_steel())
    save('paint_grey', paint_grey())
