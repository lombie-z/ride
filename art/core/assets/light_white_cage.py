"""The tunnel's slanted white work light, 2.4 long: a capsule of white panel in a hoop cage, on a bracket that slants its face 15
degrees down. Origin at the back's centre (the wall's plane), long along X, facing +Y and a little -Z."""
import math
import os
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'light_white_cage'
L, W = 2.4, 0.76
SLANT = math.radians(-15)
Y0 = 0.14  # The lamp's back, off the wall on its bracket, before the slant.
kit = A.begin()
m = _mats.mats(kit)
BODY, GLOW, WIRE = 0, 1, 2
bm = bmesh.new()
TILT = Matrix.Rotation(SLANT, 3, 'X')


def p(x, y, z):
    return TILT @ Vector((x, y, z))


def capsule(l, w):
    """The lamp's plan: long, with its ends cut in nearly to round."""
    a, b, c = l / 2, w / 2, w * 0.42
    return [(-a + c, -b), (a - c, -b), (a, -b + c * 0.55), (a, b - c * 0.55), (a - c, b), (-a + c, b), (-a, b - c * 0.55), (-a, -b + c * 0.55)]


def ring(pts, y):
    return [bm.verts.new(p(x, y, z)) for x, z in pts]


def bridge(a, b, mat):
    for i in range(len(a)):
        j = (i + 1) % len(a)
        bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat


def wire(path, r=0.03):
    kit.sweep(bm, [p(*q) for q in path], kit.circle_profile(r, 3), up=Vector((0, 1, 0)), mat=WIRE, caps=False)


# The bracket, the wall to the lamp's back.
kit.add_box(bm, (0, 0.11, 0.0), (0.5, 0.22, 0.3), mat=BODY)
# The lamp's body and its white face.
back = ring(capsule(L - 0.1, W - 0.08), Y0)
face = ring(capsule(L - 0.26, W - 0.2), Y0 + 0.14)
bridge(back, face, BODY)
bm.faces.new(face).material_index = GLOW
# The cage: a rim round the lamp, side rails standing off it, hoops arched over the face.
rim = capsule(L - 0.032, W - 0.04)
wire([(x, Y0 + 0.17, z) for x, z in rim + rim[:1]])
b = (W - 0.04) / 2
for sz in (-1, 1):
    wire([(-0.8, Y0 + 0.31, sz * (b - 0.02)), (0.8, Y0 + 0.31, sz * (b - 0.02))])
wire([(-0.9, Y0 + 0.33, 0), (0.9, Y0 + 0.33, 0)])
for x in (-0.72, -0.24, 0.24, 0.72):
    wire([(x, Y0 + 0.17, -b), (x, Y0 + 0.33, 0), (x, Y0 + 0.17, b)])

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['white'], m['lamp_wire']])
kit.box_uvs(me, 0.5)
kit.bake_light(me, [((0, 0.6, -0.1), (1.0, 0.98, 0.9), 1.6, 1.0)], ambient=(0.3, 0.3, 0.28))
A.obj(me)
A.finish(kit, NAME, budget=150, eye=(-1.1, 2.1, -0.75), look_at=(0, 0.2, 0))
