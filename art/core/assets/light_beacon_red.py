"""The red alarm beacon, 0.5 tall: a dark base, a squared red lens with a pale hot pane on each side and on top, crossed by dark
wires. Origin at the base's centre, standing up +Z (on a wall, its base goes to the wall and its top shows, as in the tunnel)."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'light_beacon_red'
A_, C = 0.19, 0.05  # Half the lens's width; its cut corners.
Z0, Z1, TOP = 0.08, 0.47, 0.5
kit = A.begin()
m = _mats.mats(kit)
BODY, GLOW, HOT, WIRE = 0, 1, 2, 3
bm = bmesh.new()


def ring(pts, z):
    return [bm.verts.new((x, y, z)) for x, y in pts]


def bridge(a, b, mat):
    for i in range(len(a)):
        j = (i + 1) % len(a)
        bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat


def quad(c, u, v, mat):
    """A flat rectangle about c, half-sides u and v."""
    pts = [[c[k] + su * u[k] + sv * v[k] for k in range(3)] for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new([bm.verts.new(q) for q in pts]).material_index = mat


oct_pts = [(-A_ + C, -A_), (A_ - C, -A_), (A_, -A_ + C), (A_, A_ - C), (A_ - C, A_), (-A_ + C, A_), (-A_, A_ - C), (-A_, -A_ + C)]
# The base.
base = ring([(-0.2, -0.2), (0.2, -0.2), (0.2, 0.2), (-0.2, 0.2)], 0.0)
collar = ring([(-0.17, -0.17), (0.17, -0.17), (0.17, 0.17), (-0.17, 0.17)], Z0)
bridge(base, collar, BODY)
# The lens.
lo = ring(oct_pts, Z0)
hi = ring(oct_pts, Z1)
bridge(lo, hi, GLOW)
bm.faces.new(hi).material_index = GLOW
# On each side a hot pane under a cross of wire; on top the same.
ZM = (Z0 + Z1) / 2
for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    side = (-ny, nx, 0)
    n = (nx, ny, 0)
    quad([n[k] * (A_ + 0.012) + (ZM if k == 2 else 0) for k in range(3)], [s * 0.12 for s in side], (0, 0, 0.13), HOT)
    quad([n[k] * (A_ + 0.03) + (ZM if k == 2 else 0) for k in range(3)], [s * 0.15 for s in side], (0, 0, 0.018), WIRE)
    quad([n[k] * (A_ + 0.03) + (ZM if k == 2 else 0) for k in range(3)], [s * 0.018 for s in side], (0, 0, 0.16), WIRE)
quad((0, 0, Z1 + 0.015), (0.12, 0, 0), (0, 0.12, 0), HOT)
quad((0, 0, TOP), (0.16, 0, 0), (0, 0.02, 0), WIRE)
quad((0, 0, TOP), (0.02, 0, 0), (0, 0.16, 0), WIRE)

me = kit.mesh_from(NAME, bm, [m['riveted_steel'], m['lamp_red'], m['lamp_red_hot'], m['lamp_red']], recalc=False)
kit.box_uvs(me, 1.0)
kit.bake_light(me, [((0.3, 0.3, 0.4), (1.0, 0.12, 0.08), 0.5, 1.0)], ambient=(0.3, 0.28, 0.27))
A.obj(me)
A.finish(kit, NAME, budget=60, eye=(-0.75, 0.85, 0.55), look_at=(0, 0, 0.25))
