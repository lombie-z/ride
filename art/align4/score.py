"""Score an arrival render of the data desert against the concept's guides (concept-features.json).

  python3 art/align4/score.py ROUND        (art/build-city4.py runs it after rendering)

Reads art/renders/city4-arrival-ids-ROUND.png (flat object-ID colours, ids.json: sky transparent) and measures the same
features off it that extract_concept.py traced off the concept; the road's lines come from the fitted camera
(arrival-camera.json, the road frame) projected, as the road's deck has no ID of its own. Writes out/ROUND-scores.json,
adds the round to out/scores-history.json, and draws:
  out/ROUND-overlay.png   the concept's guides (magenta) and the render's (cyan) over the EEVEE render
  out/ROUND-compare.png   the concept with its guides above the overlay

Metrics (1280x720 px):
  skyline_mae_px    mean |row difference| of the topmost solid row (not sky, storm, sun or lightning), all columns,
                    rows clipped to 0-300
  storm_edge_px     mean |row difference| of the storm's top edge, x 445-760 (where it meets clear sky)
  sun_px, sun_r_px  the sun's centre and radius errors
  box_iou           mean IoU of the composed pieces' boxes (monoliths LN L2 L3 L4 R1 R2 R3, CRTs, the facility, the gate)
  centre_px         the road's centre line (projected) vs the concept's dashes (mean distance, rows 400-720)
  barrier_px        the left barrier's top edge (projected) vs the concept's (mean distance, x 0-520)
  horizon_px        the camera's horizon row vs the concept's
  bike_iou          the bike's box vs the concept's (its right and bottom run off the frame in both)
  total             weighted sum (WEIGHTS); lower is better
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from skimage import morphology, segmentation

from common import (BARRIER_TOP, BARRIER_Y, CAMERA, FEATURES, H, HERE, OUT, ROOT, W, box_iou, concept_rgb,
                    horizon_row, load_json, point_to_polyline, ransac_circle, road_line, rows_of, save_json)
from extract_concept import draw_features

ROUND = sys.argv[1] if len(sys.argv) > 1 else 'r0'
RENDERS = os.path.join(ROOT, 'art', 'renders')
IDS = load_json(os.path.join(HERE, 'ids.json'))
BOX_KEYS = ['LN', 'L2', 'L3', 'L4', 'R1', 'R2', 'R3', 'CRT_L', 'CRT_M', 'CRT_R', 'CRT_R2', 'facility', 'gate']
WEIGHTS = {'skyline_mae_px': 1.0, 'storm_edge_px': 0.5, 'sun_px': 0.5, 'sun_r_px': 0.5, 'box_iou': 60.0,
           'centre_px': 0.5, 'barrier_px': 0.25, 'horizon_px': 0.5, 'bike_iou': 40.0}


def masks():
    im = np.asarray(Image.open(os.path.join(RENDERS, f'city4-arrival-ids-{ROUND}.png')).convert('RGBA')).astype(float)
    rgb, a = im[..., :3] / 255, im[..., 3] / 255
    out = {}
    for k, c in IDS.items():
        if k in ('other', 'ground'):
            continue
        c = np.array(c, float)
        c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)  # the ID colours are linear
        out[k] = (np.abs(rgb - c).max(axis=2) < 0.1) & (a > 0.5)
    out['sky'] = a < 0.5
    return out


def circle_from(m):
    if m.sum() < 30:
        return None
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    sel = (xs > 0) & (xs < W - 1) & (ys > 0) & (ys < H - 1)
    c, _ = ransac_circle(xs[sel].astype(float), ys[sel].astype(float), thr=1.5, trials=1500)
    return c


def bbox(m):
    m = morphology.opening(m, np.ones((2, 2), bool))
    ys, xs = np.nonzero(m)
    if len(xs) < 4:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def scene_features(mk):
    f = {}
    solid = ~(mk['sky'] | mk['storm'] | mk['sun'] | mk['lightning'])
    has = solid.any(axis=0)
    f['skyline'] = {'rows': [int(v) for v in np.where(has, np.argmax(solid, axis=0), H)]}
    st = mk['storm']
    f['storm_rows'] = [int(np.argmax(st[:, x])) if st[:, x].any() else H for x in range(W)]
    pts = [[x, f['storm_rows'][x]] for x in range(445, 761, 8) if f['storm_rows'][x] < H]
    f['storm_edge'] = {'points': pts} if len(pts) > 1 else None
    sun = circle_from(mk['sun'])
    f['sun'] = {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None
    f['boxes'] = {k: b for k in BOX_KEYS if (b := bbox(mk[k])) is not None}
    f['bike_box'] = bbox(mk['bike'])
    cam = load_json(CAMERA)['road']
    fov = load_json(CAMERA)['FOV']
    f['line_centre'] = road_line(cam['EYE'], cam['LOOK'], fov, 0.0, 0.0, 2, 3000).tolist()
    f['line_left'] = road_line(cam['EYE'], cam['LOOK'], fov, BARRIER_Y, BARRIER_TOP, 2, 3000).tolist()
    f['line_right'] = road_line(cam['EYE'], cam['LOOK'], fov, -BARRIER_Y, BARRIER_TOP, 2, 3000).tolist()
    return f


def metrics(c, s):
    m = {}
    cr = np.clip(rows_of(c['skyline']['points'], 0, W), 0, 300)
    sr = np.clip(np.array(s['skyline']['rows'], float), 0, 300)
    ok = ~np.isnan(cr)
    m['skyline_mae_px'] = float(np.mean(np.abs(cr[ok] - sr[ok])))
    ce = rows_of(c['storm_edge']['points'], 445, 761)
    se = np.array(s['storm_rows'][445:761], float)
    se[se >= H] = 300
    m['storm_edge_px'] = float(np.nanmean(np.abs(ce - se)))
    if s['sun']:
        m['sun_px'] = float(np.hypot(*(np.array(c['sun']['centre']) - s['sun']['centre'])))
        m['sun_r_px'] = abs(c['sun']['radius'] - s['sun']['radius'])
    else:
        m['sun_px'], m['sun_r_px'] = 99.0, 99.0
    ious = {k: (box_iou(c['boxes'][k], s['boxes'][k]) if k in s['boxes'] else 0.0) for k in BOX_KEYS}
    m['box_iou'] = float(np.mean(list(ious.values())))
    for k, v in ious.items():
        m['iou_' + k] = v
    (x0, y0), (x1, y1) = c['road_centre']['points']
    t = np.linspace((400 - y0) / (y1 - y0), 1, 12)
    pts = np.c_[x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]
    m['centre_px'] = float(point_to_polyline(pts, s['line_centre']).mean())
    (x0, y0), (x1, y1) = c['barrier_left']['points']
    t = np.linspace(0, 1, 12)
    pts = np.c_[x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]
    m['barrier_px'] = float(point_to_polyline(pts, s['line_left']).mean())
    cam = load_json(CAMERA)
    m['horizon_px'] = abs(float(horizon_row(cam['road']['EYE'], cam['road']['LOOK'], cam['FOV'])) - c['horizon'])
    m['bike_iou'] = box_iou(c['bike_box'], s['bike_box']) if s['bike_box'] else 0.0
    tot = 0.0
    for k, w in WEIGHTS.items():
        tot += w * ((1 - m[k]) if k in ('bike_iou', 'box_iou') else m[k])
    m['total'] = tot
    return {k: round(float(v), 3) for k, v in m.items()}


def main():
    c = load_json(FEATURES)
    mk = masks()
    s = scene_features(mk)
    m = metrics(c, s)
    save_json(os.path.join(OUT, f'{ROUND}-scores.json'), {'metrics': m, 'scene': {k: v for k, v in s.items()
                                                                                   if k in ('sun', 'boxes',
                                                                                            'bike_box')}})
    hist_p = os.path.join(OUT, 'scores-history.json')
    hist = load_json(hist_p) if os.path.exists(hist_p) else {}
    hist[ROUND] = m
    save_json(hist_p, hist)
    print('SCORES', ROUND, m)

    ee = os.path.join(RENDERS, f'city4-arrival-{ROUND}.png')
    base = Image.open(ee).convert('RGB') if os.path.exists(ee) else Image.new('RGB', (W, H))
    ov = base.copy()
    d = ImageDraw.Draw(ov)
    c['_label'] = ''
    c.pop('wheels', None)
    draw_features(d, c, (255, 0, 255))
    s['_label'] = f'{ROUND}  magenta = concept, cyan = render   total {m["total"]:.1f}   box IoU {m["box_iou"]:.2f}'
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
