"""Fit ConceptCam2 so the chrome bike's tyres and ground contacts land on the concept's (concept-bike2-guides.json).

The concept bike faces LEFT, so the camera sits on the bike's +Y side (the kickstand side, which the concept shows):
no mirroring. Bike frame as bike.glb: front +X, axles (+-0.78, 0, 0.315/0.325), root rolled 5 deg toward +Y.
Writes art/align-bike2/concept-cam2.json (location, look, lens for a 36 mm sensor, 1672x941).
Run: python3 art/align-bike2/fit_camera.py
"""
import json
import math
import os

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, 'concept-bike2-guides.json')))
W, H = G['size']
HORIZON = 474.0 * 941 / 720
LEAN = math.radians(5)
# tyres: (axle, radius, width) -- widths must match build-bike2.py
TYRES = {'front': (np.array([0.78, 0, 0.315]), 0.315, 0.22), 'rear': (np.array([-0.78, 0, 0.325]), 0.325, 0.30)}
ROT = np.array([[1, 0, 0], [0, math.cos(-LEAN), -math.sin(-LEAN)], [0, math.sin(-LEAN), math.cos(-LEAN)]])


def tyre_pts(axle, r, w, n=96, m=16):
    out = []
    hr, hw = 0.06, w / 2
    for k in range(m):
        a = math.tau * k / m
        c, s = math.cos(a), math.sin(a)
        u = hw * math.copysign(abs(c) ** (2 / 2.6), c)
        v = hr * math.copysign(abs(s) ** (2 / 2.6), s)
        for j in range(n):
            ph = math.tau * j / n
            rr = r - hr + v
            out.append(axle + np.array([rr * math.cos(ph), u, rr * math.sin(ph)]))
    return np.array(out) @ ROT.T


def basis(eye, look):
    f = look - eye
    f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    return f, r, np.cross(r, f)


def project(P, eye, look, vfov):
    f, r, u = basis(eye, look)
    v = P - eye
    d = v @ f
    tv = math.tan(math.radians(vfov) / 2)
    th = tv * W / H
    return np.c_[W / 2 * (1 + (v @ r) / (d * th)), H / 2 * (1 - (v @ u) / (d * tv))]


# The fit is flat in FOV from ~55 to 85 deg vertical (wider just trades the rear tread for the front); 55 deg (87 deg
# horizontal) is the narrowest that fits as well, so it is fixed. The concept's front wheel looks steered toward the
# camera (its contact sits ~55 px left of the hub); ours can't steer, so that residual stays and is down-weighted.
VFOV = 55.0


def pose(p):
    ex, ey, ez, yaw, pitch = p[:5]
    fov = VFOV
    eye = np.array([ex, ey, ez])
    d = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
    return eye, eye + d * 5, fov


PTS = {k: tyre_pts(*v) for k, v in TYRES.items()}
CONTACT = {k: (np.array([v[0][0], 0, 0.0]) @ ROT.T) for k, v in TYRES.items()}
CONTACT = {k: np.array([TYRES[k][0][0], 0.0, 0.0]) for k in TYRES}  # lean pivots about the contact line: contacts stay put
HUB = {k: (TYRES[k][0] + np.array([0, TYRES[k][2] / 2, 0])) @ ROT.T for k in TYRES}


def residuals(p):
    eye, look, fov = pose(p)
    r = []
    for k, ell, cpt, hub in (('front', 'front tyre', 'front contact', 'front axle'), ('rear', 'rear tyre', 'rear contact', 'rear axle')):
        uv = project(PTS[k], eye, look, fov)
        cx, cy, rx, ry = G['ellipses'][ell]
        if k == 'front':  # the front tyre's right edge is hidden by the body; its left edge (tread) is at 127
            r += [(uv[:, 0].min() - 127) * 1.0]
        else:
            r += [(uv[:, 0].min() - (cx - rx)) * 1.0, (uv[:, 0].max() - (cx + rx)) * 1.0]
        r += [(uv[:, 1].min() - (cy - ry)) * 1.0, (uv[:, 1].max() - (cy + ry)) * 1.0]
        c = project(CONTACT[k][None], eye, look, fov)[0]
        r += list((c - np.array(G['points'][cpt])) * np.array([0.25 if k == 'front' else 0.7, 0.7]))
        h = project(HUB[k][None], eye, look, fov)[0]
        r += list((h - np.array(G['points'][hub])) * 0.5)
    # the horizon (eye-height plane at the frame centre): the far water line, art/align2's 474 px of 720 -> 619.5 of 941
    f = (look - eye) / np.linalg.norm(look - eye)
    hz = H / 2 * (1 + math.tan(math.asin(f[2])) / math.tan(math.radians(fov) / 2))
    r.append((hz - HORIZON) * 0.8)
    return np.array(r)


def main():
    best = None
    for yaw0 in (-60, -75, -90, -105, -120):
        for _ in (0,):
            for dist in (2.0, 3.0, 4.5):
                yaw = math.radians(yaw0)
                eye0 = np.array([0.3, 0, 0.6]) - dist * np.array([math.cos(yaw), math.sin(yaw), 0])
                p0 = [*eye0, yaw, math.radians(5)]
                try:
                    s = least_squares(residuals, p0, bounds=([-8, 0, 0.05, -math.pi, -0.8], [8, 8, 3, 0, 0.8]))
                except ValueError:
                    continue
                if best is None or s.cost < best.cost:
                    best = s
    eye, look, fov = pose(best.x)
    res = residuals(best.x)
    hfov = 2 * math.degrees(math.atan(math.tan(math.radians(fov) / 2) * W / H))
    lens = 18 / math.tan(math.radians(hfov) / 2)
    out = {'location': eye.round(4).tolist(), 'look': look.round(4).tolist(), 'vfov': round(fov, 3), 'lens': round(lens, 3),
           'sensor_width': 36, 'size': [W, H], 'rms_px': round(float(np.sqrt((res ** 2).mean())), 2), 'residuals': res.round(1).tolist()}
    json.dump(out, open(os.path.join(HERE, 'concept-cam2.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
