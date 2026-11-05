"""red_room_shell: the room behind the bulkhead (concept-flooded-tunnel): walkways, rails, gantries, red-lit, 34 x 70 x 15.

Origin: floor centre at the near end, +X down the road, so the room runs x 0..70, y +/-17, z 0..15; the frame's seat is its x 0 at
z 5.5. The floor's top is a hair under z 0, for the road's deck and water to sit on. The road stays clear: nothing under z 5.5 over
|y| < 5.9, and the far wall's opening is 14 wide. Walkways stand at z 6 down both sides (rails at y +/-7) and cross on gantries; the
right one starts at x 22, past where the door swings. Tanks go at z 4.6 (their base collars through the walkway), at _bulkhead.TANKS.
All lit per vertex through the ramp, from lamps at the tanks' places.
"""
import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bulkhead as H  # noqa: E402
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'red_room_shell'
RAMP, GLOW, HOT = 0, 1, 2
W, L, HT = H.ROOM_W / 2, H.ROOM_L, H.ROOM_H
Z = H.DECK_Z
LAMPS = [((x, y, 9.5), 16.0, 0.72) for x, y in H.TANKS] + [((30.0, 0.0, 12.0), 22.0, 0.3), ((68.0, 0.0, 5.0), 9.0, 0.3), ((8.0, 0.0, 2.0), 11.0, 0.5), ((30.0, 0.0, 1.0), 12.0, 0.34), ((52.0, 0.0, 1.0), 12.0, 0.34)]


def rail_run(b, p0, p1, lit_top=0.5, post=3.5):
    """A rail between two points at walkway level: handrail, midrail, kick plate, posts, as black lines catching the red on top."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ln = d.length
    t = d.normalized()
    s = t.cross(Vector((0, 0, 1)))
    for h, r, top in ((1.1, 0.07, lit_top), (0.62, 0.045, lit_top * 0.5)):
        c = (p0 + p1) / 2 + Vector((0, 0, h))
        b.box(c, (ln, r * 2, r * 2), axes=(t, s, Vector((0, 0, 1))), mat=RAMP, row=H.DARK, lit=0.08, skip=('-x', '+x'), per_face={'+z': {'lit': top}})
    # (The kick plate.)
    c = (p0 + p1) / 2 + Vector((0, 0, 0.12))
    b.box(c, (ln, 0.05, 0.24), axes=(t, s, Vector((0, 0, 1))), mat=RAMP, row=H.DARK, lit=0.1, skip=('-x', '+x', '-z'))
    n = max(int(round(ln / post)), 1)
    for i in range(n + 1):
        q = p0 + t * (ln * i / n)
        b.box(q + Vector((0, 0, 0.55)), (0.13, 0.13, 1.1), axes=(t, s, Vector((0, 0, 1))), mat=RAMP, row=H.DARK, lit=0.06, skip=('-z',), per_face={'-x': {'lit': 0.1}})


def build(kit, m):
    b = H.B()
    # Walls: dark red steel over concrete, the tanks' light on them.
    b.grid((0, W, -0.1), (L, 0, 0), (0, 0, HT + 0.1), 10, 4, mat=RAMP, row=H.DARK, gain=1.0)
    b.grid((L, -W, -0.1), (-L, 0, 0), (0, 0, HT + 0.1), 10, 4, mat=RAMP, row=H.DARK, gain=1.0)
    # The floor, wet and burning.
    b.grid((-1.0, -W, -0.02), (L + 1.0, 0, 0), (0, 2 * W, 0), 10, 6, mat=RAMP, row=H.EMBER, gain=1.0)
    # The near end wall, either side of the frame's back wall.
    for y0, y1 in ((12.4, W), (-W, -12.4)):
        b.grid((1.2, y1, 0), (0, y0 - y1, 0), (0, 0, HT), 1, 2, mat=RAMP, row=H.DARK, gain=1.0)
    # The far end: the road's opening, 14 wide and 7 high, a wall round it, the red strip over it.
    for y0, y1 in ((7.0, W), (-W, -7.0)):
        b.grid((L, y0, -0.1), (0, y1 - y0, 0), (0, 0, HT + 0.1), 2, 3, mat=RAMP, row=H.DARK, gain=1.0)
    b.grid((L, 7.0, 7.0), (0, -14.0, 0), (0, 0, HT - 7.0), 4, 2, mat=RAMP, row=H.DARK, gain=1.0)
    b.box((L - 0.2, 0, 7.2), (0.5, 14.8, 0.4), mat=RAMP, row=H.DARK, lit=0.22)
    for sy in (-7.2, 7.2):
        b.box((L - 0.2, sy, 3.5), (0.5, 0.45, 7.0), mat=RAMP, row=H.DARK, lit=0.26, skip=('-z',))
    # The strip, as in the image: glowing under the far gantry.
    b.poly([(L - 0.45, 4.3, 7.72), (L - 0.45, -4.3, 7.72), (L - 0.45, -4.3, 8.32), (L - 0.45, 4.3, 8.32)], mat=GLOW)
    b.poly([(L - 0.5, 4.0, 7.9), (L - 0.5, -4.0, 7.9), (L - 0.5, -4.0, 8.14), (L - 0.5, 4.0, 8.14)], mat=HOT)

    # The ceiling: dark beams, red bays between them, some burning, some dark, as in the image.
    rng = np.random.default_rng(91)
    nx, ny = 10, 5
    for i in range(nx):
        for j in range(ny):
            x0, x1 = L * i / nx, L * (i + 1) / nx
            y0, y1 = -W + 2 * W * j / ny, -W + 2 * W * (j + 1) / ny
            near = 0.42 - 0.14 * abs(j - 2) / 2
            lit = float(rng.choice([0.12, 0.32, 0.5, 0.7, 0.85], p=[0.18, 0.2, 0.22, 0.25, 0.15])) * near
            b.poly([(x0, y1, HT), (x1, y1, HT), (x1, y0, HT), (x0, y0, HT)], mat=RAMP, row=H.EMBER, lit=lit)
    for i in range(nx + 1):
        x = L * i / nx
        b.box((x, 0, HT - 0.45), (0.7, 2 * W, 0.9), mat=RAMP, row=H.DARK, lit=0.13, skip=('+z',), per_face={'-z': {'lit': 0.06}})
    for j in range(ny + 1):
        y = -W + 2 * W * j / ny
        b.box((L / 2, y, HT - 0.3), (L, 0.5, 0.6), mat=RAMP, row=H.DARK, lit=0.12, skip=('+z', '-x', '+x'), per_face={'-z': {'lit': 0.05}})

    # Pilasters and pipes down the walls.
    for side in (1, -1):
        for i in range(11):
            b.box((L * i / 10, side * (W - 0.35), HT / 2), (0.8, 0.7, HT), mat=RAMP, row=H.DARK, gain=0.55, skip=('-z', '+z'))
        for z, r in ((11.6, 0.38), (10.7, 0.22)):
            b.rod((1.5, side * (W - 0.7), z), (L, side * (W - 0.7), z), r, sides=5, mat=RAMP, row=H.DARK, lit=0.3, caps=False, smooth=True)
        # Red strips high on the walls.
        for x in (10.0, 27.0, 45.0, 60.0):
            q = [(x - 2.0, side * (W - 0.8), 12.9), (x + 2.0, side * (W - 0.8), 12.9), (x + 2.0, side * (W - 0.8), 13.25), (x - 2.0, side * (W - 0.8), 13.25)]
            b.poly(q if side > 0 else list(reversed(q)), mat=GLOW)

    # The walkways down both sides, on columns, machinery in the dark beneath them.
    for side, x0 in ((1, 1.4), (-1, H.RIGHT_DECK_FROM)):
        y_in, y_out = side * H.RAIL_Y, side * W
        wn = 8
        # Top.
        b.grid((x0, y_out if side > 0 else y_in, Z), (L - x0, 0, 0), (0, abs(y_out - y_in), 0), wn, 2, mat=RAMP, row=H.DARK, gain=0.8)
        # Front edge and underside.
        b.grid((x0, y_in, Z - 0.5), (L - x0, 0, 0), (0, 0, 0.5), wn, 1, mat=RAMP, row=H.DARK, lit=0.3) if side < 0 else \
            b.grid((L, y_in, Z - 0.5), (x0 - L, 0, 0), (0, 0, 0.5), wn, 1, mat=RAMP, row=H.DARK, lit=0.3)
        b.grid((x0, y_in if side > 0 else y_out, Z - 0.5), (L - x0, 0, 0), (0, abs(y_out - y_in), 0), wn, 2, mat=RAMP, row=H.DARK, gain=0.28)
        rail_run(b, (x0, y_in, Z), (L, y_in, Z))
        # Columns.
        n = 9
        for i in range(n):
            x = x0 + 2.0 + (L - x0 - 4.0) * i / (n - 1)
            b.box((x, y_in + side * 0.6, (Z - 0.5) / 2), (0.7, 0.7, Z - 0.5), mat=RAMP, row=H.DARK, gain=0.5, skip=('-z', '+z'))
        # What's under there: dark boxes and tanks of it, lit from the road's side.
        rngm = np.random.default_rng(92 + side)
        for i in range(10):
            x = x0 + 3.0 + (L - x0 - 6.0) * i / 9 + rngm.uniform(-1, 1)
            h = rngm.uniform(2.2, 4.8)
            b.box((x, y_in + side * rngm.uniform(2.6, 4.2), h / 2), (rngm.uniform(1.5, 3.0), rngm.uniform(1.4, 2.6), h), mat=RAMP, row=H.DARK, gain=0.42, skip=('-z',))

    # The gantries over the road, at walkway level, the rail turning across the room as in the image; hangers from the ceiling.
    for gx in H.GANTRY_X:
        b.box((gx, 0, Z - 0.25), (3.0, 2 * H.RAIL_Y + 0.2, 0.5), mat=RAMP, row=H.DARK, gain=0.7, per_face={'-z': {'lit': 0.1}, '-x': {'lit': 0.32}})
        rail_run(b, (gx - 1.5, H.RAIL_Y, Z), (gx - 1.5, -H.RAIL_Y, Z), post=2.8)
        rail_run(b, (gx + 1.5, H.RAIL_Y, Z), (gx + 1.5, -H.RAIL_Y, Z), post=3.5)
        for y in (-6.0, 6.0):
            b.rod((gx - 1.3, y, Z), (gx - 1.3, y, HT - 0.9), 0.09, sides=4, mat=RAMP, row=H.DARK, lit=0.08, caps=False)

    me = b.mesh(NAME, [m['bulkhead_ramp'], m['lamp_red'], m['lamp_red_hot']], H.spill(LAMPS))
    kit.bake_light(me, [((35.0, 0.0, 8.0), (1.0, 0.1, 0.06), 30.0, 0.8)], ambient=(0.3, 0.14, 0.13))
    return me


if __name__ == '__main__':
    kit = A.begin()
    H.register(kit)
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    A.finish(kit, NAME, budget=3000, eye=(-1.0, 2.3, 1.55), look_at=(30.0, 5.0, 5.0), fov=70.0)
