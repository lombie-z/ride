"""Fit ConceptCam4 so the desert bike's tyres, contacts and bars land on the concept's (concept-bike4-guides.json).

The concept is a rear three-quarter from the bike's +Y side (the kickstand side): no mirroring. Bike frame as bike.glb:
front +X, axles (+-0.78, 0, 0.315/0.325), root rolled 5 deg toward +Y about the contact line. The rear tyre runs off the
frame, so instead of ellipses the fit uses silhouette lines: the rear tyre's upper edge, its +Y shoulder (where the
sidewall meets the tread), the front tyre's left edge, plus the rear hub, the front contact, the horizon and (lightly)
the bar ends and dash, which bike4 keeps near bike.glb's.
Writes art/align-bike4/concept-cam4.json (location, look, lens for a 36 mm sensor, 1672x941).
Run: python3 art/align-bike4/fit_camera.py
"""
import json
import math
import os

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, 'concept-bike4-guides.json')))
W, H = G['size']
LEAN = math.radians(5)
# tyres: (axle, radius, width) -- must match build-bike4.py
TYRES = {'front': (np.array([0.78, 0, 0.315]), 0.315, 0.24), 'rear': (np.array([-0.78, 0, 0.325]), 0.325, 0.36)}
ROT = np.array([[1, 0, 0], [0, math.cos(-LEAN), -math.sin(-LEAN)], [0, math.sin(-LEAN), math.cos(-LEAN)]])
# bike-local points bike4 puts where the concept has them (the hub face is the brake disc / sprocket on +Y)
POINTS = {'rear hub': ([-0.78, 0.215, 0.325], 0.6), 'front contact': ([0.78, 0.0, 0.0], 0.6),
          'left bar end': ([0.35, 0.40, 0.95], 0.15), 'right bar end': ([0.35, -0.40, 0.95], 0.15),
          'dash centre': ([0.60, 0.0, 1.06], 0.15)}


def local_to_world(P):
    return np.asarray(P) @ ROT.T


def tyre_pts(axle, r, w, n=180, m=20):
    out = []
    hr, hw = 0.07, w / 2
    for k in range(m):
        a = math.tau * k / m
        c, s = math.cos(a), math.sin(a)
        u = hw * math.copysign(abs(c) ** (2 / 2.6), c)
        v = hr * math.copysign(abs(s) ** (2 / 2.6), s)
        for j in range(n):
            ph = math.tau * j / n
            rr = r - hr + v
            out.append(axle + np.array([rr * math.cos(ph), u, rr * math.sin(ph)]))
    return local_to_world(np.array(out))


def shoulder_pts(axle, r, w, n=360):
    return local_to_world(np.array([axle + np.array([(r - 0.035) * math.cos(t), w / 2 * 0.92, (r - 0.035) * math.sin(t)])
                                    for t in np.linspace(0, math.tau, n)]))


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


def pose(p):
    ex, ey, ez, yaw, pitch, fov = p
    eye = np.array([ex, ey, ez])
    d = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
    return eye, eye + d * 5, fov


PTS = {k: tyre_pts(*v) for k, v in TYRES.items()}
SH = shoulder_pts(*TYRES['rear'])


def residuals(p):
    eye, look, fov = pose(p)
    r = []
    rear = project(PTS['rear'], eye, look, fov)
    for px, py in G['lines']['rear tyre top']:
        sel = rear[np.abs(rear[:, 0] - px) < 6]
        r.append((sel[:, 1].min() - py) * 0.8 if len(sel) else 50.0)
    front = project(PTS['front'], eye, look, fov)
    for px, py in G['lines']['front tyre'][:-1]:
        sel = front[np.abs(front[:, 1] - py) < 6]
        r.append((sel[:, 0].min() - px) * 0.6 if len(sel) else 50.0)
    sh = project(SH, eye, look, fov)
    for px, py in G['lines']['rear shoulder']:
        r.append(np.hypot(sh[:, 0] - px, sh[:, 1] - py).min() * 0.6)
    for name, (P, wgt) in POINTS.items():
        uv = project(local_to_world(np.array(P))[None], eye, look, fov)[0]
        r += list((uv - np.array(G['points'][name])) * wgt)
    f = (look - eye) / np.linalg.norm(look - eye)
    hz = H / 2 * (1 + math.tan(math.asin(f[2])) / math.tan(math.radians(fov) / 2))
    r.append((hz - G['horizon_y']) * 0.8)
    return np.array(r)


def main():
    best = None
    for yaw0 in (10, 25, 40, 55):
        for dist in (1.5, 2.5, 3.5):
            for fov0 in (40, 55, 70):
                yaw = math.radians(yaw0)
                d = np.array([math.cos(yaw), math.sin(yaw), 0])
                eye0 = np.array([0.0, 0, 0.6]) - dist * d
                eye0[2] = 1.2
                p0 = [*eye0, yaw, math.radians(-10), fov0]
                try:
                    s = least_squares(residuals, p0, bounds=([-8, -8, 0.3, -math.pi, -0.8, 25], [8, 8, 3, math.pi, 0.8, 90]))
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
    json.dump(out, open(os.path.join(HERE, 'concept-cam4.json'), 'w'), indent=1)
    print(json.dumps(out))
    for name, (P, _) in POINTS.items():
        print(name, project(local_to_world(np.array(P))[None], eye, look, fov)[0].round(0), 'concept', G['points'][name])


if __name__ == '__main__':
    main()
