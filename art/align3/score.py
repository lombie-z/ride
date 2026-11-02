"""Score the coral hive's renders against its concepts' features (concept-features.json, concept-approach-features.json).

  python3 art/align3/score.py ROUND        (art/build-city3.py runs it after rendering)

Arrival: reads art/renders/city3-arrival-ids-ROUND.png (flat object IDs, sky transparent) and measures what
extract_concept.py measured or traced off the concept:
  sun_px, sun_r_px     sun centre / radius error (circle fitted to the sun's upper rim)
  heart_px, heart_size_px   heart ellipse centre error, mean |half width/height| error (its mask's box)
  kerb_px              mean |row difference| of the kerb strip (each column's mean strip row) over the concept curve
  ribs_cover           share of the traced rib centrelines with rib pixels within their half width (front, back, inner)
  platforms_px         mean centre + half-width error of the two platform tops (their masks' boxes)
  water_iou            the moat's water vs the traced water polygon
  glow_cover           share of the traced honeycomb tower boxes lit by the towers' windows
  horizon_px, bike_iou the camera's horizon row vs the concept's; the bike boxes' IoU
  total                weighted sum (WEIGHTS); lower is better
Approach: reads city3-approach-ids-ROUND.png:
  skyline_mae_px       mean |row difference| of the topmost structure row vs the traced cathedral skyline (cols 260-960)
  sun_px               sun centre error (where it shows; 99 if off frame)
  vp_px                the road's vanishing point (the camera's) vs the concept's
Writes out/ROUND-scores.json, out/scores-history.json and the overlays:
  out/ROUND-overlay.png, out/ROUND-compare.png                  arrival (magenta concept, cyan render)
  out/ROUND-approach-overlay.png, out/ROUND-approach-compare.png approach
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from skimage import morphology, segmentation

from common import (CAMERA, CAMERA_APPROACH, CONCEPT_APPROACH, FEATURES, FEATURES_APPROACH, H, OUT, ROOT, W,
                    concept_rgb, horizon_row, load_json, project, ransac_circle, save_json)
from extract_concept import draw_approach, draw_arrival

ROUND = sys.argv[1] if len(sys.argv) > 1 else 'r0'
RENDERS = os.path.join(ROOT, 'art', 'renders')
IDS = {'sun': (1, 1, 0), 'bike': (1, 0, 0), 'heart': (1, 0.5, 0), 'kerb': (0, 1, 1), 'rib_front': (0, 1, 0),
       'rib_back': (0, 0.5, 0), 'rib_inner': (0.5, 1, 0.5), 'plat_upper': (0.5, 0, 1), 'plat_lower': (1, 0, 0.5),
       'water': (0, 0, 1), 'glow': (1, 0, 1)}
WEIGHTS = {'sun_px': 0.3, 'sun_r_px': 0.3, 'heart_px': 0.6, 'heart_size_px': 0.6, 'kerb_px': 1.0, 'ribs_cover': 40.0,
           'platforms_px': 0.5, 'water_iou': 30.0, 'glow_cover': 20.0, 'horizon_px': 0.5, 'bike_iou': 40.0}
RIB_IDS = {'front_arch': 'rib_front', 'right_arch': 'rib_back', 'heart_rib_l': 'rib_inner'}


def masks(name):
    im = np.asarray(Image.open(os.path.join(RENDERS, name)).convert('RGBA')).astype(float)
    rgb, a = im[..., :3] / 255, im[..., 3] / 255
    out = {}
    for k, c in IDS.items():
        c = np.array(c, float)
        c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)  # the ID colours are linear
        out[k] = (np.abs(rgb - c).max(axis=2) < 0.1) & (a > 0.5)
    out['sky'] = (a < 0.15) | out['sun']
    return out


def circle_from(m, upper_only=False):
    if m.sum() < 30:
        return None
    ys, xs = np.nonzero(segmentation.find_boundaries(m, mode='inner'))
    sel = np.ones(len(xs), bool)
    if upper_only:
        sel &= ys < ys.mean()
    sel &= (xs > 0) & (xs < W - 1) & (ys > 0) & (ys < H - 1)
    if sel.sum() < 10:
        return None
    c, _ = ransac_circle(xs[sel].astype(float), ys[sel].astype(float), thr=1.5, trials=1500)
    return c


def box(m):
    ys, xs = np.nonzero(m)
    if len(xs) < 10:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def ell_from(m):
    b = box(m)
    if not b:
        return None
    return {'cx': (b[0] + b[2]) / 2, 'cy': (b[1] + b[3]) / 2, 'half_w': (b[2] - b[0]) / 2, 'half_h': (b[3] - b[1]) / 2}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def poly_mask(poly):
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in poly], fill=1)
    return np.asarray(im).astype(bool)


def arrival(c):
    mk = masks(f'city3-arrival-ids-{ROUND}.png')
    s, m = {}, {}
    sun = circle_from(mk['sun'], upper_only=True)
    s['sun'] = {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None
    if sun:
        m['sun_px'] = float(np.hypot(*(np.array(c['sun']['centre']) - sun[:2])))
        m['sun_r_px'] = abs(c['sun']['radius'] - sun[2])
    else:
        m['sun_px'], m['sun_r_px'] = 99.0, 99.0
    he = ell_from(mk['heart'])
    s['heart'] = he
    if he:
        ch = c['heart']
        m['heart_px'] = float(np.hypot(ch['cx'] - he['cx'], ch['cy'] - he['cy']))
        m['heart_size_px'] = (abs(ch['half_w'] - he['half_w']) + abs(ch['half_h'] - he['half_h'])) / 2
    else:
        m['heart_px'] = m['heart_size_px'] = 99.0
    # The kerb strip: each column's mean strip row, compared with the concept curve where both exist.
    cp = np.array(c['kerb']['points'])
    kx, ky = [], []
    for x in range(int(cp[0, 0]), int(cp[-1, 0]) + 1, 3):
        rows = np.nonzero(mk['kerb'][:, x])[0]
        rows = rows[rows > 450]
        if len(rows):
            kx.append(x)
            ky.append(rows.mean())
    if len(kx) > 5:
        diff = np.abs(np.interp(kx, cp[:, 0], cp[:, 1]) - np.array(ky))
        m['kerb_px'] = float(np.mean(diff))
        m['kerb_cover'] = round(len(kx) / ((cp[-1, 0] - cp[0, 0]) / 3 + 1), 2)
        s['kerb'] = {'points': [[float(x), float(y)] for x, y in zip(kx, ky)]}
    else:
        m['kerb_px'], m['kerb_cover'] = 99.0, 0.0
        s['kerb'] = None
    # Ribs: sample the traced centrelines; covered where its own ID shows within the half width.
    cov = []
    for k, rb in c['ribs'].items():
        if k not in RIB_IDS:
            continue
        mm = morphology.dilation(mk[RIB_IDS[k]], morphology.disk(max(3, int(rb['half_w'])))).astype(bool)
        pts = np.array(rb['points'], float)
        seg = np.hypot(*np.diff(pts, axis=0).T)
        t = np.linspace(0, seg.sum(), 60)
        sx = np.interp(t, np.r_[0, np.cumsum(seg)], pts[:, 0]).astype(int).clip(0, W - 1)
        sy = np.interp(t, np.r_[0, np.cumsum(seg)], pts[:, 1]).astype(int).clip(0, H - 1)
        cov.append(mm[sy, sx].mean())
        m[f'rib_{k}'] = round(float(cov[-1]), 3)
    m['ribs_cover'] = float(np.mean(cov))
    # Platforms.
    errs = []
    s['platforms'] = {}
    for k, idk in (('upper', 'plat_upper'), ('lower', 'plat_lower')):
        e = ell_from(mk[idk])
        cpk = c['platforms'][k]
        if e is None:
            errs.append(60.0)
            continue
        # (Its top ellipse: the box's top rows; compare centre x, top y, half width.)
        e2 = {'cx': e['cx'], 'cy': e['cy'] - e['half_h'] + cpk['half_h'], 'half_w': e['half_w'], 'half_h': cpk['half_h']}
        s['platforms'][k] = e2
        errs.append((np.hypot(e2['cx'] - cpk['cx'], e2['cy'] - cpk['cy']) + abs(e2['half_w'] - cpk['half_w'])) / 2)
    m['platforms_px'] = float(np.mean(errs))
    wp = poly_mask(c['water'])
    inter = (wp & mk['water']).sum()
    union = (wp | (mk['water'] & (np.arange(H)[:, None] > 480))).sum()
    m['water_iou'] = float(inter / max(union, 1))
    g = []
    for b in c['towers'].values():
        x0, y0, x1, y1 = b
        g.append(mk['glow'][y0:y1, x0:x1].mean() / 0.55)  # a honeycomb's lit share is ~half its box
    m['glow_cover'] = float(np.clip(np.mean(g), 0, 1))
    cam = load_json(CAMERA)
    m['horizon_px'] = abs(float(horizon_row(cam['EYE'], cam['LOOK'], cam['FOV'])) - c['horizon'])
    b = box(mk['bike'])
    s['bike_box'] = b
    m['bike_iou'] = iou(c['bike_box'], b) if b else 0.0
    tot = 0.0
    for k, w in WEIGHTS.items():
        tot += w * ((1 - m[k]) if k in ('bike_iou', 'ribs_cover', 'water_iou', 'glow_cover') else m[k])
    m['total'] = tot
    m = {k: round(float(v), 3) for k, v in m.items()}
    # Overlays.
    ee = os.path.join(RENDERS, f'city3-arrival-{ROUND}.png')
    base = Image.open(ee).convert('RGB') if os.path.exists(ee) else Image.new('RGB', (W, H))
    ov = base.copy()
    d = ImageDraw.Draw(ov)
    draw_arrival(d, c, (255, 0, 255))
    s['ribs'] = None
    draw_arrival(d, {k: v for k, v in s.items() if k in ('sun', 'heart', 'kerb', 'platforms', 'bike_box')},
                 (0, 255, 255), label=f'{ROUND} arrival  magenta = concept, cyan = render   total {m["total"]:.1f}')
    ov.save(os.path.join(OUT, f'{ROUND}-overlay.png'))
    con = Image.fromarray((concept_rgb() * 255).astype(np.uint8))
    draw_arrival(ImageDraw.Draw(con), c, (255, 0, 255))
    both = Image.new('RGB', (W, H * 2))
    both.paste(con, (0, 0))
    both.paste(ov, (0, H))
    both.save(os.path.join(OUT, f'{ROUND}-compare.png'))
    return m, s


def approach(c):
    p = os.path.join(RENDERS, f'city3-approach-ids-{ROUND}.png')
    if not os.path.exists(p):
        return None, None
    mk = masks(f'city3-approach-ids-{ROUND}.png')
    m, s = {}, {}
    notsky = morphology.opening(~mk['sky'], np.ones((9, 1), bool))
    has = notsky.any(axis=0)
    rows = np.where(has, np.argmax(notsky, axis=0), H)
    s['skyline'] = {'rows': [int(v) for v in rows], 'cols': c['skyline']['cols']}
    a, b = c['skyline']['cols']
    m['skyline_mae_px'] = float(np.mean(np.abs(np.array(c['skyline']['rows'][a:b]) - rows[a:b])))
    sun = circle_from(mk['sun'], upper_only=True)
    s['sun'] = {'centre': [round(sun[0], 1), round(sun[1], 1)], 'radius': round(sun[2], 1)} if sun else None
    m['sun_px'] = float(np.hypot(*(np.array(c['sun']['centre']) - sun[:2]))) if sun else 99.0
    cam = load_json(CAMERA_APPROACH)
    (vx, vy), = project(np.array([[1e5, 0, 0]]) + np.array(cam['EYE']) * [1, 0, 0], cam['EYE'], cam['LOOK'],
                        cam['FOV'])[0]
    m['vp_px'] = float(np.hypot(vx - c['vp'][0], vy - c['vp'][1]))
    s['vp'] = [float(vx), float(vy)]
    m = {k: round(float(v), 3) for k, v in m.items()}
    ee = os.path.join(RENDERS, f'city3-approach-{ROUND}.png')
    base = Image.open(ee).convert('RGB') if os.path.exists(ee) else Image.new('RGB', (W, H))
    ov = base.copy()
    d = ImageDraw.Draw(ov)
    draw_approach(d, c, (255, 0, 255))
    draw_approach(d, s, (0, 255, 255), label=f'{ROUND} approach  magenta = concept, cyan = render   '
                                              f'skyline {m["skyline_mae_px"]:.1f} px')
    ov.save(os.path.join(OUT, f'{ROUND}-approach-overlay.png'))
    con = Image.fromarray((concept_rgb(CONCEPT_APPROACH) * 255).astype(np.uint8))
    draw_approach(ImageDraw.Draw(con), c, (255, 0, 255))
    both = Image.new('RGB', (W, H * 2))
    both.paste(con, (0, 0))
    both.paste(ov, (0, H))
    both.save(os.path.join(OUT, f'{ROUND}-approach-compare.png'))
    return m, s


def main():
    m, s = arrival(load_json(FEATURES))
    ma, sa = approach(load_json(FEATURES_APPROACH))
    save_json(os.path.join(OUT, f'{ROUND}-scores.json'), {'arrival': m, 'approach': ma,
                                                          'scene': {k: v for k, v in s.items() if k != 'kerb'}})
    hist_p = os.path.join(OUT, 'scores-history.json')
    hist = load_json(hist_p) if os.path.exists(hist_p) else {}
    hist[ROUND] = {'arrival': m, 'approach': ma}
    save_json(hist_p, hist)
    print('SCORES', ROUND, m)
    print('APPROACH', ROUND, ma)


if __name__ == '__main__':
    main()
