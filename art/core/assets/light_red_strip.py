"""The images' red wall strip: 2.8 x 0.25, dark housing, deep red glow face, pale hot core. Origin at the back's centre (the
wall's plane), long along X, facing +Y."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'light_red_strip'
kit = A.begin()
m = _mats.mats(kit)
HOUSING, GLOW, HOT = 0, 1, 2
bm = bmesh.new()


def rect(w, h, y):
    return [bm.verts.new((sx * w / 2, y, sz * h / 2)) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def bridge(a, b, mat):
    for i in range(len(a)):
        j = (i + 1) % len(a)
        bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat


# The housing: straight off the wall, a chamfered lip, then a recess for the glow.
back = rect(2.8, 0.25, 0.0)
mid = rect(2.8, 0.25, 0.05)
lip = rect(2.72, 0.21, 0.12)
recess = rect(2.6, 0.155, 0.06)
bridge(back, mid, HOUSING)
bridge(mid, lip, HOUSING)
bridge(lip, recess, HOUSING)
# The glow face fills the recess; the hot core stands off it, a long lozenge, as the images' strips burn.
bm.faces.new(recess).material_index = GLOW
core = [(-1.24, 0.0), (-1.08, -0.045), (1.08, -0.045), (1.24, 0.0), (1.08, 0.045), (-1.08, 0.045)]
bm.faces.new([bm.verts.new((x, 0.1, z)) for x, z in core]).material_index = HOT
# The clamps at its ends.
for sx in (-1, 1):
    kit.add_box(bm, (sx * 1.33, 0.075, 0), (0.14, 0.15, 0.25), mat=HOUSING)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['lamp_red'], m['lamp_red_hot']])
kit.box_uvs(me, 0.5)
kit.bake_light(me, [((0, 0.4, 0), (1.0, 0.12, 0.08), 1.6, 1.0)], ambient=(0.3, 0.28, 0.27))
A.obj(me)
A.finish(kit, NAME, budget=60, eye=(-1.1, 2.3, 0.45), look_at=(0, 0, 0))
