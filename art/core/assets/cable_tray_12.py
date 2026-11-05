"""cable_tray_12: a steel tray of bundled cables on four wall brackets. Origin at the x = 0 end on the wall's face, at the tray floor's
height: x 0..12 along +X, the wall's the y = 0 plane and the tray stands out toward +Y (y 0.2..1.2, faces +Y, like stair_wall_panel),
its floor z = 0, the brackets down to z -0.55, the cables up to about z +0.6. Runs tile end to end."""
import os
import random
import sys

import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
from cable_bundle_12 import AMBER, end_card, strand, tunnel_lights  # noqa: E402
from pipe_big_12 import make  # noqa: E402

kit = A.begin()
m = _mats.mats(kit)
CABLE, STEEL, DARK, METAL = 0, 1, 2, 3
bm = bmesh.new()
rnd = random.Random(5)
L = 12.0
Y0, Y1 = 0.2, 1.2

# The tray: a floor and two side rails, the outer with a lip.
kit.add_box(bm, (L / 2, (Y0 + Y1) / 2, -0.03), (L, Y1 - Y0, 0.06), STEEL)
kit.add_box(bm, (L / 2, Y0 + 0.03, 0.14), (L, 0.06, 0.34), STEEL)
kit.add_box(bm, (L / 2, Y1 - 0.03, 0.07), (L, 0.06, 0.2), STEEL)
# Brackets every 3 m: a plate on the wall, an arm under the tray.
for x in (1.5, 4.5, 7.5, 10.5):
    kit.add_box(bm, (x, 0.04, -0.14), (0.26, 0.08, 0.82), DARK)
    kit.add_box(bm, (x, 0.65, -0.13), (0.2, 1.14, 0.14), DARK)

# The cables, heaped: (y, z, radius).
U, V = Vector((0, 1, 0)), Vector((0, 0, 1))
XS = (0.0, 4.0, 8.0, 12.0)
for k, (y, z, r) in enumerate([(0.38, 0.15, 0.15), (0.69, 0.16, 0.16), (1.0, 0.15, 0.15), (0.54, 0.42, 0.15), (0.86, 0.42, 0.16)]):
    frames = []
    for x in XS:
        slack = 0.0 if x in (0.0, L) else 1.0
        frames.append((Vector((x, y + slack * rnd.uniform(-0.03, 0.03), z + slack * rnd.uniform(-0.01, 0.04))), U, V))
    strand(bm, frames, r, 5, METAL if k == 3 else CABLE)
# Straps round the heap, every 4 m.
for x in (2.0, 6.0, 10.0):
    kit.add_box(bm, (x, 0.7, 0.3), (0.14, 1.04, 0.66), STEEL)

end_card(bm, Vector((0, 0.69, 0.3)), V * 0.3, U * 0.47)
end_card(bm, Vector((L, 0.69, 0.3)), U * 0.47, V * 0.3)

me = make(kit, 'cable_tray_12', bm, [m['cable'], m['riveted_steel'], m['dark'], m['pipe_metal']])
kit.box_uvs(me, 0.25)
kit.bake_light(me, tunnel_lights([Vector((x, 0.7, 0)) for x in (0.0, 3.0, 6.0, 9.0, 12.0)]), ambient=AMBER)
A.obj(me)
A.finish(kit, 'cable_tray_12', budget=350, eye=(-0.4, 5.0, -1.2), look_at=(5.5, 0.5, 0.15), fov=55.0)
