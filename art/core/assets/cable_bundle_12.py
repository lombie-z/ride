"""cable_bundle_12: a thick black bank of seven cables with steel clamps every 4 m, x 0..12 along +X. Origin on the bank's centre at the
x = 0 end, its wall side toward -Y (clamps back to y = -0.4: 8.6 off the tube's axis puts them on its wall of radius 9), spanning
z -0.65..+0.65. Runs tile end to end. Also holds the strand helpers cable_tray_12 and cable_bundle_arc import."""
import os
import random
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from pipe_big_12 import join, make, ring_frame  # noqa: E402

# (across, off the wall, radius, sides): the bank's section; across is +Z here, along the tube's axis in the arc.
BANK = [
    (-0.48, 0.14, 0.15, 6), (-0.16, 0.16, 0.16, 6), (0.16, 0.15, 0.15, 6), (0.47, 0.14, 0.16, 6),
    (-0.32, -0.17, 0.15, 6), (0.0, -0.16, 0.16, 6), (0.32, -0.17, 0.15, 6),
]
AMBER = (0.42, 0.45, 0.42)  # the tunnel's dim ambient

# The tunnel's light: a green caged lamp below, a white work light above.
def tunnel_lights(pts, lift=2.4):
    out = []
    for p in pts:
        out.append((p + Vector((0, 1.4, -lift * 0.6)), (0.25, 1.0, 0.3), 2.0, 1.2))
        out.append((p + Vector((0, 1.4, lift)), (0.95, 1.0, 0.85), 2.4, 0.9))
    return out


def strand(bm, frames, r, sides, mat=0):
    """A cable through (centre, u, v) frames, one smooth chain of rings, no end caps: they butt the next piece."""
    rings = [ring_frame(bm, c, u, v, r, sides) for c, u, v in frames]
    for a, b in zip(rings, rings[1:]):
        join(bm, a, b, mat)


def end_card(bm, c, a, b, mat=0):
    """A black card closing a bank's open ends where a run stops (2 tris; facing a x b): hidden where runs butt."""
    f = bm.faces.new([bm.verts.new(c + a * i + b * j) for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    f.material_index = mat


def main():
    kit = A.begin()
    m = _mats.mats(kit)
    bm = bmesh.new()
    rnd = random.Random(12)
    L = 12.0
    XS = (0.0, 4.0, 8.0, 12.0)
    U, V = Vector((0, 1, 0)), Vector((0, 0, 1))
    for k, (across, off, r, sides) in enumerate(BANK):
        # A little slack between clamps, none at the ends, so runs line up.
        frames = []
        for x in XS:
            slack = 0.0 if x in (0.0, L) else 1.0
            frames.append((Vector((x, off + slack * rnd.uniform(-0.02, 0.03), across + slack * rnd.uniform(-0.05, 0.03))), U, V))
        # Two strands in the pipe metal catch what light there is, as the reference's do.
        strand(bm, frames, r, sides, 2 if k in (1, 3) else 0)
    for x in (2.0, 6.0, 10.0):
        kit.add_box(bm, (x, 0.0, 0.0), (0.26, 0.8, 1.32), 1)
    end_card(bm, Vector((0, 0, 0)), V * 0.62, U * 0.3)
    end_card(bm, Vector((L, 0, 0)), U * 0.3, V * 0.62)
    me = make(kit, 'cable_bundle_12', bm, [m['cable'], m['riveted_steel'], m['pipe_metal']])
    kit.box_uvs(me, 0.25)
    kit.bake_light(me, tunnel_lights([Vector((x, 0, 0)) for x in (2.0, 6.0, 10.0)]), ambient=AMBER)
    A.obj(me)
    A.finish(kit, 'cable_bundle_12', budget=300, eye=(-0.6, 4.2, -1.4), look_at=(5.0, 0.0, 0.0), fov=55.0)


if __name__ == '__main__':
    main()
