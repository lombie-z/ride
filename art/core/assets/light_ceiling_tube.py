"""The fluorescent batten at the stair's top, 3 long: a dark trough on two hangers, twin white tubes under it, clips and straps,
a thin rail each side. Origin at the top's centre (the ceiling's plane), long along X, hanging down -Z."""
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'light_ceiling_tube'
L = 3.0
kit = A.begin()
m = _mats.mats(kit)
BODY, GLOW, TRIM = 0, 1, 2
bm = bmesh.new()


def open_box(c, size, mat, drop=()):
    """A box without the faces whose normals are in `drop` (what nobody sees): fewer triangles."""
    faces = kit.add_box(bm, c, size, mat=mat)
    for f in list(faces):
        f.normal_update()
        if any(f.normal.dot(Vector(d)) > 0.9 for d in drop):
            bmesh.ops.delete(bm, geom=[f], context='FACES_ONLY')


# Two hangers, the ceiling down to the trough.
for x in (-0.95, 0.95):
    open_box((x, 0, -0.07), (0.08, 0.08, 0.14), BODY, drop=((0, 0, 1), (0, 0, -1)))
# The trough.
open_box((0, 0, -0.2), (L, 0.5, 0.12), BODY, drop=((0, 0, 1),))
# The twin tubes (square in section, corner down, so they catch the eye as round at the scene's pixel).
for y in (-0.14, 0.14):
    kit.sweep(bm, [Vector((-L / 2 + 0.14, y, -0.34)), Vector((L / 2 - 0.14, y, -0.34))], kit.circle_profile(0.062, 4), mat=GLOW, caps=False)
# The end clips and two straps under the tubes.
for sx in (-1, 1):
    open_box((sx * (L / 2 - 0.09), 0, -0.32), (0.18, 0.5, 0.16), BODY, drop=((0, 0, 1),))
    open_box((sx * 0.4, 0, -0.41), (0.08, 0.46, 0.035), TRIM, drop=((0, 0, 1),))
# The thin rails along its sides.
for sy in (-1, 1):
    kit.sweep(bm, [Vector((-L / 2, sy * 0.3, -0.3)), Vector((L / 2, sy * 0.3, -0.3))], kit.circle_profile(0.025, 3), mat=TRIM, caps=False)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['white'], m['lamp_wire']])
kit.box_uvs(me, 0.5)
kit.bake_light(me, [((0, 0, -0.75), (1.0, 1.0, 0.95), 1.6, 1.1)], ambient=(0.25, 0.26, 0.24))
A.obj(me)
A.finish(kit, NAME, budget=100, eye=(-0.9, 1.9, -2.4), look_at=(0, 0, -0.25))
