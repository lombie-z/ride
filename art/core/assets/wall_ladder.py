"""wall_ladder: a rung ladder with a safety cage, 12 high. Origin: its base, centred, on the wall's face; the wall is the plane
y 0 and the ladder stands off it to +Y (as stair_wall_panel faces +Y). 0.68 between stiles, cage out to y 1.39, z 0 to 12."""
import math
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'wall_ladder'
HIGH = 12.0
kit = A.begin()
m = _mats.mats(kit)
mats = [m['pipe_metal'], m['riveted_steel']]
RUST, STEEL = 0, 1
bm = bmesh.new()


def face(pts, mat):
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat


SX, SY, SW = 0.34, 0.28, 0.13
# Stiles: four sides, two lengths each (so the light has somewhere to change).
for sx in (-SX, SX):
    zs = (0.0, HIGH / 2, HIGH)
    rings = [[bm.verts.new((sx + a, SY + b, z)) for a, b in ((-SW / 2, -SW / 2), (SW / 2, -SW / 2), (SW / 2, SW / 2), (-SW / 2, SW / 2))] for z in zs]
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((r0[k], r0[j], r1[j], r1[k])).material_index = RUST
# Rungs: top and front, wide apart and thick so they hold at the scene's pixel.
RUNG = 0.8
T = 0.1
for i in range(15):
    z = 0.4 + i * RUNG
    y0, y1 = SY - T / 2, SY + T / 2
    face([(-SX, y0, z), (SX, y0, z), (SX, y1, z), (-SX, y1, z)], STEEL)
    face([(-SX, y1, z), (SX, y1, z), (SX, y1, z - T), (-SX, y1, z - T)], STEEL)
# Stand-offs to the wall: top and front faces of each.
for sx in (-SX, SX):
    for z in (0.7, 11.3):
        w = 0.06
        face([(sx - w, 0.0, z), (sx + w, 0.0, z), (sx + w, SY, z), (sx - w, SY, z)], RUST)
        face([(sx + w, 0.0, z), (sx + w, SY, z), (sx + w, SY, z - 0.12), (sx + w, 0.0, z - 0.12)], RUST)
# The cage: flat hoops from stile to stile round the front, with three bars up them.
CY, CR = 0.72, 0.6
ARC = [(-SX, SY)] + [(CR * math.cos(a), CY + CR * math.sin(a)) for a in (math.radians(d) for d in (200, 140, 90, 40, -20))] + [(SX, SY)]
BAND = 0.16
HOOPS = [2.8, 4.65, 6.5, 8.35, 10.2, 11.95]
for z in HOOPS:
    for (x0, y0), (x1, y1) in zip(ARC, ARC[1:]):
        face([(x0, y0, z - BAND), (x1, y1, z - BAND), (x1, y1, z), (x0, y0, z)], RUST)
for d in (135, 90, 45):
    a = math.radians(d)
    x, y = CR * math.cos(a), CY + CR * math.sin(a)
    w = 0.065
    face([(x - w, y, HOOPS[0] - BAND), (x + w, y, HOOPS[0] - BAND), (x + w, y, HIGH), (x - w, y, HIGH)], RUST)
    face([(x, y - w, HOOPS[0] - BAND), (x, y + w, HOOPS[0] - BAND), (x, y + w, HIGH), (x, y - w, HIGH)], RUST)

me = kit.mesh_from(NAME, bm, mats)
kit.box_uvs(me, 0.35)
RED = (1.0, 0.1, 0.05)
kit.bake_light(me, [((1.8, 1.4, 3.0), RED, 2.6, 1.3), ((-1.8, 1.4, 9.5), RED, 2.6, 1.3), ((0.0, 14.0, -8.0), (0.15, 0.8, 0.35), 14.0, 0.5)],
               ambient=(0.85, 0.8, 0.72))
A.obj(me)
A.finish(kit, NAME, budget=200, eye=(-3.5, 8.0, 1.45), look_at=(0.0, 0.3, 4.8))
