"""The tunnel's caged green lamp, 1.3 wide: a rounded housing, saturated green face with a pale hot centre, a wire cage over it
(rim, three bowed uprights, one crossbar), lit by it. Origin at the back's centre (the wall's plane), width along X, facing +Y."""
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'light_green_cage'
W, H = 1.3, 0.96
kit = A.begin()
m = _mats.mats(kit)
BODY, GLOW, HOT, WIRE, RIM = 0, 1, 2, 3, 4
bm = bmesh.new()


def rounded(w, h, c):
    """A rectangle with its corners cut: 8 points, (x, z), going round."""
    a, b = w / 2, h / 2
    return [(-a + c, -b), (a - c, -b), (a, -b + c), (a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c)]


def ring(pts, y):
    return [bm.verts.new((x, y, z)) for x, z in pts]


def bridge(a, b, mat):
    for i in range(len(a)):
        j = (i + 1) % len(a)
        bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat


def wire(path, r=0.03, mat=WIRE):
    """A wire of triangular section, no end caps: three sides to a segment."""
    kit.sweep(bm, [Vector(p) for p in path], kit.circle_profile(r, 3), mat=mat, caps=False)


# The housing, tapering a little to the glass.
back = ring(rounded(W - 0.06, H - 0.06, 0.2), 0.0)
front = ring(rounded(W - 0.11, H - 0.11, 0.19), 0.2)
bridge(back, front, BODY)
bm.faces.new(front).material_index = GLOW
# The hot centre, off the glass, under the wires.
bm.faces.new(ring([(-0.42, -0.27), (0.42, -0.27), (0.5, 0.0), (0.42, 0.27), (-0.42, 0.27), (-0.5, 0.0)], 0.24)).material_index = HOT
# The cage: its rim outside the glass, bowed uprights across, one crossbar.
rim = rounded(W - 0.05, H - 0.06, 0.2)
wire([(x, 0.27, z) for x, z in rim + rim[:1]], mat=RIM)
b = (H - 0.06) / 2
for x in (-0.3, 0.0, 0.3):
    wire([(x, 0.27, -b + 0.03), (x, 0.36, 0.0), (x, 0.27, b - 0.03)])
wire([(-0.58, 0.3, 0.02), (0.58, 0.3, 0.02)])

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['lamp_green'], m['lamp_green_hot'], m['lamp_green'], m['lamp_wire']])
kit.box_uvs(me, 0.5)
kit.bake_light(me, [((0, 0.5, 0), (0.45, 1.0, 0.3), 1.2, 1.0)], ambient=(0.25, 0.3, 0.24))
A.obj(me)
A.finish(kit, NAME, budget=120, eye=(-0.7, 1.6, 0.35), look_at=(0, 0.1, 0))
