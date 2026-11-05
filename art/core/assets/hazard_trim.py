"""hazard_trim: a yellow-black painted edge strip beside a floor grate, 12 m along +X, laid on a floor. Origin: its end, on the
floor, the centre of its 1.3 width at y 0: the strip is the +Y side (y 0.25 to 0.65, toward the slab's edge, as on the image's
landings), the grate the -Y side. Ends lie exactly on x 0 and x 12."""
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'hazard_trim'
LEN = 12.0
kit = A.begin()
m = _mats.mats(kit)
mats = [m['hazard'], m['dark'], m['riveted_steel']]
YEL, DARK, STEEL = 0, 1, 2
bm = bmesh.new()
Z = 0.045


def quad(p0, p1, p2, p3, mat, z=Z):
    f = bm.faces.new([bm.verts.new((*p, z)) for p in (p0, p1, p2, p3)])
    f.material_index = mat
    return f


# The strip: slanted bands, coplanar, 0.75 each so they hold at the scene's pixel.
Y0, Y1 = 0.25, 0.65
BAND = 0.75
SLANT = Y1 - Y0


def clamp(x):
    return min(max(x, 0.0), LEN)


# The sliver at the start, then whole bands; the last one's cut square at x 12.
bm.faces.new([bm.verts.new(p) for p in ((0.0, Y0, Z), (SLANT, Y1, Z), (0.0, Y1, Z))]).material_index = DARK
for i in range(16):
    a, b = i * BAND, (i + 1) * BAND
    quad((clamp(a), Y0), (clamp(b), Y0), (clamp(b + SLANT), Y1), (clamp(a + SLANT), Y1), YEL if i % 2 == 0 else DARK)
# Its edge, down to the floor.
f = bm.faces.new([bm.verts.new(p) for p in ((0.0, Y1, 0.0), (LEN, Y1, 0.0), (LEN, Y1, Z), (0.0, Y1, Z))])
f.material_index = DARK
# The grate: a dark well, a steel frame along each side, bold cross bars.
GY0, GY1 = -0.65, 0.25
quad((0.0, GY0), (LEN, GY0), (LEN, GY1), (0.0, GY1), DARK, z=0.02)
quad((0.0, GY0), (LEN, GY0), (LEN, GY0 + 0.08), (0.0, GY0 + 0.08), STEEL)
quad((0.0, GY1 - 0.08), (LEN, GY1 - 0.08), (LEN, GY1), (0.0, GY1), STEEL)
BARS = 16
for i in range(BARS):
    x = (i + 0.5) * LEN / BARS
    quad((x - 0.14, GY0 + 0.08), (x + 0.14, GY0 + 0.08), (x + 0.14, GY1 - 0.08), (x - 0.14, GY1 - 0.08), STEEL, z=Z - 0.005)

me = kit.mesh_from(NAME, bm, mats, recalc=False)
for p in me.polygons:
    if p.normal.z < -0.5:
        p.flip()
kit.box_uvs(me, 0.35)
RED = (1.0, 0.1, 0.05)
# High ambient: the paint has to stay yellow.
kit.bake_light(me, [((2.5, 1.6, 1.0), RED, 2.2, 0.5), ((9.5, 1.6, 1.0), RED, 2.2, 0.5)], ambient=(0.92, 0.9, 0.82))
A.obj(me)
A.finish(kit, NAME, budget=80, eye=(-2.0, -3.2, 1.45), look_at=(5.0, 0.0, 0.0))
