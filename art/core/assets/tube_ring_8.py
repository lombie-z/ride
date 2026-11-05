"""tube_ring_8: 8 m of the flooded tunnel's tube (art/core/ASSETS.md). Radius 9, centre 5.5 above the deck.

Origin: on the deck's centre at the ring's back end; the ring runs x 0..8 along +X, so its axis is (x, 0, 5.5), crown z 14.5,
floor z -3.5. Place the next at +8 (or rotated a few degrees about the join for a bend). The steel rib straddles the ring's
back (x -0.44..0.44), so each ring's rib covers its join with the ring before.

The ends overlap to hide a bend's wedge: the wall's front lip runs on to x 8.5 flaring out behind the next ring's wall, the
rib's back flank buries itself behind the last ring's wall to x -0.44. On a straight run neither shows or z-fights; on a bend
they hold the wall shut up to about 5 degrees a ring.

tube_ring_riveted.py builds from this file: build(kit, m, riveted=True). The lamps the bake assumes: LAMPS below, at the
ring's middle, on the wall.
"""
import math
import os
import sys

import bmesh
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402

NAME = 'tube_ring_8'
R = 9.0
CZ = 5.5
LEN = 8.0
# Vertex angles (degrees, 0 = +Y, 90 = crown, 270 = floor): coarse where the water and deck hide the floor, seam at the floor.
ANGLES = list(np.linspace(-90, -41.8, 3)) + list(np.linspace(-41.8, 221.8, 29))[1:] + [245.9, 270.0]
# The texture's streaks run down its rows, so v runs round the ring: 9 tiles round, one tile per ring along, so it tiles.
V_TILES = 9.0
# The lamps the bake assumes (the layout agent's lights go here, mid ring): green low on the wall, slanted white work light higher.
LAMPS = [
    ((4.0, 7.9, 3.0), (0.2, 1.0, 0.24), 2.8, 1.5),
    ((4.0, -7.9, 3.0), (0.2, 1.0, 0.24), 2.8, 1.5),
    ((4.0, 6.2, 10.9), (1.0, 0.95, 0.78), 5.0, 2.2),
    ((4.0, -6.2, 10.9), (1.0, 0.95, 0.78), 5.0, 2.2),
]


class Parts:
    """A bmesh and, per vertex, a colour the baked light gets multiplied by (stains, moss, grime, contact shadow)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new('UVMap')
        self.tint = []

    def vert(self, co, tint=(1.0, 1.0, 1.0)):
        v = self.bm.verts.new(co)
        self.tint.append(tint)
        return v

    def face(self, vs, uvs, mat):
        f = self.bm.faces.new(vs)
        f.material_index = mat
        for lo, uv in zip(f.loops, uvs):
            lo[self.uv].uv = uv
        return f


def at(deg, r, x):
    a = math.radians(deg)
    return (x, r * math.cos(a), CZ + r * math.sin(a))


def uv_at(deg, x):
    return (x / LEN, (deg + 90.0) / 360.0 * V_TILES)


def surface(p, profile, mat, tint=None):
    """A strip all the way round: profile is (x, r) walked with the solid on its outer side, so its normals face the axis."""
    n = len(ANGLES) - 1
    rows = [[p.vert(at(ANGLES[i], r, x), tint(ANGLES[i], r, x) if tint else (1, 1, 1)) for i in range(n)] for x, r in profile]
    for j in range(len(profile) - 1):
        x0, x1 = profile[j][0], profile[j + 1][0]
        for i in range(n):
            k = (i + 1) % n
            p.face((rows[j][i], rows[j + 1][i], rows[j + 1][k], rows[j][k]),
                   (uv_at(ANGLES[i], x0), uv_at(ANGLES[i], x1), uv_at(ANGLES[i + 1], x1), uv_at(ANGLES[i + 1], x0)), mat)


def rod(p, x0, x1, deg, r, half, mat, tint=(1, 1, 1)):
    """A square bar along the tube, flat to the wall."""
    a = math.radians(deg)
    ry, rz = math.cos(a), math.sin(a)
    ty, tz = -rz, ry
    cs = [(-half, half), (half, half), (half, -half), (-half, -half)]
    def ring(x):
        return [p.vert((x, (r - ro) * ry + t * ty, CZ + (r - ro) * rz + t * tz), tint) for t, ro in cs]
    a0, a1 = ring(x0), ring(x1)
    for i in range(4):
        j = (i + 1) % 4
        p.face((a0[i], a1[i], a1[j], a0[j]), ((x0 * 0.25, i * 0.25), (x1 * 0.25, i * 0.25), (x1 * 0.25, (i + 1) * 0.25), (x0 * 0.25, (i + 1) * 0.25)), mat)


def stain(p, rng, x, deg, length, width, colour, base, mat, r=8.93, rows=3, edge=(1.0, 1.0, 1.0)):
    """A soft run down the wall, in a material with the wall's texture: a strip that follows the curve from deg down by `length`
    metres, narrowing, a little off the wall. Its edge vertices carry the wall's own colour and share its UVs, so only its middle
    shows, lifted or darkened by `colour` (over 1 lifts it above the wall): it fades out into the wall. For a material of another
    base, `edge` is the wall's base over its, so its edges still match the wall."""
    down = 1 if deg < 90 else -1  # toward the water on either side
    arc = math.degrees(length / r)
    ls, cs, rs, spec = [], [], [], []
    for k in range(rows + 1):
        t = k / rows
        d = deg - down * arc * t
        w = width * (1 - 0.6 * t) * (0.75 + 0.5 * rng.random())
        xc = x + rng.normal(0, width * 0.16)
        strength = math.sin(t * math.pi) ** 0.6 if 0 < k < rows else 0.0
        wc = base(d, r, xc)
        tint = tuple(wc[i] * (edge[i] * (1 - strength) + strength * colour[i]) for i in range(3))
        w0, w1 = base(d, r, xc - w / 2), base(d, r, xc + w / 2)
        ls.append(p.vert(at(d, r, xc - w / 2), tuple(w0[i] * edge[i] for i in range(3))))
        cs.append(p.vert(at(d, r, xc), tint))
        rs.append(p.vert(at(d, r, xc + w / 2), tuple(w1[i] * edge[i] for i in range(3))))
        spec.append((d, xc - w / 2, xc, xc + w / 2))
    for k in range(rows):
        d0, a0, c0, b0 = spec[k]
        d1, a1, c1, b1 = spec[k + 1]
        # Lower angle first along x, so the normal faces the axis.
        for (e0, f0, x00, x01), (e1, f1, x10, x11) in (((ls, cs, a0, c0), (ls, cs, a1, c1)), ((cs, rs, c0, b0), (cs, rs, c1, b1))):
            if d0 < d1:
                quad = (e0[k], f0[k], f0[k + 1], e0[k + 1])
                uvs = (uv_at(d0, x00), uv_at(d0, x01), uv_at(d1, x11), uv_at(d1, x10))
            else:
                quad = (e0[k + 1], f0[k + 1], f0[k], e0[k])
                uvs = (uv_at(d1, x10), uv_at(d1, x11), uv_at(d0, x01), uv_at(d0, x00))
            p.face(quad, uvs, mat)


def rib_glint(p, deg0, deg1, strength, mat):
    """A wet glint along the rib's rider-facing edge, fading out at both ends: the bright arcs on the image's ribs."""
    ds = [d for d in ANGLES if deg0 <= d <= deg1]
    if len(ds) < 2:
        return
    a = (-0.37, 8.72)
    b = (-0.14, 8.53)
    n = len(ds) - 1
    ra, rb = [], []
    for i, d in enumerate(ds):
        v = strength * math.sin(i / n * math.pi) ** 0.8
        ra.append(p.vert(at(d, a[1], a[0]), (v, v, v)))
        rb.append(p.vert(at(d, b[1], b[0]), (v, v, v)))
    for i in range(n):
        p.face((ra[i], rb[i], rb[i + 1], ra[i + 1]), (uv_at(ds[i], a[0]), uv_at(ds[i], b[0]), uv_at(ds[i + 1], b[0]), uv_at(ds[i + 1], a[0])), mat)


def wall_tint(seed):
    """Light's multiplier on the wall anywhere: dark at the crown and the waterline, in the ribs' shadow, broad damp; tiles along x."""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * math.pi, 4)

    def f(deg, r, x):
        z = CZ + 9.0 * math.sin(math.radians(deg))
        v = 1.0
        v *= 0.62 + 0.38 * float(np.clip((14.4 - z) / 4.5, 0, 1))        # the crown's dark
        v *= 0.42 + 0.58 * float(np.clip((z - 0.1) / 2.6, 0, 1))         # the tide's dark
        d = min(abs(x - 0.44), abs(x - 8.0))
        v *= 0.42 + 0.58 * float(np.clip(d / 1.5, 0, 1))                 # the ribs' shadow
        a = math.radians(deg)
        damp = math.sin(2 * math.pi * x / LEN + ph[0] + 3 * a) * math.sin(5 * a + ph[1]) + 0.6 * math.sin(4 * math.pi * x / LEN + ph[2] - 7 * a + ph[3])
        v *= float(np.clip(0.86 + 0.26 * damp, 0.45, 1.1))
        low = 1 - float(np.clip((z - 0.2) / 3.2, 0, 1))
        return (v * (1 - 0.3 * low), v, v * (1 - 0.55 * low))             # slime toward the water

    return f


# Stain colours, multiplying the wall's light at their middle: over 1 lifts the wall's texture toward its full brightness.
# Moss: on the flat yellow 'hazard' base, the one bright untextured material, which lifts it above what the concrete can reach.
MOSS = (0.52, 0.72, 0.7)
MOSS_EDGE = (0.36, 0.42, 1.0)
WET = (6.5, 6.5, 6.2)
MARK = (0.16, 0.15, 0.13)


def stains(p, rng, mat, gleam, moss_mat, base, moss=8, wet=6, dark=6):
    """On the walls, as in the image: dark water marks, moss runs, yellow-green, long and narrowing, and wet gleams."""
    for side in (0, 1):
        for _ in range(dark // 2):
            d = rng.uniform(-12, 78)
            stain(p, rng, rng.uniform(1.2, 7.4), d if side == 0 else 180 - d, rng.uniform(2.6, 5.5), rng.uniform(0.9, 1.9), MARK, base, mat, rows=2)
        for _ in range(moss // 2):
            d = rng.uniform(24, 66)
            stain(p, rng, rng.uniform(1.6, 6.8), d if side == 0 else 180 - d, rng.uniform(2.0, 4.2), rng.uniform(0.9, 1.7), MOSS, base, moss_mat, r=8.92, edge=MOSS_EDGE)
        for _ in range(wet // 2):
            d = rng.uniform(4, 60)
            stain(p, rng, rng.uniform(1.0, 7.4), d if side == 0 else 180 - d, rng.uniform(2.4, 5.0), rng.uniform(0.9, 1.6), WET, base, gleam, r=8.91)


def tint_light(me, tints):
    """Multiplies each vertex's baked light by its tint."""
    n = len(me.vertices)
    ca = me.color_attributes['AO']
    vi = np.zeros(len(me.loops), np.int64)
    me.loops.foreach_get('vertex_index', vi)
    cols = np.zeros(len(me.loops) * 4, np.float32)
    ca.data.foreach_get('color', cols)
    cols = cols.reshape(-1, 4)
    per = np.zeros((n, 3), np.float32)
    per[vi] = cols[:, :3]
    per *= np.asarray(tints, np.float32)
    A._kit.set_vcol_rgb(me, per)


# The rib, walked from behind the last ring's wall: its back flank and edge face the rider, its face looks at the axis.
RIB_BACK = [(-0.44, 9.18), (-0.36, 8.74)]
RIB_FACE = [(-0.36, 8.74), (-0.22, 8.55), (0.22, 8.55), (0.44, 9.0)]
TIES = [8, 37, 66, 114, 143, 172]  # cross-tie rods, tying rib to rib along the wall (degrees)


def build(kit, m, riveted=False, name=NAME):
    p = Parts()
    rng = np.random.default_rng(11 if not riveted else 12)
    slots = [m['riveted_steel'] if riveted else m['stained_concrete'], m['rust'], m['pipe_metal'], m['wet_concrete'], m['hazard']]
    wall, rib_mat, tie, wet, moss = 0, 1, 2, 3, 4

    # The rib: its back flank takes the lamps behind it, its edge a wet glint; it straddles the join.
    surface(p, RIB_BACK, rib_mat)
    surface(p, RIB_FACE, rib_mat)
    for d0, d1, v in ((-16, 22, 3.6), (28, 70, 4.6), (110, 152, 4.6), (158, 196, 3.6)):
        rib_glint(p, d0, d1, v, wet)

    tint = wall_tint(21 if not riveted else 22)
    if riveted:
        # Two plates a ring, the forward one standing proud of the back one at their lap, so the lap's edge faces the rider.
        surface(p, [(0.44, 9.0), (2.2, 9.0), (4.0, 9.0)], wall, tint)
        surface(p, [(4.0, 9.0), (4.0, 8.92)], tie, lambda d, r, x: (0.8, 0.8, 0.8))
        surface(p, [(4.0, 8.92), (6.0, 8.92), (8.0, 8.92), (8.5, 9.06)], wall, tint)
        straps(p, rng, wall)
        rivets(p, rib_mat, wall)
        stains(p, rng, wall, wall, moss, tint, moss=2, wet=4, dark=2)
    else:
        surface(p, [(0.44, 9.0), (2.2, 9.0), (4.0, 9.0), (5.8, 9.0), (8.0, 9.0), (8.5, 9.06)], wall, tint)
        stains(p, rng, wall, wet, moss, tint)

    for d in TIES:
        rod(p, 0.2, 7.8, d, 8.74, 0.09, tie, (0.6, 0.6, 0.6))

    me = kit.mesh_from(name, p.bm, slots, smooth=True, recalc=False)
    # This ring's lamps and its neighbours', so the light runs on across the joins.
    lights = [((l[0][0] + dx, *l[0][1:]), *l[1:]) for l in LAMPS for dx in (-LEN, 0.0, LEN)]
    if riveted:
        # This is the ring nearest the bulkhead: its red light reaches back along the low walls.
        lights += [((9.0, 3.0, 1.2), (1.0, 0.08, 0.05), 5.0, 0.32), ((9.0, -3.0, 1.2), (1.0, 0.08, 0.05), 5.0, 0.32)]
    kit.bake_light(me, lights, ambient=(0.15, 0.165, 0.15))
    tint_light(me, p.tint)
    return me


def straps(p, rng, mat):
    """The plates' long seams: butt straps along the tube, every 30 degrees or so above the water."""
    for d in (-16, 22, 60, 120, 158, 196):
        rod(p, 0.3, 3.95, d, 9.02, 0.09, mat, (0.75, 0.75, 0.7))
        rod(p, 4.05, 7.8, d + 15, 8.94, 0.09, mat, (0.75, 0.75, 0.7))


def rivet(p, x, deg, r, size, mat):
    """A four-sided boss, standing in from radius r."""
    a = math.radians(deg)
    ry, rz = math.cos(a), math.sin(a)
    ty, tz = -rz, ry
    def pt(dx, dt, ro):
        return (x + dx, (r - ro) * ry + dt * ty, CZ + (r - ro) * rz + dt * tz)
    tip = p.vert(pt(0, 0, size * 0.8), (1.0, 1.0, 1.0))
    base = [p.vert(pt(dx * size, dt * size, 0), (0.6, 0.6, 0.6)) for dx, dt in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for i in range(4):
        j = (i + 1) % 4
        p.face((base[i], base[j], tip), ((0, 0), (0.05, 0), (0.025, 0.05)), mat)


def rivets(p, rib_mat, wall):
    """Rows of big rivets on the rib's face and along the plates' lap, above the water only."""
    for d in np.arange(-24, 205, 19.0):
        rivet(p, 0.0, d, 8.55, 0.1, rib_mat)
    for d in np.arange(-30, 215, 14.0):
        rivet(p, 4.22, d, 8.92, 0.08, wall)


if __name__ == '__main__':
    kit = A.begin()
    m = _mats.mats(kit)
    A.obj(build(kit, m))
    A.finish(kit, NAME, budget=900, eye=(-0.5, -4.5, 1.45), look_at=(5.0, 8.5, 6.0), fov=70.0)
