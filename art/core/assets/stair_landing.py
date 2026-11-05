"""stair_landing: 16 x 16 slab, 1 deep. Origin: top centre (its floor is z 0). A drain at the centre, the floor dished a touch to it and
darker with standing water; a band of worn yellow dashes round the edge. Symmetric under quarter turns, so any edge can meet a flight."""
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_landing'
H, BAND, DEPTH, DR = 8.0, 0.6, 1.0, 1.3
kit = A.begin()
m = _mats.mats(kit)
mats = [m['wet_concrete'], m['stained_concrete'], m['hazard'], m['dark'], m['rust']]
WET, STAINED, HAZ, DARK, RUST = range(5)
bm = bmesh.new()
gain = []
rng = np.random.default_rng(16)


def face(pts, mat, out, g=(1, 1, 1)):
    pts = [Vector(p) for p in pts]
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.dot(Vector(out)) < 0:
        pts.reverse()
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat
    if callable(g):
        gain.extend([g(p) for p in pts])
    else:
        gain.extend([g] * len(pts))
    return f


def floor_z(x, y):
    """The dish: 4 cm down to the drain's lip, flat from 3 m out."""
    d = max(abs(x), abs(y))
    return -0.04 * max(0.0, min(1.0, (5.0 - d) / (5.0 - DR)))


def wet_gain(p):
    """Dark where the water stands round the drain, patchy elsewhere: a function of position, so cells agree at their edges."""
    d = max(abs(p.x), abs(p.y))
    w = 0.6 + 0.4 * min(1.0, max(0.0, (d - DR) / 3.5))
    w *= 0.86 + 0.14 * np.sin(p.x * 0.9 + 1.0) * np.cos(p.y * 0.7 - 0.5)
    return (w, w, w)


# The floor, inside the band, round the drain.
L = [-H + BAND, -5.0, -3.0, -DR, DR, 3.0, 5.0, H - BAND]
for i in range(len(L) - 1):
    for j in range(len(L) - 1):
        if i == 3 and j == 3:
            continue
        x0, x1, y0, y1 = L[i], L[i + 1], L[j], L[j + 1]
        face([(x0, y0, floor_z(x0, y0)), (x1, y0, floor_z(x1, y0)), (x1, y1, floor_z(x1, y1)), (x0, y1, floor_z(x0, y1))], WET, (0, 0, 1), wet_gain)

# The band, mitred at the corners: 2 m dashes of paint on bare concrete, each worn differently.
for side in range(4):
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][side], [(0, 1), (-1, 0), (0, -1), (1, 0)][side]

    def at(a, o):
        return (c[0] * o + s[0] * a, c[1] * o + s[1] * a, 0.0)

    for k in range(8):
        a0, a1 = -H + 2 * k, -H + 2 * (k + 1)
        inner = (H - BAND) / H
        painted = k % 2 == 0
        w = float(0.6 + 0.4 * rng.random())
        face([at(a0, H), at(a1, H), at(a1 * inner, H - BAND), at(a0 * inner, H - BAND)], HAZ if painted else WET, (0, 0, 1), (w * 1.5, w * 1.5, w * 1.4) if painted else (w, w, w))
    # The slab's edge.
    for k in range(4):
        a0, a1 = -H + 4 * k, -H + 4 * (k + 1)
        face([at(a0, H), at(a1, H), (at(a1, H)[0], at(a1, H)[1], -DEPTH), (at(a0, H)[0], at(a0, H)[1], -DEPTH)], STAINED, (c[0], c[1], 0), (0.72, 0.72, 0.72))

# Underneath.
for x0, x1 in ((-H, 0), (0, H)):
    for y0, y1 in ((-H, 0), (0, H)):
        face([(x0, y0, -DEPTH), (x1, y0, -DEPTH), (x1, y1, -DEPTH), (x0, y1, -DEPTH)], STAINED, (0, 0, -1), (0.65, 0.65, 0.65))

# The drain: a square pit, its lip on the dish, black inside, four heavy bars over it.
PIT = 0.34
lip = floor_z(DR, 0)
for side in range(4):
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][side], [(0, 1), (-1, 0), (0, -1), (1, 0)][side]
    p = [(c[0] * DR + s[0] * a, c[1] * DR + s[1] * a) for a in (-DR, DR)]
    face([(*p[0], lip), (*p[1], lip), (*p[1], lip - PIT), (*p[0], lip - PIT)], DARK, (-c[0], -c[1], 0))
face([(-DR, -DR, lip - PIT), (DR, -DR, lip - PIT), (DR, DR, lip - PIT), (-DR, DR, lip - PIT)], DARK, (0, 0, 1))
for x in (-0.96, -0.32, 0.32, 0.96):
    t, w = lip - 0.02, 0.17
    face([(x - w, -DR, t), (x + w, -DR, t), (x + w, DR, t), (x - w, DR, t)], RUST, (0, 0, 1), (1.4, 1.3, 1.2))
    for s in (-1, 1):
        face([(x + s * w, -DR, t), (x + s * w, DR, t), (x + s * w, DR, lip - PIT), (x + s * w, -DR, lip - PIT)], RUST, (s, 0, 0), (0.7, 0.7, 0.7))

me = kit.mesh_from(NAME, bm, mats, smooth=False, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = []
# The red strips along the walls and rails, pooling on the wet floor: off centre on each side, turning with the slab.
for x, y in ((7.6, 3.2), (-3.2, 7.6), (-7.6, -3.2), (3.2, -7.6)):
    lights.append(((x, y, 1.1), RED, 2.2, 3.4))
# A grey wash from the ceiling lamps, and the green coming up the shaft past the slab's edge.
lights.append(((-1.0, -1.0, 8.0), (0.6, 0.74, 0.66), 7.0, 0.8))
lights.append(((5.5, -6.0, 0.6), GREEN, 3.5, 0.55))
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
A.finish(kit, NAME, budget=250, eye=(-11.5, -3.5, 3.0), look_at=(2.0, 0.5, -1.0))
