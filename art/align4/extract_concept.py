"""Trace the data desert's arrival-shot features off the concept (art/reference/concept-desert.webp at 1280x720).

Run: python3 art/align4/extract_concept.py
Writes art/align4/concept-features.json and art/align4/out/concept-features.png (every guide over the concept).

The concept is painted, not rendered, so its perspective isn't one camera's: the far road bends right of where its near
lines run, the right barrier's near and far parts don't line up. So, as in art/align2/, the guides are traced by hand off
gridded crops (loose priors), and refined where the pixels say something clear:
  sun            circle fitted (RANSAC) to the rim of the bright disc
  storm_edge     the storm wall's upper-left edge against the clear sky (per column, the strongest bright-above /
                 dark-below change near the traced prior), x 445-760
  barrier_left   the left barrier's inner top edge (per column, the strongest light-above / dark-below change near the
                 prior), fitted with a line over its near run (x 0-520)
  road_centre    the centre dashes (bright paint near the prior line): a line x = a y + b over y 380-720
and traced only:
  horizon        the eye-height line: the far road's end, the facility's foot and the far dune line (row 300)
  skyline        the topmost solid row per column (monoliths, the facility's towers, masts and walls, the dune line); 0
                 where the near monolith fills the top of the frame. Storm and sky are not solid.
  boxes          monoliths (LN the near left one, L2-L4, R1-R3), the CRT screens, the facility, its gate's opening
  lightning      the two bolts
  bike_box, wheels  the concept bike (its rear tyre and frame run off the bottom right)
  barrier_right_far  the right barrier's far run (its near run, by the bike, doesn't line up with it)
"""
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import color, filters, measure, morphology, segmentation

from common import FEATURES, H, OUT, W, concept_rgb, ransac_circle, rows_of, save_json

os.makedirs(OUT, exist_ok=True)
RGB = concept_rgb()
GRAY = color.rgb2gray(RGB)
GS = filters.gaussian(GRAY, 1.2)
GY = filters.sobel_h(GS)  # +: brighter going down

# --- Hand-traced priors (1280x720), off gridded crops of the concept ----------------------------------------------------
HORIZON = 300.0
SKYLINE = [(0, 0), (298, 0), (299, 219), (332, 221), (333, 233), (346, 159), (400, 151), (427, 159), (442, 172),
           (445, 250), (480, 252), (482, 240), (511, 239), (523, 251), (524, 237), (555, 237), (556, 211), (566, 203),
           (577, 211), (578, 231), (607, 229), (608, 222), (644, 221), (672, 221), (680, 165), (688, 221), (705, 221),
           (707, 192), (722, 192), (738, 162), (755, 170), (760, 192), (780, 192), (785, 172), (805, 172), (810, 132),
           (815, 172), (825, 172), (828, 137), (832, 172), (835, 172), (840, 200), (877, 203), (880, 212), (950, 212),
           (951, 227), (1012, 227), (1013, 207), (1022, 192), (1033, 207), (1034, 229), (1068, 229), (1069, 226),
           (1075, 224), (1112, 222), (1114, 226), (1115, 250), (1168, 238), (1177, 170), (1214, 159), (1266, 163),
           (1268, 242), (1279, 255)]
BOXES = {  # x0, y0, x1, y1
    'LN': (0, 0, 300, 350), 'L2': (325, 151, 445, 297), 'L3': (472, 238, 524, 300), 'L4': (538, 270, 570, 314),
    'R1': (1160, 157, 1272, 295), 'R2': (1058, 220, 1116, 292), 'R3': (978, 263, 1012, 306),
    'CRT_L': (0, 305, 266, 476), 'CRT_M': (433, 311, 510, 362), 'CRT_R': (1130, 285, 1262, 360),
    'CRT_R2': (1028, 330, 1082, 363),
    'facility': (520, 132, 1062, 300), 'gate': (752, 258, 820, 300),
}
STORM_PRIOR = [(445, 240), (480, 222), (520, 200), (560, 160), (600, 112), (650, 62), (700, 27), (760, 2)]
LIGHTNING = [[(897, 100), (905, 120), (900, 140), (912, 155), (908, 172)],
             [(1175, 62), (1168, 80), (1172, 95), (1163, 118)]]
SUN_PRIOR = (350, 0, 500, 110)
BARRIER_L_PRIOR = [(0, 536), (100, 507), (300, 451), (500, 395), (521, 389)]
BARRIER_L_FAR = [(640, 342), (700, 331), (750, 312)]
BARRIER_R_FAR = [(780, 317), (825, 332), (847, 340)]
ROAD_CENTRE_PRIOR = [(722, 416), (705, 493), (679, 658)]
ROAD_CENTRE_FAR = [(757, 333), (753, 355)]
BIKE_BOX = (765, 318, 1280, 720)
WHEELS = {'rear': (1062.0, 610.0, 155.0), 'front': (832.0, 538.0, 85.0)}  # centre x, y, half height (left faces)


def sun_circle():
    x0, y0, x1, y1 = SUN_PRIOR
    m = np.zeros((H, W), bool)
    m[y0:y1, x0:x1] = GS[y0:y1, x0:x1] > 0.93
    m = morphology.opening(m, morphology.disk(2))
    lbl = measure.label(m)
    m = lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1
    m = ndi.binary_fill_holes(m)
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    sel = ys > 0
    c, _ = ransac_circle(xs[sel].astype(float), ys[sel].astype(float), thr=1.5, accept=lambda c: 20 < c[2] < 70)
    return c


def storm_edge():
    prior = rows_of(STORM_PRIOR, STORM_PRIOR[0][0], STORM_PRIOR[-1][0] + 1)
    g = filters.sobel_h(filters.gaussian(GRAY, 3.0))
    out = []
    for i, x in enumerate(range(STORM_PRIOR[0][0], STORM_PRIOR[-1][0] + 1)):
        yc = prior[i]
        a, b = max(0, int(yc - 25)), min(H, int(yc + 25))
        col = -g[a:b, x]  # bright sky above, the darker storm below
        out.append((x, a + int(np.argmax(col))))
    xs, ys = np.array(out, float).T
    med = ndi.median_filter(ys, size=31, mode='nearest')
    ok = np.abs(ys - med) < 10
    coef = np.polyfit(xs[ok], ys[ok], 3)
    xx = np.linspace(xs[0], xs[-1], 24)
    return [[round(float(x), 1), round(max(0.0, float(np.polyval(coef, x))), 1)] for x in xx]


def barrier_left():
    prior = rows_of(BARRIER_L_PRIOR, 0, 521)
    pts = []
    for x in range(0, 521, 2):
        yc = prior[x]
        a, b = int(yc - 10), int(yc + 10)
        col = -GY[a:b, x]  # light top surface above, darker inner face below
        pts.append((x, a + int(np.argmax(col))))
    xs, ys = np.array(pts, float).T
    # Robust line: drop points far off a first fit (the LED panels, cables over the top).
    for _ in range(3):
        k, c = np.polyfit(xs, ys, 1)
        r = np.abs(ys - (k * xs + c))
        keep = r < max(2.5, np.percentile(r, 70))
        xs, ys = xs[keep], ys[keep]
    k, c = np.polyfit(xs, ys, 1)
    return [[0.0, round(float(c), 1)], [520.0, round(float(k * 520 + c), 1)]], float(k), float(c)


def road_centre():
    # The paint: bright, low-saturation pixels within 9 px of the prior line, rows 380-720.
    px, py = np.array(ROAD_CENTRE_PRIOR, float).T
    k0, c0 = np.polyfit(py, px, 1)
    hsv = color.rgb2hsv(RGB)
    xs, ys = [], []
    for y in range(380, 720):
        xc = k0 * y + c0
        a, b = int(xc - 9), int(xc + 9)
        v = GS[y, a:b]
        s = hsv[y, a:b, 1]
        m = (v > np.percentile(GS[y, a - 40:b + 40], 85)) & (s < 0.6)
        if m.sum() >= 3:
            xs.append(a + np.nonzero(m)[0].mean())
            ys.append(y)
    xs, ys = np.array(xs), np.array(ys)
    k, c = np.polyfit(ys, xs, 1)
    for _ in range(2):
        r = np.abs(xs - (k * ys + c))
        keep = r < 3
        k, c = np.polyfit(ys[keep], xs[keep], 1)
    return [[round(float(k * 380 + c), 1), 380.0], [round(float(k * 720 + c), 1), 720.0]], float(k), float(c)


def main():
    sun = sun_circle()
    storm = storm_edge()
    bl, bl_k, bl_c = barrier_left()
    rc, rc_k, rc_c = road_centre()
    f = {
        'size': [W, H],
        'horizon': HORIZON,
        'skyline': {'points': [list(p) for p in SKYLINE],
                    'note': 'topmost solid row per column, run left to right (vertical steps as x, x+1); 0 = solid to '
                            'the top of the frame'},
        'sun': {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)},
        'storm_edge': {'points': storm, 'note': "the storm wall's upper-left edge against the clear sky"},
        'lightning': LIGHTNING,
        'boxes': {k: list(v) for k, v in BOXES.items()},
        'barrier_left': {'points': bl, 'slope': round(bl_k, 4), 'note': "inner top edge, line fitted over x 0-520"},
        'barrier_left_far': [list(p) for p in BARRIER_L_FAR],
        'barrier_right_far': [list(p) for p in BARRIER_R_FAR],
        'road_centre': {'points': rc, 'note': 'the centre dashes, x = a y + b over y 380-720'},
        'road_centre_far': [list(p) for p in ROAD_CENTRE_FAR],
        'bike_box': list(BIKE_BOX),
        'wheels': {k: list(v) for k, v in WHEELS.items()},
        'bike_marks': {'tail': [1140.0, 420.0], 'dash': [885.0, 330.0],
                       'note': "the tail light's centre and the dash's top, on the bike's centre plane"},
    }
    save_json(FEATURES, f)
    print({k: v for k, v in f.items() if k not in ('skyline',)})
    im = Image.fromarray((RGB * 255).astype(np.uint8))
    draw_features(ImageDraw.Draw(im), f, (255, 0, 255))
    im.save(os.path.join(OUT, 'concept-features.png'))


def draw_features(d, f, col, width=2, label=True, boxes=True):
    """Draw a features dict (the concept's, or a render's) onto an ImageDraw."""
    if f.get('horizon') is not None:
        d.line([(0, f['horizon']), (W, f['horizon'])], fill=col, width=1)
    sk = f.get('skyline')
    if sk:
        if 'points' in sk:
            d.line([tuple(p) for p in sk['points']], fill=col, width=width)
        else:
            d.line([(x, min(int(v), H - 1)) for x, v in enumerate(sk['rows'])], fill=col, width=width)
    s = f.get('sun')
    if s:
        (cx, cy), r = s['centre'], s['radius']
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=width)
    st = f.get('storm_edge')
    if st and st.get('points'):
        d.line([tuple(p) for p in st['points']], fill=col, width=width + 1)
    for bolt in f.get('lightning') or []:
        d.line([tuple(p) for p in bolt], fill=col, width=width)
    if boxes:
        for k, b in (f.get('boxes') or {}).items():
            d.rectangle(b, outline=col, width=1)
            d.text((b[0] + 3, b[1] + 3), k, fill=col)
    for key in ('barrier_left', 'road_centre'):
        g = f.get(key)
        if g:
            d.line([tuple(p) for p in g['points']], fill=col, width=width)
    for key in ('barrier_left_far', 'barrier_right_far', 'road_centre_far'):
        for p in f.get(key) or []:
            d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), outline=col, width=1)
    for key in ('line_centre', 'line_left', 'line_right'):  # a render's road lines (projected)
        g = f.get(key)
        if g is not None and len(g) > 1:
            d.line([tuple(p) for p in g], fill=col, width=1)
    b = f.get('bike_box')
    if b:
        d.rectangle(b, outline=col, width=width)
    for k, (x, y, h) in (f.get('wheels') or {}).items():
        d.ellipse((x - 4, y - 4, x + 4, y + 4), outline=col, width=2)
        d.line([(x, y - h), (x, y + h)], fill=col, width=1)
    if label:
        d.text((8, H - 16), f.get('_label', ''), fill=col)


if __name__ == '__main__':
    main()
