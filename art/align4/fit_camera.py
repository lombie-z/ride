"""Fit the data desert's arrival camera to the concept: the road's lines, the horizon and the bike.

Run: python3 art/align4/fit_camera.py   (after bike_points.py and extract_concept.py)
Writes art/align4/arrival-camera.json, which art/build-city4.py reads:
  EYE, LOOK, FOV   in the bike's frame (the bike at the origin on the deck, its front along +X: City4.BikeMark)
  road             the same camera and the bike in the road's frame (centreline along +X, +Y its left, deck top z 0,
                   the camera's foot at x 0): where on the deck the bike stands and which way it's turned

Unlike art/align2/ (where only the bike and a water line fix the camera), the desert shot looks straight down a road of
known width (11.8 m) between barriers of known height, so the road's lines carry most of the fit:
  road_centre      the centre dashes' line (rows 400-720) and two far dashes (light)
  barrier_left     the left barrier's inner top edge (x 0-520), and three far points on it (light)
  barrier_right    three points on its far run (light)
  horizon          row 300
  gate             the road's far point (170 m on) under the facility's gate, column 786 (light)
  priors           weak pulls toward a 55 deg lens and the bike turned 4 deg left of the road
  bike marks       the concept bike's tail light and dash (concept-features.json bike_marks) as the site bike's tail and
                   dash: the line through them runs to the road's vanishing point, so the bike stands near parallel to
                   the road (the painted wheels' line runs far left; they're reported, not fitted)
  bike             the site's bike (public/models/bike.glb) against the concept's: tyre centres and half heights, the
                   box's left and top edges (its right and bottom run off the frame, so the bike must too)
The concept is painted, so these don't all agree; the residuals say by how much. Notably its left barrier is drawn as if
the eye were ~3 m up over a narrower road: with the bike's scale and the horizon holding the eye near 1.1 m, the barrier
line carries a light weight and lands steeper/lower than the painted one. Bounds: eye 0.9-1.7 m, lens 42-66 deg, the
bike turned -5..25 deg.
"""
import os

import numpy as np
from scipy.optimize import least_squares

from common import (BARRIER_TOP, BARRIER_Y, CAMERA, FEATURES, OUT, W, H, cam_basis, horizon_row, load_json,
                    point_to_polyline, project, road_line, save_json)

F = load_json(FEATURES)
B = np.load(os.path.join(OUT, 'bike-points.npz'))
PTS = B['pts']
# The bike's tail (its rearmost upper point) and its dash (the top of the front end), as the concept's tail light and
# dash: on the bike's centre plane, at about the same heights, so the line between them gives its heading.
_r = PTS[PTS[:, 0] < PTS[:, 0].min() + 0.25]
TAIL = _r[np.argmax(_r[:, 2])]
_f = PTS[PTS[:, 0] > 0.2]
DASH = _f[np.argsort(_f[:, 2])[-20:]].mean(axis=0)


def seg_points(seg, n=8):
    (x0, y0), (x1, y1) = seg
    t = np.linspace(0.05, 0.95, n)
    return np.c_[x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]


CENTRE = seg_points([[F['road_centre']['points'][0][0] + (F['road_centre']['points'][1][0] -
                                                          F['road_centre']['points'][0][0]) * 20 / 340, 400],
                     F['road_centre']['points'][1]])
LEFT = seg_points(F['barrier_left']['points'])


def pose(p):
    ey, ez, yaw, pitch, fov, bx, by, byaw = p
    eye = np.array([0.0, ey, ez])
    d = np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)])
    return eye, eye + d * 10, fov, np.array([bx, by]), byaw


def bike_xf(P, bxy, byaw):
    c, s = np.cos(byaw), np.sin(byaw)
    P = np.asarray(P, float)
    return np.c_[bxy[0] + c * P[:, 0] - s * P[:, 1], bxy[1] + s * P[:, 0] + c * P[:, 1], P[:, 2]]


def residuals(p, detail=False):
    eye, look, fov, bxy, byaw = pose(p)
    r, names = [], []

    def add(name, vals, w):
        vals = np.atleast_1d(vals) * w
        r.extend(vals)
        names.extend([name] * len(vals))

    lc = road_line(eye, look, fov, 0.0, 0.0)
    add('centre', point_to_polyline(CENTRE, lc), 1.0)
    add('centre_far', point_to_polyline(F['road_centre_far'], road_line(eye, look, fov, 0.0, 0.0, 20, 2000)), 0.3)
    ll = road_line(eye, look, fov, BARRIER_Y, BARRIER_TOP)
    add('left', point_to_polyline(LEFT, ll), 0.1)
    add('left_far', point_to_polyline(F['barrier_left_far'], road_line(eye, look, fov, BARRIER_Y, BARRIER_TOP, 20,
                                                                         2000)), 0.15)
    add('right_far', point_to_polyline(F['barrier_right_far'], road_line(eye, look, fov, -BARRIER_Y, BARRIER_TOP, 20,
                                                                           2000)), 0.3)
    add('horizon', horizon_row(eye, look, fov) - F['horizon'], 3.0)
    (gx, gy), = project([[170.0, 0.0, 0.0]], eye, look, fov)[0]
    add('gate', gx - 786.0, 0.3)
    for name in ('rear', 'front'):
        w = B[name]
        c = bike_xf(w[None, :3], bxy, byaw)[0]
        rad = float(w[3])
        (sx, sy), = project(c[None], eye, look, fov)[0]
        top, = project((c + [0, 0, rad])[None], eye, look, fov)[0]
        bot, = project((c - [0, 0, rad])[None], eye, look, fov)[0]
        tx, ty, th = F['wheels'][name]
        add('wheel_' + name, [sx - tx, sy - ty, ((bot[1] - top[1]) / 2 - th) * 0.5], 0.0)  # reported, not fitted
    for name, P in (('tail', TAIL), ('dash', DASH)):
        (sx, sy), = project(bike_xf(P[None], bxy, byaw), eye, look, fov)[0]
        add(name, [sx - F['bike_marks'][name][0], sy - F['bike_marks'][name][1]], 0.6)
    uv, d = project(bike_xf(PTS, bxy, byaw), eye, look, fov)
    uv = uv[d > 0.05]
    bb = F['bike_box']
    add('bike_box', [uv[:, 0].min() - bb[0], uv[:, 1].min() - bb[1]], 0.5)
    add('bike_clip', [min(0.0, uv[:, 0].max() - W), min(0.0, uv[:, 1].max() - H)], 0.5)
    # Weak priors: a natural lens, the bike near parallel to the road (the concept shows its left side a little).
    add('prior_fov', fov - 55.0, 0.3)
    add('prior_yaw', np.degrees(byaw) - 4.0, 0.5)
    r = np.array(r)
    return (r, names) if detail else r


def main():
    best = None
    for ey0 in (-4.0, -2.0, 0.0):
        for fov0 in (48, 56, 64):
            for by0 in (-3.5, -1.5):
                p0 = [ey0, 1.2, 0.0, 0.0, fov0, 2.5, by0, 0.1]
                lo = [-6.0, 0.9, -0.5, -0.4, 42, 0.5, -5.2, np.radians(-5)]
                hi = [3.0, 1.7, 0.5, 0.4, 66, 8.0, 5.2, np.radians(25)]
                res = least_squares(residuals, p0, bounds=(lo, hi))
                if best is None or res.cost < best.cost:
                    best = res
    eye, look, fov, bxy, byaw = pose(best.x)
    r, names = residuals(best.x, detail=True)
    groups = {}
    for n, v in zip(names, r):
        groups.setdefault(n, []).append(round(float(v), 1))
    # Into the bike's frame (City4.BikeMark): translate by the bike, rotate by -byaw.
    c, s = np.cos(-byaw), np.sin(-byaw)

    def to_bike(p):
        q = np.asarray(p, float) - [bxy[0], bxy[1], 0.0]
        return [c * q[0] - s * q[1], s * q[0] + c * q[1], q[2]]

    uv, d = project(bike_xf(PTS, bxy, byaw), eye, look, fov)
    out = {
        'frame': 'bike: the bike at the origin on the deck, its front along +X (City4.BikeMark)',
        'EYE': [round(float(v), 4) for v in to_bike(eye)],
        'LOOK': [round(float(v), 4) for v in to_bike(look)],
        'FOV': round(float(fov), 3),
        'road': {'note': 'road frame: the centreline along +X, +Y its left, deck top z 0, the camera foot at x 0',
                 'EYE': [round(float(v), 4) for v in eye], 'LOOK': [round(float(v), 4) for v in look],
                 'bike_xy': [round(float(v), 4) for v in bxy], 'bike_yaw_deg': round(float(np.degrees(byaw)), 3)},
        'fit': {'rms_px': round(float(np.sqrt(np.mean(r ** 2))), 2),
                'horizon_row': round(float(horizon_row(eye, look, fov)), 1),
                'bike_box': [round(float(v), 1) for v in (uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(),
                                                           uv[:, 1].max())],
                'residuals': groups},
    }
    save_json(CAMERA, out)
    print(out)


if __name__ == '__main__':
    main()
