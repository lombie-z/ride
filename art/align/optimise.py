"""Fit the landing camera and the bike's pose to the concept by minimising score.total() over analytic projections.

  python3 art/align/optimise.py            -> out/pose-after.json, out/optimise-log.txt

Parameters (9): the bike's place on the deck in the road's frame (s along the road, lateral, yaw off parallel), and the
camera in the bike's frame (forward, left, height above the deck, heading relative to the bike, pitch) plus vertical
FOV. Working in the bike's frame decouples the problem: the bike's own features pin the camera to the bike, and the deck's
lines then place the bike on the road. Constraints (as penalties): the bike on the drivable deck between the kerb and the
near barrier, the camera over the deck and at least 0.4 m above it, FOV 30-55 deg.

Stage 1 (multi-start, in parallel): the camera relative to the bike only (6 parameters), against the bike's own terms
(silhouette, headlight, wheels), from a grid of camera positions round the bike's front-right quarter, each aimed at the
bike. The concept's strong perspective (its rear tyre is ~0.6x the front's height) puts the camera much closer than the
current pose, which a local search from there doesn't reach. Stage 2: all 9 parameters against the full score, Nelder-Mead
from the best few stage-1 results (and from the current pose), restarting with a fresh simplex until it stops improving.
"""
import json
import math
import os

import numpy as np
from scipy.optimize import minimize

import score
from common import CURRENT, DECK_Z, OUT

S = score.scene()
O, RD, RL = S['road_frame'][:3], S['road_frame'][3:6], S['road_frame'][6:9]
KERB_IN, NEAR_IN = float(S['deck'][0]), float(S['deck'][1])  # drivable lateral range (kerb face .. near barrier)
ROAD_HEADING = math.degrees(math.atan2(RD[1], RD[0]))
BIKE_HALF_RIGHT, BIKE_HALF_LEFT = 0.29, 0.46  # the bike's extent to each side of its centre line (bars, lean)
NAMES = ['bike_s', 'bike_lat', 'bike_yaw_rel', 'cam_fwd', 'cam_left', 'cam_h', 'cam_yaw_rel', 'cam_pitch', 'fov']


def pose_from(x):
    s, lat, yaw_rel, cf, cl, ch, cyaw, pitch, fov = x
    at = O + RD * s + RL * lat
    at[2] = DECK_Z
    byaw = (ROAD_HEADING + 180.0 + yaw_rel + 180.0) % 360.0 - 180.0
    c, sn = math.cos(math.radians(byaw)), math.sin(math.radians(byaw))
    bf, bl = np.array([c, sn, 0.0]), np.array([-sn, c, 0.0])
    eye = at + bf * cf + bl * cl
    eye[2] = DECK_Z + ch
    h = math.radians(byaw + cyaw)
    p = math.radians(pitch)
    v = np.array([math.cos(p) * math.cos(h), math.cos(p) * math.sin(h), math.sin(p)])
    look = eye + v * 60.0
    return {'EYE': [round(float(q), 4) for q in eye], 'LOOK': [round(float(q), 4) for q in look], 'FOV': round(float(fov), 3),
            'BIKE_AT': [round(float(q), 4) for q in at], 'BIKE_YAW': round(float(byaw), 3)}


def params_from(pose):
    at = np.array(pose['BIKE_AT'], float)
    d = at - O
    s, lat = float(d @ RD), float(d @ RL)
    byaw = pose['BIKE_YAW']
    yaw_rel = (byaw - ROAD_HEADING - 180.0 + 180) % 360 - 180
    c, sn = math.cos(math.radians(byaw)), math.sin(math.radians(byaw))
    bf, bl = np.array([c, sn, 0.0]), np.array([-sn, c, 0.0])
    e = np.array(pose['EYE'], float)
    v = np.array(pose['LOOK'], float) - e
    v /= np.linalg.norm(v)
    cyaw = (math.degrees(math.atan2(v[1], v[0])) - byaw + 180) % 360 - 180
    return np.array([s, lat, yaw_rel, (e - at) @ bf, (e - at) @ bl, e[2] - DECK_Z, cyaw,
                     math.degrees(math.asin(v[2])), pose['FOV']])


def penalty(x, pose):
    s, lat, yaw_rel, cf, cl, ch, cyaw, pitch, fov = x
    pen = 0.0
    pen += 1e3 * max(0.0, 0.4 - ch) ** 2
    pen += 1e3 * (max(0.0, 30 - fov) ** 2 + max(0.0, fov - 55) ** 2)
    pen += 1e3 * (max(0.0, KERB_IN - (lat - BIKE_HALF_LEFT)) ** 2 + max(0.0, (lat + BIKE_HALF_RIGHT) - NEAR_IN) ** 2)
    el = (np.array(pose['EYE']) - O) @ RL
    pen += 1e3 * (max(0.0, KERB_IN - el) ** 2 + max(0.0, el - NEAR_IN) ** 2)
    pen += 1.0 * max(0.0, abs(s) - 15.0) ** 2
    # Priors: keep the build's layout (bike parallel to the road, abreast its mark) unless the concept insists. Only the
    # deck's lines see these two, and the concept's lines are not perspective-consistent (see the report).
    pen += 0.5 * abs(yaw_rel) + 0.2 * abs(s)
    return pen


def objective(x):
    pose = pose_from(x)
    return score.analytic(pose)['total'] + penalty(x, pose)


def aim(x):
    """Turn the camera so the bike's middle lands where the concept's bike centroid is."""
    pose = pose_from(x)
    F = score.feats()
    cx, cy = F['bike']['centroid']
    mid = np.array(pose['BIKE_AT']) + np.array([0, 0, 0.5])
    e = np.array(pose['EYE'])
    v = mid - e
    yaw = math.degrees(math.atan2(v[1], v[0]))
    pitch = math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))
    tv = math.tan(math.radians(x[8]) / 2)
    yaw += math.degrees(math.atan((cx - 640) / 640 * tv * 16 / 9))  # look right of the bike so it sits left of centre
    pitch += math.degrees(math.atan((cy - 360) / 360 * tv))
    x = x.copy()
    x[6] = (yaw - pose['BIKE_YAW'] + 180) % 360 - 180
    x[7] = pitch
    return x


def bike_objective(xc, xb):
    x = np.r_[xb, xc]
    pose = pose_from(x)
    return score.analytic(pose, bike_only=True)['total_bike'] + penalty(x, pose)


def stage1_run(args):
    xb, xc = args
    r = minimize(bike_objective, xc, args=(xb,), method='Nelder-Mead',
                 options={'initial_simplex': np.array([xc] + [xc + np.eye(6)[i] * [0.25, 0.25, 0.15, 3, 2, 4][i] for i in range(6)]),
                          'maxfev': 1500, 'xatol': 1e-3, 'fatol': 1e-3, 'adaptive': True})
    return r.fun, r.x


def stage1(x0):
    from multiprocessing import Pool
    xb = x0[:3]
    starts = []
    for cf in (0.9, 1.4, 1.9, 2.4):
        for cl in (-1.3, -1.8, -2.3):
            for ch in (0.75, 1.05):
                for fov in (40.0, 50.0):
                    x = np.r_[xb, cf, cl, ch, 0.0, 0.0, fov]
                    starts.append((xb, aim(x)[3:]))
    with Pool(min(12, os.cpu_count() or 4)) as pool:
        res = pool.map(stage1_run, starts)
    res.sort(key=lambda r: r[0])
    return [(f, np.r_[xb, xc]) for f, xc in res]


def main():
    x0 = params_from(CURRENT)
    log = [f'start {dict(zip(NAMES, np.round(x0, 3)))}  total {objective(x0):.3f}']
    print(log[-1])
    s1 = stage1(x0)
    for f, x in s1[:6]:
        log.append(f'stage 1: bike terms {f:.3f} at {dict(zip(NAMES[3:], np.round(x[3:], 3)))}  full total {objective(x):.3f}')
        print(log[-1])
    cands = [x0] + [x for _, x in s1[:4]]
    best_x, best_f = None, np.inf
    for x in cands:
        r = minimize(objective, x, method='Nelder-Mead', options={'maxfev': 2000, 'xatol': 1e-3, 'fatol': 1e-3, 'adaptive': True})
        log.append(f'stage 2 from candidate: total {r.fun:.3f}')
        print(log[-1])
        if r.fun < best_f:
            best_x, best_f = r.x, r.fun
    step = np.array([0.5, 0.3, 3.0, 0.2, 0.2, 0.1, 2.0, 1.5, 2.0])
    for rnd in range(8):
        simplex = [best_x] + [best_x + np.eye(9)[i] * step[i] * (1 if (rnd + i) % 2 == 0 else -1) for i in range(9)]
        r = minimize(objective, best_x, method='Nelder-Mead',
                     options={'initial_simplex': np.array(simplex), 'maxfev': 2500, 'xatol': 1e-3, 'fatol': 1e-3,
                              'adaptive': True})
        log.append(f'round {rnd}: total {r.fun:.3f} after {r.nfev} evals')
        print(log[-1])
        if r.fun < best_f - 0.05:
            best_x, best_f = r.x, r.fun
            step = step * 0.7
        else:
            if r.fun < best_f:
                best_x, best_f = r.x, r.fun
            break
    pose = pose_from(best_x)
    log.append(f'best {dict(zip(NAMES, np.round(best_x, 3)))}  total {best_f:.3f}')
    log.append(json.dumps(pose))
    print('\n'.join(log[-2:]))
    with open(os.path.join(OUT, 'pose-after.json'), 'w') as f:
        json.dump(pose, f, indent=1)
    with open(os.path.join(OUT, 'optimise-log.txt'), 'w') as f:
        f.write('\n'.join(log) + '\n')


if __name__ == '__main__':
    main()
