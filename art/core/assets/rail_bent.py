"""rail_bent: a landing rail wrecked and bent out over the shaft. Origin: its sound end, on the floor, the rail's centre at y 0,
the same section as rail_flat_16 so it butts on one at x 0. It runs along +X and tears away toward +Y, down into the shaft
(for the other side, mirror y). About 7.4 along, 7.8 out, z 2.6 at its height, -0.8 at the lowest tip."""
import os
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'rail_bent'
H = 1.1
kit = A.begin()
m = _mats.mats(kit)
mats = [m['riveted_steel'], m['rust'], m['hazard']]
STEEL, RUST, HAZ = 0, 1, 2
bm = bmesh.new()
UP = Vector((0, 0, 1))


def sweep(points, profile, mat, edge_mats=None):
    """A closed (lateral, up) section along a path; returns the faces of its length (not its caps)."""
    path = [Vector(p) for p in points]
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        side = t.cross(UP).normalized()
        u = side.cross(t).normalized()
        rings.append([bm.verts.new(p + side * a + u * b) for a, b in profile])
    n = len(profile)
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            f = bm.faces.new((a[k], a[j], b[j], b[k]))
            f.material_index = edge_mats[k] if edge_mats else mat
            faces.append(f)
    for r in (rings[0], rings[-1]):
        bm.faces.new(r).material_index = mat
    return faces


def post(base, top, w=0.11):
    """An untidy post between two points: four sides, no caps."""
    base, top = Vector(base), Vector(top)
    t = (top - base).normalized()
    a = t.cross(Vector((0.3, 1, 0.1))).normalized() * (w / 2)
    b = t.cross(a).normalized() * (w / 2)
    corners = [a + b, a - b, -a - b, -a + b]
    low = [bm.verts.new(base + c) for c in corners]
    high = [bm.verts.new(top + c) for c in corners]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((low[k], low[j], high[j], high[k])).material_index = STEEL


R = 0.085
TOP = H - R * 0.866
HAND = [(0, 0, TOP), (1.2, 0, TOP), (2.4, 0, TOP), (3.6, 0.5, TOP + 0.5), (4.7, 1.4, TOP + 1.25), (5.5, 2.9, TOP + 1.55), (6.5, 3.9, TOP + 0.85),
        (6.8, 5.4, TOP + 0.45), (7.2, 6.6, TOP - 0.35), (7.3, 7.8, TOP - 1.5)]
MID = [(0, 0, 0.63), (1.2, 0, 0.63), (2.3, 0, 0.63), (3.3, 0.45, 0.85), (4.3, 1.6, 1.05), (5.0, 3.0, 0.95), (5.4, 4.2, 0.5), (5.6, 5.0, -0.3)]
tube_faces = sweep(HAND, kit.circle_profile(R, 6), STEEL)
sweep(MID, [(-0.04, -0.05), (0.04, -0.05), (0.04, 0.05), (-0.04, 0.05)], STEEL)
# The kick plate: sound to x 2.4, then a torn length hanging out with the rail.
T = 0.055
kick = [(T, -0.45), (T, 0.16), (T, 0.32), (-T, 0.32), (-T, 0.16), (-T, -0.45)]
sweep([(0, 0, 0), (2.4, 0, 0)], kick, RUST, edge_mats=[RUST, HAZ, HAZ, HAZ, RUST, RUST])
sweep([(2.5, 0.08, -0.02), (3.4, 0.6, 0.15), (4.3, 1.7, 0.1), (4.85, 2.9, -0.5)], [(T, -0.34), (T, 0.3), (-T, 0.3), (-T, -0.34)], RUST)
# Posts: two still upright, one dragged over, three torn out and hanging from the rail by their tops, a stump left in the floor.
post((0.08, 0, -0.1), (0.08, 0, TOP))
post((1.25, 0, -0.1), (1.25, 0, TOP))
post((2.5, -0.02, -0.1), (2.4, 0, TOP))
post((3.35, 0.75, 0.25), (3.6, 0.5, TOP + 0.5))
post((5.3, 3.5, 0.6), (5.5, 2.9, TOP + 1.55))
post((7.2, 6.0, -0.45), (6.8, 5.4, TOP + 0.45))
post((4.0, 0.0, -0.1), (4.02, 0.02, 0.34), w=0.12)

me = kit.mesh_from(NAME, bm, mats)
kit.box_uvs(me, 0.35)
for p in me.polygons[:len(tube_faces)]:
    p.use_smooth = True
# Red off the landing's strips where it's still on the landing; green coming up the shaft on what hangs out over it.
RED = (1.0, 0.1, 0.05)
kit.bake_light(me, [((1.5, -1.4, 0.3), RED, 2.8, 1.4), ((4.0, -1.2, 0.8), RED, 2.2, 0.9), ((7.0, 9.0, -14.0), (0.15, 0.85, 0.35), 16.0, 0.95)],
               ambient=(0.75, 0.73, 0.68))
A.obj(me)
A.finish(kit, NAME, budget=300, eye=(-1.5, -3.0, 1.45), look_at=(3.6, 2.4, 1.1))
