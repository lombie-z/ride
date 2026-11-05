"""pipe_broken: pipe_big_12's bore sheared open, for steam. Origin on the axis at the flanged x = 0 end (mates with a run coming
from -X); it runs along +X and tears open at about x 2.3 to 3.7 (the long lip on top), its black mouth looking along +X: steam comes from about (3, 0, 0)."""
import math
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from pipe_big_12 import BORE, FLANGE, FLANGE_T, STAIR_AMBIENT, cap, join, make, ring_x, stair_lights, turned  # noqa: E402

kit = A.begin()
m = _mats.mats(kit)
RUST, DARK, STEEL = 0, 1, 2
bm = bmesh.new()
seg = 18
WALL = 0.11

# The shear: a slant across the pipe (2.3 on the low side, about 3.6 at the lip on top), its edge torn into short uneven teeth, the
# long lip peeled outward a little.
JAG = [0.12, -0.16, 0.2, -0.1, 0.05, -0.2, 0.26, -0.08, 0.14, -0.22, 0.08, -0.12, 0.2, -0.18, 0.03, -0.1, 0.24, -0.14]
LIP = math.radians(115)
BODY_END = 2.3
REACH = []
PEEL = []
for _i in range(seg):
    _s = 0.5 + 0.5 * math.cos(2 * math.pi * _i / seg - LIP)
    REACH.append(0.22 + 1.05 * _s ** 1.4 + JAG[_i] * (0.5 + _s))
    PEEL.append(0.2 * _s ** 3 + max(JAG[_i], 0.0) * 0.25)


def rim(frac, inner=False):
    """A ring of the torn part, `frac` of the way out along each tooth."""
    out = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        x = BODY_END + REACH[i] * frac
        r = BORE + PEEL[i] * frac * frac - (WALL if inner else 0.0)
        out.append(bm.verts.new((x, r * math.cos(a), r * math.sin(a))))
    return out


turned(bm, [(0.0, FLANGE), (FLANGE_T, FLANGE), (FLANGE_T, BORE)], seg, mat=DARK)
cap(bm, ring_x(bm, 0.0, FLANGE, seg), DARK, flip=True)
base = ring_x(bm, FLANGE_T, BORE, seg)
start = rim(0.0)
join(bm, base, start, RUST)
mid = rim(0.55)
join(bm, start, mid, RUST)
tip = rim(1.0)
join(bm, mid, tip, RUST, smooth=False)
# The torn lip, bright steel, then the inside: black, back to a plug that hides the far end.
tip2 = rim(1.0)
in_tip = rim(1.0, inner=True)
join(bm, tip2, in_tip, STEEL, smooth=False)
in_tip2 = rim(1.0, inner=True)
in_back = ring_x(bm, 1.2, BORE - WALL, seg)
join(bm, in_tip2, in_back, DARK)
cap(bm, ring_x(bm, 1.2, BORE - WALL, seg), DARK)

me = make(kit, 'pipe_broken', bm, [m['pipe_metal'], m['dark'], m['riveted_steel']])
kit.box_uvs(me, 0.25)
kit.bake_light(me, stair_lights((0.2, 1.2, 2.3, 3.0, 3.6)), ambient=STAIR_AMBIENT)
A.obj(me)
A.finish(kit, 'pipe_broken', budget=350, eye=(6.2, -3.0, 0.5), look_at=(1.8, 0.0, 0.0), fov=50.0)
