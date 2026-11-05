"""rail_flat_16: a level rail for landing edges, 16 m along +X, the same section as rail_12. Origin: its end, on the floor, the
rail's centre at y 0; the handrail's top is at z 1.1, the kick plate goes on down to z -0.45 past the slab's edge. Ends lie
exactly on x 0 and x 16, so lengths butt."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'rail_flat_16'
LEN = 16.0
H = 1.1
kit = A.begin()
m = _mats.mats(kit)
mats = [m['riveted_steel'], m['rust'], m['hazard']]
STEEL, RUST, HAZ = 0, 1, 2
bm = bmesh.new()


def prism(profile, segs, mat, edge_mats=None, caps=True):
    """A closed (y, z) section run along +X; edge_mats sets a material per section edge."""
    rings = []
    for i in range(segs + 1):
        x = LEN * i / segs
        rings.append([bm.verts.new((x, y, z)) for y, z in profile])
    n = len(profile)
    faces = []
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            f = bm.faces.new((a[k], a[j], b[j], b[k]))
            f.material_index = edge_mats[k] if edge_mats else mat
            faces.append(f)
    if caps:
        for r in (rings[0], rings[-1]):
            bm.faces.new(r).material_index = mat
    return faces


R = 0.085
CEN = H - R * 0.866  # (the hexagon's flats are up: this puts its top at exactly 1.1)
tube_faces = prism([(c, CEN + s) for c, s in kit.circle_profile(R, 6)], 3, STEEL)
prism([(-0.04, 0.58), (0.04, 0.58), (0.04, 0.68), (-0.04, 0.68)], 2, STEEL, caps=False)
T = 0.055
kick = [(T, -0.45), (T, 0.16), (T, 0.32), (-T, 0.32), (-T, 0.16), (-T, -0.45)]
prism(kick, 3, RUST, edge_mats=[RUST, HAZ, HAZ, HAZ, RUST, RUST], caps=False)
POSTS = 8
W = 0.11
for i in range(POSTS):
    x = W / 2 + (LEN - W) * i / (POSTS - 1)
    corners = [(x - W / 2, -W / 2), (x + W / 2, -W / 2), (x + W / 2, W / 2), (x - W / 2, W / 2)]
    low = [bm.verts.new((cx, cy, -0.1)) for cx, cy in corners]
    top = [bm.verts.new((cx, cy, CEN)) for cx, cy in corners]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((low[k], low[j], top[j], top[k])).material_index = STEEL

me = kit.mesh_from(NAME, bm, mats)
kit.box_uvs(me, 0.35)
for p in me.polygons[:len(tube_faces)]:
    p.use_smooth = True
RED = (1.0, 0.1, 0.05)
kit.bake_light(me, [((3.0, 1.2, 0.2), RED, 2.6, 1.3), ((12.0, -1.2, 0.2), RED, 2.6, 1.3), ((8.0, 6.0, -18.0), (0.15, 0.8, 0.35), 18.0, 0.6)],
               ambient=(0.75, 0.73, 0.68))
A.obj(me)
A.finish(kit, NAME, budget=160, eye=(-1.5, -5.0, 1.45), look_at=(8.0, 0.0, 0.4))
