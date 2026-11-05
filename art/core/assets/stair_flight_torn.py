"""stair_flight_torn: the top of a flight, steps and stringers just as stair_flight_12's, torn off across the shaft. Origin: the top step's back edge,
road centre, on its tread. The break runs jagged from x 6.8 to 9.8 (the -Y side reaches furthest), the snapped slab's rebar out over the gap, a chunk hung off it.
It carries its own rail both sides (at y +/-6.1, rail_12's heights), since it has to end with the slab: the -Y one tears off the post and hangs down the gap.
Don't place rail_12 on it."""
import math
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_flight_torn'
TREAD, RISE, HALF = 1.2, 0.5, 5.9
STR_OUT, STR_TOP, STR_BOT, SOFFIT = 6.3, 0.1, -1.0, -0.7
kit = A.begin()
m = _mats.mats(kit)
mats = [m['wet_concrete'], m['stained_concrete'], m['rust'], m['riveted_steel'], m['hazard']]
WET, STAINED, RUST, STEEL, HAZ = range(5)
bm = bmesh.new()
gain = []
rng = np.random.default_rng(7)


def line(x):
    return -RISE / TREAD * x


def face(pts, mat, out, g=(1, 1, 1)):
    pts = [Vector(p) for p in pts]
    # Drop repeated corners.
    q = []
    for p in pts:
        if not q or (p - q[-1]).length > 1e-4:
            q.append(p)
    if len(q) > 1 and (q[0] - q[-1]).length < 1e-4:
        q.pop()
    if len(q) < 3:
        return None
    n = (q[1] - q[0]).cross(q[2] - q[0])
    if n.length < 1e-9 and len(q) > 3:
        n = (q[2] - q[0]).cross(q[3] - q[0])
    if n.dot(Vector(out)) < 0:
        q.reverse()
    f = bm.faces.new([bm.verts.new(p) for p in q])
    f.material_index = mat
    gain.extend([g] * len(q))
    return f


def tube(path, r, n, mat, g=(1, 1, 1), cap_end=True):
    """A bar along a path, flat-sided, on its own vertices."""
    path = [Vector(p) for p in path]
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        a = t.cross(Vector((0.13, 0.31, 0.94))).normalized()
        b = a.cross(t).normalized()
        rings.append([p + (a * math.cos(2 * math.pi * k / n) + b * math.sin(2 * math.pi * k / n)) * r for k in range(n)])
    for i in range(len(rings) - 1):
        mid = (path[i] + path[i + 1]) / 2
        for k in range(n):
            j = (k + 1) % n
            pts = [rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]]
            face(pts, mat, sum(pts, Vector()) / 4 - mid, g)
    if cap_end:
        face(rings[-1], mat, path[-1] - path[-2], g)


# The break: where the slab's top stops, by y, and how much further its underside runs (it snapped on a slant).
KNOTS = [(-HALF, 9.6), (-4.7, 8.5), (-3.4, 9.3), (-1.9, 7.5), (-0.4, 8.4), (1.2, 7.0), (2.9, 7.9), (4.4, 6.9), (HALF, 7.3)]
UNDER = [0.5, 0.2, 0.75, -0.25, 0.6, 0.15, 0.5, 0.0, 0.45]


def stop(y):
    for (y0, b0), (y1, b1) in zip(KNOTS, KNOTS[1:]):
        if y0 <= y <= y1:
            return b0 + (b1 - b0) * (y - y0) / (y1 - y0)
    return KNOTS[0][1]


def clip(poly, keep):
    """Sutherland-Hodgman against x <= stop(y), on one column (where stop is linear)."""
    out = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        ia, ib = keep(a), keep(b)
        if ia:
            out.append(a)
        if ia != ib:
            fa, fb = a[0] - stop(a[1]), b[0] - stop(b[1])
            t = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


# The steps: the sound ones in four columns as they cost nothing to see, the ones by the break in the break's own.
COARSE = [-HALF, -2.3, 0.0, 2.3, HALF]
FINE = [k[0] for k in KNOTS]
last = int(max(k[1] for k in KNOTS) / TREAD) + 1
for i in range(last):
    xb, xn, z = i * TREAD, (i + 1) * TREAD, -i * RISE
    cols = COARSE if xn < min(k[1] for k in KNOTS) - TREAD else FINE
    for j in range(len(cols) - 1):
        y0, y1 = cols[j], cols[j + 1]
        ch0, dz0 = 0.15 + 0.13 * rng.random(), 0.08 + 0.09 * rng.random()
        ch1, dz1 = 0.15 + 0.13 * rng.random(), 0.08 + 0.09 * rng.random()
        wet = float(0.6 + 0.4 * rng.random())
        tread = [(xb, y0), (xb, y1), (xn - ch1, y1), (xn - ch0, y0)]
        keep = (lambda p: p[0] <= stop(p[1]) + 1e-6)
        kept = clip(tread, keep) if cols is FINE else tread
        if len(kept) >= 3:
            face([(a, b, z) for a, b in kept], WET, (0, 0, 1), (wet,) * 3)
        # Nose and riser only where the whole column still stands at this step.
        if stop(y0) >= xn and stop(y1) >= xn:
            face([(xn - ch0, y0, z), (xn - ch1, y1, z), (xn, y1, z - dz1), (xn, y0, z - dz0)], WET, (1, 0, 1), (1.75, 1.75, 1.65))
            face([(xn, y0, z - dz0), (xn, y1, z - dz1), (xn, y1, z - RISE), (xn, y0, z - RISE)], STAINED, (1, 0, 0), (0.42, 0.42, 0.42))
    for s in (-1, 1):
        lim = stop(s * HALF)
        if xn - 0.05 <= lim:
            xs = xb + STR_TOP / RISE * TREAD
            face([(xs, s * HALF, z), (xn, s * HALF, z), (xn, s * HALF, z - RISE + STR_TOP)], STAINED, (0, s, 0), (0.5, 0.5, 0.5))


def tread_z(x):
    return -math.floor(max(x, 0.0) / TREAD) * RISE


# The snapped face, in two rows: from the top's edge in, out to a jutting middle, back to the soffit's edge. This is the piece's bright, raw thing.
tops, mids, bots = [], [], []
for (y, b), u in zip(KNOTS, UNDER):
    tops.append((b, y, tread_z(b) - 0.02))
    bx = b + u
    mids.append((b + u * 0.5 + rng.uniform(-0.35, 0.35), y + rng.uniform(-0.1, 0.1), (tread_z(b) + line(bx) + SOFFIT) / 2))
    bots.append((bx, y, line(bx) + SOFFIT))
for j in range(len(KNOTS) - 1):
    tone = float(1.3 + 0.5 * rng.random())
    face([tops[j], tops[j + 1], mids[j + 1], mids[j]], STAINED, (1, 0, 0.4), (tone, tone, tone * 0.95))
    face([mids[j], mids[j + 1], bots[j + 1], bots[j]], STAINED, (1, 0, -0.4), (tone * 0.75, tone * 0.72, tone * 0.68))
    # The soffit, from the top to the torn edge.
    for a0, a1, frac0, frac1 in ((0.0, 0.0, 0.0, 0.55), (0.0, 0.0, 0.55, 1.0)):
        p = lambda f, b, y: (b * f, y, line(b * f) + SOFFIT)
        y0, y1, b0, b1 = bots[j][1], bots[j + 1][1], bots[j][0], bots[j + 1][0]
        face([p(frac0, b0, y0), p(frac0, b1, y1), p(frac1, b1, y1), p(frac1, b0, y0)], STAINED, (-1, 0, -3), (0.62, 0.62, 0.62))
face([(0, -HALF, 0), (0, HALF, 0), (0, HALF, SOFFIT), (0, -HALF, SOFFIT)], STAINED, (-1, 0, 0), (0.6, 0.6, 0.6))

# The stringers, snapped at different lengths: the -Y one reaches past the slab, the +Y one's short.
for s, end, lean in ((-1, 10.2, -0.5), (1, 7.5, 0.55)):
    n = 4
    xs = [end * k / n for k in range(n + 1)]
    tip = end + lean
    for a, b in zip(xs, xs[1:]):
        bb = b if b < end - 1e-6 else tip
        face([(a, s * STR_OUT, line(a) + STR_TOP), (b, s * STR_OUT, line(b) + STR_TOP), (bb, s * STR_OUT, line(bb) + STR_BOT), (a, s * STR_OUT, line(a) + STR_BOT)], STAINED, (0, s, 0))
    a, b = 0.0, end
    face([(a, s * HALF, line(a) + STR_TOP), (b, s * HALF, line(b) + STR_TOP), (b, s * STR_OUT, line(b) + STR_TOP), (a, s * STR_OUT, line(a) + STR_TOP)], STAINED, (1, 0, 3), (0.9, 0.9, 0.9))
    face([(a, s * HALF, line(a) + STR_BOT), (tip, s * HALF, line(tip) + STR_BOT), (tip, s * STR_OUT, line(tip) + STR_BOT), (a, s * STR_OUT, line(a) + STR_BOT)], STAINED, (-1, 0, -3), (0.6, 0.6, 0.6))
    # Its inner side, wherever the steps don't hide it: past the break, the lot.
    stopx = min(stop(s * HALF), end)
    face([(stopx, s * HALF, line(stopx) + STR_TOP), (b, s * HALF, line(b) + STR_TOP), (tip, s * HALF, line(tip) + STR_BOT), (stopx, s * HALF, line(stopx) + STR_BOT)], STAINED, (0, -s, 0), (0.6, 0.6, 0.6))
    face([(0, s * HALF, line(0) + SOFFIT), (stopx, s * HALF, line(stopx) + SOFFIT), (stopx, s * HALF, line(stopx) + STR_BOT), (0, s * HALF, line(0) + STR_BOT)], STAINED, (0, -s, 0), (0.6, 0.6, 0.6))
    # The torn end: a raw slant.
    mid = (end + tip) / 2 + 0.3
    midz = line(end) + (STR_TOP + STR_BOT) / 2 + 0.1
    face([(end, s * HALF, line(end) + STR_TOP), (end, s * STR_OUT, line(end) + STR_TOP), (mid, s * STR_OUT, midz), (mid, s * HALF, midz)], STAINED, (1, 0, 0.3), (1.5, 1.5, 1.4))
    face([(mid, s * HALF, midz), (mid, s * STR_OUT, midz), (tip, s * STR_OUT, line(tip) + STR_BOT), (tip, s * HALF, line(tip) + STR_BOT)], STAINED, (1, 0, -0.3), (1.2, 1.2, 1.1))

# The rebar: out of the snapped face in pairs, along the slab, then bent down by its own weight. Bold enough for the scene's pixel.
for k, (y, b) in enumerate(KNOTS[1:-1]):
    for row, dz in enumerate((0.34, 0.58)):
        if (k + row) % 3 == 2:
            continue
        y0 = y + rng.uniform(-0.28, 0.28)
        x0 = stop(y0) - 0.1
        z0 = tread_z(x0) - dz
        reach = rng.uniform(0.9, 2.5)
        droop = rng.uniform(0.25, 1.2)
        sway = rng.uniform(-0.4, 0.4)
        p0 = (x0, y0, z0)
        # The top mat's bars were bent up as the slab went, so they stand against the shaft from the rider's side; the bottom mat's hang.
        up = 1.0 if row == 0 else -1.0
        p1 = (x0 + reach * 0.55, y0 + sway * 0.3, z0 + up * 0.12 - 0.12)
        p2 = (x0 + reach * 0.95, y0 + sway * 0.7, z0 + up * droop * 0.45 - 0.12)
        p3 = (x0 + reach * 1.08, y0 + sway, z0 + up * droop * 1.2 - 0.12)
        tube([p0, p1, p2, p3], 0.07, 3, RUST, (1.7, 1.45, 1.2))

# A slab of it, hanging off the rebar below the break.
CX, CY, CZ = 9.1, 2.0, -5.0
corners = [(-1.0, -1.1, 0.15), (0.9, -0.9, 0.6), (1.1, 1.2, 0.3), (-0.8, 1.0, -0.05), (-0.75, -0.8, -0.5), (0.7, -0.7, -0.1), (0.85, 0.9, -0.35), (-0.6, 0.8, -0.7)]
cw = [(CX + a, CY + b, CZ + c) for a, b, c in corners]
for idx, out, g in (((0, 1, 2, 3), (0.2, 0, 1), 1.0), ((4, 5, 6, 7), (0, 0, -1), 0.6), ((0, 1, 5, 4), (0, -1, 0), 0.8), ((1, 2, 6, 5), (1, 0, 0), 1.5), ((2, 3, 7, 6), (0, 1, 0), 0.8), ((3, 0, 4, 7), (-1, 0, 0), 0.8)):
    face([cw[i] for i in idx], STAINED if idx != (0, 1, 2, 3) else WET, out, (g, g, g))
for (ax, ay, az), (bx, by) in (((8.4, 1.1, -4.0), (8.7, 1.4)), ((8.2, 2.5, -4.0), (8.6, 2.5)), ((8.7, 3.0, -3.9), (9.5, 2.9))):
    tube([(ax, ay, az), (ax + 0.2, (ay + by) / 2, az - 0.45), (bx, by, CZ + 0.1)], 0.07, 3, RUST, (1.6, 1.35, 1.1))

# The rails.
RAIL_Y = 6.1
HANDRAIL = 1.1
R = 0.085


def post(x, s, top_x=None, top_y=None, top_z=None, foot=None):
    fx, fz = (x, line(x) + STR_TOP) if foot is None else foot
    tx = x if top_x is None else top_x
    ty = s * RAIL_Y if top_y is None else top_y
    tz = line(x) + HANDRAIL if top_z is None else top_z
    tube([(fx, s * RAIL_Y, fz), (tx, ty, tz)], 0.075, 4, STEEL, (1.1, 1.1, 1.05), cap_end=False)


# +Y: sound along the short stringer, snapped at the end post with its tip kicked out over the shaft.
X_END = 7.0
ht = lambda x: line(x) + HANDRAIL
tube([(0.0, RAIL_Y, ht(0.0)), (3.6, RAIL_Y, ht(3.6)), (X_END, RAIL_Y, ht(X_END)), (8.0, RAIL_Y + 0.9, ht(X_END) - 0.75)], R, 6, STEEL, (1.2, 1.2, 1.15))
for x in (1.0, 2.8, 4.6, 6.4):
    post(x, 1)
tube([(0.0, RAIL_Y, line(0) + 0.63), (X_END - 0.2, RAIL_Y, line(X_END - 0.2) + 0.63)], 0.05, 4, STEEL, (1.1, 1.1, 1.05))

# -Y: the long one runs past the break, then lets go, its length hanging down the gap with two posts still on it.
XR = 9.4
hang = [(0.0, -RAIL_Y, ht(0.0)), (4.6, -RAIL_Y, ht(4.6)), (XR, -RAIL_Y, ht(XR)), (10.6, -RAIL_Y - 0.15, ht(XR) - 0.5), (11.25, -RAIL_Y - 0.35, ht(XR) - 2.0), (11.1, -RAIL_Y - 0.25, ht(XR) - 4.2), (11.55, -RAIL_Y + 0.2, ht(XR) - 6.2)]
tube(hang, R, 6, STEEL, (1.2, 1.2, 1.15))
for x in (1.0, 2.8, 4.6, 6.4, 8.2):
    post(x, -1)
tube([(0.0, -RAIL_Y, line(0) + 0.63), (8.5, -RAIL_Y, line(8.5) + 0.63), (9.6, -RAIL_Y - 0.1, line(8.5) + 0.2), (9.9, -RAIL_Y - 0.1, line(8.5) - 1.4)], 0.05, 4, STEEL, (1.1, 1.1, 1.05))
# The hanging length's posts, swinging free off it.
for (ax, az), (bx, bz) in (((11.2, ht(XR) - 2.6), (11.95, ht(XR) - 3.1)), ((11.25, ht(XR) - 4.8), (10.75, ht(XR) - 5.5))):
    tube([(ax, -RAIL_Y - 0.28, az), (bx, -RAIL_Y - 0.2, bz)], 0.07, 4, STEEL, (1.1, 1.1, 1.05))

# The kick plates, up to the break, their tops painted.
for s, xe in ((1, 6.9), (-1, 9.2)):
    T = 0.055
    y0, y1 = s * RAIL_Y - T, s * RAIL_Y + T
    a, b = 0.0, xe
    for y, o in ((y0, -1), (y1, 1)):
        face([(a, y, line(a) + 0.32), (b, y, line(b) + 0.32), (b, y, line(b) - 0.2), (a, y, line(a) - 0.2)], RUST, (0, o, 0), (1.05, 1.0, 0.95))
    face([(a, y0, line(a) + 0.32), (b, y0, line(b) + 0.32), (b, y1, line(b) + 0.32), (a, y1, line(a) + 0.32)], HAZ, (1, 0, 3), (1.3, 1.3, 1.2))

me = kit.mesh_from(NAME, bm, mats, smooth=False, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = [
    ((2.5, 5.9, line(2.5) + 1.0), RED, 1.8, 3.4),
    ((2.5, -5.9, line(2.5) + 1.0), RED, 1.8, 3.4),
    ((7.5, -6.5, line(7.5) + 1.0), RED, 2.0, 3.4),
    # The shaft's green, up through the gap at the raw edge and everything hanging in it.
    ((13.0, 0.0, -9.0), (0.42, 0.85, 0.5), 11.0, 0.8),
    ((4.0, 0.8, line(4.0) + 7.0), (0.6, 0.74, 0.66), 5.5, 0.9),
]
kit.bake_light(me, lights, ambient=(0.12, 0.16, 0.145))
ca = me.color_attributes['AO']
vi = np.zeros(len(me.loops), np.int64)
me.loops.foreach_get('vertex_index', vi)
cols = np.zeros(len(me.loops) * 4, np.float32)
ca.data.foreach_get('color', cols)
rgb = np.zeros((len(me.vertices), 3), np.float32)
rgb[vi] = cols.reshape(-1, 4)[:, :3]
kit.set_vcol_rgb(me, rgb * np.asarray(gain, np.float32))
A.obj(me)
A.finish(kit, NAME, budget=900, eye=(18.0, -8.0, -6.0), look_at=(8.5, -1.0, -5.0))
