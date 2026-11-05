"""tube_cross_grate: the overhead grating and ladder under the tube's crown, as at the top of the image (art/core/ASSETS.md).

Origin: top centre, on the crown's surface (a ring's x + 4, y 0, z 14.5). It runs x -4..+4 along the tube, hanging below z 0, its
hangers' ends rising to z +0.1 into the crown: a mesh panel 3 wide hung by two cross yokes that run on into the wall,
and a long ladder either side. Lowest point z -1.3, so 13.2 over the deck.
"""
import math
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'tube_cross_grate'
R = 9.0
PANEL_Z = -1.05
PANEL_W = 3.0
LADDER_Y = 3.05
LADDER_W = 1.05
YOKE_Y = 4.75  # where the yokes run into the wall
# A white work light at each side of the crown, and a dim green from below.
LIGHTS = [((0.0, 5.5, -3.5), (1.0, 0.95, 0.78), 5.0, 1.0), ((0.0, -5.5, -3.5), (1.0, 0.95, 0.78), 5.0, 1.0), ((0.0, 0.0, -11.0), (0.2, 1.0, 0.24), 9.0, 0.5)]


def crown_drop(y):
    """How far below the crown the wall is at y."""
    return R - math.sqrt(R * R - y * y)


def bar(bm, a, b, half, mat):
    """A three-sided bar from a to b, one flat facing down, the cheapest thing that holds a bold line from below."""
    ax = [b[i] - a[i] for i in range(3)]
    ln = math.sqrt(sum(c * c for c in ax))
    t = [c / ln for c in ax]
    # A perpendicular pair.
    up = (0.0, 0.0, 1.0) if abs(t[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = (t[1] * up[2] - t[2] * up[1], t[2] * up[0] - t[0] * up[2], t[0] * up[1] - t[1] * up[0])
    ul = math.sqrt(sum(c * c for c in u))
    u = tuple(c / ul for c in u)
    v = (t[1] * u[2] - t[2] * u[1], t[2] * u[0] - t[0] * u[2], t[0] * u[1] - t[1] * u[0])
    tri = []
    for k in range(3):
        an = 2 * math.pi * k / 3 + math.pi / 2
        tri.append((math.cos(an) * half, math.sin(an) * half))
    ra = [bm.verts.new(tuple(a[i] + u[i] * p + v[i] * q for i in range(3))) for p, q in tri]
    rb = [bm.verts.new(tuple(b[i] + u[i] * p + v[i] * q for i in range(3))) for p, q in tri]
    for k in range(3):
        j = (k + 1) % 3
        bm.faces.new((ra[k], ra[j], rb[j], rb[k])).material_index = mat


def build(kit, m):
    bm = bmesh.new()
    rust, steel = 0, 1
    x0, x1 = -4.0, 4.0
    hw = PANEL_W / 2
    # The mesh: bold bars, wide apart: at the scene's pixel they're a grid, not a shimmer.
    for k in range(1, 12):
        x = x0 + (x1 - x0) * k / 12
        bar(bm, (x, -hw, PANEL_Z), (x, hw, PANEL_Z), 0.05, steel)
    for k in range(1, 6):
        y = -hw + PANEL_W * k / 6
        bar(bm, (x0, y, PANEL_Z), (x1, y, PANEL_Z), 0.05, steel)
    # Its frame: heavy angle, long sides and ends.
    for y in (-hw, hw):
        kit.add_box(bm, (0, y, PANEL_Z), (8.0, 0.16, 0.2), rust)
    for x in (x0, x1):
        kit.add_box(bm, (x, 0, PANEL_Z), (0.14, PANEL_W, 0.16), rust)
    # Two cross yokes under it, their ends running on into the wall, hangers up to the crown.
    for x in (-2.6, 2.6):
        kit.add_box(bm, (x, 0, PANEL_Z - 0.18), (0.2, 2 * YOKE_Y, 0.18), steel)
        for y in (-hw, hw):
            bar(bm, (x, y, PANEL_Z), (x, y, 0.1), 0.06, rust)
    # The ladders along the crown either side of the panel, as the image's runs: rails and rungs, slung on the yokes.
    lz = PANEL_Z - 0.06
    for c in (LADDER_Y, -LADDER_Y):
        for y in (c - LADDER_W / 2, c + LADDER_W / 2):
            kit.add_box(bm, (0, y, lz), (8.0, 0.1, 0.16), rust)
        for k in range(10):
            x = x0 + 0.4 * (x1 - x0) / 8 + (x1 - x0 - 0.8) * k / 9
            bar(bm, (x, c - LADDER_W / 2, lz), (x, c + LADDER_W / 2, lz), 0.05, rust)
    me = kit.mesh_from(NAME, bm, [m['rust'], m['pipe_metal']], smooth=False)
    kit.box_uvs(me, 0.5)
    kit.bake_light(me, LIGHTS, ambient=(0.38, 0.38, 0.36))
    return me


if __name__ == '__main__':
    kit = A.begin()
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    A.finish(kit, NAME, budget=400, eye=(-7.5, -1.0, -5.5), look_at=(1.0, 0.8, -1.0), fov=60.0)
