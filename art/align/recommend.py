"""What would close the remaining gaps on the city's side, at a given pose (default out/pose-after.json).

  python3 art/align/recommend.py [POSE.json]   -> prints, and writes out/recommendations.json

  - skyline per region: the mean row difference between the scene's and the concept's skylines in column bands, turned
    into metres of height at the depth of whatever forms the scene's skyline there (dz = drow * depth / f)
  - the spire: its column span near the top of the frame, centre shift and width ratio (concept / scene)
  - the deck's edge, back-projected from the concept's lines through the camera: the road edge onto the deck plane gives
    the kerb face's lateral offset; the kerb ledge, wall top and rail lines onto the vertical plane of that face give
    their heights above the deck
  - the gantry's underside: the scene's lower boundary vs the concept's, as angle and offset, and in metres at its depth
"""
import json
import math
import os
import sys

import numpy as np

import score
from common import DECK_Z, H, OUT, W, cam_basis, load_json, project

BANDS = [(420, 560), (560, 700), (700, 790), (790, 900), (900, 1000), (1000, 1100), (1100, 1210), (1210, 1280)]


def focal(pose):
    return (H / 2) / math.tan(math.radians(pose['FOV']) / 2)


def ray(pose, x, y):
    f, r, u = cam_basis(pose['EYE'], pose['LOOK'])
    tv = math.tan(math.radians(pose['FOV']) / 2)
    th = tv * W / H
    d = f + r * ((x - W / 2) / (W / 2)) * th + u * ((H / 2 - y) / (H / 2)) * tv
    return np.array(pose['EYE'], float), d / np.linalg.norm(d)


def skyline_with_depth(pose):
    S = score.scene()
    uv, d = project(S['sky_pts'], pose['EYE'], pose['LOOK'], pose['FOV'])
    k = (d > 1.0) & (uv[:, 0] >= 0) & (uv[:, 0] < W)
    x, y, dd, ob = uv[k, 0].astype(int), uv[k, 1], d[k], S['sky_obj'][k]
    order = np.lexsort((y, x))
    x, y, dd, ob = x[order], y[order], dd[order], ob[order]
    first = np.r_[True, x[1:] != x[:-1]]
    prof = np.full(W, float(H))
    depth = np.full(W, np.nan)
    obj = np.full(W, -1)
    prof[x[first]] = y[first]
    depth[x[first]] = dd[first]
    obj[x[first]] = ob[first]
    return prof, depth, obj


def main():
    pose = load_json(sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, 'pose-after.json'))
    F = score.feats()
    S = score.scene()
    names = [str(n) for n in S['sky_obj_names']]
    f = focal(pose)
    rec = {'pose': pose}

    # --- Skyline by region.
    prof, depth, obj = skyline_with_depth(pose)
    cs = np.array(F['skyline']['rows'], float)
    sky = []
    for x0, x1 in BANDS:
        sl = slice(x0, x1)
        top_scene = np.clip(prof[sl], 0, H)
        top_c = np.clip(cs[sl], 0, H)
        both_clipped = (top_scene <= 0.5) & (top_c <= 0.5)
        drow = float(np.mean(top_scene - top_c))
        dep = float(np.nanmedian(depth[sl]))
        ob = np.bincount(obj[sl][obj[sl] >= 0], minlength=len(names))
        who = names[int(ob.argmax())] if ob.sum() else '-'
        sky.append({'cols': [x0, x1], 'scene_row': round(float(np.mean(top_scene)), 1), 'concept_row': round(float(np.mean(top_c)), 1),
                    'drow_px': round(drow, 1), 'depth_m': round(dep, 1), 'raise_m': round(drow * dep / f, 1),
                    'mostly': who, 'frame_top_in_both_pct': round(100 * float(both_clipped.mean()), 0)})
    rec['skyline'] = sky

    # --- The spire.
    sp = names.index('City.Spire')
    uv, d = project(S['sky_pts'], pose['EYE'], pose['LOOK'], pose['FOV'])
    k = (S['sky_obj'] == sp) & (d > 1) & (uv[:, 1] < 40)
    scols = (float(uv[k, 0].min()), float(uv[k, 0].max())) if k.any() else None
    cols = np.nonzero(cs[600:1100] < 40)[0] + 600
    # The concept's spire: the run of columns round x 840 where its skyline is in the top 40 rows.
    run = [c for c in cols if 780 <= c <= 920]
    ccols = (float(min(run)), float(max(run))) if run else None
    spire_depth = float(np.median(d[S['sky_obj'] == sp]))
    if scols and ccols:
        rec['spire'] = {'scene_cols_top40': scols, 'concept_cols_top40': ccols,
                        'centre_shift_px': round((sum(ccols) - sum(scols)) / 2, 1),
                        'centre_shift_m': round((sum(ccols) - sum(scols)) / 2 * spire_depth / f, 1),
                        'width_ratio': round((ccols[1] - ccols[0]) / max(scols[1] - scols[0], 1), 2),
                        'depth_m': round(spire_depth, 0)}

    # --- The deck's edge from the concept's lines.
    O, RD, RL = S['road_frame'][:3], S['road_frame'][3:6], S['road_frame'][6:9]

    def to_road(p):
        q = p - O
        return float(q @ RD), float(q @ RL), float(p[2] - DECK_Z)

    def on_plane_z(x, y, z):
        e, v = ray(pose, x, y)
        t = (z - e[2]) / v[2]
        return e + v * t

    def on_plane_lat(x, y, lat):
        e, v = ray(pose, x, y)
        t = (lat - (e - O) @ RL) / (v @ RL)
        return e + v * t

    L = F['lines']
    xs = np.linspace(800, 1250, 10)

    def yl(name, x):
        (x0, y0), (x1, y1) = L[name]['p0'], L[name]['p1']
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    edge = [to_road(on_plane_z(x, yl('road edge', x), DECK_Z)) for x in xs]
    lat_edge = float(np.median([e[1] for e in edge]))
    s_range = (round(min(e[0] for e in edge), 1), round(max(e[0] for e in edge), 1))
    heights = {}
    for name in ('kerb top', 'wall top', 'rail'):
        hs = [to_road(on_plane_lat(x, yl(name, x), lat_edge))[2] for x in xs]
        heights[name] = (round(float(np.median(hs)), 3), round(float(np.ptp(hs)), 3))
    # How parallel the concept's road edge is to the scene's road: its lateral drift along the visible stretch.
    drift = float(np.polyfit([e[0] for e in edge], [e[1] for e in edge], 1)[0])
    bike_lat = float((np.array(pose['BIKE_AT']) - O) @ RL)
    rec['deck_edge'] = {
        'concept_kerb_face_lateral_m': round(lat_edge, 3), 'scene_kerb_face_lateral_m': -0.85,
        'kerb_face_from_bike_centre_m': round(lat_edge - bike_lat, 3),
        'visible_s_range_m': s_range, 'lateral_drift_per_m': round(drift, 4),
        'heights_above_deck_m (median, spread)': heights,
        'scene': {'kerb top': 0.22, 'kerb rail top': 0.44, 'note': 'lower carriageway barrier is out of frame below the deck edge'}}

    # The concept's barrier read as the lower carriageway's instead (the build's reading): where its wall top and rail
    # would have to be laterally, at the lower deck's heights (fw2 barrier top deck-3.75, rail top deck-3.16).
    alt = {}
    for name, z in (('wall top', -3.75), ('rail', -3.16)):
        lats = [to_road(on_plane_z(x, yl(name, x), DECK_Z + z))[1] for x in xs]
        alt[name] = round(float(np.median(lats)), 2)
    rec['deck_edge']['if_lower_carriageway (lateral m; scene FW_NEAR -4.9)'] = alt

    # --- build-city.py's hero towers: the concept's extracted skyline at each hero's column (its top_sy now came from
    # the hand traces). The heroes are (screen x, top y, depth, width, crown) in the landing camera's screen.
    import re
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build-city.py')).read()
    block = src[src.index('HEROES = ['):src.index(']', src.index('HEROES = [') + 12) + 1]
    heroes = []
    for sx, top, dep, wid in re.findall(r'\((\d+), (\d+), (\d+), (\d+), ', block):
        sx, top, dep, wid = int(sx), int(top), int(dep), int(wid)
        half = max(4, int(wid * f / dep / 4))  # the middle half of its width on screen, roughly
        lo, hi = max(0, sx - half), min(W, sx + half + 1)
        c = int(np.median(cs[lo:hi])) if lo < hi else None
        heroes.append({'sx': sx, 'top_sy_now': top, 'concept_top_sy': c, 'depth': dep,
                       'note': 'behind the gantry in the concept' if c is not None and sx < 420 else ''})
    rec['heroes'] = heroes

    # --- Gantry.
    m = score.analytic(pose)
    g = {}
    for name in ('gantry soffit', 'gantry underside'):
        cl = F['lines'][name]
        xm = (cl['p0'][0] + cl['p1'][0]) / 2
        uvg, dg = project(S['gantry_pts'], pose['EYE'], pose['LOOK'], pose['FOV'])
        kk = (np.abs(uvg[:, 0] - xm) < 20) & (dg > 0.5)
        dep = float(np.median(dg[kk])) if kk.any() else float('nan')
        off = m[name + '_offset_px']
        g[name] = {'angle_diff_deg (scene - concept)': round(m[name + '_angle_deg'], 2), 'offset_px (scene - concept, + = scene lower)': round(off, 1),
                   'depth_m': round(dep, 1), 'raise_m': round(off * dep / f, 2)}
    rec['gantry'] = g
    with open(os.path.join(OUT, 'recommendations.json'), 'w') as fh:
        json.dump(rec, fh, indent=1)
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
