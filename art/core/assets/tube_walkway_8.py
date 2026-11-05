"""tube_walkway_8: the tube's side walkway (art/core/ASSETS.md), the wet concrete ledge in the image's lower left, with its rail.

Origin: the walkway's back end, on the deck's level (z 0 = deck top), at the road-side edge of its top. It runs x 0..8 along +X,
its top going off toward the wall along +Y; the top is z 0.95, the water's z 0.35 running up its sloped front. Left of the road:
y +6.2 in the ring's frame. Right: the ring's far end (x 8), y -6.2, turned 180 degrees about z. It's cut to bury itself in the
tube's wall and ribs. A dark filler inside its section runs 0.3 past both ends, to shut the joint on a bend.
"""
import math
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'tube_walkway_8'
LEN = 8.0
TOP = 0.95
BACK = 1.75
# The ledge's section, y, z, walked from under the water up its sloped front, over the top and into the wall.
SECTION = [(-0.34, -0.6), (-0.1, TOP - 0.16), (0.02, TOP), (0.85, TOP), (BACK, TOP), (BACK, -0.6)]
# Lights in the asset's frame, for the left wall: green lamp ahead on the wall, a white work light overhead.
LIGHTS = [((4.0, 1.8, 3.0), (0.2, 1.0, 0.24), 2.8, 1.3), ((4.0, 0.0, 10.9), (1.0, 0.95, 0.78), 6.0, 0.8),
          ((12.0, 1.8, 3.0), (0.2, 1.0, 0.24), 2.8, 1.3), ((-4.0, 1.8, 3.0), (0.2, 1.0, 0.24), 2.8, 1.3)]


def section_at(bm, x, chip=0.0):
    return [bm.verts.new((x, y + (chip if i < 3 else 0.0), z - (chip * 0.6 if i in (1, 2, 3, 4) else 0.0))) for i, (y, z) in enumerate(SECTION)]


def add_rail_pipe(bm, x0, x1, y, z, half, mat):
    return A._kit.add_box(bm, ((x0 + x1) / 2, y, z), (x1 - x0, half * 2, half * 2), mat)


def build(kit, m):
    bm = bmesh.new()
    wet, conc, rust, steel, dark = 0, 1, 2, 3, 4
    # The ledge, its ends chipped back a little so the joint between two reads as the dark V between the image's blocks.
    xs = [(0.0, 0.1), (0.14, 0.0), (2.7, 0.0), (5.3, 0.0), (7.86, 0.0), (8.0, 0.1)]
    rows = [section_at(bm, x, c) for x, c in xs]
    n = len(SECTION)
    for a, b in zip(rows, rows[1:]):
        for i in range(n - 1):
            bm.faces.new((a[i], b[i], b[i + 1], a[i + 1])).material_index = wet if i in (1, 2, 3) else conc
    bm.faces.new(list(reversed(rows[0]))).material_index = conc
    bm.faces.new(rows[-1]).material_index = conc
    # The joint's filler, inside the ledge's section, running past both ends.
    kit.add_box(bm, (LEN / 2, 0.85, 0.15), (LEN + 0.6, 1.6, 1.1), dark)
    # The steel angle along the top's edge: the bright line the image's ledge has.
    kit.add_box(bm, (LEN / 2, 0.03, TOP + 0.015), (LEN - 0.28, 0.14, 0.05), steel)
    # The rail: rail height 1.1, posts between rings' worth of pitch, so two in a row keep their rhythm.
    for x in (1.33, 4.0, 6.67):
        kit.add_box(bm, (x, 0.2, TOP + 0.55), (0.11, 0.11, 1.1), rust)
        kit.add_box(bm, (x, 0.2, TOP + 0.03), (0.3, 0.3, 0.06), rust)
    add_rail_pipe(bm, 0.0, LEN, 0.2, TOP + 1.1, 0.065, rust)
    add_rail_pipe(bm, 0.0, LEN, 0.2, TOP + 0.6, 0.04, rust)
    kit.add_box(bm, (LEN / 2, 0.2, TOP + 0.12), (LEN, 0.05, 0.2), steel)
    me = kit.mesh_from(NAME, bm, [m['wet_concrete'], m['stained_concrete'], m['rust'], m['pipe_metal'], m['dark']], smooth=False)
    kit.box_uvs(me, 0.25)
    kit.bake_light(me, LIGHTS, ambient=(0.45, 0.48, 0.44))
    return me


if __name__ == '__main__':
    kit = A.begin()
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    _ = math
    A.finish(kit, NAME, budget=200, eye=(-3.2, -2.2, 1.45), look_at=(5.0, 0.7, 1.0), fov=60.0)
