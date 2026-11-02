"""Fit ConceptCam3 so the bone bike's tyres, hubs and ground contacts land on the concept's traced ones.

  python3 art/align-bike3/fit_camera.py          -> concept-cam3.json  (concept-hive-city.webp, concept-bike3-guides.json)
  python3 art/align-bike3/fit_camera.py plaza    -> plaza-cam3.json    (concept-hive-plaza.webp, the check view)

Both concepts show the bike from behind its +Y side (the kickstand side), front far left: no mirroring. Bike frame as
bike.glb: front +X, axles (+-0.78, 0, 0.315/0.325), root rolled 5 deg toward +Y. The tyre sizes must match
build-bike3.py. In the city concept the rear tyre's bottom is cut by the frame and its left flank is hidden by the
swingarm, so only its top and right edges count. The horizon (where the road vanishes) pins the pitch.
"""
import json
import math
import os
import sys

import numpy as np
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
WHICH = sys.argv[1] if len(sys.argv) > 1 else 'city'
G = json.load(open(os.path.join(HERE, 'concept-bike3-guides.json' if WHICH == 'city' else 'concept-bike3-plaza-guides.json')))
W, H = G['size']
LEAN = math.radians(5)
# (axle, radius, width, profile half-height) -- must match build-bike3.py
TYRES = {'front': (np.array([0.78, 0, 0.315]), 0.315, 0.20, 0.057), 'rear': (np.array([-0.78, 0, 0.325]), 0.325, 0.34, 0.067)}
ROT = np.array([[1, 0, 0], [0, math.cos(LEAN), math.sin(LEAN)], [0, -math.sin(LEAN), math.cos(LEAN)]])  # local -> world (roll -5 about X)


def tyre_pts(axle, r, w, hr, n=120, m=20):
    out = []
    hw = w / 2
    for k in range(m):
        a = math.tau * k / m
        c, s = math.cos(a), math.sin(a)
        u = hw * math.copysign(abs(c) ** (2 / 2.8), c)
        v = hr * math.copysign(abs(s) ** (2 / 2.8), s)
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


def pose(p):
    ex, ey, ez, yaw, pitch, fov = p
    eye = np.array([ex, ey, ez])
    d = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)])
    return eye, eye + d * 5, fov


PTS = {k: tyre_pts(*v) for k, v in TYRES.items()}
CONTACT = {k: np.array([TYRES[k][0][0], 0.0, 0.0]) for k in TYRES}  # the lean pivots about the contact line
HUB = {k: (TYRES[k][0] + np.array([0, TYRES[k][2] / 2 * 0.9, 0])) @ ROT.T for k in TYRES}


def residuals(p):
    eye, look, fov = pose(p)
    r = []
    E = G['ellipses']
    P = G['points']
    uvf = project(PTS['front'], eye, look, fov)
    uvr = project(PTS['rear'], eye, look, fov)
    cx, cy, rx, ry = E['front tyre']
    r += [uvf[:, 0].min() - (cx - rx), uvf[:, 1].min() - (cy - ry), uvf[:, 1].max() - (cy + ry)]
    cx, cy, rx, ry = E['rear tyre']
    if WHICH == 'city':
        r += [uvr[:, 0].max() - (cx + rx), uvr[:, 1].min() - (cy - ry), 0.3 * (uvr[:, 0].min() - (cx - rx))]
    else:
        r += [uvr[:, 0].max() - (cx + rx), uvr[:, 0].min() - (cx - rx), uvr[:, 1].min() - (cy - ry), uvr[:, 1].max() - (cy + ry)]
        c = project(CONTACT['rear'][None], eye, look, fov)[0]
        r += list((c - np.array(P['rear contact'])) * 0.7)
    c = project(CONTACT['front'][None], eye, look, fov)[0]
    r += list((c - np.array(P['front contact'])) * 0.5)
    for k, name in (('front', 'front axle'), ('rear', 'rear axle')):
        if name in P:
            h = project(HUB[k][None], eye, look, fov)[0]
            r += list((h - np.array(P[name])) * 0.6)
    f = (look - eye) / np.linalg.norm(look - eye)
    hz = H / 2 * (1 + math.tan(math.asin(f[2])) / math.tan(math.radians(fov) / 2))
    r.append((hz - G['horizon']) * 0.8)
    return np.array(r)


def main():
    best = None
    for yaw0 in (-10, -30, -50, -70):          # looking roughly toward +X from behind the +Y side
        for dist in (1.8, 2.6, 3.6, 5.0):
            for fov0 in (35, 50, 65):
                yaw = math.radians(yaw0)
                eye0 = np.array([-0.2, 0, 0.5]) - dist * np.array([math.cos(yaw), math.sin(yaw), 0])
                p0 = [*eye0, yaw, math.radians(2), fov0]
                try:
                    s = least_squares(residuals, p0, bounds=([-9, 0, 0.05, -math.pi, -0.8, 20], [3, 9, 3, math.pi / 2, 0.8, 85]))
                except ValueError:
                    continue
                if best is None or s.cost < best.cost:
                    best = s
    eye, look, fov = pose(best.x)
    res = residuals(best.x)
    hfov = 2 * math.degrees(math.atan(math.tan(math.radians(fov) / 2) * W / H))
    lens = 18 / math.tan(math.radians(hfov) / 2)
    out = {'concept': WHICH, 'location': eye.round(4).tolist(), 'look': look.round(4).tolist(), 'vfov': round(fov, 3), 'lens': round(lens, 3),
           'sensor_width': 36, 'size': [W, H], 'rms_px': round(float(np.sqrt((res ** 2).mean())), 2), 'residuals': res.round(1).tolist()}
    name = 'concept-cam3.json' if WHICH == 'city' else 'plaza-cam3.json'
    json.dump(out, open(os.path.join(HERE, name), 'w'), indent=1)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
