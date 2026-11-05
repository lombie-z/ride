"""stair_wall_ramp: the road from a landing's floor up onto a wall, turned 90 degrees over, in 24 m along +X. Origin: its start, road centre, on
the surface (flat there, normal +Z, 11.8 wide). It banks toward -Y (the rider's right, the side where a stair_wall_panel's +Y face looks at the road):
at x 24 the road's centre is at (24, -WALL, WALL) with normal +Y, flat on a wall plane 0.4 proud of an 8 m-away panel, so the panel's ribs stay behind it.

Each cross-section is a floor, a fillet and a wall; the fillet's radius opens from 1.7 at the ends to WALL at the middle, and the road slides across it, so
it's a long smooth swoop that never pokes through the floor or the wall. The section's kept wider through the middle, as the road crosses it on the slant."""
import math
import os
import sys

import bmesh
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'stair_wall_ramp'
LEN, HALF, WALL = 24.0, 5.9, 7.6
R0, RM = WALL - HALF, WALL
ROWS = 24
US = [-1.0, -0.93, -0.76, -0.58, -0.4, -0.2, 0.0, 0.2, 0.4, 0.58, 0.76, 0.93, 1.0]  # Across the road: -1 the edge away from the wall, 1 the wall's.
KERB_H, KERB_W, SHELL = 0.24, 0.3, 0.4
kit = A.begin()
m = _mats.mats(kit)
mats = [m['wet_concrete'], m['stained_concrete'], m['hazard']]
WET, STAINED, HAZ = range(3)
bm = bmesh.new()
gain = []


def sstep(t):
    return t * t * (3 - 2 * t)


def radius(t):
    return R0 + (RM - R0) * math.sin(math.pi * t) ** 2


def lift(t):
    """Up off the landing's floor, so the two surfaces don't fight, from nothing at the very start."""
    return 0.05 * sstep(min(1.0, t / 0.05))


def centre_sigma(t):
    r = radius(t)
    return (1 - sstep(t)) * (-(WALL - r)) + sstep(t) * (math.pi * r / 2 + WALL - r)


def half_width(t):
    """11.8 at both ends; 22% wider at the middle in this upright section, where the road crosses it on the slant (so about 10.7 square to the road there)."""
    return HALF * (1 + 0.22 * math.sin(math.pi * t) ** 2)


def on_profile(sig, r, e):
    """(y, z) and the (y, z) normal at arc length sig along floor (sig < 0), fillet, wall."""
    arc = math.pi * r / 2
    y0 = -WALL + r
    if sig < 0:
        return (y0 - sig, e), (0.0, 1.0)
    if sig < arc:
        a = sig / r
        return (y0 - r * math.sin(a), e + r - r * math.cos(a)), (math.sin(a), math.cos(a))
    return (-WALL, e + r + sig - arc), (1.0, 0.0)


def vert(p, g=(1, 1, 1)):
    gain.append(g)
    return bm.verts.new(p)


def quad(a, b, c, d, mat, out):
    if (b.co - a.co).cross(c.co - a.co).dot(Vector(out)) < 0:
        a, b, c, d = d, c, b, a
    f = bm.faces.new((a, b, c, d))
    f.material_index = mat
    return f


def road_gain(t, u):
    """Dark and wet down the middle where it runs off; a touch of patchiness, by position."""
    w = 0.74 + 0.2 * abs(u)
    w *= 0.86 + 0.14 * math.sin(t * 19.0 + u * 3.0) * math.cos(t * 7.0 - u * 2.0)
    return (w, w, w)


# The road, smooth, one grid.
grid = []
rows_t = [i / ROWS for i in range(ROWS + 1)]
for t in rows_t:
    x = LEN * t
    r, e, sc, h = radius(t), lift(t), centre_sigma(t), half_width(t)
    row = []
    for u in US:
        (y, z), _n = on_profile(sc + u * h, r, e)
        row.append(vert((x, y, z), road_gain(t, u)))
    grid.append(row)
for i in range(ROWS):
    t = rows_t[i]
    tm = (rows_t[i] + rows_t[i + 1]) / 2
    r, e, sc, h = radius(tm), lift(tm), centre_sigma(tm), half_width(tm)
    for j in range(len(US) - 1):
        um = (US[j] + US[j + 1]) / 2
        _p, n = on_profile(sc + um * h, r, e)
        edge = j == 0 or j == len(US) - 2
        mat = HAZ if edge and i % 4 < 2 else WET
        quad(grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1], mat, (0, n[0], n[1]))


# The kerbs, at half the rows: over the road's edge, its top, and the outer side down to the shell behind.
KROWS = rows_t[::2]
for u, s in ((-1.0, -1.0), (1.0, 1.0)):
    rings = []
    for t in KROWS:
        x = LEN * t
        r, e, sc, h = radius(t), lift(t), centre_sigma(t), half_width(t)
        sig = sc + u * h
        ring = []
        for ds, dn, g in ((-s * 0.03, -0.05, 0.6), (0.0, KERB_H, 0.9), (s * KERB_W, KERB_H, 0.95), (s * KERB_W, -SHELL, 0.5)):
            (y, z), n = on_profile(sig + ds, r, e)
            ring.append(vert((x, y + n[0] * dn, z + n[1] * dn), (g, g, g)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        tm = (KROWS[k] + KROWS[k + 1]) / 2
        r, e, sc, h = radius(tm), lift(tm), centre_sigma(tm), half_width(tm)
        (_y, _z), n = on_profile(sc + u * h, r, e)
        d = 1e-3
        (y2, z2), _n = on_profile(sc + u * h + s * d, r, e)
        (y1, z1), _n = on_profile(sc + u * h - s * d, r, e)
        tan_out = Vector((0, y2 - y1, z2 - z1)).normalized()
        norm = Vector((0, n[0], n[1]))
        quad(rings[k][0], rings[k][1], rings[k + 1][1], rings[k + 1][0], STAINED, -tan_out)
        quad(rings[k][1], rings[k][2], rings[k + 1][2], rings[k + 1][1], STAINED, norm)
        quad(rings[k][2], rings[k][3], rings[k + 1][3], rings[k + 1][2], STAINED, tan_out)

# The two ends' faces, thickness of the shell.
END_U = [-1.0, -0.5, 0.0, 0.5, 1.0]
for t, o, ri in ((0.0, -1, 0), (1.0, 1, -1)):
    x = LEN * t
    r, e, sc, h = radius(t), lift(t), centre_sigma(t), half_width(t)
    for a, b in zip(END_U, END_U[1:]):
        pts = []
        for u, dn in ((a, 0.0), (b, 0.0), (b, -SHELL), (a, -SHELL)):
            (y, z), n = on_profile(sc + u * h, r, e)
            pts.append(vert((x, y + n[0] * dn, z + n[1] * dn), (0.55, 0.55, 0.55)))
        quad(*pts, STAINED, (o, 0, 0))

me = kit.mesh_from(NAME, bm, mats, smooth=True, recalc=False)
kit.box_uvs(me, 0.25)
RED = (1.0, 0.07, 0.04)
GREEN = (0.3, 1.0, 0.42)
lights = [
    # Red strips: on the rails at the floor end, then along the wall the road climbs.
    ((3.0, 6.4, 1.1), RED, 2.2, 3.4),
    ((3.0, -6.4, 1.1), RED, 2.2, 3.4),
    ((10.5, -2.0, 7.5), RED, 2.4, 1.8),
    ((16.0, 1.5, 1.2), RED, 2.2, 2.4),
    ((21.5, -6.2, 1.2), RED, 2.2, 3.4),
    ((21.5, -6.2, 14.2), RED, 2.2, 3.4),
    # The wash over the bend, the shaft's green on the wall end.
    ((12.0, 4.0, 11.0), (0.6, 0.74, 0.66), 10.0, 0.95),
    ((28.0, 6.0, 4.0), GREEN, 11.0, 1.1),
]
kit.bake_light(me, lights, ambient=(0.12, 0.16, 0.145))
ca = me.color_attributes['AO']
vi = np.zeros(len(me.loops), np.int64)
me.loops.foreach_get('vertex_index', vi)
cols = np.zeros(len(me.loops) * 4, np.float32)
ca.data.foreach_get('color', cols)
rgb = np.zeros((len(me.vertices), 3), np.float32)
rgb[vi] = cols.reshape(-1, 4)[:, :3]
kit.set_vcol_rgb(me, rgb * np.asarray(gain, np.float32))
for p in me.polygons:
    p.use_smooth = True
A.obj(me)
_ = np
A.finish(kit, NAME, budget=800, eye=(-7.5, 0.0, 1.45), look_at=(20.0, -5.0, 5.0))
