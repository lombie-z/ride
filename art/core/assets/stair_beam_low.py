"""stair_beam_low: a low beam across the road: 14 long along Y, 1.4 deep (z -0.7 to 0.7), origin at its centre. Concrete, a steel flange
under it (what passes over your head, so the part to see), steel straps round it, chipped lower edges."""
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_beam_low'
HL, HD = 7.0, 0.7
kit = A.begin()
m = _mats.mats(kit)
mats = [m['stained_concrete'], m['riveted_steel'], m['rust']]
CONC, STEEL, RUST = range(3)
bm = bmesh.new()
gain = []
rng = np.random.default_rng(14)


def face(pts, mat, out, g=(1, 1, 1)):
    pts = [Vector(p) for p in pts]
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.dot(Vector(out)) < 0:
        pts.reverse()
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat
    gain.extend([g] * len(pts))
    return f


def box(x0, x1, y0, y1, z0, z1, mat, g=(1, 1, 1), skip=()):
    if 'y0' not in skip:
        face([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mat, (0, -1, 0), g)
    if 'y1' not in skip:
        face([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], mat, (0, 1, 0), g)
    if 'x0' not in skip:
        face([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], mat, (-1, 0, 0), g)
    if 'x1' not in skip:
        face([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], mat, (1, 0, 0), g)
    if 'z1' not in skip:
        face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat, (0, 0, 1), g)
    if 'z0' not in skip:
        face([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], mat, (0, 0, -1), g)


# The concrete, its lower corners chipped per bay.
W, ZT, ZB, CH = 0.48, HD - 0.04, -0.55, 0.16
YS = [-HL, -4.6, -2.4, 0.0, 2.4, 4.6, HL]
chips = 1.0 + 0.9 * rng.random(len(YS))
for i in range(len(YS) - 1):
    y0, y1 = YS[i], YS[i + 1]
    c0, c1 = CH * chips[i], CH * chips[i + 1]
    tone = (0.72 + 0.4 * rng.random(),) * 3
    for s in (-1, 1):
        face([(s * W, y0, ZT), (s * W, y1, ZT), (s * W, y1, ZB + c1), (s * W, y0, ZB + c0)], CONC, (s, 0, 0), tone)
        face([(s * W, y0, ZB + c0), (s * W, y1, ZB + c1), (s * (W - c1), y1, ZB), (s * (W - c0), y0, ZB)], CONC, (s, 0, -1), (1.5, 1.5, 1.45))
    face([(-W, y0, ZT), (W, y0, ZT), (W, y1, ZT), (-W, y1, ZT)], CONC, (0, 0, 1), (0.7, 0.7, 0.7))
for y, o in ((-HL, -1), (HL, 1)):
    face([(-W, y, ZT), (W, y, ZT), (W, y, ZB), (-W, y, ZB)], CONC, (0, o, 0), (0.6, 0.6, 0.6))

# The flange under it, wider than the concrete, down to the beam's full depth.
FW = 0.64
FY = [-HL, -2.4, 2.4, HL]
for a, b in zip(FY, FY[1:]):
    box(-FW, FW, a, b, -HD, ZB, STEEL, (1.15, 1.15, 1.1), skip=('y0', 'y1') + (('z1',) if abs(a) < 3 else ()))
for y, o in ((-HL, -1), (HL, 1)):
    face([(-FW, y, -HD), (FW, y, -HD), (FW, y, ZB), (-FW, y, ZB)], STEEL, (0, o, 0))

# Three straps round it, rusting, and what they've bled down the concrete.
for y in (-4.9, 0.0, 4.9):
    box(-W - 0.05, W + 0.05, y - 0.2, y + 0.2, ZB - 0.02, ZT + 0.04, RUST, (1.4, 1.25, 1.1), skip=('z0',))

me = kit.mesh_from(NAME, bm, mats, smooth=False, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = [
    # Red from the strips on the rails below it, either side of the road, catching the soffit and the facing side.
    ((-1.2, -6.0, -2.4), RED, 2.2, 3.4),
    ((-1.2, 6.0, -2.4), RED, 2.2, 3.4),
    ((1.2, -6.0, -2.4), RED, 2.0, 1.4),
    ((1.2, 6.0, -2.4), RED, 2.0, 1.4),
    # The green of the shaft from further down.
    ((14.0, 0.0, -9.0), GREEN, 12.0, 1.0),
]
kit.bake_light(me, lights, ambient=(0.2, 0.25, 0.22))
ca = me.color_attributes['AO']
vi = np.zeros(len(me.loops), np.int64)
me.loops.foreach_get('vertex_index', vi)
cols = np.zeros(len(me.loops) * 4, np.float32)
ca.data.foreach_get('color', cols)
rgb = np.zeros((len(me.vertices), 3), np.float32)
rgb[vi] = cols.reshape(-1, 4)[:, :3]
kit.set_vcol_rgb(me, rgb * np.asarray(gain, np.float32))
A.obj(me)
# As it comes at you: the rider's eye, 1.45 over a road 5.5 under the beam's lowest point.
A.finish(kit, NAME, budget=150, eye=(-9.0, -2.0, -4.75), look_at=(0.0, 0.0, 0.0))
