"""stair_wall_panel: 16 wide (x -8 to 8), 16 high (z 0 to 16). Origin: base centre, its concrete face on y 0, facing +Y; ribs and plinth stand
proud of that (to y 0.35), the body goes back to y -0.6. Tiles side by side and stacked: half a rib at each edge makes a whole one, the conduit
grooves run on through, and the stains repeat on 16 m."""
import math
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_wall_panel'
H, TOP = 8.0, 16.0
RIB_IN, RIB_Y, PLINTH, PLINTH_Y, BACK = 7.2, 0.35, 0.8, 0.22, -0.6
GX, GW, GZ0, GZ1, GD = 5.0, 0.32, 3.2, 12.8, 0.18  # The grooves' frame: x centre, half width, its rows' z, depth.
kit = A.begin()
m = _mats.mats(kit)
mats = [m['stained_concrete'], m['dark'], m['pipe_metal']]
CONC, DARK, PIPE = range(3)
bm = bmesh.new()
gain = []
TAU = 2 * math.pi


def stain(p):
    """Periodic on 16 m both ways, so tiled panels agree at their seams. Vertical runs, a dark tide low down, olive and rust among it."""
    x, z = p.x, p.z
    k = TAU / 16.0
    runs = 0.5 + 0.5 * math.sin(k * 3 * x + 1.2) * math.sin(k * 5 * x - 0.6)
    patch = 0.5 + 0.5 * math.sin(k * 2 * x + 0.8) * math.cos(k * z + 0.4)
    tide = 0.5 + 0.5 * math.cos(k * z)  # Darkest at the panel's foot and head, where it meets the next.
    v = 1.25 - 0.75 * runs - 0.28 * tide
    moss = max(0.0, patch - 0.5) * 0.7
    rust = max(0.0, 0.5 - patch) * 1.0
    # The pale wall gives way to the strips' red: without this the additive red just washes it pink.
    near = max(math.exp(-((x + 3.5) ** 2 + (z - 2.2) ** 2) / 7.0), math.exp(-((x - 4.2) ** 2 + (z - 1.9) ** 2) / 6.0))
    gb = 1 - 0.8 * near
    return (v * (1 - 0.55 * moss + 0.25 * rust), v * gb * (1 - 0.1 * moss - 0.1 * rust), v * gb * (1 - 0.75 * moss - 0.4 * rust))


def face(pts, mat, out, g=(1, 1, 1)):
    pts = [Vector(p) for p in pts]
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.dot(Vector(out)) < 0:
        pts.reverse()
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat
    gain.extend([g(p) for p in pts] if callable(g) else [g] * len(pts))
    return f


XS = [-RIB_IN, -6.1, -GX - GW, -GX + GW, -3.2, -1.2, 1.2, 3.2, GX - GW, GX + GW, 6.1, RIB_IN]
ZS = [PLINTH, GZ0 - GW, GZ0 + GW, 5.6, 8.0, 10.4, GZ1 - GW, GZ1 + GW, TOP]
for i in range(len(XS) - 1):
    for j in range(len(ZS) - 1):
        x0, x1, z0, z1 = XS[i], XS[i + 1], ZS[j], ZS[j + 1]
        cx = (x0 + x1) / 2
        vert = abs(abs(cx) - GX) < GW
        horiz = abs(cx) < GX - GW and j in (1, 6)
        if vert or horiz:
            y = -GD
            face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], DARK, (0, 1, 0))
        else:
            face([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], CONC, (0, 1, 0), stain)

# The grooves' walls: one long quad each, down the two runs and across the two rows.
for s in (-1, 1):
    for x, o in ((s * GX - GW, 1), (s * GX + GW, -1)):
        face([(x, 0, PLINTH), (x, 0, TOP), (x, -GD, TOP), (x, -GD, PLINTH)], DARK, (o, 0, 0), (0.4, 0.4, 0.4))
for zc in (GZ0, GZ1):
    for z, o in ((zc - GW, 1), (zc + GW, -1)):
        face([(-GX + GW, 0, z), (GX - GW, 0, z), (GX - GW, -GD, z), (-GX + GW, -GD, z)], DARK, (0, 0, o), (0.4, 0.4, 0.4))

# The conduit in the two long runs, standing just proud of the wall, with its elbows into the rows.
CW = 0.19
for s in (-1, 1):
    x = s * GX
    face([(x - CW, 0.07, PLINTH), (x + CW, 0.07, PLINTH), (x + CW, 0.07, TOP), (x - CW, 0.07, TOP)], PIPE, (0, 1, 0), (1.6, 1.6, 1.5))
    for o in (-1, 1):
        face([(x + o * CW, 0.07, PLINTH), (x + o * CW, 0.07, TOP), (x + o * CW, -GD, TOP), (x + o * CW, -GD, PLINTH)], PIPE, (o, 0, 0), (0.9, 0.9, 0.9))
for zc in (GZ0, GZ1):
    a, b = -GX + CW, GX - CW
    face([(a, 0.04, zc - CW), (b, 0.04, zc - CW), (b, 0.04, zc + CW), (a, 0.04, zc + CW)], PIPE, (0, 1, 0), (1.6, 1.6, 1.5))
    face([(a, 0.04, zc + CW), (b, 0.04, zc + CW), (b, -GD, zc + CW), (a, -GD, zc + CW)], PIPE, (0, 0, 1), (1.2, 1.2, 1.2))
    face([(a, 0.04, zc - CW), (b, 0.04, zc - CW), (b, -GD, zc - CW), (a, -GD, zc - CW)], PIPE, (0, 0, -1), (0.6, 0.6, 0.6))

# The ribs: half a rib at each edge, full height. The plinth runs between them.
RZ = [0.0, 4.0, 8.0, 12.0, 16.0]
for s in (-1, 1):
    a, b = s * RIB_IN, s * H
    for z0, z1 in zip(RZ, RZ[1:]):
        face([(a, RIB_Y, z0), (b, RIB_Y, z0), (b, RIB_Y, z1), (a, RIB_Y, z1)], CONC, (0, 1, 0), lambda p: tuple(1.3 * c for c in stain(p)))
    face([(a, 0, 0), (a, RIB_Y, 0), (a, RIB_Y, TOP), (a, 0, TOP)], CONC, (-s, 0, 0), (0.55, 0.55, 0.55))
    # The seam's face, seen only where a run of panels ends.
    face([(b, BACK, 0), (b, RIB_Y, 0), (b, RIB_Y, TOP), (b, BACK, TOP)], CONC, (s, 0, 0), (0.5, 0.5, 0.5))
PX = [-RIB_IN, -3.6, 0.0, 3.6, RIB_IN]
for a, b in zip(PX, PX[1:]):
    face([(a, PLINTH_Y, 0), (b, PLINTH_Y, 0), (b, PLINTH_Y, PLINTH), (a, PLINTH_Y, PLINTH)], CONC, (0, 1, 0), lambda p: tuple(0.75 * c for c in stain(p)))
    face([(a, 0, PLINTH), (b, 0, PLINTH), (b, PLINTH_Y, PLINTH), (a, PLINTH_Y, PLINTH)], CONC, (0, 0, 1), (0.9, 0.9, 0.9))

# The body behind, closed: back, head, foot.
face([(-H, BACK, 0), (H, BACK, 0), (H, BACK, TOP), (-H, BACK, TOP)], CONC, (0, -1, 0), (0.5, 0.5, 0.5))
for z, o in ((0.0, -1), (TOP, 1)):
    face([(-H, BACK, z), (H, BACK, z), (H, RIB_Y, z), (-H, RIB_Y, z)], CONC, (0, 0, o), (0.5, 0.5, 0.5))

me = kit.mesh_from(NAME, bm, mats, smooth=False, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = [
    ((-3.5, 1.2, 2.2), RED, 2.0, 2.8),
    ((4.2, 1.2, 1.9), RED, 1.9, 2.5),
    ((0.0, 1.8, 8.0), GREEN, 3.5, 0.3),
    # The white-grey wash from the battens above that makes this wall the image's palest thing.
    ((-1.0, 9.0, 10.0), (0.82, 0.84, 0.76), 14.0, 1.0),
]
kit.bake_light(me, lights, ambient=(0.64, 0.64, 0.58))
ca = me.color_attributes['AO']
vi = np.zeros(len(me.loops), np.int64)
me.loops.foreach_get('vertex_index', vi)
cols = np.zeros(len(me.loops) * 4, np.float32)
ca.data.foreach_get('color', cols)
rgb = np.zeros((len(me.vertices), 3), np.float32)
rgb[vi] = cols.reshape(-1, 4)[:, :3]
kit.set_vcol_rgb(me, rgb * np.asarray(gain, np.float32))
A.obj(me)
A.finish(kit, NAME, budget=300, eye=(-7.5, 9.5, 1.45), look_at=(0.5, 0.0, 7.0))
