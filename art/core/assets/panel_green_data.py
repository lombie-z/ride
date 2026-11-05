"""The images' green data window, 2 x 2.6: a deep tapered steel box on the wall, four panes of terminal text behind a cross
mullion, the green spilling on its reveal. Origin at the back's centre (the wall's plane), width along X, height along Z,
facing +Y. Context wall in the still only: it isn't exported."""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'panel_green_data'
W, H, D = 2.0, 2.6, 0.62
kit = A.begin()
m = _mats.mats(kit)
STEEL, DARK, SCREEN, PAINT = 0, 1, 2, 3
bm = bmesh.new()


def tint(me, mat, rgb):
    """Darkens and cools a material's baked colour on this mesh: the steel's rust held back to the images' dark steel."""
    ca = me.color_attributes['AO']
    for p in me.polygons:
        if p.material_index == mat:
            for li in p.loop_indices:
                c = ca.data[li].color
                ca.data[li].color = (c[0] * rgb[0], c[1] * rgb[1], c[2] * rgb[2], 1.0)


def quad(pts, mat, n):
    f = kit.add_quad(bm, pts, mat)
    f.normal_update()
    if f.normal.dot(Vector(n)) < 0:
        f.normal_flip()
    return f


def band(a, b, mat, s=1):
    """Four quads between two rectangles, each (half width, half height, y); s = 1 facing out, -1 into the box."""
    (ax, az, ay), (bx, bz, by) = a, b
    quad([(-ax, ay, az), (ax, ay, az), (bx, by, bz), (-bx, by, bz)], mat, (0, 1, s))
    quad([(-ax, ay, -az), (ax, ay, -az), (bx, by, -bz), (-bx, by, -bz)], mat, (0, 1, -s))
    quad([(ax, ay, -az), (ax, ay, az), (bx, by, bz), (bx, by, -bz)], mat, (s, 1, 0))
    quad([(-ax, ay, -az), (-ax, ay, az), (-bx, by, bz), (-bx, by, -bz)], mat, (-s, 1, 0))


# The box: a flange on the wall, sides tapering to the front, a broad rim, the reveal going back to the glass.
OP_X, OP_Z, GLASS_Y = 0.74, 1.04, 0.36
band((W / 2, H / 2, 0.0), (W / 2, H / 2, 0.07), STEEL)
band((W / 2, H / 2, 0.07), (0.9, 1.2, D), STEEL)
band((0.9, 1.2, D), (OP_X, OP_Z, D), STEEL)
band((OP_X, OP_Z, D), (OP_X, OP_Z, GLASS_Y), PAINT, -1)
quad([(-OP_X, GLASS_Y, -OP_Z), (OP_X, GLASS_Y, -OP_Z), (OP_X, GLASS_Y, OP_Z), (-OP_X, GLASS_Y, OP_Z)], DARK, (0, 1, 0))

# The panes: two by two, a window of the terminal's text on each.
GAP = 0.055
PANES = []
for sx in (-1, 1):
    for sz in (-1, 1):
        x0, x1 = (GAP, OP_X - 0.03) if sx > 0 else (-OP_X + 0.03, -GAP)
        z0, z1 = (GAP, OP_Z - 0.03) if sz > 0 else (-OP_Z + 0.03, -GAP)
        y = GLASS_Y + 0.012
        quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], SCREEN, (0, 1, 0))
        PANES.append((x0, x1, z0, z1))

# The cross mullion and the rim's four corner bolts.
kit.add_box(bm, (0, GLASS_Y + 0.06, 0), (GAP * 2, 0.12, OP_Z * 2 - 0.02), STEEL)
kit.add_box(bm, (0, GLASS_Y + 0.05, 0), (OP_X * 2 - 0.02, 0.1, GAP * 2), STEEL)
for bx in (-0.82, 0.82):
    for bz in (-1.12, 1.12):
        kit.add_box(bm, (bx, D + 0.012, bz), (0.07, 0.03, 0.07), DARK)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['dark'], m['screen'], m['paint_grey']], recalc=False)
kit.box_uvs(me, 0.45)
# The screen's UVs: each pane its own window on the text (viewed from +Y, +X is on the left, so u runs against x).
WINDOWS = {(1, 1): (0.03, 0.02), (-1, 1): (0.1, 0.42), (1, -1): (0.12, 0.55), (-1, -1): (0.03, 0.28)}
uv = me.uv_layers['UVMap']
for p in me.polygons:
    if p.material_index != SCREEN:
        continue
    c = p.center
    x0, x1, z0, z1 = next(q for q in PANES if q[0] <= c.x <= q[1] and q[2] <= c.z <= q[3])
    u0, v0 = WINDOWS[(1 if c.x > 0 else -1, 1 if c.z > 0 else -1)]
    for li in p.loop_indices:
        co = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = (u0 + (x1 - co.x) / (x1 - x0) * 0.68, v0 + (co.z - z0) / (z1 - z0) * 2.0)
kit.bake_light(me, [((0, 0.72, 0), (0.25, 1.0, 0.35), 1.15, 1.1), ((0.9, 2.5, -2.4), (1.0, 0.1, 0.06), 3.2, 0.35)], ambient=(0.42, 0.45, 0.4))
tint(me, STEEL, (0.62, 0.8, 0.72))
tint(me, PAINT, (0.34, 0.8, 0.42))
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
    kit.bake_light(w, [((0, 1.2, 0), (0.25, 1.0, 0.35), 2.6, 0.45), ((1.5, 3, -3), (1.0, 0.1, 0.06), 4.0, 0.4)], ambient=(0.52, 0.53, 0.48))
    return A.obj(w), w


tris = A._check(kit, NAME, 120)
wo, wm = context_wall()
A.still(NAME, eye=(2.3, 2.9, -0.7), look_at=(0, 0.2, 0))
bpy.data.objects.remove(wo)
bpy.data.meshes.remove(wm)
path = A.export(NAME)
print(f'ASSET {NAME}: {tris} tris (budget 120), {os.path.getsize(path)} bytes -> {path}')
