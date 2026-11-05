"""pipe_elbow: pipe_big_12's bore through 90 degrees. Origin on the axis at its x = 0 end, comes in along +X and bends up to +Z in
the XZ plane; the other mating face is at (2, 0, 2), facing +Z. Turn it about X to bend any way a run needs."""
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
bm = bmesh.new()
seg = 12
STUB, R = FLANGE_T, 2 - FLANGE_T  # the bend runs flange to flange: no straights, more spans for its budget
Y = Vector((0, 1, 0))

# The bent body, one smooth chain of rings.
frames = []
SPANS = 7
for k in range(SPANS + 1):
    a = math.pi / 2 * k / SPANS
    frames.append((Vector((STUB + R * math.sin(a), 0, R - R * math.cos(a))), Vector((-math.sin(a), 0, math.cos(a)))))
rings = [ring_frame(bm, c, Y, v, BORE, seg) for c, v in frames]
for a, b in zip(rings, rings[1:]):
    join(bm, a, b, mat=0)

# Flanges: the first along +X, the other turned to face +Z.
turned(bm, [(0.0, FLANGE), (FLANGE_T, FLANGE), (FLANGE_T, BORE)], seg, mat=1)
cap(bm, ring_x(bm, 0.0, FLANGE, seg), mat=1, flip=True)
V = Vector((-1, 0, 0))
e = STUB + R
for (z0, r0), (z1, r1) in [((2 - FLANGE_T, BORE), (2 - FLANGE_T, FLANGE)), ((2 - FLANGE_T, FLANGE), (2.0, FLANGE))]:
    join(bm, ring_frame(bm, Vector((e, 0, z0)), Y, V, r0, seg), ring_frame(bm, Vector((e, 0, z1)), Y, V, r1, seg), mat=1)
cap(bm, ring_frame(bm, Vector((e, 0, 2.0)), Y, V, FLANGE, seg), mat=1)

me = make(kit, 'pipe_elbow', bm, [m['pipe_metal'], m['dark']])
kit.box_uvs(me, 0.25)
lights = []
for c, _v in frames:
    lights += stair_lights([c.x], z=c.z)
kit.bake_light(me, lights, ambient=STAIR_AMBIENT)
A.obj(me)
A.finish(kit, 'pipe_elbow', budget=300, eye=(0.2, -5.0, -0.2), look_at=(1.0, 0.0, 1.0), fov=50.0)
