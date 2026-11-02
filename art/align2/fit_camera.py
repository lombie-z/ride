"""Fit the arrival camera to the concept's bike and horizon, in the bike's frame (the bike at the origin on the floor,
its front along +X: what City2.BikeMark is). Writes art/align2/arrival-camera.json (EYE, LOOK, FOV in the bike frame),
which art/build-city2.py reads and carries into City2's frame.

Run: python3 art/align2/fit_camera.py   (after bike_points.py and extract_concept.py)

Targets (1280x720 px):
  bike_box     the brief's box round the concept bike
  wheels       the concept's tyre centres and half heights (traced: WHEELS below; the brief gives only the box)
  horizon      the water's far edge (extract_concept.py), standing in for the eye-height horizon
The bike is our own (public/models/bike.glb), not the concept's, so the fit is a compromise between its box and its
wheels; the wheels carry more weight (they fix distance and the three-quarter turn), the box keeps the framing.
"""
import os

import numpy as np
from scipy.optimize import least_squares

from common import CAMERA, FEATURES, OUT, load_json, project, save_json

F = load_json(FEATURES)
B = np.load(os.path.join(OUT, 'bike-points.npz'))
PTS = B['pts']
# Traced off the concept (1280x720): tyre centre (x, y) and half height. The rear tyre is nearer (bigger).
WHEELS = {'rear': (229.0, 545.0, 126.0), 'front': (771.0, 527.0, 95.0)}


def pose(p):
    ex, ey, ez, yaw, pitch, fov = p
    eye = np.array([ex, ey, ez])
    d = np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)])
    return eye, eye + d * 10, fov


def residuals(p):
    eye, look, fov = pose(p)
    r = []
    for name, key in (('rear', 'rear'), ('front', 'front')):
        c = B[key][:3]
        rad = float(B[key][3])
        (sx, sy), = project(c[None], eye, look, fov)[0]
        top, = project((c + [0, 0, rad])[None], eye, look, fov)[0]
        bot, = project((c - [0, 0, rad])[None], eye, look, fov)[0]
        tx, ty, th = WHEELS[name]
        r += [(sx - tx) * 1.0, (sy - ty) * 1.0, ((bot[1] - top[1]) / 2 - th) * 1.5]
    uv, _ = project(PTS, eye, look, fov)
    box = [uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()]
    r += [(a - b) * 0.4 for a, b in zip(box, F['bike_box'])]
    # The horizon: the eye-height plane's row at the frame's centre.
    f = (look - eye) / np.linalg.norm(look - eye)
    hz = 360 * (1 + np.tan(np.arcsin(f[2])) / np.tan(np.radians(fov) / 2))
    r.append((hz - F['horizon']) * 0.8)
    return np.array(r)


def main():
    best = None
    for yaw0 in (60, 70, 80):
        for fov0 in (35, 45, 55):
            p0 = [-1.0, -3.0, 1.0, np.radians(yaw0), np.radians(5), fov0]
            res = least_squares(residuals, p0, bounds=([-6, -9, 0.3, 0, -0.5, 20], [4, -1, 2.5, np.pi, 0.6, 80]))
            if best is None or res.cost < best.cost:
                best = res
    eye, look, fov = pose(best.x)
    uv, _ = project(PTS, eye, look, fov)
    box = [round(float(v), 1) for v in (uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max())]
    out = {
        'frame': 'bike: the bike at the origin on the floor, its front along +X (City2.BikeMark)',
        'EYE': [round(float(v), 4) for v in eye],
        'LOOK': [round(float(v), 4) for v in look],
        'FOV': round(float(fov), 3),
        'fit': {'rms_px': round(float(np.sqrt(np.mean(best.fun ** 2))), 2), 'bike_box': box,
                'residuals': [round(float(v), 1) for v in best.fun]},
    }
    save_json(CAMERA, out)
    print(out)


if __name__ == '__main__':
    main()
