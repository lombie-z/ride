"""Grey wall box with conduit stubs (the one beside the image's B4 data window), 1.2 x 1.4 body: a chamfered lid, a latch, corner
screws, conduit stubs in nuts going up and down. Origin at the back's centre (the wall's plane), width along X, height along Z,
facing +Y. Context wall in the still only: it isn't exported."""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'junction_box'
BUDGET = 150
W, H, D = 1.2, 1.4, 0.5
kit = A.begin()
m = _mats.mats(kit)
GREY, METAL, DARK = 0, 1, 2
bm = bmesh.new()


def quad(pts, mat, n):
    f = kit.add_quad(bm, pts, mat)
    f.normal_update()
    if f.normal.dot(Vector(n)) < 0:
        f.normal_flip()
    return f


def band(a, b, mat):
    (ax, az, ay), (bx, bz, by) = a, b
    quad([(-ax, ay, az), (ax, ay, az), (bx, by, bz), (-bx, by, bz)], mat, (0, 1, 1))
    quad([(-ax, ay, -az), (ax, ay, -az), (bx, by, -bz), (-bx, by, -bz)], mat, (0, 1, -1))
    quad([(ax, ay, -az), (ax, ay, az), (bx, by, bz), (bx, by, -bz)], mat, (1, 1, 0))
    quad([(-ax, ay, -az), (-ax, ay, az), (-bx, by, bz), (-bx, by, -bz)], mat, (-1, 1, 0))


def stub(x, y, s, r, length, nut=True):
    """A conduit going up (s = 1) or down from the box: six sides and an end, a nut where it meets the box."""
    z0 = s * H / 2
    rings = [(r, z0, z0 + s * length)]
    if nut:
        rings.append((r * 1.45, z0, z0 + s * 0.13))
    for rr, a, b in rings:
        for i in range(6):
            a0, a1 = 2 * math.pi * i / 6, 2 * math.pi * (i + 1) / 6
            am = (a0 + a1) / 2
            quad([(x + rr * math.cos(a0), y + rr * math.sin(a0), a), (x + rr * math.cos(a1), y + rr * math.sin(a1), a),
                  (x + rr * math.cos(a1), y + rr * math.sin(a1), b), (x + rr * math.cos(a0), y + rr * math.sin(a0), b)], METAL, (math.cos(am), math.sin(am), 0))
    cap = bm.faces.new([bm.verts.new((x + r * math.cos(2 * math.pi * i / 6), y + r * math.sin(2 * math.pi * i / 6), z0 + s * length)) for i in range(6)])
    cap.material_index = DARK
    cap.normal_update()
    if cap.normal.z * s < 0:
        cap.normal_flip()


# The body: sides off the wall, a chamfer, the lid.
band((W / 2, H / 2, 0), (W / 2, H / 2, D - 0.09), GREY)
band((W / 2, H / 2, D - 0.09), (W / 2 - 0.09, H / 2 - 0.09, D), GREY)
quad([(-W / 2 + 0.09, D, -H / 2 + 0.09), (W / 2 - 0.09, D, -H / 2 + 0.09), (W / 2 - 0.09, D, H / 2 - 0.09), (-W / 2 + 0.09, D, H / 2 - 0.09)], GREY, (0, 1, 0))

# The latch, on the viewer's right (-X), and four screws.
kit.add_box(bm, (-0.36, D + 0.02, 0.0), (0.06, 0.04, 0.2), DARK)
for bx in (-0.4, 0.4):
    for bz in (-0.5, 0.5):
        x, z, a, y = bx, bz, 0.035, D
        for p, q_ in (((x - a, z - a), (x + a, z - a)), ((x + a, z - a), (x + a, z + a)), ((x + a, z + a), (x - a, z + a)), ((x - a, z + a), (x - a, z - a))):
            f = bm.faces.new([bm.verts.new((p[0], y, p[1])), bm.verts.new((q_[0], y, q_[1])), bm.verts.new((x, y + 0.03, z))])
            f.material_index = METAL
            f.normal_update()
            if f.normal.y < 0:
                f.normal_flip()

# The stubs: two up, two down, thick ones going on into the wall's bundles.
stub(0.26, 0.26, 1, 0.125, 0.6)
stub(-0.2, 0.26, 1, 0.095, 0.42)
stub(0.2, 0.26, -1, 0.125, 0.5)
stub(-0.22, 0.26, -1, 0.095, 0.34, nut=False)

me = kit.mesh_from(NAME, bm, [m['paint_grey'], m['rust'], m['dark']], recalc=False)
kit.box_uvs(me, 0.4)
# Green from the data window on the viewer's right, a little red from below.
kit.bake_light(me, [((-1.9, 0.9, 0.0), (0.25, 1.0, 0.35), 1.4, 0.8), ((0.6, 1.8, -2.2), (1.0, 0.1, 0.06), 2.4, 0.4)], ambient=(0.95, 0.96, 0.92))
A.obj(me)


def context_wall():
    b = bmesh.new()
    for i in range(30):
        for j in range(30):
            x0, x1 = -30 + 2 * i, -28 + 2 * i
            z0, z1 = -30 + 2 * j, -28 + 2 * j
            f = b.faces.new([b.verts.new(c) for c in ((x0, 0, z0), (x0, 0, z1), (x1, 0, z1), (x1, 0, z0))])
            f.material_index = 0
    w = kit.mesh_from('ContextWall', b, [m['stained_concrete']], recalc=False)
    kit.box_uvs(w, 0.25)
    kit.bake_light(w, [((-2.2, 1.0, 0.0), (0.25, 1.0, 0.35), 2.2, 0.5), ((1, 2.5, -3), (1.0, 0.1, 0.06), 3.0, 0.4)], ambient=(0.5, 0.52, 0.46))
    return A.obj(w), w


tris = A._check(kit, NAME, BUDGET)
wo, wm = context_wall()
A.still(NAME, eye=(-1.3, 2.7, -0.2), look_at=(0, 0.2, 0))
bpy.data.objects.remove(wo)
bpy.data.meshes.remove(wm)
path = A.export(NAME)
print(f'ASSET {NAME}: {tris} tris (budget {BUDGET}), {os.path.getsize(path)} bytes -> {path}')
