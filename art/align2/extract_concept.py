"""Extract the chrome city's arrival-shot features from the concept (art/reference/concept-chrome-city.webp at 1280x720).

Run: python3 art/align2/extract_concept.py
Writes art/align2/concept-features.json and, under art/align2/out/:
  concept-sky-mask.png     sky (white) vs everything else
  concept-screen-mask.png  the billboard's violet screen
  concept-features.png     every feature over the concept

Features (1280x720 px):
  skyline        topmost non-sky row per column (random-walker sky segmentation from loose seed strokes)
  sun            circle fitted to the visible disc's rim (bright warm pixels in the sky, RANSAC on the upper rim)
  screen         the billboard screen's quad (violet saturated region, holes filled, corners from the hull)
  dome           ellipse fitted to the glass dome's rim edges (RANSAC, gated by a loose prior box)
  monorail       the elevated track's underside, mid-left to centre (strongest bright-to-dark edge per column inside a
                 loose band), smoothed
  water_line     the reflective water's far edge (row of the strongest dark-above / bright-below change in a column band)
  horizon        where the eye-height plane sits: taken as the water line (the water is at the plaza's level, far away)
  bike_box       given by the brief (x 120-1110, y 370-890 of 1672x941), scaled to 1280x720
As in art/align/, the priors are loose regions; the measured value is what the pixels say inside them.
"""
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import color, feature, filters, measure, morphology, segmentation

from common import (FEATURES, H, OUT, SRC_H, SRC_W, W, concept_rgb, ransac_circle, ransac_ellipse, ellipse_box,
                    save_json)

os.makedirs(OUT, exist_ok=True)
RGB = concept_rgb()
GRAY = color.rgb2gray(RGB)
LAB = color.rgb2lab(RGB)
HSV = color.rgb2hsv(RGB)
GS = filters.gaussian(GRAY, 1.5)
GY = filters.sobel_h(GS)  # +: brighter going down


def save_mask(m, name):
    Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(OUT, name))


def draw(strokes, value, im):
    d = ImageDraw.Draw(im)
    for kind, a in strokes:
        if kind == 'rect':
            d.rectangle(a, fill=value)
        elif kind == 'poly':
            d.polygon(a, fill=value)
        elif kind == 'line':
            d.line(a[0], fill=value, width=a[1])


# --- Sky -------------------------------------------------------------------------------------------------------------
# The sky is smooth and shades from blue-violet overhead to pink-orange at the sun. A reference colour per row is taken
# from a clean strip of it (SKY_STRIPS), and sky = close to its row's colour (Lab) and untextured. Clouds and the flying
# car (non-sky blobs that don't reach down into the city) are folded back into the sky. Below SKY_FLOOR it's all city.
SKY_STRIPS = {(0, 200): (705, 785), (200, 330): (745, 770)}
SKY_FLOOR = 330
SKY_COLS = (400, 965)  # left of it the terraces fill the frame, right of it the billboard and its building


def sky_mask():
    lab = filters.gaussian(LAB, 1, channel_axis=-1)
    ref = np.zeros((H, 3))
    for (a, b), (x0, x1) in SKY_STRIPS.items():
        for y in range(a, b):
            ref[y] = np.median(lab[y, x0:x1], axis=0)
    ref[SKY_FLOOR:] = ref[SKY_FLOOR - 1]
    ref = ndi.uniform_filter1d(ref, 9, axis=0)
    dist = np.linalg.norm(lab - ref[:, None, :], axis=2)
    tex = ndi.generic_filter(GRAY, np.std, size=5)
    sky = (dist < 12) & (tex < 0.03)
    sky[SKY_FLOOR:] = False
    sky[:, :SKY_COLS[0]] = False
    sky[:, SKY_COLS[1]:] = False
    sky = morphology.remove_small_objects(sky, max_size=30)
    # Fold in non-sky blobs that float in the sky (clouds, the flying car): they don't reach the floor or the sides.
    lbl = measure.label(~sky)
    for r in measure.regionprops(lbl):
        y0, x0, y1, x1 = r.bbox
        if y1 < SKY_FLOOR - 40 and x0 > SKY_COLS[0] and x1 < SKY_COLS[1] and r.area < 2500 and \
                (y1 - y0) < 2.0 * (x1 - x0):
            sky[lbl == r.label] = True
    return sky


def skyline_from(sky):
    notsky = ~sky
    has = notsky.any(axis=0)
    return np.where(has, np.argmax(notsky, axis=0), H)


# --- Sun -------------------------------------------------------------------------------------------------------------
SUN_PRIOR = (700, 160, 880, 300)  # x0, y0, x1, y1


def sun_circle():
    x0, y0, x1, y1 = SUN_PRIOR
    r, g, b = RGB[..., 0], RGB[..., 1], RGB[..., 2]
    warm = (r > 0.93) & (g > 0.62) & (b < 0.80) & (r - b > 0.18)
    m = np.zeros_like(warm)
    m[y0:y1, x0:x1] = warm[y0:y1, x0:x1]
    m = morphology.binary_opening(m, morphology.disk(2))
    lbl = measure.label(m)
    if lbl.max() == 0:
        return None, m
    m = lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1
    m = ndi.binary_fill_holes(m)
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    # The disc's lower part sinks into the haze and the towers: fit on the upper rim only.
    cy0 = ys.mean()
    sel = ys < cy0
    c, _ = ransac_circle(xs[sel].astype(float), ys[sel].astype(float), thr=1.5,
                         accept=lambda c: 20 < c[2] < 90)
    return c, m


# --- Billboard screen ------------------------------------------------------------------------------------------------
SCREEN_PRIOR = (940, 0, W, 360)


def screen_quad():
    x0, y0, x1, y1 = SCREEN_PRIOR
    h, s, v = HSV[..., 0], HSV[..., 1], HSV[..., 2]
    violet = (h > 0.62) & (h < 0.80) & (s > 0.28) & (v > 0.35)
    m = np.zeros_like(violet)
    m[y0:y1, x0:x1] = violet[y0:y1, x0:x1]
    m = morphology.binary_closing(m, morphology.disk(3))
    lbl = measure.label(m)
    m = lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1
    # The logo inside is white: close it over generously, then fill.
    m = morphology.binary_closing(m, morphology.disk(25))
    m = ndi.binary_fill_holes(m)
    ys, xs = np.nonzero(m)
    # Corners: the extreme points along the two diagonals.
    s_, d_ = xs + ys, xs - ys
    tl = (xs[np.argmin(s_)], ys[np.argmin(s_)])
    br = (xs[np.argmax(s_)], ys[np.argmax(s_)])
    tr = (xs[np.argmax(d_)], ys[np.argmax(d_)])
    bl = (xs[np.argmin(d_)], ys[np.argmin(d_)])
    return [list(map(int, p)) for p in (tl, tr, br, bl)], m


# --- Dome ------------------------------------------------------------------------------------------------------------
DOME_PRIOR = (935, 300, 60, 75)  # centre x, y, half w, half h of the search region


def dome_ellipse():
    cx, cy, rx, ry = DOME_PRIOR
    e = feature.canny(GRAY, sigma=1.5, low_threshold=0.02, high_threshold=0.06)
    ys, xs = np.nonzero(e)
    r = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    # Its rim, left of the billboard's frame (the frame hides its right side), above the trees at its foot.
    sel = (r > 0.45) & (r < 1.15) & (xs < 962) & (ys < 345)
    xs, ys = xs[sel].astype(float), ys[sel].astype(float)

    def ok(p):
        bx, by, hw, hh = ellipse_box(p)
        return 25 < hw < 70 and 30 < hh < 90 and abs(bx - cx) < 30 and abs(by - cy) < 35

    p, inl = ransac_ellipse(xs, ys, thr=1.5, trials=4000, accept=ok)
    return p, (xs[inl], ys[inl]) if inl is not None else None


# --- Monorail --------------------------------------------------------------------------------------------------------
# A loose band along the track (where it shows: from behind the left terrace to where it meets the far bridge).
MONO_PRIOR = [(222, 232), (330, 246), (440, 262), (560, 280), (660, 296), (760, 320), (880, 330)]
MONO_BAND = 22


def monorail_curve():
    px, py = np.array(MONO_PRIOR, float).T
    cols = np.arange(int(px[0]), int(px[-1]) + 1)
    rows = []
    for x in cols:
        yc = np.interp(x, px, py)
        a, b = int(yc - MONO_BAND), int(yc + MONO_BAND)
        g = -GY[a:b, x]  # bright above, darker below: the beam's lit underside
        rows.append(a + int(np.argmax(g)))
    rows = np.array(rows, float)
    # Reject outliers against a running median, then fit a smooth cubic.
    med = ndi.median_filter(rows, size=41, mode='nearest')
    ok = np.abs(rows - med) < 6
    coef = np.polyfit(cols[ok], rows[ok], 3)
    xs = np.linspace(cols[0], cols[-1], 24)
    return [[round(float(x), 1), round(float(np.polyval(coef, x)), 1)] for x in xs], (cols[ok], rows[ok])


# --- Water line ------------------------------------------------------------------------------------------------------
WATER_COLS = (860, 960)
WATER_ROWS = (440, 520)


def water_line():
    x0, x1 = WATER_COLS
    y0, y1 = WATER_ROWS
    prof = GS[y0:y1, x0:x1].mean(axis=1)
    g = np.gradient(filters.gaussian(prof, 1.5))
    # The water's far edge: the shore's dark band gives way to the bright reflections below.
    return float(y0 + np.argmax(g))


def main():
    sky = sky_mask()
    save_mask(sky, 'concept-sky-mask.png')
    skyline = skyline_from(sky)
    sun, sun_m = sun_circle()
    quad, scr_m = screen_quad()
    save_mask(scr_m, 'concept-screen-mask.png')
    dome, dome_pts = dome_ellipse()
    mono, mono_pts = monorail_curve()
    wl = water_line()
    sx, sy = W / SRC_W, H / SRC_H
    bike = [round(120 * sx, 1), round(370 * sy, 1), round(1110 * sx, 1), round(890 * sy, 1)]
    f = {
        'size': [W, H],
        'skyline': {'rows': [int(v) for v in skyline], 'note': 'topmost non-sky row per column; 720 = no structure'},
        'sun': {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None,
        'screen': {'quad': quad, 'note': 'tl, tr, br, bl'},
        'dome': dict(zip(('cx', 'cy', 'half_w', 'half_h'), [round(v, 1) for v in ellipse_box(dome)])) if dome else None,
        'monorail': {'points': mono, 'note': "the track beam's underside"},
        'water_line': round(wl, 1),
        'horizon': round(wl, 1),
        'bike_box': bike,
    }
    save_json(FEATURES, f)
    print({k: v for k, v in f.items() if k != 'skyline'})

    ov = (RGB * 255).astype(np.uint8).copy()
    ov[sky] = (0.55 * ov[sky] + [0, 50, 90]).astype(np.uint8)
    ov[scr_m] = (0.6 * ov[scr_m] + [90, 0, 90]).astype(np.uint8)
    im = Image.fromarray(ov)
    draw_features(ImageDraw.Draw(im), f, (255, 0, 255))
    d = ImageDraw.Draw(im)
    if dome_pts is not None:
        for x, y in zip(*dome_pts):
            d.point((x, y), fill=(0, 255, 0))
    for x, y in zip(*mono_pts):
        d.point((x, y), fill=(255, 255, 0))
    im.save(os.path.join(OUT, 'concept-features.png'))


def draw_features(d, f, col, width=2, label=True):
    """Draw a features dict (concept or scene) onto an ImageDraw."""
    sk = f.get('skyline')
    if sk:
        d.line([(x, min(int(v), H - 1)) for x, v in enumerate(sk['rows'])], fill=col, width=width)
    s = f.get('sun')
    if s:
        (cx, cy), r = s['centre'], s['radius']
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=width)
    q = f.get('screen')
    if q:
        d.line([tuple(p) for p in q['quad']] + [tuple(q['quad'][0])], fill=col, width=width)
    dm = f.get('dome')
    if dm:
        d.ellipse((dm['cx'] - dm['half_w'], dm['cy'] - dm['half_h'], dm['cx'] + dm['half_w'], dm['cy'] + dm['half_h']),
                  outline=col, width=width)
    m = f.get('monorail')
    if m:
        d.line([tuple(p) for p in m['points']], fill=col, width=width + 1)
    if f.get('water_line') is not None:
        y = f['water_line']
        d.line([(840, y), (W, y)], fill=col, width=width)
    if f.get('horizon') is not None and f.get('horizon') != f.get('water_line'):
        d.line([(0, f['horizon']), (W, f['horizon'])], fill=col, width=1)
    b = f.get('bike_box')
    if b:
        d.rectangle(b, outline=col, width=width)
    if label:
        d.text((8, H - 16), f.get('_label', ''), fill=col)


if __name__ == '__main__':
    main()
