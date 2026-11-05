"""pipe_cluster_12: four mixed pipes on three wall brackets, as on the images' left walls. Origin at the x = 0 end on the wall's
face, at the cluster's mid height: x 0..12 along +X, the wall's the y = 0 plane and the pipes stand out toward +Y (faces +Y, like
stair_wall_panel), z about -1.3..+1.3. Runs tile end to end."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from pipe_big_12 import STAIR_AMBIENT, cap, make, ring_x, stair_lights, turned  # noqa: E402

kit = A.begin()
m = _mats.mats(kit)
RUST, METAL, DARK, STEEL = 0, 1, 2, 3
bm = bmesh.new()
L = 12.0
BRACKETS = (2.0, 6.0, 10.0)

# (radius, y, z, sides, material)
BIG = (0.52, 0.86, -0.2, 12, RUST)
MID = (0.27, 0.46, 0.72, 10, METAL)
SMALL_A = (0.12, 0.3, 1.16, 6, RUST)
SMALL_B = (0.15, 0.34, -1.02, 6, METAL)


def run(p, stops):
    """A plain pipe, split at the x's in `stops`."""
    r, y, z, s, mat = p
    xs = [0.0, *stops, L]
    for a, b in zip(xs, xs[1:]):
        turned(bm, [(a, r), (b, r)], s, y, z, mat)
    cap(bm, ring_x(bm, 0.0, r, s, y, z), mat, flip=True)
    cap(bm, ring_x(bm, L, r, s, y, z), mat)


# The big one: a flange at each end and a dark collar on each bracket.
r, y, z, s, mat = BIG
fr = r + 0.2
turned(bm, [(0.0, fr), (0.18, fr), (0.18, r)], s, y, z, DARK)
cap(bm, ring_x(bm, 0.0, fr, s, y, z), DARK, flip=True)
turned(bm, [(L - 0.18, r), (L - 0.18, fr), (L, fr)], s, y, z, DARK)
cap(bm, ring_x(bm, L, fr, s, y, z), DARK)
xs = [0.18, *BRACKETS, L - 0.18]
for a, b in zip(xs, xs[1:]):
    a2 = a + 0.17 if a > 0.18 else a
    b2 = b - 0.17 if b < L - 0.18 else b
    turned(bm, [(a2, r), (b2, r)], s, y, z, mat)
for x in BRACKETS:
    turned(bm, [(x - 0.17, r), (x - 0.17, r + 0.1), (x + 0.17, r + 0.1), (x + 0.17, r)], s, y, z, DARK)

run(MID, [])
run(SMALL_A, [])
run(SMALL_B, [])

# Brackets: a channel up the wall, an arm out to each pipe, a clamp block on the thinner ones.
for x in BRACKETS:
    kit.add_box(bm, (x, 0.07, 0.03), (0.24, 0.14, 2.7), STEEL)
    kit.add_box(bm, (x, 0.33, BIG[2]), (0.16, 0.4, 0.2), STEEL)
    kit.add_box(bm, (x, MID[1], MID[2]), (0.26, 0.66, 0.66), DARK)
    kit.add_box(bm, (x, SMALL_A[1] - 0.04, SMALL_A[2]), (0.2, 0.4, 0.34), DARK)
    kit.add_box(bm, (x, SMALL_B[1] - 0.04, SMALL_B[2]), (0.2, 0.42, 0.4), DARK)

me = make(kit, 'pipe_cluster_12', bm, [m['rust'], m['pipe_metal'], m['dark'], m['riveted_steel']])
kit.box_uvs(me, 0.25)
lights = []
for x in (0.0, 2.0, 6.0, 10.0, 12.0):
    lights += stair_lights([x], r=BIG[0], y=BIG[1], z=BIG[2], side=1)
    lights += stair_lights([x], r=MID[0], y=MID[1], z=MID[2], side=1)
kit.bake_light(me, lights, ambient=STAIR_AMBIENT, rays=10, dist=1.2, floor=0.55)
A.obj(me)
A.finish(kit, 'pipe_cluster_12', budget=700, eye=(0.0, 6.0, -0.5), look_at=(6.0, 0.4, 0.1), fov=60.0)
