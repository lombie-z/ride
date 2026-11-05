"""pipe_valve: a big handwheel valve in pipe_big_12's bore. Origin at the valve's centre on the pipe's axis: the pipe runs x -1.5..+1.5
along +X (flanged to mate with a run at each end), the stem and wheel stand out toward +Y (the wheel's face at y 2.3)."""
import math
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from pipe_big_12 import BORE, FLANGE, FLANGE_T, STAIR_AMBIENT, cap, join, make, ring_frame, ring_x, stair_lights, turned  # noqa: E402

kit = A.begin()
m = _mats.mats(kit)
RUST, DARK, BRASS = 0, 1, 2
bm = bmesh.new()
seg = 12
E = 1.5
BODY = 1.0

# The pipe through it, swelling to the valve's body.
turned(bm, [(-E, FLANGE), (-E + FLANGE_T, FLANGE), (-E + FLANGE_T, BORE)], seg, mat=DARK)
turned(bm, [(E - FLANGE_T, BORE), (E - FLANGE_T, FLANGE), (E, FLANGE)], seg, mat=DARK)
cap(bm, ring_x(bm, -E, FLANGE, seg), DARK, flip=True)
cap(bm, ring_x(bm, E, FLANGE, seg), DARK)
turned(bm, [(-E + FLANGE_T, BORE), (-0.72, BORE), (-0.45, BODY), (0.45, BODY), (0.72, BORE), (E - FLANGE_T, BORE)], seg, mat=RUST)

# Up the stem, along +Y: u x v = +Y with u = Z, v = X.
U, V, Y = Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, 1, 0))


def up(profile, sides, mat):
    for (y0, r0), (y1, r1) in zip(profile, profile[1:]):
        join(bm, ring_frame(bm, Y * y0, U, V, r0, sides), ring_frame(bm, Y * y1, U, V, r1, sides), mat)


up([(0.8, 0.56), (1.45, 0.42)], 8, RUST)
up([(1.45, 0.42), (1.45, 0.62), (1.62, 0.62)], 8, DARK)
bm.faces.new(ring_frame(bm, Y * 1.62, U, V, 0.62, 8)).material_index = DARK
up([(1.62, 0.1), (2.2, 0.1)], 3, RUST)
up([(2.1, 0.2), (2.34, 0.2)], 5, BRASS)
bm.faces.new(ring_frame(bm, Y * 2.34, U, V, 0.2, 5)).material_index = BRASS

# The handwheel: a rim round the stem at y 2.22, three spokes.
RIM, TUBE, RS, TS = 0.95, 0.09, 12, 3
rings = []
for i in range(RS):
    a = 2 * math.pi * i / RS
    n = U * math.cos(a) + V * math.sin(a)
    t = (-U * math.sin(a) + V * math.cos(a))
    # This ring's around the rim's own tangent: u x v = t, with u = n and v = t x n.
    rings.append(ring_frame(bm, Y * 2.22 + n * RIM, n, t.cross(n), TUBE, TS, phase=0.5))
for i in range(RS):
    join(bm, rings[i], rings[(i + 1) % RS], BRASS)
for k in range(3):
    a = 2 * math.pi * k / 3 + 0.5
    n = U * math.cos(a) + V * math.sin(a)
    side = n.cross(Y)
    # Three long faces, no ends: buried in the hub and the rim.
    pts = [Y * 2.22 + n * 0.15, Y * 2.22 + n * (RIM - 0.03)]
    rs = [[bm.verts.new(p + side * dx + Y * dy) for dx, dy in ((0.06, 0.05), (-0.06, 0.05), (0.0, -0.06))] for p in pts]
    for i in range(3):
        j = (i + 1) % 3
        f = bm.faces.new((rs[0][i], rs[0][j], rs[1][j], rs[1][i]))
        f.material_index = BRASS
        f.smooth = False

me = make(kit, 'pipe_valve', bm, [m['pipe_metal'], m['dark'], m['hazard']])
kit.box_uvs(me, 0.25)
lights = stair_lights((-E, -0.7, 0.0, 0.7, E)) + [((0.0, 3.4, 2.0), (0.9, 1.0, 0.85), 2.2, 1.4), ((0.0, 3.4, -1.6), (1.0, 0.1, 0.05), 2.4, 1.6)]
kit.bake_light(me, lights, ambient=STAIR_AMBIENT)
A.obj(me)
A.finish(kit, 'pipe_valve', budget=400, eye=(-3.2, 5.0, -0.8), look_at=(0.0, 0.9, 0.0), fov=50.0)
