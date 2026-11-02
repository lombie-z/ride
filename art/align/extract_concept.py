"""Extract the landing shot's alignment features from the concept art (art/reference/concept-green-city.webp at 1280x720).

Run: python3 art/align/extract_concept.py
Writes art/align/concept-features.json and debug PNGs under art/align/out/:
  concept-edges.png        structural edge map (Canny, quantile thresholds, small fragments dropped)
  concept-bike-mask.png    the bike silhouette (seeded random-walker segmentation, cut at the ground line, cleaned)
  concept-sky-mask.png     sky (white) vs everything else, and the skyline profile
  concept-features.png     everything over the concept: bike outline, wheel ellipses + their edge inliers, headlight,
                           skyline, the rail / wall / road-edge lines and the gantry underside

Every feature is measured from the pixels. Where the method needs a prior (a seed stroke for the segmentation, a search
band for a line), the prior is a deliberately loose region written out below; the result is what the data says inside it.
"""
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import color, feature, filters, measure, morphology, segmentation, transform

from common import (FEATURES, H, OUT, W, concept_rgb, ellipse_points, ellipse_summary, ransac_ellipse, save_json)

os.makedirs(OUT, exist_ok=True)
RGB = concept_rgb()
GRAY = color.rgb2gray(RGB)
LAB = color.rgb2lab(RGB)
GS = filters.gaussian(GRAY, 2)
GY = filters.sobel_h(GS)  # +: brighter going down
GX = filters.sobel_v(GS)


def save_mask(m, name):
    Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(OUT, name))


# --- 1. Edge map -----------------------------------------------------------------------------------------------------
def edge_map():
    e = feature.canny(GRAY, sigma=2.0, low_threshold=0.80, high_threshold=0.93, use_quantiles=True)
    e = morphology.remove_small_objects(e, max_size=24, connectivity=2)
    return e


# --- 2. Bike silhouette ----------------------------------------------------------------------------------------------
# Seed strokes. Bike: inside the head cowl, the ribcage, the seat, both tyre bands, the exhaust run, the fork. Not bike: the
# sky and city above, the lower carriageway and the city to the right, the deck below and between the wheels, the gantry
# pier on the left, the gaps above the head and behind the bars. Loose on purpose: the walker decides the boundary.
BIKE_SEEDS = [
    ('poly', [(330, 300), (420, 270), (520, 270), (585, 310), (560, 350), (470, 330), (400, 315)]),
    ('poly', [(250, 370), (330, 335), (390, 355), (400, 410), (330, 420), (260, 400)]),
    ('poly', [(190, 325), (240, 320), (260, 333), (225, 342)]),
    ('ring', (575, 500, 85, 100, 10)),
    ('ring', (128, 455, 42, 70, 8)),
    ('line', [(120, 440), (230, 455), (360, 520), (430, 560)], 8),
    ('line', [(515, 340), (545, 480)], 8),
]
BG_SEEDS = [
    ('rect', (0, 0, W, 225)),
    ('poly', [(690, 230), (1280, 230), (1280, 720), (700, 720), (690, 450)]),
    ('rect', (0, 640, W, H)),
    ('poly', [(0, 560), (60, 560), (200, 600), (420, 660), (420, 720), (0, 720)]),
    ('poly', [(0, 230), (60, 230), (60, 380), (0, 390)]),
    ('poly', [(180, 230), (330, 230), (300, 280), (180, 300)]),
    ('poly', [(620, 240), (690, 240), (690, 330), (640, 330)]),
    ('rect', (0, 385, 52, 560)),
    ('poly', [(200, 543), (300, 564), (420, 601), (466, 616), (470, 640), (200, 640)]),
    ('poly', [(450, 226), (640, 226), (640, 300), (600, 290), (560, 262), (500, 246), (455, 242)]),
    ('poly', [(250, 226), (330, 226), (330, 252), (290, 275), (250, 290)]),
]


def draw_seeds(strokes, value, im):
    d = ImageDraw.Draw(im)
    for kind, *args in strokes:
        if kind == 'poly':
            d.polygon(args[0], fill=value)
        elif kind == 'rect':
            d.rectangle(args[0], fill=value)
        elif kind == 'ring':
            cx, cy, rx, ry, w = args[0]
            d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=value, width=w)
        elif kind == 'line':
            d.line(args[0], fill=value, width=args[1])


def bike_probability():
    im = Image.new('L', (W, H), 0)
    draw_seeds(BG_SEEDS, 2, im)
    draw_seeds(BIKE_SEEDS, 1, im)
    seeds = np.asarray(im).copy()
    feat = np.dstack([LAB[..., 0] / 100, (LAB[..., 1] + 20) / 60, (LAB[..., 2] + 20) / 60])
    feat = filters.gaussian(feat, sigma=1, channel_axis=-1)
    y0, y1, x0, x1 = 200, 700, 0, 720
    prob = segmentation.random_walker(feat[y0:y1, x0:x1], seeds[y0:y1, x0:x1], beta=800, mode='cg_j',
                                      channel_axis=-1, return_full_prob=True)
    P = np.zeros((H, W))
    P[y0:y1, x0:x1] = np.clip(prob[0], 0, 1)
    return P, seeds


def largest(m):
    lbl = measure.label(m)
    if lbl.max() == 0:
        return m
    return lbl == np.argmax(np.bincount(lbl.ravel())[1:]) + 1


# --- 3. Wheels (tyre outer contours) ---------------------------------------------------------------------------------
# Rough priors (centre, half-width, half-height) only gate which edges are considered; RANSAC fits the ellipse to the edge
# pixels whose gradient points across the tyre's contour.
WHEEL_PRIORS = {'front': (577, 502, 100, 115), 'rear': (128, 455, 52, 80)}


def wheel_ellipses(silhouette):
    e = feature.canny(GRAY, sigma=2, low_threshold=0.01, high_threshold=0.04)
    # Add the silhouette's own boundary (the tyre's outer contour where it meets the background).
    e = e | (segmentation.find_boundaries(silhouette, mode='inner') & (np.mgrid[0:H, 0:W][0] < 470))
    out = {}
    for name, (cx, cy, rx, ry) in WHEEL_PRIORS.items():
        ys, xs = np.nonzero(e)
        r = np.hypot((xs - cx) / rx, (ys - cy) / ry)
        k = (r > 0.8) & (r < 1.25)
        xs, ys = xs[k], ys[k]
        vx, vy = (xs - cx) / rx ** 2, (ys - cy) / ry ** 2
        gx, gy = GX[ys, xs], GY[ys, xs]
        cos = (vx * gx + vy * gy) / (np.hypot(vx, vy) * np.hypot(gx, gy) + 1e-9)
        k = np.abs(cos) > 0.85
        xs, ys = xs[k].astype(float), ys[k].astype(float)

        def plausible(p):
            return (min(p[2], p[3]) > 0.6 * rx and max(p[2], p[3]) < 1.3 * ry and abs(p[0] - cx) < 0.3 * rx
                    and abs(p[1] - cy) < 0.3 * ry)

        # The rear tyre shows only its outer arc (the exhaust hides the rest), so a single RANSAC run is not unique:
        # run several, keep the better-supported half and take the run with the median centre; the spread is recorded.
        runs = []
        for seed in range(12):
            p, inl = ransac_ellipse(xs, ys, thr=1.5, trials=3000, accept=plausible, seed=seed)
            if p is not None:
                runs.append((int(inl.sum()), p, inl))
        runs.sort(key=lambda r: -r[0])
        top = runs[:max(3, len(runs) // 2)]
        cxs = np.array([r[1][0] for r in top])
        n_in, p, inl = top[int(np.argsort(cxs)[len(cxs) // 2])]
        s = ellipse_summary(p)
        s['params'] = [round(v, 4) for v in p]
        s['bottom_y'] = round(float(ellipse_points(p, 720)[1].max()), 2)
        s['n_inliers'] = n_in
        sums = [ellipse_summary(r[1]) for r in top]
        s['spread'] = {k: round(float(np.ptp([q[k] if k != 'cx' else q['centre'][0] for q in sums])), 2)
                       for k in ('cx', 'half_w', 'half_h')}
        s['spread']['cy'] = round(float(np.ptp([q['centre'][1] for q in sums])), 2)
        # The arc actually supported by edges, in any of the kept runs (for an arc-distance metric that copes with
        # the occlusion).
        anyin = np.any([r[2] for r in top], axis=0)
        s['arc'] = [[int(x), int(y)] for x, y in zip(xs[anyin][::2], ys[anyin][::2])]
        out[name] = s
    return out


# --- 4. Headlight ----------------------------------------------------------------------------------------------------
def headlight():
    """The lens: the brightest blob in the head, grown to the disc at half its brightness over the surround; its centre
    from an ellipse fitted to the disc's boundary (the blob's own centroid leans toward the brighter side)."""
    x0, y0, x1, y1 = 530, 290, 650, 390
    L = filters.gaussian(LAB[y0:y1, x0:x1, 0], 1.0, preserve_range=True)
    core = largest(L >= np.percentile(L, 99))
    lvl = (np.percentile(L[core], 50) + np.median(L)) / 2
    disc = measure.label(ndi.binary_fill_holes(L >= lvl))
    disc = disc == np.bincount(disc[core]).argmax()
    disc = ndi.binary_fill_holes(morphology.opening(disc, morphology.disk(2)))
    by, bx = np.nonzero(segmentation.find_boundaries(disc, mode='inner'))
    from common import conic_to_params, fit_ellipse
    p = conic_to_params(fit_ellipse(bx.astype(float), by.astype(float)))
    cy, cx = ndi.center_of_mass(disc)
    return {'centre': [round(p[0] + x0, 2), round(p[1] + y0, 2)], 'radius': round(float(np.sqrt(p[2] * p[3])), 2),
            'blob_centroid': [round(cx + x0, 2), round(cy + y0, 2)], 'area_px': int(disc.sum())}


# --- 5. Sky and skyline ----------------------------------------------------------------------------------------------
# Sky seeds: top-row strips over columns where sky is plainly showing; not-sky seeds: the gantry block, the spire's core,
# the right tower's face and the city mass low down. The green beams (thin, bright, vertical) are opened away first.
SKY_SEEDS = [(410, 0, 600, 12), (700, 0, 770, 10), (960, 0, 1200, 10), (440, 60, 460, 80), (1110, 100, 1150, 140),
             (900, 0, 930, 30), (1040, 20, 1070, 60), (560, 40, 600, 60)]
NOT_SKY_SEEDS = [(0, 0, 360, 110), (815, 0, 860, 220), (1230, 110, 1275, 330), (0, 330, W, 420),
                 (460, 150, 580, 300), (620, 60, 680, 300), (1000, 150, 1030, 300), (935, 200, 990, 320)]


def sky_mask():
    lum = LAB[..., 0] / 100
    lum = morphology.opening(lum, np.ones((1, 9)))  # drop the beams
    feat = np.dstack([lum, (LAB[..., 1] + 20) / 60, (LAB[..., 2] + 20) / 60])
    feat = filters.gaussian(feat, sigma=1.0, channel_axis=-1)
    seeds = np.zeros((H, W), np.uint8)
    for x0, y0, x1, y1 in NOT_SKY_SEEDS:
        seeds[y0:y1, x0:x1] = 2
    for x0, y0, x1, y1 in SKY_SEEDS:
        seeds[y0:y1, x0:x1] = 1
    y1 = 420
    prob = segmentation.random_walker(feat[:y1], seeds[:y1], beta=2500, mode='cg_j', channel_axis=-1,
                                      return_full_prob=True)
    sky = np.zeros((H, W), bool)
    sky[:y1] = prob[0] > 0.5
    # Sky is one region connected to the top edge; drop speckle both ways.
    sky = morphology.remove_small_objects(sky, max_size=300)
    sky = ~morphology.remove_small_objects(~sky, max_size=150)
    lbl = measure.label(sky)
    top = set(np.unique(lbl[0])) - {0}
    sky = np.isin(lbl, list(top)) if top else sky
    return sky, seeds


def skyline_from(sky):
    """For each column, the topmost non-sky row (0 where something reaches the top of the frame)."""
    notsky = ~sky
    has = notsky.any(axis=0)
    prof = np.where(has, np.argmax(notsky, axis=0), H)
    return prof


# --- 6. Lines --------------------------------------------------------------------------------------------------------
# Each line: a search band (two loose bounding lines, given by their y at the band's x0 and x1), the edge polarity
# expected going down the image (-1 bright above dark, +1 dark above bright) and which peak to take.
LINE_BANDS = {
    # The top of the barrier's hand rail, behind the bike, running down to the right edge.
    'rail': dict(x=(680, 1280), top=(470, 525), bottom=(505, 560), polarity=-1, pick='top'),
    # The top edge of the concrete wall under it.
    'wall top': dict(x=(680, 1280), top=(492, 545), bottom=(520, 575), polarity=-1, pick='strongest'),
    # The lit top of the kerb ledge at the wall's foot.
    'kerb top': dict(x=(680, 1280), top=(530, 605), bottom=(565, 640), polarity=+1, pick='strongest'),
    # Where the wet road surface begins under the kerb ledge: the road's edge.
    'road edge': dict(x=(680, 1280), top=(555, 634), bottom=(580, 660), polarity=+1, pick='strongest'),
    # The gantry's underside: its bottom edge against the city below, from the soffit to the plated box's corner.
}
# The gantry's underside against the hazy city below it (dark over bright), found per column by scanning up from the haze
# to where it darkens, then a RANSAC line through those points (the ooze strands hanging below are the outliers): the
# soffit's edge over x 200-300 and the plated box's bottom edge falling to its corner over x 300-398.
GANTRY_SPANS = {'gantry soffit': (200, 300), 'gantry underside': (300, 398)}


def ransac_line(x, y, thr=4.0, trials=500, seed=0):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(trials):
        i, j = rng.choice(len(x), 2, replace=False)
        if x[i] == x[j]:
            continue
        sl = (y[j] - y[i]) / (x[j] - x[i])
        inl = np.abs(y - (y[i] + sl * (x - x[i]))) < thr
        if best is None or inl.sum() > best.sum():
            best = inl
    sl, ic = np.polyfit(x[best], y[best], 1)
    return sl, ic, best


def gantry_lines():
    g = filters.gaussian(GRAY, 1)
    out = {}
    for name, (x0, x1) in GANTRY_SPANS.items():
        xs, ys = [], []
        for x in range(x0, x1 + 1):
            col = g[:, x]
            haze = np.median(col[180:200])
            y = 200
            while y > 100 and col[y] > 0.55 * haze:
                y -= 1
            if haze > 0.15:
                xs.append(x)
                ys.append(y)
        xs, ys = np.array(xs, float), np.array(ys, float)
        sl, ic, inl = ransac_line(xs, ys)
        p0, p1 = (x0, sl * x0 + ic), (x1, sl * x1 + ic)
        out[name] = {'p0': [x0, round(float(p0[1]), 2)], 'p1': [x1, round(float(p1[1]), 2)],
                     'angle_deg': round(float(np.degrees(np.arctan(sl))), 3), 'support_px': int(inl.sum())}
    return out


def band_lines():
    e = feature.canny(GRAY, sigma=1.5, low_threshold=0.02, high_threshold=0.06)
    out = {}
    for name, b in LINE_BANDS.items():
        x0, x1 = b['x']
        yy, xx = np.mgrid[0:H, 0:W]
        f = (xx - x0) / (x1 - x0)
        top = b['top'][0] + (b['top'][1] - b['top'][0]) * f
        bot = b['bottom'][0] + (b['bottom'][1] - b['bottom'][0]) * f
        band = (xx >= x0) & (xx < x1) & (yy >= top) & (yy <= bot)
        m = e & band & (np.sign(GY) == b['polarity']) & (np.abs(GY) > np.abs(GX))
        slope_band = np.degrees(np.arctan2((b['top'][1] - b['top'][0]), (x1 - x0)))
        # Normal angles for near-horizontal lines, within +-12 deg of the band's own slope.
        base = np.radians(slope_band)
        thetas = np.linspace(base - np.radians(12), base + np.radians(12), 241) + np.pi / 2
        thetas = np.where(thetas > np.pi / 2, thetas - np.pi, thetas)
        hs, ang, dist = transform.hough_line(m, theta=np.sort(thetas))
        acc, angs, dists = transform.hough_line_peaks(hs, ang, dist, num_peaks=6, min_distance=4, min_angle=2,
                                                      threshold=0.3 * hs.max())
        cands = []
        for a_, t, r in zip(acc, angs, dists):
            y_at = lambda x, t=t, r=r: (r - x * np.cos(t)) / np.sin(t)
            cands.append((int(a_), y_at(x0), y_at(x1)))
        if b['pick'] == 'top':
            strong = [c for c in cands if c[0] >= 0.6 * cands[0][0]]
            c = min(strong, key=lambda c: c[1] + c[2])
        else:
            c = cands[0]
        # Refine: least squares on the oriented edge pixels within 2 px of the chosen line.
        ys, xs = np.nonzero(m)
        yl = c[1] + (c[2] - c[1]) * (xs - x0) / (x1 - x0)
        k = np.abs(ys - yl) < 2.0
        if k.sum() > 20:
            A = np.c_[xs[k], np.ones(k.sum())]
            (sl, ic), *_ = np.linalg.lstsq(A, ys[k], rcond=None)
            p0, p1 = (x0, sl * x0 + ic), (x1, sl * x1 + ic)
        else:
            p0, p1 = (x0, c[1]), (x1, c[2])
        out[name] = {'p0': [round(float(p0[0]), 2), round(float(p0[1]), 2)],
                     'p1': [round(float(p1[0]), 2), round(float(p1[1]), 2)],
                     'angle_deg': round(float(np.degrees(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))), 3),
                     'support_px': int(k.sum()), 'hough_votes': c[0]}
    return out


# --- main ------------------------------------------------------------------------------------------------------------
def main():
    edges = edge_map()
    save_mask(edges, 'concept-edges.png')

    P, seeds = bike_probability()
    raw = largest(morphology.closing(morphology.opening(P > 0.5, morphology.disk(3)), morphology.disk(5)))
    raw = ndi.binary_fill_holes(raw)
    wheels = wheel_ellipses(raw)
    # The ground: the line through the two tyres' lowest points. Nothing of the bike is below it (what the walker
    # found there is the tyres' reflection in the wet deck).
    fx, fy = wheels['front']['centre'][0], wheels['front']['bottom_y']
    rx, ry = wheels['rear']['centre'][0], wheels['rear']['bottom_y']
    yy, xx = np.mgrid[0:H, 0:W]
    ground_y = ry + (fy - ry) * (xx - rx) / (fx - rx)
    bike = raw & (yy <= ground_y + 1)
    bike = largest(morphology.opening(bike, morphology.disk(2)))
    bike = ndi.binary_fill_holes(bike)
    save_mask(bike, 'concept-bike-mask.png')
    head = headlight()

    sky, sky_seeds = sky_mask()
    save_mask(sky, 'concept-sky-mask.png')
    skyline = skyline_from(sky)
    lines = band_lines()
    lines.update(gantry_lines())

    ys, xs = np.nonzero(bike)
    feats = {
        '_': 'Features extracted from art/reference/concept-green-city.webp at 1280x720 by art/align/extract_concept.py. '
             'Pixels, origin top left. Replaces the hand traces in art/reference/concept-guides.json.',
        'size': [W, H],
        'bike': {'mask': 'out/concept-bike-mask.png', 'area_px': int(bike.sum()),
                 'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                 'centroid': [round(float(xs.mean()), 2), round(float(ys.mean()), 2)],
                 'ground_line': [[round(rx, 2), round(ry, 2)], [round(fx, 2), round(fy, 2)]]},
        'headlight': head,
        'wheels': wheels,
        'skyline': {'mask': 'out/concept-sky-mask.png', 'rows': [int(v) for v in skyline],
                    'note': 'topmost non-sky row per column; 0 = structure reaches the top of the frame'},
        'lines': lines,
        'edges': 'out/concept-edges.png',
    }
    save_json(FEATURES, feats)

    # Debug overlay.
    base = (RGB * 255).astype(np.uint8)
    ov = base.copy()
    ov[bike] = (0.55 * ov[bike] + [0, 0, 110]).astype(np.uint8)
    ov[segmentation.find_boundaries(bike)] = [255, 0, 255]
    ov[sky] = (0.6 * ov[sky] + [60, 40, 0]).astype(np.uint8)
    im = Image.fromarray(ov)
    d = ImageDraw.Draw(im)
    d.line([(x, min(int(v), H - 1)) for x, v in enumerate(skyline)], fill=(255, 220, 0), width=2)
    for name, w in wheels.items():
        for x, y in w['arc']:
            d.point((x, y), fill=(0, 255, 0))
        ex, ey = ellipse_points(w['params'])
        d.line(list(zip(ex, ey)), fill=(0, 255, 255), width=2)
    cx, cy = head['centre']
    r = head['radius']
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 60, 60), width=2)
    d.line([(cx - 6, cy), (cx + 6, cy)], fill=(255, 60, 60))
    d.line([(cx, cy - 6), (cx, cy + 6)], fill=(255, 60, 60))
    colours = {'rail': (255, 80, 80), 'wall top': (255, 160, 0), 'kerb top': (200, 120, 255), 'road edge': (80, 160, 255),
               'gantry underside': (0, 255, 160), 'gantry soffit': (0, 200, 255)}
    for name, l in lines.items():
        d.line([tuple(l['p0']), tuple(l['p1'])], fill=colours[name], width=2)
        d.text((l['p1'][0] - 110 if l['p1'][0] > 600 else l['p1'][0] + 5, l['p1'][1] - 14), name, fill=colours[name])
    d.line([(0, ground_y[0, 0]), (W, ground_y[0, W - 1])], fill=(120, 120, 120))
    im.save(os.path.join(OUT, 'concept-features.png'))

    sv = base.copy()
    sv[seeds == 1] = [0, 255, 0]
    sv[seeds == 2] = (0.5 * sv[seeds == 2] + [127, 0, 0]).astype(np.uint8)
    sv[sky_seeds == 1] = [0, 120, 255]
    Image.fromarray(sv).save(os.path.join(OUT, 'concept-seeds.png'))
    print('bike area', feats['bike']['area_px'], 'bbox', feats['bike']['bbox'])
    print('headlight', head)
    for n, w in wheels.items():
        print('wheel', n, {k: v for k, v in w.items() if k not in ('arc', 'params')})
    for n, l in lines.items():
        print('line', n, l)


if __name__ == '__main__':
    main()
