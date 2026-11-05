"""stair_flight_12: 10 steps, 1.2 tread, 0.5 rise: 12 along +X, 5 down, 11.8 wide, with side stringers. Origin: the top step's
back edge, road centre, on its tread (z 0). Flights chain: the next starts at (12, 0, -5). rail_12's walking line (z = -5/12 x)
runs through the steps' inner corners, so a rail at this flight's origin, y +/-6.1, sits on the stringer as it should."""
import math
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_flight_12'
STEPS, TREAD, RISE, HALF = 10, 1.2, 0.5, 5.9
STR_OUT, STR_TOP, STR_BOT, SOFFIT = 6.3, 0.1, -1.0, -0.7  # Stringer's outer y; its top, bottom and the slab's soffit over the walking line.
LEN = STEPS * TREAD
kit = A.begin()
m = _mats.mats(kit)
mats = [m['wet_concrete'], m['stained_concrete']]
WET, STAINED = 0, 1
bm = bmesh.new()
gain = []
rng = np.random.default_rng(12)


def line(x):
    return -RISE / TREAD * x


def face(pts, mat, out, g=(1, 1, 1)):
    """One face on its own vertices (so the baked light follows its own normal), wound to face `out`."""
    pts = [Vector(p) for p in pts]
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.dot(Vector(out)) < 0:
        pts.reverse()
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat
    gain.extend([g] * len(pts))
    return f


# The steps: six columns across, each step's tread, worn nose and riser, the nose chipped differently per column.
YS = [-HALF, -4.5, -2.3, 0.0, 2.3, 4.5, HALF]
for i in range(STEPS):
    xb, xn, z = i * TREAD, (i + 1) * TREAD, -i * RISE
    ch = 0.15 + 0.13 * rng.random(len(YS))
    dz = 0.08 + 0.09 * rng.random(len(YS))
    # A few real bites out of the edge, wider toward the sides where nothing rides.
    for k in rng.choice(len(YS), 2, replace=False):
        ch[k] += 0.16
        dz[k] += 0.1
    wet = 0.6 + 0.4 * rng.random(len(YS) - 1)
    for j in range(len(YS) - 1):
        y0, y1 = YS[j], YS[j + 1]
        g = (wet[j],) * 3
        face([(xb, y0, z), (xb, y1, z), (xn - ch[j + 1], y1, z), (xn - ch[j], y0, z)], WET, (0, 0, 1), g)
        # The edge: bare, pale, where the wet's worn off.
        face([(xn - ch[j], y0, z), (xn - ch[j + 1], y1, z), (xn, y1, z - dz[j + 1]), (xn, y0, z - dz[j])], WET, (1, 0, 1), (1.75, 1.75, 1.65))
        face([(xn, y0, z - dz[j]), (xn, y1, z - dz[j + 1]), (xn, y1, z - RISE), (xn, y0, z - RISE)], STAINED, (1, 0, 0), (0.42, 0.42, 0.42))
    # The steps' ends, over the stringer's top.
    for s, idx in ((-1, 0), (1, len(YS) - 1)):
        xs = xb + STR_TOP / RISE * TREAD
        face([(xs, s * HALF, z), (xn - ch[idx], s * HALF, z), (xn, s * HALF, z - dz[idx]), (xn, s * HALF, z - RISE + STR_TOP)], STAINED, (0, s, 0), (0.5, 0.5, 0.5))

# The stringers: deep sloped beams each side, standing below the slab's soffit.
for s in (-1, 1):
    n = 6
    xs = [LEN * k / n for k in range(n + 1)]
    for a, b in zip(xs, xs[1:]):
        face([(a, s * STR_OUT, line(a) + STR_TOP), (b, s * STR_OUT, line(b) + STR_TOP), (b, s * STR_OUT, line(b) + STR_BOT), (a, s * STR_OUT, line(a) + STR_BOT)], STAINED, (0, s, 0))
    for a, b in zip(xs[::3], xs[3::3]):
        face([(a, s * HALF, line(a) + STR_TOP), (b, s * HALF, line(b) + STR_TOP), (b, s * STR_OUT, line(b) + STR_TOP), (a, s * STR_OUT, line(a) + STR_TOP)], STAINED, (1, 0, 3), (0.9, 0.9, 0.9))
        face([(a, s * HALF, line(a) + STR_BOT), (b, s * HALF, line(b) + STR_BOT), (b, s * STR_OUT, line(b) + STR_BOT), (a, s * STR_OUT, line(a) + STR_BOT)], STAINED, (-1, 0, -3), (0.6, 0.6, 0.6))
        face([(a, s * HALF, line(a) + SOFFIT), (b, s * HALF, line(b) + SOFFIT), (b, s * HALF, line(b) + STR_BOT), (a, s * HALF, line(a) + STR_BOT)], STAINED, (0, -s, 0), (0.6, 0.6, 0.6))
    for x, o in ((0.0, -1), (LEN, 1)):
        face([(x, s * HALF, line(x) + STR_TOP), (x, s * STR_OUT, line(x) + STR_TOP), (x, s * STR_OUT, line(x) + STR_BOT), (x, s * HALF, line(x) + STR_BOT)], STAINED, (o, 0, 0), (0.6, 0.6, 0.6))

# The soffit, seen from the flights below, and the slab's two ends.
for a, b in zip((0, 4, 8), (4, 8, 12)):
    for y0, y1 in ((-HALF, -2.0), (-2.0, 2.0), (2.0, HALF)):
        face([(a, y0, line(a) + SOFFIT), (a, y1, line(a) + SOFFIT), (b, y1, line(b) + SOFFIT), (b, y0, line(b) + SOFFIT)], STAINED, (-1, 0, -3), (0.7, 0.7, 0.7))
face([(0, -HALF, 0), (0, HALF, 0), (0, HALF, SOFFIT), (0, -HALF, SOFFIT)], STAINED, (-1, 0, 0), (0.6, 0.6, 0.6))
ze = -STEPS * RISE
face([(LEN, -HALF, ze), (LEN, HALF, ze), (LEN, HALF, line(LEN) + SOFFIT), (LEN, -HALF, line(LEN) + SOFFIT)], STAINED, (1, 0, 0), (0.6, 0.6, 0.6))

me = kit.mesh_from(NAME, bm, mats, smooth=False, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = []
# The red strips on the rails' lower band: one each side at the flight's upper part, one each at its lower, a flight's rhythm.
for x, s in ((2.5, 1), (9.5, 1), (2.5, -1), (9.5, -1)):
    lights.append(((x, s * 5.9, line(x) + 1.0), RED, 1.8, 3.4))
# The shaft's green coming up from below, and the grey wash from above that makes the treads read.
lights.append(((LEN + 8, 0, line(LEN) - 2.0), GREEN, 16.0, 1.3))
lights.append(((6.5, 0.8, line(6.5) + 7.0), (0.6, 0.74, 0.66), 5.5, 0.9))
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
_ = math
A.finish(kit, NAME, budget=500, eye=(-3.0, -4.2, 4.2), look_at=(7.5, 0.5, -3.2))
