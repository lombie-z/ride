"""Score an arrival render of the chrome city against the concept's features (concept-features.json).

  python3 art/align2/score.py ROUND        (art/build-city2.py runs it after rendering)

Reads art/renders/city2-arrival-ids-ROUND.png (flat object-ID colours: sky transparent, sun yellow, bike red, billboard
screen magenta, dome green, monorail beam orange, water blue) and measures the same features off it the way
extract_concept.py measures them off the concept. Writes out/ROUND-scores.json, adds the round to
out/scores-history.json, and draws:
  out/ROUND-overlay.png   concept features (magenta) and the render's (cyan) over the EEVEE render
  out/ROUND-compare.png   the concept with its features above the overlay

Metrics (1280x720 px):
  skyline_mae_px     mean |row difference| of the topmost non-sky row, columns 400-964
  sun_px, sun_r_px   sun centre error, radius error
  screen_px          billboard screen corner error, mean of br and bl (tl is soft, tr clipped in the concept)
  dome_px, dome_r_px dome centre error, radius error
  monorail_px        mean |row difference| of the beam's underside over the concept curve's columns where the beam shows
  water_px           water line row error
  horizon_px         the camera's true horizon row vs the concept's (the water line)
  bike_iou           IoU of the bike boxes (the site's bike vs the concept's box)
  total              weighted sum (WEIGHTS); lower is better
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from skimage import measure, morphology, segmentation

from common import CAMERA, FEATURES, H, OUT, ROOT, W, concept_rgb, horizon_row, load_json, ransac_circle, save_json
from extract_concept import draw_features

ROUND = sys.argv[1] if len(sys.argv) > 1 else 'r0'
RENDERS = os.path.join(ROOT, 'art', 'renders')
IDS = {'sun': (1, 1, 0), 'bike': (1, 0, 0), 'screen': (1, 0, 1), 'dome': (0, 1, 0), 'mono': (1, 0.5, 0),
       'water': (0, 0, 1)}
WEIGHTS = {'skyline_mae_px': 1.0, 'sun_px': 0.5, 'sun_r_px': 0.5, 'screen_px': 0.5, 'dome_px': 0.5, 'dome_r_px': 0.5,
           'monorail_px': 1.0, 'water_px': 0.5, 'horizon_px': 0.5, 'bike_iou': 50.0}
SKY_COLS = (400, 965)


def masks():
    im = np.asarray(Image.open(os.path.join(RENDERS, f'city2-arrival-ids-{ROUND}.png')).convert('RGBA')).astype(float)
    rgb, a = im[..., :3] / 255, im[..., 3] / 255
    out = {}
    for k, c in IDS.items():
        c = np.array(c, float)
        c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)  # the ID colours are linear
        out[k] = (np.abs(rgb - c).max(axis=2) < 0.12) & (a > 0.5)
    out['sky'] = (a < 0.15) | out['sun']  # thin spire tips render part-covered: anything over 15% is structure
    return out


def circle_from(m, upper_only=False, xmax=None, ymax=None):
    if m.sum() < 30:
        return None
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    sel = np.ones(len(xs), bool)
    if upper_only:
        sel &= ys < ys.mean()
    if xmax is not None:
        sel &= xs < xmax
    if ymax is not None:
        sel &= ys < ymax
    # Drop the frame's edges (a clipped shape's border with the image isn't its rim).
    sel &= (xs > 0) & (xs < W - 1) & (ys > 0) & (ys < H - 1)
    if sel.sum() < 10:
        return None
    c, _ = ransac_circle(xs[sel].astype(float), ys[sel].astype(float), thr=1.5, trials=1500)
    return c


def quad_from(m):
    if m.sum() < 50:
        return None
    hull = morphology.convex_hull_image(m)
    cont = max(measure.find_contours(hull.astype(float), 0.5), key=len)
    for tol in np.arange(2, 60, 1.0):
        poly = measure.approximate_polygon(cont, tolerance=tol)[:-1]
        if len(poly) <= 4:
            break
    pts = np.array([(float(c), float(r)) for r, c in poly])
    s_, d_ = pts[:, 0] + pts[:, 1], pts[:, 0] - pts[:, 1]
    return [[round(float(pts[i, 0]), 1), round(float(pts[i, 1]), 1)]
            for i in (np.argmin(s_), np.argmax(d_), np.argmax(s_), np.argmin(d_))]


def scene_features(mk, concept):
    f = {}
    notsky = morphology.opening(~mk['sky'], np.ones((15, 1), bool))  # as extract_concept.skyline_from
    has = notsky.any(axis=0)
    f['skyline'] = {'rows': [int(v) for v in np.where(has, np.argmax(notsky, axis=0), H)]}
    sun = circle_from(mk['sun'], upper_only=True)
    f['sun'] = {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None
    q = quad_from(mk['screen'])
    f['screen'] = {'quad': q} if q else None
    dm = circle_from(mk['dome'], xmax=962, ymax=345)
    f['dome'] = {'cx': round(dm[0], 1), 'cy': round(dm[1], 1), 'half_w': round(dm[2], 1),
                 'half_h': round(dm[2], 1)} if dm else None
    cx = np.array([p[0] for p in concept['monorail']['points']])
    pts = []
    for x in range(int(cx[0]), int(cx[-1]) + 1, 4):
        col = np.nonzero(mk['mono'][:, x])[0]
        if len(col):
            # The beam's underside: the bottom of the topmost run of beam pixels in the column.
            runs = np.split(col, np.nonzero(np.diff(col) > 1)[0] + 1)
            pts.append([x, float(runs[0][-1])])
    f['monorail'] = {'points': pts} if len(pts) > 1 else None
    wcols = mk['water'][440:540, 860:960]
    tops = [440 + np.argmax(c) for c in wcols.T if c.any()]
    f['water_line'] = float(np.median(tops)) if tops else None
    ys, xs = np.nonzero(mk['bike'])
    f['bike_box'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    return f


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / area


def metrics(c, s):
    m = {}
    cr, sr = np.array(c['skyline']['rows'][SKY_COLS[0]:SKY_COLS[1]]), np.array(s['skyline']['rows'][SKY_COLS[0]:SKY_COLS[1]])
    m['skyline_mae_px'] = float(np.mean(np.abs(np.minimum(cr, 330) - np.minimum(sr, 330))))
    if s['sun']:
        m['sun_px'] = float(np.hypot(*(np.array(c['sun']['centre']) - s['sun']['centre'])))
        m['sun_r_px'] = abs(c['sun']['radius'] - s['sun']['radius'])
    else:
        m['sun_px'], m['sun_r_px'] = 99.0, 99.0
    if s['screen']:
        m['screen_px'] = float(np.mean([np.hypot(*(np.array(c['screen']['quad'][i]) - s['screen']['quad'][i]))
                                        for i in (2, 3)]))
    else:
        m['screen_px'] = 99.0
    if s['dome']:
        m['dome_px'] = float(np.hypot(c['dome']['cx'] - s['dome']['cx'], c['dome']['cy'] - s['dome']['cy']))
        m['dome_r_px'] = abs(c['dome']['half_w'] - s['dome']['half_w'])
    else:
        m['dome_px'], m['dome_r_px'] = 99.0, 99.0
    if s['monorail']:
        cp = np.array(c['monorail']['points'])
        sp = np.array(s['monorail']['points'])
        m['monorail_px'] = float(np.mean(np.abs(np.interp(sp[:, 0], cp[:, 0], cp[:, 1]) - sp[:, 1])))
        m['monorail_cover'] = round(len(sp) / ((cp[-1, 0] - cp[0, 0]) / 4 + 1), 2)
    else:
        m['monorail_px'] = 99.0
    m['water_px'] = abs(c['water_line'] - s['water_line']) if s['water_line'] is not None else 99.0
    cam = load_json(CAMERA)
    m['horizon_px'] = abs(float(horizon_row(cam['EYE'], cam['LOOK'], cam['FOV'])) - c['horizon'])
    m['bike_iou'] = iou(c['bike_box'], s['bike_box']) if s['bike_box'] else 0.0
    tot = 0.0
    for k, w in WEIGHTS.items():
        tot += w * ((1 - m[k]) if k == 'bike_iou' else m[k])
    m['total'] = tot
    return {k: round(float(v), 3) for k, v in m.items()}


def main():
    c = load_json(FEATURES)
    mk = masks()
    s = scene_features(mk, c)
    m = metrics(c, s)
    save_json(os.path.join(OUT, f'{ROUND}-scores.json'), {'metrics': m, 'scene': {k: v for k, v in s.items()
                                                                                   if k != 'skyline'}})
    hist_p = os.path.join(OUT, 'scores-history.json')
    hist = load_json(hist_p) if os.path.exists(hist_p) else {}
    hist[ROUND] = m
    save_json(hist_p, hist)
    print('SCORES', ROUND, m)

    ee = os.path.join(RENDERS, f'city2-arrival-{ROUND}.png')
    base = Image.open(ee).convert('RGB') if os.path.exists(ee) else Image.new('RGB', (W, H))
    ov = base.copy()
    d = ImageDraw.Draw(ov)
    c['_label'] = ''
    draw_features(d, c, (255, 0, 255))
    s['horizon'] = None
    s['_label'] = f'{ROUND}  magenta = concept, cyan = render   total {m["total"]:.1f}'
    draw_features(d, s, (0, 255, 255), label=True)
    ov.save(os.path.join(OUT, f'{ROUND}-overlay.png'))
    con = Image.fromarray((concept_rgb() * 255).astype(np.uint8))
    draw_features(ImageDraw.Draw(con), c, (255, 0, 255))
    both = Image.new('RGB', (W, H * 2))
    both.paste(con, (0, 0))
    both.paste(ov, (0, H))
    both.save(os.path.join(OUT, f'{ROUND}-compare.png'))


if __name__ == '__main__':
    main()
