"""First-person gloved hands holding the holo-map projector (art/reference/concept-transition.webp for the gloves).

Builds from scratch, saves art/hands.blend and exports public/models/hands.glb (Draco).
Run:    blender --background --factory-startup --python art/build-hands.py
Review: blender --background --factory-startup --python art/build-hands.py -- --render [--tag r1] [--views pov,lowered]

Frame: camera space, so the site parents the `Hands` root straight to the camera. In glTF the camera sits at the origin
looking down -Z with +Y up (built in Blender as camera at the origin looking down +Y, Z up, exported Y-up).
Nodes: Hands (root, identity) > LeftHand, RightHand (one mesh each, glove + cuff), Projector, HologramAnchor (empty at
the emitter's centre: +Y up out of the emitter, +Z toward the camera).
Materials: HandsGlove (black leather), HandsQuilt (padded panels), HandsChrome, HandsEmitter (emissive strip, UV u runs
0..1 along it).

How the hands are made: each hand is a signed-distance field (smooth unions of tapered capsules for metacarpals,
phalanges, thenar, wrist and gauntlet, with padded quilt panels inflated off the surface by masks), meshed with surface
nets on a 1 mm grid, relaxed onto the field, decimated, then re-projected. Fingers and thumb curl until they touch the
projector, so the grip always sits on its surface. The left hand is the right one mirrored.
"""
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
BLEND_OUT = os.path.join(HERE, 'hands.blend')
GLB_OUT = os.path.join(ROOT, 'public', 'models', 'hands.glb')
RENDER_DIR = os.path.join(HERE, 'renders')

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(name, default, cast=str):
    return cast(ARGS[ARGS.index(name) + 1]) if name in ARGS else default


DO_RENDER = '--render' in ARGS
NO_EXPORT = '--no-export' in ARGS
TAG = arg('--tag', '')
VIEWS = arg('--views', ['pov', 'lowered'], lambda s: s.split(','))
SAMPLES = arg('--samples', 64, int)
VOXEL = arg('--voxel', 0.15, float)  # cm
OUT_DIR = arg('--out', RENDER_DIR)
RES = arg('--res', (1600, 900), lambda s: tuple(int(v) for v in s.split('x')))
HAND_TRIS = arg('--hand-tris', 15500, int)  # per hand, the glove surface (welts and chrome come on top)

VFOV = 65.0
ASPECT = 16 / 9


def gl2b(x, y, z):
    """glTF / three camera space -> Blender (x right, y forward, z up)."""
    return np.array([x, -z, y], float)


# ---------------------------------------------------------------- the projector (Blender world, cm)
DEV_GL = arg('--dev', [0.0, -0.16, -0.38], lambda s: [float(v) for v in s.split(',')])  # metres, glTF camera space
DEV_C = gl2b(*DEV_GL) * 100.0
BAR_LEN, BAR_DEP, BAR_HGT = 22.0, 3.0, 1.85
BAR_HALF = np.array([BAR_LEN / 2, BAR_DEP / 2 + 0.05, BAR_HGT / 2])
BAR_R = 0.72  # edge radius of the chrome end caps (what the hands touch)

# ---------------------------------------------------------------- hand anatomy (right hand, hand space H, cm)
# H: origin at the wrist joint, +y distal (toward the middle knuckle), +z dorsal (back of the hand), +x ulnar (pinky
# side), so the thumb is on -x. Lengths are joint centre to joint centre; the distal one stops at the tip's centre.
FINGERS = {
    #          MCP joint centre       splay  segment lengths       radii at MCP, PIP, DIP, tip     curl bias
    'index': dict(mcp=(-2.45, 9.05, 0.20), splay=7, L=(3.95, 2.35, 1.40), R=(1.04, 0.96, 0.88, 0.83)),
    'middle': dict(mcp=(-0.42, 9.40, 0.30), splay=1, L=(4.35, 2.75, 1.50), R=(1.07, 0.99, 0.91, 0.85)),
    'ring': dict(mcp=(1.50, 9.00, 0.22), splay=-5, L=(4.05, 2.60, 1.42), R=(1.02, 0.95, 0.87, 0.81)),
    'pinky': dict(mcp=(3.20, 8.05, 0.02), splay=-12, L=(3.20, 1.95, 1.30), R=(0.92, 0.86, 0.80, 0.75)),
}
FINGER_ORDER = ('index', 'middle', 'ring', 'pinky')
FINGER_ZS = 0.88  # fingers are a little flatter than wide
THUMB = dict(cmc=(-1.95, 1.55, -0.55), L=(4.45, 3.05, 1.80), R=(1.55, 1.18, 1.08, 0.98, 0.94))

# grip / pose (right hand; the left mirrors it). World directions are Blender axes.
POSE = dict(
    finger_dir=(-0.35, 0.80, 0.45),   # wrist -> knuckles, world
    palm_dir=(-0.85, 0.0, 0.50),    # the way the palm faces, world
    forearm_dir=(0.42, -0.55, -0.72),  # wrist -> elbow, world
    grip_h=(-3.2, 9.9, -3.9),          # hand-space point that sits on the grip point below
    grip_bar=(-2.4, 0.0, 0.0),         # bar-local offset from the right end centre (cm)
    thumb_target=(-3.0, -0.4, 1.85),   # thumb tip centre, bar-end relative: on the top face near the near edge
    curl_max=dict(index=1.0, middle=1.0, ring=0.95, pinky=0.95),
)
for k in list(POSE):
    if '--pose-' + k in ARGS:
        POSE[k] = tuple(float(v) for v in arg('--pose-' + k, '').split(','))

TAU = math.tau


# ---------------------------------------------------------------- small maths
def nrm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def rad(d):
    return math.radians(d)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def frame_from(axis, hint):
    y = nrm(axis)
    z = nrm(np.asarray(hint, float) - (np.dot(hint, y)) * y)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)  # columns


F32 = np.float32


def sd_round_cone(P, a, b, r1, r2):
    """iq's round cone, vectorised. P (N,3)."""
    a = np.asarray(a, F32)
    b = np.asarray(b, F32)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    x = pa * F32(l2) - y[:, None] * ba
    x2 = np.einsum('ij,ij->i', x, x)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2 if rr != 0 else np.zeros_like(x2)
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3)).astype(F32)


def local(P, a, M):
    return (P - np.asarray(a, F32)) @ np.asarray(M, F32)


def sd_aniso_cone(P, a, b, r1, r2, hint, sx=1.0, sz=1.0):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    M = frame_from(b - a, hint)
    L = float(np.linalg.norm(b - a))
    Q = local(P, a, M) / np.array([sx, 1, sz], F32)
    return sd_round_cone(Q, (0, 0, 0), (0, L, 0), r1, r2) * F32(min(sx, sz))


def sd_ellipsoid(P, c, radii, M=None):
    Q = P - np.asarray(c, F32)
    if M is not None:
        Q = Q @ np.asarray(M, F32)
    r = np.asarray(radii, F32)
    k0 = np.linalg.norm(Q / r, axis=1)
    k1 = np.maximum(np.linalg.norm(Q / (r * r), axis=1), 1e-6)
    return (k0 * (k0 - 1.0) / k1).astype(F32)


def sd_tube(P, a, b, r1, r2, hint, sx=1.0, sz=1.0, rnd=0.15):
    """Flat-capped elliptical tube whose radius runs r1 -> r2 from a to b (gauntlet, strap)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    M = frame_from(b - a, hint)
    L = float(np.linalg.norm(b - a))
    Q = local(P, a, M)
    t = np.clip(Q[:, 1] / L, 0, 1)
    r = r1 + (r2 - r1) * t
    rho = np.sqrt((Q[:, 0] / sx) ** 2 + (Q[:, 2] / sz) ** 2) * F32(min(sx, sz))
    dr = rho - (r * F32(min(sx, sz)) - rnd)
    dy = np.abs(Q[:, 1] - L / 2) - (L / 2 - rnd)
    out = np.sqrt(np.maximum(dr, 0) ** 2 + np.maximum(dy, 0) ** 2)
    return (out + np.minimum(np.maximum(dr, dy), 0) - rnd).astype(F32), Q


def sd_bar_world(Pw):
    q = np.abs(Pw - DEV_C.astype(F32)) - (BAR_HALF - BAR_R).astype(F32)
    out = np.linalg.norm(np.maximum(q, 0), axis=1)
    return out + np.minimum(q.max(1), 0) - BAR_R


def groove(t, w):
    """1 on integer lines of t, 0 away, half-width w (in t units)."""
    return sstep(w, 0.0, np.abs(t - np.round(t)))


# ---------------------------------------------------------------- the hand (forward kinematics + field)
class Hand:
    def __init__(self, pose):
        self.pose = pose
        y = nrm(pose['finger_dir'])
        n = nrm(pose['palm_dir'])
        n = nrm(n - np.dot(n, y) * y)
        z = -n
        x = np.cross(y, z)
        self.R = np.stack([x, y, z], 1)  # H -> world rotation (columns are H axes in world)
        self.t = np.zeros(3)
        # bar grip point (world)
        g_bar = DEV_C + np.array([BAR_LEN / 2, 0, 0]) + np.asarray(pose['grip_bar'], float)
        self.t = g_bar - self.R @ np.asarray(pose['grip_h'], float)
        self.v = nrm(self.R.T @ nrm(pose['forearm_dir']))  # wrist -> elbow, hand space
        self.curl = {}
        for name in FINGER_ORDER:
            self.curl[name] = None
        self.solve_grip()

    # --- kinematics
    def finger(self, name, c):
        f = FINGERS[name]
        mcp, pip, dip = rad(4 + 78 * c), rad(6 + 96 * c), rad(2 + 62 * c)
        # flexed fingers converge a little toward the middle
        conv = {'index': -3, 'middle': 0, 'ring': 3, 'pinky': 6}[name] * c
        F0 = rot_z(rad(f['splay'] + conv)) @ rot_x(-mcp)
        F1 = F0 @ rot_x(-pip)
        F2 = F1 @ rot_x(-dip)
        J0 = np.asarray(f['mcp'], float)
        J1 = J0 + F0[:, 1] * f['L'][0]
        J2 = J1 + F1[:, 1] * f['L'][1]
        J3 = J2 + F2[:, 1] * f['L'][2]
        return [J0, J1, J2, J3], [F0, F1, F2], f['R']

    def thumb(self, c, prm=None):
        ra, pa, roll = prm if prm is not None else self.thumb_prm
        T0 = rot_z(rad(ra)) @ rot_x(-rad(pa)) @ rot_y(rad(roll))
        T1 = T0 @ rot_x(-rad(8 + 38 * c))
        T2 = T1 @ rot_x(-rad(4 + 58 * c))
        J0 = np.asarray(THUMB['cmc'], float)
        J1 = J0 + T0[:, 1] * THUMB['L'][0]
        J2 = J1 + T1[:, 1] * THUMB['L'][1]
        J3 = J2 + T2[:, 1] * THUMB['L'][2]
        return [J0, J1, J2, J3], [T0, T1, T2], THUMB['R']

    def to_world(self, P):
        return (np.asarray(P, float) @ self.R.T) + self.t

    def chain_clearance(self, joints, radii, skip_first=False):
        pts, rs = [], []
        for i in range(len(joints) - 1):
            if skip_first and i == 0:
                continue
            for s in np.linspace(0, 1, 9):
                pts.append(joints[i] * (1 - s) + joints[i + 1] * s)
                rs.append(radii[i] * (1 - s) + radii[i + 1] * s)
        pts = self.to_world(np.array(pts))
        d = sd_bar_world(pts.astype(F32)) - np.array(rs) * 0.97
        return float(d.min())

    def solve_grip(self):
        info = []
        for name in FINGER_ORDER:
            cmax = self.pose['curl_max'][name]
            hit = None
            for c in np.linspace(0, cmax, 101):
                J, F, R = self.finger(name, c)
                if self.chain_clearance(J, R) < 0.03:
                    hit = c
                    break
            if hit is None:
                prev = [self.curl[n] for n in FINGER_ORDER if self.curl.get(n) is not None]
                hit = cmax if not prev else min(cmax, max(prev[-1] + 0.12, 0.84))
                info.append(f'{name}: free c={hit:.2f}')
            else:
                info.append(f'{name}: touch c={hit:.2f}')
            self.curl[name] = hit
        self.fch = {n: self.finger(n, self.curl[n]) for n in FINGER_ORDER}
        self.solve_thumb()
        info.append(f'thumb: ra/pa/roll {np.round(self.thumb_prm, 0)} c={self.thumb_c:.2f}')
        print('GRIP', '; '.join(info))
        self.tch = self.thumb(self.thumb_c)
        end = DEV_C + np.array([BAR_LEN / 2, 0, 0])
        for n in FINGER_ORDER:
            print(f'  tip {n:6s} rel bar end', np.round(self.to_world(self.fch[n][0][3]) - end, 1))
        print('  tip thumb  rel bar end', np.round(self.to_world(self.tch[0][3]) - end, 1),
              ' thumb MCP', np.round(self.to_world(self.tch[0][1]) - end, 1))

    def solve_thumb(self):
        """Search the thumb's base angles and flex so its tip rests on the bar (pose['thumb_target'], bar-end
        relative, the tip *centre*), without going into the bar or through the index finger."""
        end = DEV_C + np.array([BAR_LEN / 2, 0, 0])
        target = end + np.asarray(self.pose['thumb_target'], float)
        rest = np.array([35.0, 40.0, -60.0])
        J, F, R = self.fch['index']
        idx_pts = np.array([J[i] * (1 - s) + J[i + 1] * s for i in range(3) for s in np.linspace(0, 1, 6)])
        idx_r = np.array([R[i] * (1 - s) + R[i + 1] * s for i in range(3) for s in np.linspace(0, 1, 6)])

        def cost(prm, c):
            TJ, TF, TR = self.thumb(c, prm)
            tip = self.to_world(TJ[3])
            e = np.linalg.norm(tip - target)
            clr = self.chain_clearance(TJ, TR)
            pen = 40.0 * max(0.0, -clr)
            pts = np.array([TJ[i] * (1 - s) + TJ[i + 1] * s for i in (1, 2) for s in np.linspace(0, 1, 6)])
            rr = np.array([TR[i] * (1 - s) + TR[i + 1] * s for i in (1, 2) for s in np.linspace(0, 1, 6)])
            dd = np.linalg.norm(pts[:, None] - idx_pts[None], axis=2) - rr[:, None] - idx_r[None]
            pen += 20.0 * max(0.0, -dd.min())
            reg = 0.004 * np.sum(((np.asarray(prm) - rest) / 30.0) ** 2) * 10
            return e + pen + reg
        best = (1e9, None, None)
        for ra in np.linspace(-10, 80, 10):
            for pa in np.linspace(-10, 100, 12):
                for roll in np.linspace(-160, 40, 11):
                    for c in np.linspace(0.0, 1.0, 6):
                        k = cost((ra, pa, roll), c)
                        if k < best[0]:
                            best = (k, np.array([ra, pa, roll]), c)
        rng = np.random.default_rng(1)
        k0, prm, c = best
        for it in range(1500):
            sc = 8.0 * (1 - it / 1500) + 0.5
            p2 = prm + rng.normal(0, sc, 3)
            c2 = float(np.clip(c + rng.normal(0, sc / 60), 0, 1))
            k = cost(p2, c2)
            if k < k0:
                k0, prm, c = k, p2, c2
        self.thumb_prm, self.thumb_c = tuple(prm), c
        TJ, _, TR = self.thumb(c)
        print(f'  thumb solve: cost {k0:.2f}, tip miss {np.linalg.norm(self.to_world(TJ[3]) - target):.2f} cm, '
              f'clearance {self.chain_clearance(TJ, TR):.2f}')

    # --- the field (hand space, cm)
    def sdf(self, P, masks=False):
        P = np.asarray(P, F32)
        Z = np.array([0, 0, 1.0])
        v = self.v
        # palm: metacarpals as flattened capsules, smooth-unioned into a slab, plus the fleshy palm and hypothenar
        metas = [((-1.75, 1.55, -0.05), FINGERS['index']['mcp'], 1.30, 1.13),
                 ((-0.45, 1.35, 0.05), FINGERS['middle']['mcp'], 1.34, 1.16),
                 ((0.85, 1.45, 0.0), FINGERS['ring']['mcp'], 1.30, 1.11),
                 ((1.85, 1.75, -0.08), FINGERS['pinky']['mcp'], 1.22, 1.00)]
        d = None
        for a, b, r1, r2 in metas:
            di = sd_aniso_cone(P, a, b, r1, r2, Z, 1.0, 0.86)
            d = di if d is None else smin(d, di, 1.5)
        d = smin(d, sd_ellipsoid(P, (0.35, 4.6, -0.35), (3.15, 3.6, 1.25)), 1.0)
        d = smin(d, sd_ellipsoid(P, (2.55, 3.4, -0.65), (1.25, 2.6, 1.05)), 0.8)
        d_palm = d
        # wrist: palm base -> joint -> along the forearm
        w0 = sd_aniso_cone(P, (0.0, 1.9, -0.15), (0, 0, 0), 2.52, 2.48, Z, 1.28, 0.86)
        w1 = sd_aniso_cone(P, (0, 0, 0), v * 5.2, 2.48, 2.42, Z, 1.28, 0.86)
        d = smin(d, smin(w0, w1, 1.0), 1.5)
        # thumb: metacarpal inside the thenar, then the free thumb
        TJ, TF, TR = self.tch
        thenar = sd_aniso_cone(P, TJ[0], TJ[1], TR[0], TR[1], TF[0][:, 2], 1.08, 0.90)
        d = smin(d, thenar, 1.35)
        dt = None
        for i in (1, 2):
            di = sd_aniso_cone(P, TJ[i], TJ[i + 1], TR[i], TR[i + 1] if i == 1 else TR[4], TF[i][:, 2], 1.0, 0.86)
            dt = di if dt is None else smin(dt, di, 0.25)
        kweb = (0.35 + 0.85 * sstep(2.2, 0.0, d_palm)).astype(F32)
        d = smin(d, dt, kweb)
        # fingers
        pad = np.zeros(len(P), F32)  # inflation (cm)
        m_quilt = np.zeros(len(P), F32)
        for name in FINGER_ORDER:
            J, F, R = self.fch[name]
            fr = 1.05
            df = sd_aniso_cone(P, J[0] - F[0][:, 1] * 0.8, J[1], R[0] * 1.02 * fr, R[1] * fr, F[0][:, 2], 1.0, FINGER_ZS)
            for i in (1, 2):
                di = sd_aniso_cone(P, J[i], J[i + 1], R[i] * fr, R[i + 1] * fr, F[i][:, 2], 1.0, FINGER_ZS)
                df = smin(df, di, 0.22)
            k = (0.18 + 0.75 * sstep(1.8, -0.2, d_palm)).astype(F32)
            d = smin(d, df, k)
            # padded segments on the backs of the proximal and middle phalanges
            for i, (h, y0, y1) in enumerate(((0.26, 0.85, -0.55), (0.18, 0.45, -0.40))):
                Q = local(P, J[i], F[i])
                L = FINGERS[name]['L'][i]
                rr = R[i]
                m = (sstep(y0 - 0.25, y0 + 0.15, Q[:, 1]) * sstep(L + y1 + 0.25, L + y1 - 0.15, Q[:, 1])
                     * sstep(0.15, 0.55, Q[:, 2] / rr) * sstep(0.95 * rr, 0.60 * rr, np.abs(Q[:, 0]))
                     * sstep(rr + 0.9, rr + 0.3, np.sqrt(Q[:, 0] ** 2 + Q[:, 2] ** 2)))
                pad = np.maximum(pad, h * m)
                m_quilt = np.maximum(m_quilt, m)
            # knuckle pad over the MCP joint: domes that rise from the knuckle bar
            fl = math.acos(np.clip(np.dot(F[0][:, 1], (0, 1, 0)), -1, 1))
            kd = nrm(np.array([0, 0, 1.0]) + math.sin(fl) * np.array([0, 1.0, 0]) * 0.9)
            K = J[0] + kd * R[0] * 0.88 + np.array([0, 0.15, 0])
            dist = np.linalg.norm(P - K.astype(F32), axis=1)
            m = sstep(1.5, 0.6, dist)
            pad = np.maximum(pad, 0.52 * m)
            m_quilt = np.maximum(m_quilt, sstep(0.3, 0.6, m))
        # thumb: padded back of the proximal phalanx
        Q = local(P, TJ[1], TF[1])
        rr = TR[1]
        m = (sstep(0.45, 0.85, Q[:, 1]) * sstep(THUMB['L'][1] - 0.15, THUMB['L'][1] - 0.55, Q[:, 1])
             * sstep(0.15, 0.55, Q[:, 2] / rr) * sstep(0.95 * rr, 0.6 * rr, np.abs(Q[:, 0]))
             * sstep(rr + 0.9, rr + 0.3, np.sqrt(Q[:, 0] ** 2 + Q[:, 2] ** 2)))
        pad = np.maximum(pad, 0.26 * m)
        m_quilt = np.maximum(m_quilt, m)
        # back of the hand: a diamond-quilted panel
        e = ((P[:, 0] - 0.30) / 3.05) ** 2 + ((P[:, 1] - 4.75) / 2.85) ** 2
        m_back = sstep(1.0, 0.72, e) * sstep(0.1, 0.7, P[:, 2])
        u = (P[:, 0] + P[:, 1]) / 1.55
        w = (P[:, 0] - P[:, 1]) / 1.55
        g = np.maximum(groove(u, 0.11), groove(w, 0.11))
        pad = np.maximum(pad, m_back * (0.40 - 0.26 * g))
        m_quilt = np.maximum(m_quilt, m_back)
        # palm heel patch (slightly raised reinforcement)
        e2 = ((P[:, 0] - 0.9) / 2.7) ** 2 + ((P[:, 1] - 3.2) / 2.2) ** 2
        m_heel = sstep(1.0, 0.72, e2) * sstep(-0.2, -0.8, P[:, 2])
        u2 = P[:, 1] / 1.1
        pad = np.maximum(pad, m_heel * (0.24 - 0.14 * groove(u2, 0.1)))
        m_quilt = np.maximum(m_quilt, m_heel)
        d_glove = d - pad
        # wrist strap: a band with square edges
        d_strap, _ = sd_tube(P, v * 1.7, v * 3.9, 2.70, 2.66, Z, 1.28, 0.88, rnd=0.12)
        # gauntlet: flared, diamond quilted, runs well off the bottom of the frame
        L_g = 15.0
        d_g, Qg = sd_tube(P, v * 5.05, v * (5.05 + L_g), 2.72, 3.6, Z, 1.20, 0.95, rnd=0.25)
        theta = np.arctan2(Qg[:, 2] / 0.95, Qg[:, 0] / 1.20)
        S = TAU * 2.95 / 9
        ug = (theta * 2.95 + Qg[:, 1]) / S
        wg = (theta * 2.95 - Qg[:, 1]) / S
        gg = np.maximum(groove(ug, 0.10), groove(wg, 0.10)) * sstep(0.6, 1.4, Qg[:, 1])
        d_g = d_g + 0.22 * gg
        out = np.minimum(np.minimum(d_glove, d_strap), d_g)
        if not masks:
            return out
        quilt = (m_quilt > 0.42) | ((d_g <= np.minimum(d_glove, d_strap) + 0.02) & (Qg[:, 1] > 0.3))
        return out, quilt

    def grad(self, P, eps=0.02, fn=None):
        fn = fn or self.sdf
        g = np.zeros_like(P)
        for i in range(3):
            o = np.zeros(3, F32)
            o[i] = eps
            g[:, i] = (fn(P + o) - fn(P - o)) / (2 * eps)
        return g

    def part_sdf(self, name):
        """Field of one digit alone (seams are projected onto it so they never jump to a neighbour)."""
        if name == 'thumb':
            J, F, R = self.tch
            segs = [(J[1], J[2], R[1], R[2], F[1]), (J[2], J[3], R[2], R[4], F[2])]
            zs = 0.86
        else:
            J, F, R = self.fch[name]
            segs = [(J[i], J[i + 1], R[i], R[i + 1], F[i]) for i in range(3)]
            zs = FINGER_ZS

        def fn(P):
            d = None
            for a, b, r1, r2, Fi in segs:
                di = sd_aniso_cone(np.asarray(P, F32), a, b, r1, r2, Fi[:, 2], 1.0, zs)
                d = di if d is None else smin(d, di, 0.22)
            return d
        return fn

    def project(self, V, iters=2, chunk=200000, fn=None):
        fn = fn or self.sdf
        V = V.astype(F32).copy()
        for _ in range(iters):
            for s in range(0, len(V), chunk):
                P = V[s:s + chunk]
                d = fn(P)
                g = self.grad(P, fn=fn)
                gg = np.maximum(np.einsum('ij,ij->i', g, g), 1e-4)
                V[s:s + chunk] = P - (d / gg)[:, None] * g
        return V

    def bounds(self):
        pts = [np.zeros(3), self.v * 30.0]
        for name in FINGER_ORDER:
            pts += list(self.fch[name][0])
        pts += list(self.tch[0])
        pts = np.array(pts)
        return pts.min(0) - 4.6, pts.max(0) + 4.6


# ---------------------------------------------------------------- meshing: surface nets on a coarse-to-fine grid
def eval_chunks(fn, P, chunk=300000):
    out = np.empty(len(P), F32)
    for s in range(0, len(P), chunk):
        out[s:s + chunk] = fn(P[s:s + chunk])
    return out


def sample_grid(fn, lo, hi, h, factor=4):
    n = np.ceil((hi - lo) / h).astype(int) + 1
    n = ((n - 1 + factor - 1) // factor) * factor + 1
    nc = (n - 1) // factor + 1
    axes_c = [lo[i] + np.arange(nc[i]) * h * factor for i in range(3)]
    G = np.stack(np.meshgrid(*axes_c, indexing='ij'), -1).reshape(-1, 3).astype(F32)
    Dc = eval_chunks(fn, G).reshape(nc)
    near = np.abs(Dc) < h * 7.5
    # dilate by one coarse cell
    nd = near.copy()
    for ax in range(3):
        nd |= np.roll(near, 1, ax) | np.roll(near, -1, ax)
    ci = [np.clip(np.rint(np.arange(n[i]) / factor).astype(int), 0, nc[i] - 1) for i in range(3)]
    F = Dc[np.ix_(*ci)].copy()
    NEAR = nd[np.ix_(*ci)]
    idx = np.nonzero(NEAR)
    P = (lo + h * np.stack(idx, 1)).astype(F32)
    F[idx] = eval_chunks(fn, P)
    print(f'  grid {tuple(n)} = {F.size / 1e6:.1f}M, exact {len(P) / 1e6:.2f}M')
    return F


def surface_nets(F, lo, h):
    inside = F < 0
    nx, ny, nz = F.shape
    corners = [(i, j, k) for k in (0, 1) for j in (0, 1) for i in (0, 1)]

    def cs(a, b, c):
        return inside[a:nx - 1 + a, b:ny - 1 + b, c:nz - 1 + c]
    s = sum(cs(*c).astype(np.int8) for c in corners)
    active = (s > 0) & (s < 8)
    cidx = -np.ones(active.shape, np.int64)
    ai = np.nonzero(active)
    cidx[ai] = np.arange(len(ai[0]))
    base = np.stack(ai, 1).astype(F32)
    acc = np.zeros_like(base)
    cnt = np.zeros(len(base), F32)
    edges = [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0)), ((0, 0, 1), (1, 0, 1)), ((0, 1, 1), (1, 1, 1)),
             ((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0)), ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1)),
             ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)), ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1))]
    for oa, ob in edges:
        Fa = F[ai[0] + oa[0], ai[1] + oa[1], ai[2] + oa[2]]
        Fb = F[ai[0] + ob[0], ai[1] + ob[1], ai[2] + ob[2]]
        m = (Fa < 0) != (Fb < 0)
        t = np.where(m, Fa / np.where(m, Fa - Fb, 1), 0)
        pos = base + np.asarray(oa, F32) + t[:, None] * (np.asarray(ob, F32) - np.asarray(oa, F32))
        acc[m] += pos[m]
        cnt[m] += 1
    V = lo + h * (acc / cnt[:, None])
    quads = []
    # x edges
    for axis in range(3):
        sl0 = [slice(0, nx), slice(0, ny), slice(0, nz)]
        sl1 = list(sl0)
        dims = [nx, ny, nz]
        sl0[axis] = slice(0, dims[axis] - 1)
        sl1[axis] = slice(1, dims[axis])
        ch = inside[tuple(sl0)] != inside[tuple(sl1)]
        # need the two other indices >= 1
        o1, o2 = [(1, 2), (2, 0), (0, 1)][axis]
        ii = np.nonzero(ch)
        keep = (ii[o1] >= 1) & (ii[o2] >= 1) & (ii[o1] < dims[o1] - 1) & (ii[o2] < dims[o2] - 1)
        ii = [a[keep] for a in ii]
        flip = inside[tuple(ii)]  # inside at the lower end -> normal +axis

        def cell(d1, d2):
            c = [ii[0].copy(), ii[1].copy(), ii[2].copy()]
            c[o1] = c[o1] - d1
            c[o2] = c[o2] - d2
            return cidx[c[0], c[1], c[2]]
        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], 1)
        q[~flip] = q[~flip][:, ::-1]
        quads.append(q)
    Q = np.concatenate(quads)
    assert (Q >= 0).all()
    return V.astype(F32), Q


def relax(V, Q, hand, iters=4, lam=0.5):
    e = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    for _ in range(iters):
        acc = np.zeros_like(V)
        deg = np.zeros(len(V), F32)
        np.add.at(acc, e[:, 0], V[e[:, 1]])
        np.add.at(acc, e[:, 1], V[e[:, 0]])
        np.add.at(deg, e[:, 0], 1)
        np.add.at(deg, e[:, 1], 1)
        V = V + lam * (acc / np.maximum(deg, 1)[:, None] - V)
        V = hand.project(V, iters=1)
    return V


# ---------------------------------------------------------------- Blender helpers
def srgb(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16)) for i in (1, 3, 5))


def principled(name, base, metallic=0.0, rough=0.5, coat=0.0, coat_rough=0.03, emit=None, emit_strength=0.0, spec=0.5,
               sheen=0.0, sheen_tint=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    b.inputs['Sheen Weight'].default_value = sheen
    b.inputs['Sheen Tint'].default_value = (*sheen_tint, 1)
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    m.diffuse_color = (*base, 1)
    return m


def make_materials():
    return {
        'glove': principled('HandsGlove', srgb('#050406'), rough=0.45, coat=0.6, coat_rough=0.045, spec=0.35),
        'quilt': principled('HandsQuilt', srgb('#100e12'), rough=0.6, coat=0.25, coat_rough=0.18, spec=0.4,
                            sheen=0.08, sheen_tint=srgb('#c9b8d8')),
        'chrome': principled('HandsChrome', (0.96, 0.96, 0.98), metallic=1.0, rough=0.06),
        'emit': principled('HandsEmitter', srgb('#7f9bff'), rough=0.2, emit=srgb('#86b4ff'), emit_strength=6.0),
    }


def tube_geom(bm, pts, radius, sides=4, closed=False, mat=0):
    """Sweep a small tube along a polyline (pts (N,3)), parallel-transport frames."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    if n < 2:
        return
    tangents = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tangents.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    nrm_ = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        nrm_ = (nrm_ - t * nrm_.dot(t)).normalized()
        b = t.cross(nrm_)
        ring = []
        for k in range(sides):
            a = TAU * k / sides
            ring.append(bm.verts.new(pts[i] + (nrm_ * math.cos(a) + b * math.sin(a)) * radius))
        rings.append(ring)
    segs = n if closed else n - 1
    for i in range(segs):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            f = bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
            f.material_index = mat
            f.smooth = True
    if not closed:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            f = bm.faces.new(ring[::-1] if rev else ring)
            f.material_index = mat
            f.smooth = True


def surface_curve(hand, guesses, lift=0.02, fn=None):
    """Project guess points onto the hand surface (or one digit's), lift along the normal."""
    P = hand.project(np.asarray(guesses, F32), iters=4, fn=fn)
    g = hand.grad(P, fn=fn)
    g /= np.maximum(np.linalg.norm(g, axis=1), 1e-6)[:, None]
    return P + g * lift, g


def seam_loops(hand):
    """Glove seams: one loop per finger (up one side, round the tip, down the other) and one round the thumb."""
    loops = []
    for name in FINGER_ORDER:
        J, F, R = hand.fch[name]
        side = []
        for sgn in (-1, 1):
            pts = []
            for i in range(3):
                for s in np.linspace(0.15 if i == 0 else 0, 1, 6 if i == 0 else 4, endpoint=False):
                    c = J[i] * (1 - s) + J[i + 1] * s
                    r = R[i] * (1 - s) + R[i + 1] * s
                    pts.append(c + F[i][:, 0] * sgn * (r + 0.4) - F[i][:, 2] * r * 0.18)
            side.append(pts)
        tip = []
        Fx, Fy, Fz = hand.fch[name][1][2][:, 0], hand.fch[name][1][2][:, 1], hand.fch[name][1][2][:, 2]
        for a in np.linspace(-80, 80, 7):
            tip.append(J[3] + (Fx * math.sin(rad(a)) + Fy * math.cos(rad(a))) * (R[3] + 0.4) - Fz * R[3] * 0.18)
        pts = side[0] + tip + side[1][::-1]
        loops.append((name, np.array(pts)))
    # thumb: same idea, from the web round the tip and back down the outside
    J, F, R = hand.tch
    side = []
    for sgn in (-1, 1):
        pts = []
        for i in (1, 2):
            for s in np.linspace(0, 1, 5, endpoint=False):
                c = J[i] * (1 - s) + J[i + 1] * s
                r = R[i] * (1 - s) + R[i + 1] * s
                pts.append(c + F[i][:, 0] * sgn * (r + 0.4) - F[i][:, 2] * r * 0.1)
        side.append(pts)
    Fx, Fy, Fz = F[2][:, 0], F[2][:, 1], F[2][:, 2]
    tip = [J[3] + (Fx * math.sin(rad(a)) + Fy * math.cos(rad(a))) * (R[4] + 0.4) - Fz * R[4] * 0.1
           for a in np.linspace(-80, 80, 7)]
    loops.append(('thumb', np.array(side[0] + tip + side[1][::-1])))
    # wrist seam where the glove meets the strap
    return loops


def ring_points(hand, s, n=48, lift=0.0, sx=1.30, sz=0.86, r=3.2):
    v = hand.v
    M = frame_from(v, (0, 0, 1.0))
    c = v * s
    pts = [c + (M[:, 0] * math.cos(a) * sx + M[:, 2] * math.sin(a) * sz) * r for a in np.linspace(0, TAU, n, endpoint=False)]
    P, g = surface_curve(hand, pts, lift)
    # keep them in the ring's plane
    P = P - np.outer((P - c) @ v, v)
    return P, M


def build_hand_mesh(hand, mats):
    t0 = time.time()
    lo, hi = hand.bounds()
    F = sample_grid(hand.sdf, lo, hi, VOXEL)
    V, Q = surface_nets(F, lo.astype(F32), F32(VOXEL))
    print(f'  nets: {len(V)} verts {len(Q)} quads ({time.time() - t0:.1f}s)')
    V = relax(V, Q, hand, iters=3)
    me = bpy.data.meshes.new('HandTmp')
    me.from_pydata(V.tolist(), [], Q.tolist())
    me.validate()
    ob = bpy.data.objects.new('HandTmp', me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new('Decimate', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = min(1.0, HAND_TRIS / (2.0 * len(Q)))
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    # re-project the decimated verts onto the field, assign materials from the panel masks
    co = np.zeros(len(me2.vertices) * 3, F32)
    me2.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    vn = np.zeros(len(me2.vertices) * 3, F32)
    me2.vertex_normals.foreach_get('vector', vn)
    vn = vn.reshape(-1, 3)
    # pull verts back onto the field, but only along their own normal and only a little (a vert that would jump to
    # a neighbouring finger stays put)
    pr = hand.project(co, iters=2)
    mv = pr - co
    ok = (np.linalg.norm(mv, axis=1) < 0.12)
    co = np.where(ok[:, None], pr, co).astype(F32)
    me2.vertices.foreach_set('co', co.ravel())
    me2.update()
    me2.vertex_normals.foreach_get('vector', vn.ravel())
    gn = hand.grad(co)
    gn /= np.maximum(np.linalg.norm(gn, axis=1), 1e-6)[:, None]
    agree = np.einsum('ij,ij->i', gn, vn) > 0.6
    gn = np.where(agree[:, None], gn, vn)
    print(f'  reprojected {ok.mean():.3f}, field normals used {agree.mean():.3f}')
    me2['surf_normals'] = gn.astype(np.float64).ravel().tolist()
    cen = np.zeros(len(me2.polygons) * 3, F32)
    me2.polygons.foreach_get('center', cen)
    _, quilt = hand.sdf(cen.reshape(-1, 3), masks=True)
    for m in (mats['glove'], mats['quilt'], mats['chrome']):
        me2.materials.append(m)
    me2.polygons.foreach_set('material_index', quilt.astype(np.int32))
    print(f'  decimated to {len(me2.polygons)} tris ({time.time() - t0:.1f}s)')
    # seams, chrome ring, strap snap -> same mesh
    bm = bmesh.new()
    bm.from_mesh(me2)
    for name, loop in seam_loops(hand):
        P, _ = surface_curve(hand, loop, lift=0.02, fn=hand.part_sdf(name))
        tube_geom(bm, P, 0.065, sides=4, mat=0)
    # wrist seam (glove edge under the strap) and the chrome ring at the gauntlet
    P, _ = ring_points(hand, 1.45, n=40, lift=0.03)
    tube_geom(bm, P, 0.07, sides=4, closed=True, mat=0)
    P, M = ring_points(hand, 5.0, n=56, lift=0.34, r=3.6)
    tube_geom(bm, P, 0.42, sides=10, closed=True, mat=2)
    # snap on the strap (dorsal)
    snap_c = hand.v * 2.8 + np.array([0, 0, 1.0]) * 3.0
    P, g = surface_curve(hand, [snap_c], lift=0.0)
    c, nn = Vector(P[0]), Vector(g[0]).normalized()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.62, radius2=0.5, depth=0.32)
    rotq = nn.to_track_quat('Z', 'Y')
    for vv in res['verts']:
        vv.co = c + rotq @ vv.co + nn * 0.14
    for f in {f for vv in res['verts'] for f in vv.link_faces}:
        f.material_index = 2
        f.smooth = True
    # chrome palm slider (an oval puck on the heel of the palm)
    P, g = surface_curve(hand, [(1.0, 2.9, -3.0)], lift=0.0)
    c, nn = Vector(P[0]), Vector(g[0]).normalized()
    res = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=8, radius=1.0)
    yax = Vector((0, 1, 0))
    xax = yax.cross(nn).normalized()
    yax = nn.cross(xax).normalized()
    for vv in res['verts']:
        p = vv.co
        vv.co = c + xax * p.x * 1.05 + yax * p.y * 1.5 + nn * (p.z * 0.24 + 0.08)
    for f in {f for vv in res['verts'] for f in vv.link_faces}:
        f.material_index = 2
        f.smooth = True
    bm.to_mesh(me2)
    bm.free()
    me2.shade_smooth()
    return me2


def bake_world(me, hand, mirror=False):
    co = np.zeros(len(me.vertices) * 3, float)
    me.vertices.foreach_get('co', co)
    W = hand.to_world(co.reshape(-1, 3)) * 0.01
    if mirror:
        W[:, 0] *= -1
    me.vertices.foreach_set('co', W.astype(F32).ravel())
    if mirror:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
    me.update()
    # exact smooth normals for the glove surface, straight from the field's gradient (the decimated mesh would
    # otherwise shade faceted); welts, ring and snap keep their own
    gn = np.asarray(me['surf_normals'], float).reshape(-1, 3) @ hand.R.T
    if mirror:
        gn[:, 0] *= -1
    vn = np.zeros(len(me.vertices) * 3, F32)
    me.vertex_normals.foreach_get('vector', vn)
    vn = vn.reshape(-1, 3)
    vn[:len(gn)] = gn
    me.normals_split_custom_set_from_vertices([tuple(v) for v in vn])
    del me['surf_normals']
    return W


def recentre(ob, origin):
    me = ob.data
    me.transform(Matrix.Translation(-Vector(origin)))
    ob.location = origin


def rounded_box(bm, centre, size, radius, segments=4, mat=0):
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res['verts']
    for v in verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(centre)
    edges = list({e for v in verts for e in v.link_edges})
    out = bmesh.ops.bevel(bm, geom=verts + edges, offset=radius, offset_type='OFFSET', segments=segments,
                          profile=0.5, affect='EDGES', clamp_overlap=True)
    faces = {f for v in verts if v.is_valid for f in v.link_faces} | set(out.get('faces', []))
    for f in faces:
        if f.is_valid:
            f.material_index = mat
            f.smooth = True
    return faces


def build_projector(mats):
    bm = bmesh.new()
    s = 0.01
    # black glossy core, chrome end caps, chrome rim round the emitter strip, a chrome pinstripe on the near face
    rounded_box(bm, (0, 0, 0), (17.6 * s, 2.85 * s, 1.68 * s), 0.62 * s, 4, mat=0)
    for sx in (-1, 1):
        rounded_box(bm, (sx * 9.55 * s, 0, 0), (2.9 * s, BAR_HALF[1] * 2 * s, BAR_HGT * s), BAR_R * s, 4, mat=2)
        # a thin chrome collar where cap meets core
        rounded_box(bm, (sx * 7.95 * s, 0, 0), (0.35 * s, 3.0 * s, 1.78 * s), 0.16 * s, 2, mat=2)
    top = 1.68 / 2
    rounded_box(bm, (0, 0, (top + 0.05) * s), (15.0 * s, 0.95 * s, 0.22 * s), 0.08 * s, 2, mat=2)
    emit_faces = rounded_box(bm, (0, 0, (top + 0.14) * s), (14.4 * s, 0.5 * s, 0.2 * s), 0.07 * s, 2, mat=3)
    rounded_box(bm, (0, -1.43 * s, 0.0), (15.6 * s, 0.1 * s, 0.14 * s), 0.04 * s, 1, mat=2)
    # three status pips on the near face, left of centre
    for i in range(3):
        rounded_box(bm, ((-6.4 + i * 0.55) * s, -1.44 * s, 0.42 * s), (0.28 * s, 0.1 * s, 0.14 * s), 0.04 * s, 1, mat=3)
    me = bpy.data.meshes.new('Projector')
    uv = bm.loops.layers.uv.new('UVMap')
    xs = [v.co.x for f in emit_faces if f.is_valid for v in f.verts]
    ys = [v.co.y for f in emit_faces if f.is_valid for v in f.verts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    emit_set = {f for f in emit_faces if f.is_valid}
    for f in bm.faces:
        for lp in f.loops:
            if f in emit_set:
                lp[uv].uv = ((lp.vert.co.x - x0) / (x1 - x0), (lp.vert.co.y - y0) / (y1 - y0))
            else:
                lp[uv].uv = (lp.vert.co.x / (BAR_LEN * s) + 0.5, lp.vert.co.z / (BAR_HGT * s) + 0.5)
    bm.to_mesh(me)
    bm.free()
    for m in (mats['glove'], mats['quilt'], mats['chrome'], mats['emit']):
        me.materials.append(m)
    ob = bpy.data.objects.new('Projector', me)
    ob.location = Vector(DEV_C * 0.01)
    anchor_local = Vector((0, 0, (top + 0.24) * s))
    return ob, ob.location + anchor_local


# ---------------------------------------------------------------- render setup (review only, not exported)
def setup_render(scene):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = 'GPU'
    except Exception as e:  # noqa: BLE001
        print('GPU unavailable', e)
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.resolution_x, scene.render.resolution_y = RES
    world = bpy.data.worlds.new('SunsetWorld')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    remap = nt.nodes.new('ShaderNodeMapRange')
    remap.inputs['From Min'].default_value = -1.0
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    nt.links.new(sep.outputs['Z'], remap.inputs['Value'])
    nt.links.new(remap.outputs['Result'], ramp.inputs['Fac'])
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.03, 0.015, 0.04, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.10, 0.07, 0.32, 1)
    cr.elements[0].color = (0.006, 0.004, 0.01, 1)
    for pos, c in ((0.40, (0.012, 0.008, 0.02, 1)), (0.47, (0.07, 0.03, 0.07, 1)), (0.50, (1.6, 0.55, 0.32, 1)), (0.53, (1.1, 0.42, 0.62, 1)),
                   (0.62, (0.55, 0.30, 0.85, 1)), (0.80, (0.22, 0.15, 0.55, 1))):
        e = cr.elements.new(pos)
        e.color = c
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    col = bpy.data.collections.new('Render')
    scene.collection.children.link(col)
    # low sunset sun ahead, a pink key from above-behind the viewer, a violet rim from the side
    sd = bpy.data.lights.new('Sun', 'SUN')
    sd.color = (1.0, 0.55, 0.35)
    sd.energy = 3.0
    sd.angle = math.radians(3)
    sun = bpy.data.objects.new('Sun', sd)
    sun.rotation_euler = Vector((0.25, -1.0, -0.25)).to_track_quat('-Z', 'Y').to_euler()
    col.objects.link(sun)
    for name, loc, colr, energy, size in (('Key', (0.25, -0.15, 0.6), (1.0, 0.9, 0.95), 18.0, 0.35),
                                          ('Rim', (-0.9, 0.9, 0.1), (0.62, 0.5, 1.0), 40.0, 0.8),
                                          ('Rim2', (0.9, 0.8, 0.0), (1.0, 0.5, 0.7), 30.0, 0.8)):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.color = colr
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0.45, -0.25)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        col.objects.link(lo)
    # bright panels for the chrome and the wet leather to reflect
    for loc, size, colr, s in (((0, 3, 2.0), (6, 1.2), (0.95, 0.85, 1.0), 3.0), ((-2.5, 1.0, 1.2), (3, 1.5), (1.0, 0.6, 0.85), 2.0),
                               ((2.5, 1.5, 1.4), (3, 1.2), (0.7, 0.65, 1.0), 2.0), ((0, -0.5, 2.5), (3, 2), (1.0, 0.8, 0.9), 1.0)):
        me = bpy.data.meshes.new('Panel')
        me.from_pydata([(-size[0] / 2, -size[1] / 2, 0), (size[0] / 2, -size[1] / 2, 0), (size[0] / 2, size[1] / 2, 0),
                        (-size[0] / 2, size[1] / 2, 0)], [], [(0, 1, 2, 3)])
        p = bpy.data.objects.new('Panel', me)
        p.location = loc
        p.rotation_euler = (Vector((0, 0.45, -0.25)) - Vector(loc)).to_track_quat('Z', 'Y').to_euler()
        p.visible_camera = False
        pm = bpy.data.materials.new('PanelLight')
        pm.use_nodes = True
        pb = pm.node_tree.nodes['Principled BSDF']
        pb.inputs['Base Color'].default_value = (0, 0, 0, 1)
        pb.inputs['Emission Color'].default_value = (*colr, 1)
        pb.inputs['Emission Strength'].default_value = s
        me.materials.append(pm)
        col.objects.link(p)
    ng = bpy.data.node_groups.new('Bloom', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    glare = ng.nodes.new('CompositorNodeGlare')
    glare.inputs['Type'].default_value = 'Bloom'
    glare.inputs['Threshold'].default_value = 1.2
    glare.inputs['Strength'].default_value = 0.35
    glare.inputs['Size'].default_value = 0.5
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
    ng.links.new(glare.outputs['Image'], out.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    return col


def add_camera(col, name, loc, target, vfov=None, lens=None):
    cd = bpy.data.cameras.new(name)
    cd.clip_start = 0.01
    cd.clip_end = 100
    if vfov:
        cd.sensor_fit = 'VERTICAL'
        cd.angle_y = math.radians(vfov)
    else:
        cd.lens = lens or 50
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    col.objects.link(ob)
    return ob


def visible_count(objs, M=None):
    """Vertices of objs inside the POV frustum (camera at origin, +Y forward), after the root transform M."""
    th = math.tan(math.radians(VFOV / 2))
    tw = th * ASPECT
    n = 0
    top = -1e9
    for ob in objs:
        mw = ob.matrix_world if M is None else M @ ob.matrix_world
        for v in ob.data.vertices:
            p = mw @ v.co
            if p.y <= 0.02:
                continue
            ry, rx = p.z / p.y, p.x / p.y
            top = max(top, ry)
            if abs(ry) < th and abs(rx) < tw:
                n += 1
    return n, top


PIVOT2 = (0, -0.6, 0.0)  # recommended lowering pivot (glTF camera space)


def lowered_matrix(pivot_gl, deg):
    p = Vector(gl2b(*pivot_gl))
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, 'X') @ Matrix.Translation(-p)


def render_views(scene, root, objs):
    col = setup_render(scene)
    os.makedirs(OUT_DIR, exist_ok=True)
    suffix = f'-{TAG}' if TAG else ''
    tgt = Vector(DEV_C * 0.01)
    views = {
        'pov': (Vector((0, 0, 0)), Vector((0, 1, 0)), VFOV, None),
        'lowered': (Vector((0, 0, 0)), Vector((0, 1, 0)), VFOV, None),
        'lowered-pivot2': (Vector((0, 0, 0)), Vector((0, 1, 0)), VFOV, None),
        'side': (tgt + Vector((0.55, -0.05, 0.05)), tgt + Vector((0.06, 0, -0.03)), None, 50),
        'top': (tgt + Vector((0.0, -0.05, 0.55)), tgt + Vector((0.0, 0, -0.03)), None, 40),
        'front': (tgt + Vector((0.12, 0.55, 0.08)), tgt + Vector((0.0, 0, -0.04)), None, 45),
        'close': (Vector((0.04, 0.12, -0.12)), tgt + Vector((0.11, 0.0, -0.02)), None, 55),
        'three': (tgt + Vector((0.42, -0.38, 0.22)), tgt + Vector((0.06, 0, -0.04)), None, 50),
    }
    base = root.matrix_world.copy()
    for name in VIEWS:
        loc, look, vfov, lens = views[name]
        cam = add_camera(col, 'Cam_' + name, loc, look, vfov=vfov, lens=lens)
        scene.camera = cam
        root.matrix_world = {'lowered': lowered_matrix((0, -0.6, -0.2), -35),
                             'lowered-pivot2': lowered_matrix(PIVOT2, -35)}.get(name, base)
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(OUT_DIR, f'hands-{name}{suffix}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDER', scene.render.filepath)
    root.matrix_world = base
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    mats = make_materials()
    hand = Hand(POSE)
    bend = math.degrees(math.acos(np.clip(np.dot(-hand.v, (0, 1, 0)), -1, 1)))
    print(f'wrist bend {bend:.0f} deg, wrist world {np.round(hand.t, 2)}')
    if '--grip-only' in ARGS:
        return

    me_r = build_hand_mesh(hand, mats)
    me_l = me_r.copy()
    bake_world(me_r, hand)
    bake_world(me_l, hand, mirror=True)
    me_r.name, me_l.name = 'RightHand', 'LeftHand'

    root = bpy.data.objects.new('Hands', None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.05
    scene.collection.objects.link(root)
    wrist = hand.t * 0.01
    objs = []
    for name, me, origin in (('RightHand', me_r, wrist), ('LeftHand', me_l, wrist * np.array([-1, 1, 1]))):
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
        recentre(ob, Vector(origin))
        ob.parent = root
        objs.append(ob)
    proj, anchor_w = build_projector(mats)
    scene.collection.objects.link(proj)
    proj.parent = root
    objs.append(proj)
    anchor = bpy.data.objects.new('HologramAnchor', None)
    anchor.empty_display_type = 'ARROWS'
    anchor.empty_display_size = 0.04
    anchor.location = anchor_w
    anchor.parent = root
    scene.collection.objects.link(anchor)
    bpy.context.view_layer.update()

    # stats
    tris = 0
    for ob in objs:
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
        print(f'  {ob.name}: {len(ob.data.loop_triangles)} tris')
    inside = 0
    for ob in objs[:2]:
        co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices]) * 100.0
        inside += int((sd_bar_world(co.astype(F32)) < -0.05).sum())
    n_up, top_up = visible_count(objs)
    lows = {}
    for piv, deg in (((0, -0.6, -0.2), -35), ((0, -0.6, 0.0), -35), ((0, -0.55, 0.05), -40), ((0, -0.7, -0.1), -35)):
        n, top = visible_count(objs, lowered_matrix(piv, deg))
        lows[(piv, deg)] = (n, math.degrees(math.atan(top)))
    a_gl = (anchor_w.x, anchor_w.z, -anchor_w.y)
    print(f'TRIS {tris}; hand verts inside the bar: {inside}')
    print(f'VISIBLE raised: {n_up} verts')
    for k, (n, top) in lows.items():
        print(f'LOWERED pivot {k[0]} rot {k[1]}: {n} verts visible, topmost at {top:.1f} deg (frame edge -{VFOV / 2})')
    print('ANCHOR (glTF) ', tuple(round(c, 4) for c in a_gl))
    print('PROJECTOR (glTF)', tuple(round(c, 4) for c in (proj.location.x, proj.location.z, -proj.location.y)))
    for ob in objs[:2]:
        print(f'{ob.name} origin (glTF)', tuple(round(c, 4) for c in (ob.location.x, ob.location.z, -ob.location.y)))

    if not NO_EXPORT:
        os.makedirs(os.path.dirname(GLB_OUT), exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT')
        for ob in [root, anchor] + objs:
            ob.select_set(True)
        bpy.ops.export_scene.gltf(filepath=GLB_OUT, export_format='GLB', use_selection=True, export_apply=True,
                                  export_yup=True, export_draco_mesh_compression_enable=True,
                                  export_draco_mesh_compression_level=6, export_draco_position_quantization=14,
                                  export_draco_normal_quantization=10, export_draco_texcoord_quantization=12,
                                  export_cameras=False, export_lights=False, export_extras=False)
        print('GLB', GLB_OUT, os.path.getsize(GLB_OUT))
        bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    if DO_RENDER:
        render_views(scene, root, objs)
    print(f'done in {time.time() - t0:.0f}s')


main()
