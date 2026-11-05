"""rail_12: a stair rail, 12 m along +X and 5 m down (22.6 degrees), with posts and a kick plate. Origin: its top end, on the
walking line (the steps' slope), the rail's centre at y 0; the handrail's top stands 1.1 above that line. Sections are cut
upright, so the ends lie exactly on x 0 and x 12 and lengths butt. Placed at y = +/-6.1."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'rail_12'
LEN = 12.0
SLOPE = 5.0 / 12.0
H = 1.1
kit = A.begin()
m = _mats.mats(kit)
mats = [m['riveted_steel'], m['rust'], m['hazard']]
STEEL, RUST, HAZ = 0, 1, 2
bm = bmesh.new()


def z_of(x):
    return -SLOPE * x


def prism(profile, segs, mat, edge_mats=None, caps=True):
    """A closed (y, height over the slope) section run down the slope, upright; edge_mats sets a material per section edge."""
    rings = []
    for i in range(segs + 1):
        x = LEN * i / segs
        rings.append([bm.verts.new((x, y, z_of(x) + dz)) for y, dz in profile])
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


# The handrail: thick, for the scene's pixel. Round in true section, so a touch taller in this upright one.
R = 0.085
CEN = H - R * 0.866 * 1.083  # (the hexagon's flats are up: this puts its top at exactly 1.1)
ROUND = [(c, CEN + s * 1.083) for c, s in kit.circle_profile(R, 6)]
tube_faces = prism(ROUND, 3, STEEL)
# The mid rail, square.
prism([(-0.04, 0.58), (0.04, 0.58), (0.04, 0.68), (-0.04, 0.68)], 3, STEEL)
# The kick plate: goes on below the line to cover the stringer's edge; its top painted, as on the image's landings.
T = 0.055
kick = [(T, -0.45), (T, 0.16), (T, 0.32), (-T, 0.32), (-T, 0.16), (-T, -0.45)]
prism(kick, 3, RUST, edge_mats=[RUST, HAZ, HAZ, HAZ, RUST, RUST])
# Posts, upright, the end ones inside the length so a run of rails stays exactly 12 per piece.
POSTS = 8
W = 0.11
for i in range(POSTS):
    x = W / 2 + (LEN - W) * i / (POSTS - 1)
    z0, z1 = z_of(x) - 0.1, z_of(x) + CEN
    corners = [(x - W / 2, -W / 2), (x + W / 2, -W / 2), (x + W / 2, W / 2), (x - W / 2, W / 2)]
    low = [bm.verts.new((cx, cy, z0)) for cx, cy in corners]
    top = [bm.verts.new((cx, cy, z1)) for cx, cy in corners]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((low[k], low[j], top[j], top[k])).material_index = STEEL

me = kit.mesh_from(NAME, bm, mats)
kit.box_uvs(me, 0.35)
n_tube = len(tube_faces)
for p in me.polygons[:n_tube]:
    p.use_smooth = True
# Red from the strips low on the wall every few metres, either side (the rail goes on both sides of the road), green from
# the far end of the shaft below.
RED = (1.0, 0.1, 0.05)
kit.bake_light(me, [((1.5, 1.2, -0.3), RED, 2.6, 1.3), ((7.5, -1.2, -3.0), RED, 2.6, 1.3), ((11.5, 1.2, -4.6), RED, 2.0, 0.9),
                    ((32.0, 0.0, -18.0), (0.15, 0.8, 0.35), 26.0, 0.7)], ambient=(0.75, 0.73, 0.68))
A.obj(me)
A.finish(kit, NAME, budget=200, eye=(-1.0, -5.0, 1.45 + 0.42), look_at=(6.0, 0.0, -1.3))
