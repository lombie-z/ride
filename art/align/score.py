"""Alignment metrics between the concept's extracted features (concept-features.json) and the scene at a pose.

  python3 art/align/score.py POSE.json [--render PREFIX] [--name NAME]

Most metrics are analytic: the scene's geometry (scene-geometry.npz, from render_masks.py --export) is projected through
the pose's camera, no Blender needed, so the optimiser can call analytic() thousands of times. With --render PREFIX (the
PNGs render_masks.py --render wrote for the same pose) the bike IoU and skyline are also measured on the real render, and
the onion skins are drawn: out/NAME-onion.png (concept edges magenta over render edges cyan, on black) and
out/NAME-onion-blend.png (the same over a 50% blend of the concept and the render).

Metrics (px are 1280x720 pixels):
  bike_iou          soft IoU of the bike silhouettes (holes filled in both)
  headlight_px      lens centre error
  wheel_{f,r}_*     tyre ellipse centre error, size error (half width + half height), and arc distance: the median
                    distance from the concept's tyre-edge pixels to the projected tyre ellipse (copes with occlusion).
                    The rear tyre shows only its outer-left arc (top to foot), so its width and centre x are ambiguous:
                    it is scored on arc distance, its height, and 0.15 x its centre error
  skyline_mae_px    mean |row difference| of the topmost non-sky row, columns 420-1279 (left of that the gantry fills
                    the top of the frame in both)
  {line}_angle_deg, {line}_offset_px   for each concept line matched to a scene line (LINE_MATCH): angle difference and
                    mean vertical offset over the concept line's x range
  total             the weighted sum (WEIGHTS)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from common import (FEATURES, H, OUT, SCENE, W, bike_to_world, cam_basis, concept_rgb, conic_to_params, ellipse_points,
                    ellipse_summary, fit_ellipse, load_json, project, sampson)

# Concept line -> scene line (render_masks.py LINES). The concept's barrier is a ~1 m wall with a hand rail and a kerb
# ledge at its foot, beside the road; the scene's is a 0.22 m kerb with a low W-beam rail. The road edge (where the
# road surface stops) is the same thing in both; the rail is each barrier's topmost rail.
LINE_MATCH = {
    'road edge': 'kerb foot',
    'rail': 'kerb rail top',
    'kerb top': 'kerb inner top',
}
WEIGHTS = {
    'bike_iou': 100.0,        # (1 - IoU) * 100
    'headlight_px': 0.6,
    'wheel_f': 0.5,            # centre px + 0.5 * size px + arc px
    'wheel_r': 0.5,            # only its outer arc shows: arc px + 0.15 x centre px + 0.5 x height px (not its width)
    'road edge': 0.5,          # offset px + 5 * angle deg
    'rail': 0.15,              # the rail is a city-design difference (heights differ), so it only nudges
    'kerb top': 0.0,           # reported, not optimised
    'skyline_mae_px': 0.0,     # reported only: build-city composes the skyline in the landing camera's screen space,
                               # so it follows the camera on a rebuild; it's the thing to change, not the camera
    'gantry': 0.0,             # reported only (its shape differs; see the report)
}
SKY_COLS = (420, W)
HALF = 2  # the analytic bike mask is splatted at half resolution

_FEAT = None
_SCN = None


def feats():
    global _FEAT
    if _FEAT is None:
        f = load_json(FEATURES)
        m = np.asarray(Image.open(os.path.join(OUT, 'concept-bike-mask.png'))) > 0
        f['_bike_half'] = soft(m.reshape(H // HALF, HALF, W // HALF, HALF).mean(axis=(1, 3)))
        f['_bike_mask'] = m
        _FEAT = f
    return _FEAT


def scene():
    global _SCN
    if _SCN is None:
        z = np.load(SCENE)
        _SCN = {k: z[k] for k in z.files}
        _SCN['line_map'] = {str(n): l for n, l in zip(z['line_names'], z['lines'])}
    return _SCN


def soft(m, sigma=1.0):
    return np.clip(ndi.gaussian_filter(m.astype(np.float32), sigma), 0, 1)


# --- Projections -------------------------------------------------------------------------------------------------------
def bike_mask_half(pose):
    S = scene()
    P = bike_to_world(S['bike_pts'], pose['BIKE_AT'], pose['BIKE_YAW'])
    uv, d = project(P, pose['EYE'], pose['LOOK'], pose['FOV'])
    k = d > 0.1
    x = (uv[k, 0] / HALF).astype(int)
    y = (uv[k, 1] / HALF).astype(int)
    h, w = H // HALF, W // HALF
    k2 = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    m = np.zeros((h, w), bool)
    m[y[k2], x[k2]] = True
    m = ndi.binary_closing(m, np.ones((3, 3)), iterations=1)
    m = ndi.binary_fill_holes(m)
    return m


def headlight(pose):
    S = scene()
    hl = S['headlight']
    c = bike_to_world(hl[None, :3], pose['BIKE_AT'], pose['BIKE_YAW'])
    uv, _ = project(c, pose['EYE'], pose['LOOK'], pose['FOV'])
    # Its projected radius: the rim circle (in the plane normal to the lens axis).
    n = bike_to_world(hl[None, 3:6], [0, 0, 0], pose['BIKE_YAW'])[0]
    a = np.cross(n, [0, 0, 1.0])
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    t = np.linspace(0, 2 * np.pi, 48)
    ring = c + hl[6] * (np.cos(t)[:, None] * a + np.sin(t)[:, None] * b)
    ruv, _ = project(ring, pose['EYE'], pose['LOOK'], pose['FOV'])
    r = np.sqrt(np.ptp(ruv[:, 0]) * np.ptp(ruv[:, 1])) / 2
    return uv[0], r


def wheel_ellipse(pose, key):
    """The tyre's outer silhouette: circles across the tread (rounded profile), projected, hull points fitted."""
    S = scene()
    w = S[key]
    c, ax, r, hw = w[:3], w[3:6], w[6], w[7]
    a = np.cross(ax, [0, 0, 1.0])
    a /= np.linalg.norm(a)
    b = np.cross(ax, a)
    t = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    pts = []
    for off, rr in ((0.0, r), (0.55, r - 0.012), (-0.55, r - 0.012), (0.85, r - 0.04), (-0.85, r - 0.04)):
        pts.append(c + ax * hw * off + rr * (np.cos(t)[:, None] * a + np.sin(t)[:, None] * b))
    P = bike_to_world(np.concatenate(pts), pose['BIKE_AT'], pose['BIKE_YAW'])
    uv, d = project(P, pose['EYE'], pose['LOOK'], pose['FOV'])
    from scipy.spatial import ConvexHull
    hull = uv[ConvexHull(uv).vertices]
    # Densify the hull before fitting so long hull edges are weighted fairly.
    seg = np.r_[hull, hull[:1]]
    dense = np.concatenate([np.linspace(p, q, 8, endpoint=False) for p, q in zip(seg[:-1], seg[1:])])
    con = fit_ellipse(dense[:, 0], dense[:, 1])
    return conic_to_params(con), con


def skyline(pose):
    S = scene()
    uv, d = project(S['sky_pts'], pose['EYE'], pose['LOOK'], pose['FOV'])
    k = (d > 1.0) & (uv[:, 0] >= 0) & (uv[:, 0] < W)
    x = uv[k, 0].astype(int)
    y = np.clip(uv[k, 1], 0, H)
    prof = np.full(W, float(H))
    np.minimum.at(prof, x, y)
    return prof


def line2d(pose, seg):
    """The infinite image line of a 3-D segment: (slope, y at x=0), from two well-in-front points."""
    a, b = seg[:3], seg[3:6]
    t = np.linspace(0, 1, 4001)[:, None]
    P = a + (b - a) * t
    uv, d = project(P, pose['EYE'], pose['LOOK'], pose['FOV'])
    k = d > 2.0
    uv = uv[k]
    inf = (uv[:, 0] > -2 * W) & (uv[:, 0] < 3 * W)
    uv = uv[inf]
    p, q = uv[0], uv[-1]
    sl = (q[1] - p[1]) / (q[0] - p[0])
    return sl, p[1] - sl * p[0]


def gantry_boundary(pose, x0, x1):
    S = scene()
    uv, d = project(S['gantry_pts'], pose['EYE'], pose['LOOK'], pose['FOV'])
    k = (d > 0.5) & (uv[:, 0] >= x0) & (uv[:, 0] <= x1) & (uv[:, 1] < H)
    if k.sum() < 10:
        return None
    x = uv[k, 0].astype(int) - x0
    low = np.full(x1 - x0 + 1, -np.inf)
    np.maximum.at(low, x, uv[k, 1])
    xs = np.arange(x0, x1 + 1)[np.isfinite(low)]
    ys = low[np.isfinite(low)]
    sl, ic = np.polyfit(xs, ys, 1)
    return sl, ic


# --- Metrics -----------------------------------------------------------------------------------------------------------
def line_metrics(sl, ic, cl):
    (x0, y0), (x1, y1) = cl['p0'], cl['p1']
    xs = np.linspace(x0, x1, 50)
    yc = y0 + (y1 - y0) * (xs - x0) / (x1 - x0)
    ys = sl * xs + ic
    ang = np.degrees(np.arctan(sl)) - np.degrees(np.arctan2(y1 - y0, x1 - x0))
    return float(ang), float(np.mean(ys - yc))


def analytic(pose, with_masks=False, bike_only=False):
    F = feats()
    S = scene()
    m = {}
    bm = bike_mask_half(pose)
    sb = soft(bm.astype(np.float32))
    cb = F['_bike_half']
    m['bike_iou'] = float(np.minimum(sb, cb).sum() / max(np.maximum(sb, cb).sum(), 1e-9))
    uv, r = headlight(pose)
    hc = np.array(F['headlight']['centre'])
    m['headlight_dx'], m['headlight_dy'] = float(uv[0] - hc[0]), float(uv[1] - hc[1])
    m['headlight_px'] = float(np.hypot(*(uv - hc)))
    m['headlight_r_px'] = float(r - F['headlight']['radius'])
    for key, name in (('wheel_front', 'front'), ('wheel_rear', 'rear')):
        p, con = wheel_ellipse(pose, key)
        cw = F['wheels'][name]
        s = ellipse_summary(p)
        tag = 'wheel_' + name[0]
        m[tag + '_dx'] = s['centre'][0] - cw['centre'][0]
        m[tag + '_dy'] = s['centre'][1] - cw['centre'][1]
        m[tag + '_centre_px'] = float(np.hypot(m[tag + '_dx'], m[tag + '_dy']))
        m[tag + '_dw_px'] = s['half_w'] - cw['half_w']
        m[tag + '_dh_px'] = s['half_h'] - cw['half_h']
        arc = np.array(cw['arc'], float)
        m[tag + '_arc_px'] = float(np.median(np.abs(sampson(con, arc[:, 0], arc[:, 1]))))
        m[tag + '_params'] = p
    if bike_only:
        m['total_bike'] = bike_total(m)
        return m
    prof = skyline(pose)
    cs = np.array(F['skyline']['rows'], float)
    c0, c1 = SKY_COLS
    m['skyline_mae_px'] = float(np.mean(np.abs(np.clip(prof[c0:c1], 0, H) - np.clip(cs[c0:c1], 0, H))))
    m['skyline_bias_px'] = float(np.mean(np.clip(prof[c0:c1], 0, H) - np.clip(cs[c0:c1], 0, H)))
    m['_skyline'] = prof
    for cname, sname in LINE_MATCH.items():
        sl, ic = line2d(pose, S['line_map'][sname])
        a, o = line_metrics(sl, ic, F['lines'][cname])
        m[cname + '_angle_deg'], m[cname + '_offset_px'] = a, o
        m['_line_' + cname] = (sl, ic)
    for cname in ('gantry soffit', 'gantry underside'):
        cl = F['lines'][cname]
        g = gantry_boundary(pose, int(cl['p0'][0]), int(cl['p1'][0]))
        if g is None:
            m[cname + '_angle_deg'] = m[cname + '_offset_px'] = float('nan')
            continue
        a, o = line_metrics(g[0], g[1], cl)
        m[cname + '_angle_deg'], m[cname + '_offset_px'] = a, o
        m['_line_' + cname] = g
    m['total'] = total(m)
    if with_masks:
        m['_bike_half'] = bm
    return m


def wheel_term(m, tag):
    return m[tag + '_centre_px'] + 0.5 * (abs(m[tag + '_dw_px']) + abs(m[tag + '_dh_px'])) + m[tag + '_arc_px']


def line_term(m, name):
    return abs(m[name + '_offset_px']) + 5 * abs(m[name + '_angle_deg'])


def rear_term(m):
    # Its outer-left arc runs from the tyre's top (under the fender) to its foot, so its height is measured; its width
    # and so its centre's x are not (the right side is behind the exhaust).
    return m['wheel_r_arc_px'] + 0.15 * m['wheel_r_centre_px'] + 0.5 * abs(m['wheel_r_dh_px'])


def terms(m):
    t = {
        'bike_iou': WEIGHTS['bike_iou'] * (1 - m['bike_iou']),
        'headlight': WEIGHTS['headlight_px'] * m['headlight_px'],
        'wheel_f': WEIGHTS['wheel_f'] * wheel_term(m, 'wheel_f'),
        'wheel_r': WEIGHTS['wheel_r'] * rear_term(m),
        'skyline': WEIGHTS['skyline_mae_px'] * m['skyline_mae_px'],
    }
    for name in LINE_MATCH:
        t[name] = WEIGHTS[name] * line_term(m, name)
    g = [line_term(m, n) for n in ('gantry soffit', 'gantry underside') if np.isfinite(m[n + '_offset_px'])]
    t['gantry'] = WEIGHTS['gantry'] * (np.mean(g) if g else 0)
    return t


def total(m):
    return float(sum(terms(m).values()))


def bike_total(m):
    """The bike's own terms: what pins the camera to the bike."""
    return float(WEIGHTS['bike_iou'] * (1 - m['bike_iou']) + WEIGHTS['headlight_px'] * m['headlight_px']
                 + WEIGHTS['wheel_f'] * wheel_term(m, 'wheel_f') + WEIGHTS['wheel_r'] * rear_term(m))


# --- Render-based checks and overlays ----------------------------------------------------------------------------------
def render_masks(prefix):
    ids = np.asarray(Image.open(prefix + '-ids.png').convert('RGB')).astype(int)
    r, g, b = ids[..., 0], ids[..., 1], ids[..., 2]
    bike = (r > 128) & (g < 100) & (b < 100)
    sky = (r < 30) & (g < 30) & (b < 30)
    return ids, ndi.binary_fill_holes(bike), sky


def render_metrics(prefix):
    F = feats()
    ids, bike, sky = render_masks(prefix)
    cb = F['_bike_mask']
    iou = (bike & cb).sum() / max((bike | cb).sum(), 1)
    notsky = ~sky
    prof = np.where(notsky.any(axis=0), np.argmax(notsky, axis=0), H).astype(float)
    cs = np.array(F['skyline']['rows'], float)
    c0, c1 = SKY_COLS
    return {'bike_iou_render': float(iou),
            'skyline_mae_px_render': float(np.mean(np.abs(prof[c0:c1] - cs[c0:c1]))),
            '_skyline_render': prof, '_bike_render': bike}


def edges_of(img_gray, extra=None):
    from skimage import feature
    e = feature.canny(img_gray, sigma=1.5, low_threshold=0.03, high_threshold=0.08)
    if extra is not None:
        e |= extra
    return e


def onion(prefix, name, m=None):
    from skimage import color, segmentation
    F = feats()
    cedges = np.asarray(Image.open(os.path.join(OUT, 'concept-edges.png'))) > 0
    shaded = np.asarray(Image.open(prefix + '-shaded.png').convert('RGB')).astype(float) / 255
    ids, bike, sky = render_masks(prefix)
    ib = segmentation.find_boundaries(ids[..., 0] * 65536 + ids[..., 1] * 256 + ids[..., 2], mode='inner')
    redges = edges_of(color.rgb2gray(shaded), ib)
    a = np.zeros((H, W, 3))
    a[redges] = [0, 1, 1]
    a[cedges] = [1, 0, 1]
    a[redges & cedges] = [1, 1, 1]
    Image.fromarray((a * 255).astype(np.uint8)).save(os.path.join(OUT, name + '-onion.png'))
    cg = concept_rgb()
    blend = 0.5 * cg + 0.5 * shaded
    blend[redges] = 0.3 * blend[redges] + 0.7 * np.array([0, 1, 1])
    blend[cedges] = 0.3 * blend[cedges] + 0.7 * np.array([1, 0, 1])
    im = Image.fromarray((np.clip(blend, 0, 1) * 255).astype(np.uint8))
    if m is not None:
        annotate(im, m)
    im.save(os.path.join(OUT, name + '-onion-blend.png'))


def annotate(im, m):
    """Feature markers: concept in magenta/yellow, scene in cyan."""
    F = feats()
    d = ImageDraw.Draw(im)
    for name in ('front', 'rear'):
        ex, ey = ellipse_points(F['wheels'][name]['params'])
        d.line(list(zip(ex, ey)), fill=(255, 0, 255), width=2)
        ex, ey = ellipse_points(m['wheel_' + name[0] + '_params'])
        d.line(list(zip(ex, ey)), fill=(0, 255, 255), width=2)
    hc = F['headlight']['centre']
    d.ellipse((hc[0] - 4, hc[1] - 4, hc[0] + 4, hc[1] + 4), outline=(255, 0, 255), width=2)
    hx, hy = hc[0] + m['headlight_dx'], hc[1] + m['headlight_dy']
    d.ellipse((hx - 4, hy - 4, hx + 4, hy + 4), outline=(0, 255, 255), width=2)
    cs = F['skyline']['rows']
    d.line([(x, cs[x]) for x in range(SKY_COLS[0], W)], fill=(255, 0, 255), width=1)
    d.line([(x, m['_skyline'][x]) for x in range(SKY_COLS[0], W)], fill=(0, 255, 255), width=1)
    for cname in list(LINE_MATCH) + ['gantry soffit', 'gantry underside']:
        cl = F['lines'][cname]
        d.line([tuple(cl['p0']), tuple(cl['p1'])], fill=(255, 0, 255), width=2)
        if '_line_' + cname in m:
            sl, ic = m['_line_' + cname]
            x0, x1 = cl['p0'][0], cl['p1'][0]
            d.line([(x0, sl * x0 + ic), (x1, sl * x1 + ic)], fill=(0, 255, 255), width=2)


def table(m, rm=None):
    rows = [('total (weighted)', m['total']), ('bike IoU (analytic)', m['bike_iou'])]
    if rm:
        rows.append(('bike IoU (render)', rm['bike_iou_render']))
    rows += [('headlight error px', m['headlight_px']), ('headlight dx, dy px', (m['headlight_dx'], m['headlight_dy'])),
             ('headlight radius diff px', m['headlight_r_px'])]
    for t, n in (('wheel_f', 'front'), ('wheel_r', 'rear')):
        rows += [(f'{n} wheel centre err px', m[t + '_centre_px']), (f'{n} wheel dx, dy px', (m[t + '_dx'], m[t + '_dy'])),
                 (f'{n} wheel half w, half h diff px', (m[t + '_dw_px'], m[t + '_dh_px'])),
                 (f'{n} wheel arc dist px', m[t + '_arc_px'])]
    rows += [('skyline MAE px (analytic)', m['skyline_mae_px']), ('skyline bias px (+ = scene lower)', m['skyline_bias_px'])]
    if rm:
        rows.append(('skyline MAE px (render)', rm['skyline_mae_px_render']))
    for n in list(LINE_MATCH) + ['gantry soffit', 'gantry underside']:
        rows.append((f'{n}: angle deg, offset px', (m[n + '_angle_deg'], m[n + '_offset_px'])))
    out = []
    for k, v in rows:
        if isinstance(v, tuple):
            out.append(f'  {k:38s} ' + ', '.join(f'{x:8.2f}' for x in v))
        else:
            out.append(f'  {k:38s} {v:8.3f}')
    t = terms(m)
    out.append('  weighted terms: ' + ', '.join(f'{k} {v:.2f}' for k, v in t.items()))
    return '\n'.join(out)


def public(m):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items() if not k.startswith('_')
            and not k.endswith('_params')}


def main():
    pose = load_json(sys.argv[1])
    prefix = sys.argv[sys.argv.index('--render') + 1] if '--render' in sys.argv else None
    name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'pose'
    m = analytic(pose)
    rm = render_metrics(prefix) if prefix else None
    print(table(m, rm))
    res = {'pose': pose, 'metrics': public(m), 'terms': {k: round(v, 3) for k, v in terms(m).items()}}
    if rm:
        res['render'] = {k: round(v, 4) for k, v in rm.items() if not k.startswith('_')}
        onion(prefix, name, m)
    with open(os.path.join(OUT, name + '-metrics.json'), 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
