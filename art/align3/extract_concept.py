"""Measure the coral hive's concepts at 1280x720: the arrival (concept-hive-plaza.webp) and the approach
(concept-hive-city.webp). As in art/align2/, loose priors say where to look and the pixels say where things are; what
can't be segmented reliably off a painting (bone ribs crossing bone ribs) is traced by hand as guide lines.

Run: python3 art/align3/extract_concept.py
Writes art/align3/concept-features.json (arrival), concept-approach-features.json (approach) and, under out/:
  concept-features.png, concept-approach-features.png   every feature over its concept

Arrival features (1280x720 px):
  sun          circle fitted to the blown-out disc (upper left), RANSAC on its rim
  heart        the amber heart's ellipse: fitted to the rim of the glowing region inside a loose prior, hand-traced
               fallback (the ooze and the ribs bite into it)
  kerb         the amber strip in the kerb: the bright amber pixels near a loose traced band, fitted with a quadratic
               (it curves: the plaza edge bends round the heart's moat as it recedes); out to where the bike hides it
  ribs         the calcified bone arches' centrelines (hand-traced polylines, with a half width)
  platforms    the two dripping platforms' top ellipses (hand-traced)
  water        the moat's visible water, a polygon (hand-traced)
  towers       the honeycomb bone towers' boxes either side (hand-traced)
  bike_box, wheels   the concept bike (hand-traced: hubs and tyre half heights)
  horizon      the eye-height row, estimated from the far water edge and the floor (hand; the kerb curves so it gives none)
Approach features:
  vp           the causeway's vanishing point: where the left kerb strip's line (auto) meets the right kerb's (traced)
  kerb_l/kerb_r  those lines; horizon = vp row
  sun          as above
  skyline      the cathedral's silhouette against the sky (hand-traced: the painted clouds are too textured and the
               haze too close to the bone for a sky mask to separate them)
  portal       the glowing gate at the end of the causeway (brightest blob near the vp)
"""
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import color, filters, measure, morphology, segmentation

from common import (CONCEPT_APPROACH, FEATURES, FEATURES_APPROACH, H, OUT, W, concept_rgb, ransac_circle,
                    ransac_ellipse, ellipse_box, save_json)

os.makedirs(OUT, exist_ok=True)


def save_mask(m, name):
    Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(OUT, name))


# ======================================================================================================================
# Arrival
# ======================================================================================================================
SUN_PRIOR = (220, 90, 380, 230)
HEART_PRIOR = (700, 233, 100, 113)  # cx, cy, half w, half h (hand-traced off a 2x crop)
KERB_TRACE = [(100, 717), (293, 657), (420, 630), (527, 603), (573, 597), (667, 580), (720, 572), (800, 563),
              (835, 559)]
RIBS = {  # name: (centreline, half width px). Traced off 2x crops of the concept.
    'front_arch': ([(365, 340), (372, 250), (390, 170), (425, 100), (480, 50), (550, 20), (620, 8), (680, 25),
                    (740, 62), (800, 120), (860, 190), (920, 260), (980, 330), (1030, 400), (1055, 450)], 16),
    'right_arch': ([(760, 110), (800, 95), (850, 90), (900, 110), (950, 150), (975, 200), (990, 275), (1000, 340)],
                   11),
    'heart_rib_l': ([(525, 330), (530, 270), (545, 215), (575, 165), (615, 125), (660, 100)], 9),
    'left_trunk': ([(60, 720), (70, 600), (80, 450), (75, 300), (60, 150), (40, 0)], 55),
    'right_trunk': ([(1180, 0), (1190, 120), (1200, 230)], 50),
}
PLATFORMS = {'upper': (532, 312, 108, 15), 'lower': (676, 372, 112, 11)}  # cx, cy, half w, half h
DRIPS = [[(445, 330), (447, 480)], [(480, 322), (482, 505)], [(575, 300), (578, 490)], [(610, 380), (610, 492)],
         [(720, 365), (722, 495)]]
WATER = [(205, 508), (845, 508), (845, 556), (720, 572), (560, 597), (420, 628), (300, 650), (200, 650)]
TOWERS = {'left': (150, 230, 240, 410), 'right_top': (1165, 0, 1280, 140), 'right_low': (1185, 265, 1275, 400)}
BIKE_BOX = [847, 392, 1240, 665]
WHEELS = {'rear': (1100.0, 555.0, 112.0), 'front': (888.0, 536.0, 62.0)}  # hub x, y and tyre half height
HORIZON = 488.0


def sun_circle(rgb, prior):
    x0, y0, x1, y1 = prior
    hsv = color.rgb2hsv(rgb)
    m = np.zeros(rgb.shape[:2], bool)
    m[y0:y1, x0:x1] = ((hsv[..., 2] > 0.975) & (hsv[..., 1] < 0.2))[y0:y1, x0:x1]
    m = morphology.opening(m, morphology.disk(2))
    lbl = measure.label(m)
    if lbl.max() == 0:
        return None, m
    m = lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1
    m = ndi.binary_fill_holes(m)
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    c, _ = ransac_circle(xs.astype(float), ys.astype(float), thr=1.5, accept=lambda c: 8 < c[2] < 80)
    return c, m


def heart_ellipse(rgb):
    hsv = color.rgb2hsv(rgb)
    cx, cy, rx, ry = HEART_PRIOR
    yy, xx = np.mgrid[0:H, 0:W]
    inside = np.hypot((xx - cx) / (rx * 1.15), (yy - cy) / (ry * 1.15)) < 1
    glow = (hsv[..., 0] < 0.11) & (hsv[..., 1] > 0.42) & (hsv[..., 2] > 0.72) & inside
    glow = morphology.closing(glow, morphology.disk(6))
    glow = ndi.binary_fill_holes(glow)
    lbl = measure.label(glow)
    if lbl.max() == 0:
        return None, glow
    glow = lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1
    ys, xs = np.nonzero(segmentation.find_boundaries(glow, mode='inner'))
    p, _ = ransac_ellipse(xs.astype(float), ys.astype(float), thr=2.0, trials=3000,
                          accept=lambda p: abs(p[0] - cx) < 30 and abs(p[1] - cy) < 30 and 70 < max(p[2], p[3]) < 140)
    return p, glow


def kerb_curve(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    amber = (r > 0.95) & (g > 0.72) & (b < 0.75) & (b > 0.25)
    px, py = np.array(KERB_TRACE, float).T
    xs, ys = [], []
    for x in range(int(px[0]), int(px[-1]) + 1):
        yc = np.interp(x, px, py)
        col = np.nonzero(amber[int(yc - 12):int(yc + 12), x])[0]
        if len(col) >= 2:
            xs.append(x)
            ys.append(yc - 12 + col.mean())
    xs, ys = np.array(xs, float), np.array(ys, float)
    coef = np.polyfit(xs, ys, 2)
    ok = np.abs(np.polyval(coef, xs) - ys) < 4
    coef = np.polyfit(xs[ok], ys[ok], 2)
    xq = np.linspace(px[0], px[-1], 24)
    return [[round(float(x), 1), round(float(np.polyval(coef, x)), 1)] for x in xq], (xs[ok], ys[ok])


def arrival():
    rgb = concept_rgb()
    sun, _ = sun_circle(rgb, SUN_PRIOR)
    hp, glow = heart_ellipse(rgb)
    if hp is not None:
        hx, hy, hw, hh = ellipse_box(hp)
        heart = {'cx': round(hx, 1), 'cy': round(hy, 1), 'half_w': round(hw, 1), 'half_h': round(hh, 1),
                 'source': 'fitted'}
        # Sanity: the ooze can pull the fit off; keep it within reach of the trace.
        if abs(hx - HEART_PRIOR[0]) > 25 or abs(hw - HEART_PRIOR[2]) > 25 or abs(hh - HEART_PRIOR[3]) > 30:
            hp = None
    if hp is None:
        heart = {'cx': HEART_PRIOR[0], 'cy': HEART_PRIOR[1], 'half_w': HEART_PRIOR[2], 'half_h': HEART_PRIOR[3],
                 'source': 'traced'}
    kerb, kerb_pts = kerb_curve(rgb)
    f = {
        'size': [W, H],
        'sun': {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None,
        'heart': heart,
        'kerb': {'points': kerb, 'note': 'the amber strip in the kerb face, left edge to where the bike hides it'},
        'kerb_trace': KERB_TRACE,
        'ribs': {k: {'points': v[0], 'half_w': v[1]} for k, v in RIBS.items()},
        'platforms': {k: {'cx': v[0], 'cy': v[1], 'half_w': v[2], 'half_h': v[3]} for k, v in PLATFORMS.items()},
        'drips': DRIPS,
        'water': WATER,
        'towers': TOWERS,
        'bike_box': BIKE_BOX,
        'wheels': WHEELS,
        'horizon': HORIZON,
    }
    save_json(FEATURES, f)
    print('arrival', {k: v for k, v in f.items() if k not in ('ribs', 'kerb', 'kerb_trace')})
    im = Image.fromarray((rgb * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    draw_arrival(d, f, (255, 0, 255))
    for x, y in zip(*kerb_pts):
        d.point((x, y), fill=(255, 255, 0))
    im.save(os.path.join(OUT, 'concept-features.png'))


def ellipse(d, e, col, width):
    d.ellipse((e['cx'] - e['half_w'], e['cy'] - e['half_h'], e['cx'] + e['half_w'], e['cy'] + e['half_h']),
              outline=col, width=width)


def draw_arrival(d, f, col, width=2, label=''):
    """Draw arrival features (concept or render) onto an ImageDraw."""
    s = f.get('sun')
    if s:
        (cx, cy), r = s['centre'], s['radius']
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=width)
    if f.get('heart'):
        ellipse(d, f['heart'], col, width)
    if f.get('kerb'):
        d.line([tuple(p) for p in f['kerb']['points']], fill=col, width=width + 1)
    for rb in (f.get('ribs') or {}).values():
        d.line([tuple(p) for p in rb['points']], fill=col, width=width)
    for p in (f.get('platforms') or {}).values():
        ellipse(d, p, col, width)
    for dr in f.get('drips') or []:
        d.line([tuple(p) for p in dr], fill=col, width=1)
    if f.get('water'):
        d.line([tuple(p) for p in f['water']] + [tuple(f['water'][0])], fill=col, width=1)
    for b in (f.get('towers') or {}).values():
        d.rectangle(b, outline=col, width=1)
    if f.get('bike_box'):
        d.rectangle(f['bike_box'], outline=col, width=width)
    if f.get('horizon') is not None:
        d.line([(0, f['horizon']), (W, f['horizon'])], fill=col, width=1)
    if label:
        d.text((8, H - 16), label, fill=col)


# ======================================================================================================================
# Approach
# ======================================================================================================================
KERB_L_BAND = [(0, 700), (540, 448)]   # loose: the left kerb's strip, foreground to the gate
KERB_R_TRACE = [(612, 455), (690, 478), (760, 497)]  # the right kerb's strip (faint), traced
SUN_PRIOR_A = (110, 100, 260, 230)
SKYLINE_TRACE = [(260, 200), (300, 185), (315, 165), (335, 130), (350, 140), (365, 90), (378, 120), (390, 65),
                 (398, 100), (402, 42), (415, 130), (432, 128), (445, 120), (462, 50), (470, 70), (480, 20), (495, 40),
                 (515, 0), (620, 0), (640, 10), (660, 5), (670, 40), (680, 60), (695, 118), (710, 110), (740, 125),
                 (760, 150), (780, 58), (790, 60), (800, 82), (860, 82), (900, 90), (960, 90)]


def approach():
    rgb = concept_rgb(CONCEPT_APPROACH)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    amber = (r > 0.93) & (g > 0.62) & (b < 0.7)
    (x0, y0), (x1, y1) = KERB_L_BAND
    xs, ys = [], []
    for x in range(x0, x1, 2):
        yc = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        col = np.nonzero(amber[max(0, int(yc - 40)):int(yc + 30), x])[0]
        if len(col) >= 2:
            xs.append(x)
            ys.append(max(0, int(yc - 40)) + col.mean())
    xs, ys = np.array(xs, float), np.array(ys, float)
    kl = np.polyfit(xs, ys, 1)
    ok = np.abs(np.polyval(kl, xs) - ys) < 6
    kl = np.polyfit(xs[ok], ys[ok], 1)
    kr = np.polyfit(*np.array(KERB_R_TRACE, float).T, 1)
    vx = (kr[1] - kl[1]) / (kl[0] - kr[0])
    vy = float(np.polyval(kl, vx))
    sun, _ = sun_circle(rgb, SUN_PRIOR_A)
    tx, ty = np.array(SKYLINE_TRACE, float).T
    skyline = np.full(W, H)
    skyline[260:961] = np.round(np.interp(np.arange(260, 961), tx, ty))
    # The gate: the brightest warm blob just above the vanishing point.
    gray = color.rgb2gray(rgb)
    win = gray[int(vy) - 80:int(vy) + 5, int(vx) - 40:int(vx) + 40]
    gy, gx = np.unravel_index(np.argmax(filters.gaussian(win, 3)), win.shape)
    f = {
        'size': [W, H],
        'vp': [round(float(vx), 1), round(vy, 1)],
        'horizon': round(vy, 1),
        'kerb_l': [[0, round(float(np.polyval(kl, 0)), 1)], [round(float(vx), 1), round(vy, 1)]],
        'kerb_r': [[round(float(vx), 1), round(vy, 1)], [900, round(float(np.polyval(kr, 900)), 1)]],
        'sun': {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None,
        'skyline': {'rows': [int(v) for v in skyline], 'cols': [260, 960],
                    'note': 'topmost non-sky row per column; scored over the cathedral (cols)'},
        'portal': [round(float(vx) - 40 + float(gx), 1), round(vy - 80 + float(gy), 1)],
        'bike_box': [757, 285, 1280, 720],
    }
    save_json(FEATURES_APPROACH, f)
    print('approach', {k: v for k, v in f.items() if k != 'skyline'})
    im = Image.fromarray((rgb * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    draw_approach(d, f, (255, 0, 255))
    for x, y in zip(xs[ok], ys[ok]):
        d.point((x, y), fill=(255, 255, 0))
    im.save(os.path.join(OUT, 'concept-approach-features.png'))


def draw_approach(d, f, col, width=2, label=''):
    if f.get('skyline'):
        a, b = f['skyline']['cols']
        d.line([(x, min(int(f['skyline']['rows'][x]), H - 1)) for x in range(a, b)], fill=col, width=width)
    for k in ('kerb_l', 'kerb_r'):
        if f.get(k):
            d.line([tuple(p) for p in f[k]], fill=col, width=width)
    if f.get('vp'):
        x, y = f['vp']
        d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=col, width=width)
    if f.get('horizon') is not None:
        d.line([(0, f['horizon']), (W, f['horizon'])], fill=col, width=1)
    s = f.get('sun')
    if s:
        (cx, cy), r = s['centre'], s['radius']
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=width)
    if f.get('portal'):
        x, y = f['portal']
        d.rectangle((x - 8, y - 8, x + 8, y + 8), outline=col, width=width)
    if label:
        d.text((8, H - 16), label, fill=col)


if __name__ == '__main__':
    arrival()
    approach()
