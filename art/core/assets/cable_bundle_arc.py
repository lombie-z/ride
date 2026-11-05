"""cable_bundle_arc: cable_bundle_12's bank curving round the tube's wall: 8 m of arc at radius 8.6 (53.3 degrees) in the YZ plane, the
tube's axis along +X. Origin on the bank's centre at its start, with the wall behind it (-Y) and the arc's centre at (0, 8.6, 0): it
starts heading +Z and curves toward +Y. Placed at (x, -8.6, 5.5) in a tube centred on y 0, it climbs the right wall from the tube's mid
height; turn it about the tube's axis (X, through the arc's centre) to start anywhere else. Clamps every 4 m, as the run's."""
import math
import os
import random
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from cable_bundle_12 import AMBER, BANK, end_card, strand, tunnel_lights  # noqa: E402
from pipe_big_12 import make  # noqa: E402

kit = A.begin()
m = _mats.mats(kit)
bm = bmesh.new()
rnd = random.Random(8)
R, ARC = 8.6, 8.0
SPANS = 5
X = Vector((1, 0, 0))
C = Vector((0, R, 0))


def at(s, across=0.0, off=0.0):
    """The point s along the arc, `across` along the tube, `off` inward from the bank's centreline; and its tangent and inward normal."""
    a = s / R
    n = Vector((0, math.cos(a), -math.sin(a)))
    t = Vector((0, math.sin(a), math.cos(a)))
    return C - n * (R - off) + X * across, t, n


for k, (across, off, r, sides) in enumerate(BANK):
    frames = []
    for i in range(SPANS + 1):
        s = ARC * i / SPANS
        slack = 0.0 if i in (0, SPANS) else 1.0
        p, t, _n = at(s, across + slack * rnd.uniform(-0.04, 0.04), off + slack * rnd.uniform(-0.02, 0.02))
        frames.append((p, X, t.cross(X)))
    # Here the bank's across is X: X x (t x X) = t, so its rings run the way the arc does.
    strand(bm, frames, r, 5 if k < 4 else 4, 2 if k in (1, 3) else 0)

for s in (2.0, 6.0):
    p, t, n = at(s)
    # The box's x across the tube, y radial (inward), z along the arc.
    rot = Matrix((X, n, t)).transposed()
    kit.add_box(bm, p, (1.32, 0.8, 0.26), 1, rot=rot)

p0, _t, n0 = at(0.0)
end_card(bm, p0, n0 * 0.3, X * 0.62)
p1, _t, n1 = at(ARC)
end_card(bm, p1, X * 0.62, n1 * 0.3)

me = make(kit, 'cable_bundle_arc', bm, [m['cable'], m['riveted_steel'], m['pipe_metal']])
kit.box_uvs(me, 0.25)
kit.bake_light(me, tunnel_lights([at(s)[0] for s in (0.0, 4.0, 8.0)]), ambient=AMBER)
A.obj(me)
A.finish(kit, 'cable_bundle_arc', budget=350, eye=(-2.6, 7.6, 1.0), look_at=(0.0, 0.8, 3.6), fov=55.0)
