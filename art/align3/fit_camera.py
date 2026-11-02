"""Fit the coral hive's cameras to its concepts.

Arrival (concept-hive-plaza): EYE/LOOK/FOV in the bike's frame (the bike at the origin on the floor, its front along +X:
what City3.BikeMark is), fitted to the concept bike's hubs, tyre sizes and box and to the horizon. Writes
art/align3/arrival-camera.json, which art/build-city3.py carries into City3's frame.

Approach (concept-hive-city): the eye over the causeway (deck top z 0, the road along +X, centred on y 0), fitted to the
vanishing point and the two kerb strips' lines. The concept isn't consistent with an 11.8 m road: its kerbs want the eye
~2 m up, its huge bike wants it ~0.7 m up (its causeway is far wider than ours). So the eye's height is held at the
rider's (APP_Z), the view aimed at the vanishing point, and the eye's offset across the road fitted to the left kerb (the
strong, long one); the right kerb's error is reported, not fitted. No bike in the approach render (it is the rider's view,
as city2's). The field of view isn't fixed by lines through one point, so it stays at APP_FOV. Writes
art/align3/approach-camera.json: EYE (x 0: the script puts it down the causeway), LOOK, FOV.

Run: python3 art/align3/fit_camera.py   (after bike_points.py and extract_concept.py)
Our bike (public/models/bike.glb) isn't the concept's (a fat-tyred bone bike, bigger in the frame), so the arrival fit
is a compromise between its wheels and its box: the hubs carry most weight (where it stands and how it's turned), the box
keeps the framing, the horizon keeps the camera's tilt.
"""
import os

import numpy as np
from scipy.optimize import least_squares

from common import CAMERA, CAMERA_APPROACH, FEATURES, FEATURES_APPROACH, OUT, load_json, project, save_json

F = load_json(FEATURES)
B = np.load(os.path.join(OUT, 'bike-points.npz'))
PTS = B['pts']
WHEELS = F['wheels']
ROAD_W = 11.8
STRIP_IN = 0.55      # the kerb strips stand this far in from the deck's edge (art/build-city3.py) ...
STRIP_Z = 0.32       # ... and this high over the deck
APP_FOV = 50.0
APP_Z = 1.45       # the rider's eye over the deck


def pose(p):
    ex, ey, ez, yaw, pitch, fov = p
    eye = np.array([ex, ey, ez])
    d = np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)])
    return eye, eye + d * 10, fov


def horizon(eye, look, fov):
    f = (look - eye) / np.linalg.norm(look - eye)
    return 360 * (1 + np.tan(np.arcsin(f[2])) / np.tan(np.radians(fov) / 2))


def bike_box(eye, look, fov, offset=(0, 0, 0)):
    uv, _ = project(PTS + np.asarray(offset), eye, look, fov)
    return [uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()]


def arrival_residuals(p):
    eye, look, fov = pose(p)
    r = []
    for key in ('rear', 'front'):
        c = B[key][:3]
        rad = float(B[key][3])
        (sx, sy), = project(c[None], eye, look, fov)[0]
        top, = project((c + [0, 0, rad])[None], eye, look, fov)[0]
        bot, = project((c - [0, 0, rad])[None], eye, look, fov)[0]
        tx, ty, th = WHEELS[key]
        r += [(sx - tx) * 1.0, (sy - ty) * 1.0, ((bot[1] - top[1]) / 2 - th) * 1.0]
    r += [(a - b) * 0.4 for a, b in zip(bike_box(eye, look, fov), F['bike_box'])]
    r.append((horizon(eye, look, fov) - F['horizon']) * 0.6)
    return np.array(r)


def fit_arrival():
    best = None
    for yaw0 in (-40, -15, 0, 15, 40):
        for ey0 in (-1.5, 1.0, 3.0):
            for fov0 in (35, 50, 65):
                p0 = [-3.0, ey0, 0.7, np.radians(yaw0), np.radians(3), fov0]
                res = least_squares(arrival_residuals, p0,
                                    bounds=([-9, -5, 0.2, -np.pi, -0.5, 20], [1, 6, 2.5, np.pi, 0.6, 85]))
                if best is None or res.cost < best.cost:
                    best = res
    eye, look, fov = pose(best.x)
    out = {
        'frame': 'bike: the bike at the origin on the floor, its front along +X (City3.BikeMark)',
        'EYE': [round(float(v), 4) for v in eye],
        'LOOK': [round(float(v), 4) for v in look],
        'FOV': round(float(fov), 3),
        'fit': {'rms_px': round(float(np.sqrt(np.mean(best.fun ** 2))), 2),
                'bike_box': [round(float(v), 1) for v in bike_box(eye, look, fov)],
                'horizon': round(float(horizon(eye, look, fov)), 1),
                'residuals': [round(float(v), 1) for v in best.fun]},
    }
    save_json(CAMERA, out)
    print('arrival', out)


A = load_json(FEATURES_APPROACH)


def line_angle(a, b):
    return np.arctan2(b[1] - a[1], b[0] - a[0])


def approach_residuals(p, report=False):
    ey, yaw, pitch = p
    eye, look, fov = pose([0.0, ey, APP_Z, yaw, pitch, APP_FOV])
    r = []
    # The road's vanishing point: a point far down the road (+X).
    (vx, vy), = project(np.array([[1e5, 0, 0]]), eye, look, fov)[0]
    r += [(vx - A['vp'][0]) * 1.0, (vy - A['vp'][1]) * 1.0]
    # The kerb strips: compare each line's angle (as px offsets 300 px out from the vp).
    for key, side in (('kerb_l', 1), ('kerb_r', -1)):
        y = side * (ROAD_W / 2 - STRIP_IN)
        q, _ = project(np.array([[5.0, y, STRIP_Z], [60.0, y, STRIP_Z]]), eye, look, fov)
        a_r = line_angle(q[1], q[0])
        c = A[key]
        a_c = line_angle(c[1], c[0]) if key == 'kerb_l' else line_angle(c[0], c[1])
        if key == 'kerb_l' or report:
            r.append((np.angle(np.exp(1j * (a_r - a_c)))) * 300)
    return np.array(r)


def fit_approach():
    best = None
    for ey0 in (-2.0, 0.0, 2.0):
        res = least_squares(approach_residuals, [ey0, 0.0, 0.0], bounds=([-5, -0.6, -0.4], [5, 0.6, 0.4]))
        if best is None or res.cost < best.cost:
            best = res
    ey, yaw, pitch = best.x
    eye, look, fov = pose([0.0, ey, APP_Z, yaw, pitch, APP_FOV])
    out = {
        'frame': 'City3 causeway: deck top z 0, the road along +X centred on y 0; EYE x 0 (placed down the causeway by '
                 'art/build-city3.py), LOOK = EYE + 10 x the view direction',
        'EYE': [0.0, round(float(ey), 4), APP_Z],
        'LOOK': [round(float(v), 4) for v in look],
        'FOV': APP_FOV,
        'fit': {'residuals_vp_kerbl_kerbr': [round(float(v), 1) for v in approach_residuals(best.x, True)]},
    }
    save_json(CAMERA_APPROACH, out)
    print('approach', out)


if __name__ == '__main__':
    fit_arrival()
    fit_approach()
