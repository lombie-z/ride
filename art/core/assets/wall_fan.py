"""Wall vent fan, 4 across, in a square steel housing: round bore, dark blades, a guard of pale struts and rings, a hub, corner
bolts (the image's fan by the top landing). Origin at the back's centre (the wall's plane), width along X, facing +Y. Context
wall in the still only: it isn't exported."""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'wall_fan'
BUDGET = 400
S, D, R = 4.0, 0.8, 1.72
kit = A.begin()
m = _mats.mats(kit)
STEEL, DARK, METAL, PAINT, RING = 0, 1, 2, 3, 4
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


def polar(r, a, y):
    return (r * math.cos(a), y, r * math.sin(a))


# The housing: sides, a chamfer, the front plate from its square edge in to the round bore, the bore going back.
h, c = S / 2, 0.08
for s in (-1, 1):
    quad([(s * h, 0, -h), (s * h, 0, h), (s * h, D - c, h), (s * h, D - c, -h)], STEEL, (s, 0, 0))
    quad([(-h, 0, s * h), (h, 0, s * h), (h, D - c, s * h), (-h, D - c, s * h)], STEEL, (0, 0, s))
    quad([(s * h, D - c, -h), (s * h, D - c, h), (s * (h - c), D, h - c), (s * (h - c), D, -h + c)], STEEL, (s, 1, 0))
    quad([(-h, D - c, s * h), (h, D - c, s * h), (h - c, D, s * (h - c)), (-h + c, D, s * (h - c))], STEEL, (0, 1, s))
N = 24
BACK_Y = 0.12
for i in range(N):
    a0 = math.pi / 4 + 2 * math.pi * i / N
    a1 = math.pi / 4 + 2 * math.pi * (i + 1) / N

    def edge(a):
        k = (h - c) / max(abs(math.cos(a)), abs(math.sin(a)))
        return (k * math.cos(a), D, k * math.sin(a))

    quad([edge(a0), edge(a1), polar(R, a1, D), polar(R, a0, D)], STEEL, (0, 1, 0))
    am = (a0 + a1) / 2
    quad([polar(R, a0, D), polar(R, a1, D), polar(R, a1, BACK_Y), polar(R, a0, BACK_Y)], DARK, (-math.cos(am), 0, -math.sin(am)))
disc = bm.faces.new([bm.verts.new(polar(R, 2 * math.pi * i / N, BACK_Y)) for i in range(N)])
disc.material_index = DARK
disc.normal_update()
if disc.normal.y < 0:
    disc.normal_flip()

# The guard: eight struts, three rings.
GY = 0.68
for i in range(8):
    a = 2 * math.pi * i / 8 + math.pi / 8
    t = Vector((-math.sin(a), 0, math.cos(a))) * 0.05
    p0, p1 = Vector(polar(0.3, a, GY)), Vector(polar(R + 0.02, a, GY))
    b = Vector((0, -0.09, 0))
    quad([p0 - t, p1 - t, p1 + t, p0 + t], PAINT, (0, 1, 0))
    quad([p0 - t, p1 - t, p1 - t + b, p0 - t + b], PAINT, -t)
    quad([p0 + t, p1 + t, p1 + t + b, p0 + t + b], PAINT, t)
M = 24
for r in (0.68, 1.08, 1.46):
    for i in range(M):
        a0, a1 = 2 * math.pi * i / M, 2 * math.pi * (i + 1) / M
        quad([polar(r - 0.035, a0, GY - 0.03), polar(r - 0.035, a1, GY - 0.03), polar(r + 0.035, a1, GY - 0.03), polar(r + 0.035, a0, GY - 0.03)], RING, (0, 1, 0))

# The hub.
K = 8
for i in range(K):
    a0, a1 = 2 * math.pi * i / K, 2 * math.pi * (i + 1) / K
    am = (a0 + a1) / 2
    quad([polar(0.32, a0, 0.28), polar(0.32, a1, 0.28), polar(0.24, a1, GY + 0.04), polar(0.24, a0, GY + 0.04)], PAINT, (math.cos(am), 0.3, math.sin(am)))
cap = bm.faces.new([bm.verts.new(polar(0.24, 2 * math.pi * i / K, GY + 0.04)) for i in range(K)])
cap.material_index = PAINT
cap.normal_update()
if cap.normal.y < 0:
    cap.normal_flip()

# The corner bolts.
for bx in (-1.72, 1.72):
    for bz in (-1.72, 1.72):
        kit.add_box(bm, (bx, D + 0.03, bz), (0.16, 0.06, 0.16), METAL)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['dark'], m['pipe_metal'], m['paint_grey'], m['stained_concrete']], recalc=False)
kit.box_uvs(me, 0.3)
kit.bake_light(me, [((1.6, 3.0, -2.6), (1.0, 0.1, 0.06), 3.6, 0.7), ((-2.5, 3.0, 2.8), (0.75, 0.9, 0.7), 4.0, 0.3)], ambient=(0.56, 0.58, 0.54))
tint(me, STEEL, (0.55, 0.72, 0.68))
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
    kit.bake_light(w, [((2.5, 3, -4), (1.0, 0.1, 0.06), 5.0, 0.5)], ambient=(0.52, 0.53, 0.48))
    return A.obj(w), w


tris = A._check(kit, NAME, BUDGET)
wo, wm = context_wall()
A.still(NAME, eye=(1.8, 4.6, 0.6), look_at=(0, 0.3, 0))
bpy.data.objects.remove(wo)
bpy.data.meshes.remove(wm)
path = A.export(NAME)
print(f'ASSET {NAME}: {tris} tris (budget {BUDGET}), {os.path.getsize(path)} bytes -> {path}')
