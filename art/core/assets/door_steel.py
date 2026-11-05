"""Heavy steel door and frame, 4 wide x 6 high: a thick frame standing proud of the wall, two dark recessed leaves, the left ribbed,
the right plain with a raised border, strap hinges, a lever (the image's door at the top landing). Origin at the base's centre on
the wall's plane, width along X, height along Z, facing +Y. Context wall in the still only: it isn't exported."""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'door_steel'
BUDGET = 250
W, H, D, F = 4.0, 6.0, 0.5, 0.32
LEAF_Y = 0.2
kit = A.begin()
m = _mats.mats(kit)
STEEL, DARK, METAL, PAINT = 0, 1, 2, 3
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


def block(x0, x1, y0, y1, z0, z1, mat, ends=True):
    """A box's visible faces: front, top, bottom, sides (no back, it's on what's behind it)."""
    quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], mat, (0, 1, 0))
    quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mat, (0, 0, 1))
    quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], mat, (0, 0, -1))
    if ends:
        quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], mat, (-1, 0, 0))
        quad([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], mat, (1, 0, 0))


# The frame: jambs and lintel, a threshold plate.
hw, ix, iz = W / 2, W / 2 - F, H - F
block(-hw, -ix, 0, D, 0, H, STEEL)
block(ix, hw, 0, D, 0, H, STEEL)
block(-ix, ix, 0, D, iz, H, STEEL, ends=False)
block(-ix, ix, 0, 0.3, 0, 0.1, METAL, ends=False)
# A pale worn edge on the frame's inner lip, the line that draws the door in the image.
for s in (-1, 1):
    quad([(s * ix, D + 0.006, 0), (s * (ix + 0.06), D + 0.006, 0), (s * (ix + 0.06), D + 0.006, iz + 0.06), (s * ix, D + 0.006, iz + 0.06)], PAINT, (0, 1, 0))
quad([(-ix - 0.06, D + 0.006, iz), (ix + 0.06, D + 0.006, iz), (ix + 0.06, D + 0.006, iz + 0.06), (-ix - 0.06, D + 0.006, iz + 0.06)], PAINT, (0, 1, 0))

# The leaves: viewed from +Y, +X is on the left. A black seam between them.
SEAM = 0.025
ROWS = 3
for s in (-1, 1):
    x0, x1 = (SEAM, ix) if s > 0 else (-ix, -SEAM)
    for r in range(ROWS):
        z0, z1 = 0.1 + (iz - 0.1) * r / ROWS, 0.1 + (iz - 0.1) * (r + 1) / ROWS
        quad([(x0, LEAF_Y, z0), (x1, LEAF_Y, z0), (x1, LEAF_Y, z1), (x0, LEAF_Y, z1)], STEEL, (0, 1, 0))
quad([(-SEAM, LEAF_Y - 0.02, 0.1), (SEAM, LEAF_Y - 0.02, 0.1), (SEAM, LEAF_Y - 0.02, iz), (-SEAM, LEAF_Y - 0.02, iz)], DARK, (0, 1, 0))

# The left leaf's ribs: dark bars, closely packed, top to bottom.
for i in range(17):
    z = 0.36 + i * 0.3
    block(SEAM + 0.12, ix - 0.12, LEAF_Y, LEAF_Y + 0.05, z, z + 0.14, DARK, ends=False)

# The right leaf: a raised border, a heavy lever.
x0, x1 = -ix + 0.14, -SEAM - 0.14
z0, z1 = 0.32, iz - 0.22
block(x0, x1, LEAF_Y, LEAF_Y + 0.05, z0, z0 + 0.14, METAL, ends=False)
block(x0, x1, LEAF_Y, LEAF_Y + 0.05, z1 - 0.14, z1, METAL, ends=False)
block(x0, x0 + 0.14, LEAF_Y, LEAF_Y + 0.05, z0 + 0.14, z1 - 0.14, METAL, ends=False)
block(x1 - 0.14, x1, LEAF_Y, LEAF_Y + 0.05, z0 + 0.14, z1 - 0.14, METAL, ends=False)
block(x1 - 0.46, x1 - 0.1, LEAF_Y, LEAF_Y + 0.14, 2.62, 2.74, PAINT)

# The strap hinges, across the jambs' inner faces onto the leaves.
for s in (-1, 1):
    for z in (0.9, 4.5):
        block(s * ix - 0.5 if s > 0 else s * ix, s * ix if s > 0 else s * ix + 0.5, LEAF_Y, LEAF_Y + 0.07, z, z + 0.26, METAL, ends=False)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['dark'], m['pipe_metal'], m['paint_grey']], recalc=False)
kit.box_uvs(me, 0.3)
# The landing's batten up over the door, a little green from the data window beside it, red from low down.
kit.bake_light(me, [((0, 2.2, 7.2), (0.82, 0.95, 0.76), 3.4, 1.0), ((-3.2, 2.0, 1.4), (0.25, 1.0, 0.35), 2.2, 0.35), ((2.8, 3.0, -0.4), (1.0, 0.1, 0.06), 2.8, 0.45)],
               ambient=(0.38, 0.4, 0.36))
tint(me, STEEL, (0.42, 0.52, 0.5))
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
    kit.bake_light(w, [((0, 2.2, 7.2), (0.82, 0.95, 0.76), 5.0, 0.7)], ambient=(0.48, 0.5, 0.45))
    return A.obj(w), w


tris = A._check(kit, NAME, BUDGET)
wo, wm = context_wall()
A.still(NAME, eye=(2.6, 6.2, 1.45), look_at=(0, 0.2, 3.0))
bpy.data.objects.remove(wo)
bpy.data.meshes.remove(wm)
path = A.export(NAME)
print(f'ASSET {NAME}: {tris} tris (budget {BUDGET}), {os.path.getsize(path)} bytes -> {path}')
